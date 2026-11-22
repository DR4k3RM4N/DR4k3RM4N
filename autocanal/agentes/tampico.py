"""🌮 Tampiqueando: la oficina foodie de Miguel en Tampico, Madero y Altamira.

El equipo:
- 🔎 Lupita (negocios): busca restaurantes, taquerías, cafés… en Google Maps (Serper), sin repetir, y lleva el
  seguimiento de cada uno (nuevo → contactado → respondió → interesado → plan → grabado → publicado).
- 💬 Chuy (relaciones): manda el primer WhatsApp con la plantilla aprobada por Meta (regla de WhatsApp: a quien no te
  ha escrito solo se le puede mandar una plantilla), y cuando el negocio contesta le responde con Claude dentro de la
  ventana de 24 h, sin prometer nada que no esté en tu propuesta; te avisa de cada respuesta. Tope diario y horario.
- 🎬 Fer (producción): plan de visita por negocio: formato, gancho, guion, lista de tomas (cel, cámara, gimbal, dron),
  preguntas al dueño, textos para Facebook/Instagram/TikTok; y crea el proyecto en la sala de edición.
- 🚁 Dron: lugares para tomas aéreas en la zona conurbada, sin repetir, con mejor hora y precauciones.
- 🧪 Formatos: busca qué hacen ya los foodies de Tampico y propone formatos que nadie hace (para experimentar).
- 📣 Publicación: Facebook (página) e Instagram (Reels) solos con la API de Meta; TikTok queda listo para subir
  (TikTok no deja publicar automático sin auditar la app).
- ♻️ Remarketing: reusar lo ya publicado (recopilatorios, «regresamos», colaboraciones) sin repetir lugares.

Claves en .env (nunca en el chat): TAMPICO_WA_PLANTILLA (nombre de la plantilla aprobada, con {{1}} = nombre del
negocio), TAMPICO_FB_PAGINA, TAMPICO_FB_TOKEN (token de página), TAMPICO_IG_ID (cuenta de Instagram de empresa).
El WhatsApp es el mismo número de la oficina (WHATSAPP_*).
"""
from __future__ import annotations

import datetime as dt
import json
import re
import secrets
import threading
import time
import unicodedata
from pathlib import Path
from zoneinfo import ZoneInfo

from . import buscar_web, claude, config

ARCHIVO = config.ESTILO_DIR / "tampico.json"
MEDIOS = config.ESTILO_DIR / "tampico_medios"
ZONA_HORARIA = ZoneInfo("America/Monterrey")
ZONAS = ["Tampico", "Ciudad Madero", "Altamira"]
ESTADOS = ["nuevo", "contactado", "respondio", "interesado", "plan", "grabado", "publicado", "no_interesado", "sin_numero"]
_candado = threading.RLock()
AJUSTES = {
    "propuesta": "",           # lo que ofreces a los negocios (colaboración, costo, qué incluye): Chuy solo dice esto
    "envio_auto": False,       # mandar WhatsApp solos a los negocios nuevos
    "responder_auto": True,    # contestar solos cuando un negocio responde (siempre te avisa)
    "mensajes_dia": 8,         # tope de primeros mensajes al día (que no se vea como spam)
    "hora_inicio": 10, "hora_fin": 19,
}
DRON_PRECAUCIONES = ("Antes de volar: dron registrado ante la AFAC si lo pide su peso, máx. 120 m de altura, siempre a "
                     "la vista, nunca sobre gente ni cerca del aeropuerto de Tampico ni de instalaciones como la "
                     "refinería o el puerto; revisa en el mapa de zonas de la AFAC y pide permiso si es propiedad privada.")


# ---------- guardar / leer ----------
def cargar() -> dict:
    try:
        d = json.loads(ARCHIVO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    for k in ("negocios", "planes", "dron", "formatos", "publicaciones", "remarketing"):
        d.setdefault(k, [])
    d.setdefault("chats", {})
    d["ajustes"] = {**AJUSTES, **(d.get("ajustes") or {})}
    return d


def guardar(d: dict) -> None:
    ARCHIVO.parent.mkdir(parents=True, exist_ok=True)
    tmp = ARCHIVO.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(ARCHIVO)


def _clave(t: str) -> str:
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", t)


def _id() -> str:
    return secrets.token_hex(4)


def _ahora() -> dt.datetime:
    return dt.datetime.now(ZONA_HORARIA)


def numero_whatsapp(tel: str) -> str:
    """'833 123 4567' → '528331234567' (México). Vacío si no parece celular/fijo mexicano."""
    d = re.sub(r"\D", "", tel or "")
    if d.startswith("521") and len(d) == 13:
        d = "52" + d[3:]
    if len(d) == 10:
        return "52" + d
    return d if d.startswith("52") and len(d) == 12 else ""


def _gastar(conteo: dict, que: str) -> None:
    gasto = buscar_web.costo(conteo)
    if claude.al_gastar and gasto:
        claude.al_gastar(None, "tampico", "búsqueda", gasto, 0, 0, que)


# ---------- 🔎 Lupita: buscar negocios ----------
def buscar_negocios(tipo: str = "restaurantes", zona: str = "Tampico", cuantos: int = 20) -> dict:
    import os

    import requests
    zona = zona if zona in ZONAS else "Tampico"
    consulta = f"{tipo.strip() or 'restaurantes'} en {zona}, Tamaulipas"
    if os.environ.get("AUTOCANAL_DEMO"):  # demo: negocios de ejemplo (inventados, solo para ver la pantalla)
        lugares = [{"title": f"(Demo) {n}", "address": f"Calle {i}, {zona}", "category": tipo, "rating": 4.5,
                    "ratingCount": 100 + i * 37, "phoneNumber": f"833 100 00{i:02d}", "cid": f"demo{_clave(n)}"}
                   for i, n in enumerate(["Mariscos La Ola", "Tacos El Güero", "Café Puerto", "Jaibas Doña Mary",
                                          "Gorditas La Esquina"], 1)]
    else:
        if not buscar_web.SERPER:
            raise ValueError("Falta SERPER_API_KEY en el .env del servidor (la búsqueda de Google Maps).")
        r = requests.post("https://google.serper.dev/places", timeout=30,
                          headers={"X-API-KEY": buscar_web.SERPER, "Content-Type": "application/json"},
                          json={"q": consulta, "gl": "mx", "hl": "es", "num": min(40, max(10, cuantos))})
        r.raise_for_status()
        _gastar({"serper": 1}, f"Google Maps: {consulta}")
        lugares = r.json().get("places") or []
    nuevos = 0
    with _candado:
        d = cargar()
        vistos = {(x.get("cid") or "") for x in d["negocios"]} | {_clave(x["nombre"] + x.get("direccion", "")[:20])
                                                                  for x in d["negocios"]}
        for p in lugares[:cuantos]:
            nombre = (p.get("title") or "").strip()
            if not nombre:
                continue
            clave = _clave(nombre + (p.get("address") or "")[:20])
            if (p.get("cid") and str(p["cid"]) in vistos) or clave in vistos:
                continue
            numero = numero_whatsapp(p.get("phoneNumber") or "")
            d["negocios"].append({
                "id": _id(), "nombre": nombre[:80], "categoria": (p.get("category") or tipo)[:60],
                "direccion": (p.get("address") or "")[:160], "zona": zona, "telefono": p.get("phoneNumber") or "",
                "whatsapp": numero, "web": p.get("website") or "", "estrellas": p.get("rating"),
                "resenas": p.get("ratingCount"), "cid": str(p.get("cid") or ""),
                "lat": p.get("latitude"), "lng": p.get("longitude"),
                "estado": "nuevo" if numero else "sin_numero", "creado": time.time(), "historial": []})
            vistos |= {str(p.get("cid") or ""), clave}
            nuevos += 1
        guardar(d)
    return {"ok": True, "nuevos": nuevos, "encontrados": len(lugares)}


def mover(nid: str, estado: str, nota: str = "") -> dict:
    if estado not in ESTADOS:
        return {"error": "Estado no válido."}
    with _candado:
        d = cargar()
        n = next((x for x in d["negocios"] if x["id"] == nid), None)
        if not n:
            return {"error": "No encontré ese negocio."}
        n["estado"] = estado
        n["historial"].append({"t": time.time(), "que": f"→ {estado}" + (f": {nota}" if nota else "")})
        guardar(d)
    return {"ok": True}


# ---------- 💬 Chuy: WhatsApp ----------
def _plantilla() -> str:
    return config.env("TAMPICO_WA_PLANTILLA", "")


def enviar_pendientes(avisar=None) -> int:
    """Manda el primer mensaje (plantilla) a los negocios nuevos, con tope diario y en horario. Regresa cuántos."""
    from . import whatsapp as wa
    with _candado:
        d = cargar()
        aj = d["ajustes"]
        ahora = _ahora()
        if not (aj["envio_auto"] and wa.activo() and _plantilla()):
            return 0
        if not (aj["hora_inicio"] <= ahora.hour < aj["hora_fin"]) or ahora.weekday() == 6:  # domingo no
            return 0
        hoy = ahora.date().isoformat()
        enviados_hoy = sum(1 for n in d["negocios"] if n.get("contactado_dia") == hoy)
        cupo = max(0, int(aj["mensajes_dia"]) - enviados_hoy)
        cola = [n for n in d["negocios"] if n["estado"] == "nuevo" and n.get("whatsapp")][:cupo]
    hechos = 0
    for n in cola:
        try:
            wa._post({"messaging_product": "whatsapp", "to": n["whatsapp"], "type": "template",
                      "template": {"name": _plantilla(), "language": {"code": config.env("TAMPICO_WA_IDIOMA", "es_MX")},
                                   "components": [{"type": "body", "parameters": [{"type": "text", "text": n["nombre"][:60]}]}]}})
            estado, que = "contactado", "WhatsApp: primer mensaje (plantilla)"
            hechos += 1
        except Exception as exc:  # noqa: BLE001
            estado, que = "nuevo", f"No se pudo mandar el WhatsApp: {str(exc)[:120]}"
            if "131026" in str(exc) or "not a WhatsApp" in str(exc) or "invalid" in str(exc).lower():
                estado = "sin_numero"
        with _candado:
            d = cargar()
            x = next((y for y in d["negocios"] if y["id"] == n["id"]), None)
            if x:
                x["estado"] = estado
                if estado == "contactado":
                    x["contactado_dia"], x["contactado_t"] = hoy, time.time()
                x["historial"].append({"t": time.time(), "que": que})
                guardar(d)
        time.sleep(4)
    if hechos and avisar:
        avisar(f"🌮 Chuy le escribió a {hechos} negocio(s) nuevo(s) por WhatsApp. Te aviso cuando contesten.")
    return hechos


SCHEMA_RESPUESTA = {
    "type": "object",
    "properties": {
        "respuesta": {"type": "string", "description": "Lo que se le contesta al negocio por WhatsApp (corto, cálido)"},
        "estado": {"type": "string", "enum": ["respondio", "interesado", "no_interesado"]},
        "para_el_jefe": {"type": "string", "description": "Resumen de 1-2 frases para Miguel"},
        "fecha_propuesta": {"type": "string", "description": "Si propusieron día/hora para grabar, tal cual; si no, vacío"},
    },
    "required": ["respuesta", "estado", "para_el_jefe", "fecha_propuesta"],
    "additionalProperties": False,
}
BAJA = re.compile(r"\b(no gracias|no me interesa|no estamos interesad|baja|stop|no molest|ya no (me )?escrib)", re.I)


def respuesta_negocio(mensaje: dict, avisar=None) -> bool:
    """Un negocio contestó por WhatsApp. True si era de Tampiqueando (si no, no es nuestro)."""
    from . import whatsapp as wa
    numero = re.sub(r"\D", "", mensaje.get("de") or "")
    with _candado:
        d = cargar()
        n = next((x for x in d["negocios"] if x.get("whatsapp") and x["whatsapp"][-10:] == numero[-10:]), None)
        if not n:
            return False
        chat = d["chats"].setdefault(n["id"], [])
        chat.append({"t": time.time(), "de": "negocio", "texto": (mensaje.get("texto") or "")[:1000]})
        aj = d["ajustes"]
        guardar(d)
    texto = mensaje.get("texto") or ""
    if BAJA.search(texto):
        respuesta, estado, resumen, fecha = ("¡Entendido, gracias por contestar! No le volvemos a escribir. "
                                             "¡Que le vaya muy bien! 🌮"), "no_interesado", "No le interesa; ya no se le escribe.", ""
    elif aj["responder_auto"]:
        r = claude.json_estructurado(
            "Eres Chuy, de Tampiqueando (cuenta foodie de Tampico, Madero y Altamira en Facebook, Instagram y TikTok; "
            "la lleva Miguel). Platicas por WhatsApp con un negocio de comida que contestó a nuestra invitación para "
            "hacerle contenido. Español de México, amable, breve (máx. 3 frases), sin presionar. REGLAS: solo ofreces "
            "lo que dice LA PROPUESTA (si no dice algo, como precios o fechas, di que Miguel se los confirma); nunca "
            "inventes números de seguidores ni resultados; si quieren agendar, pide día y hora que les acomode y di que "
            "Miguel lo confirma; si piden hablar con alguien, di que Miguel les escribe.",
            f"NEGOCIO: {n['nombre']} ({n.get('categoria')}, {n.get('zona')})\nLA PROPUESTA: {aj['propuesta'] or '(Miguel no la ha escrito: no ofrezcas nada concreto, pregunta si les gustaría que Miguel les platique la idea)'}\n"
            "PLÁTICA:\n" + "\n".join(f"{'Negocio' if m['de'] == 'negocio' else 'Nosotros'}: {m['texto']}" for m in chat[-12:]),
            SCHEMA_RESPUESTA, tarea="whatsapp", que="Tampiqueando: responder a un negocio")
        respuesta, estado, resumen, fecha = r["respuesta"], r["estado"], r["para_el_jefe"], r["fecha_propuesta"]
    else:
        respuesta, estado, resumen, fecha = "", "respondio", f"Contestó: «{texto[:120]}»", ""
    if respuesta:
        try:
            wa.enviar_texto(numero, respuesta)
        except Exception as exc:  # noqa: BLE001
            resumen += f" (No pude contestarle: {str(exc)[:80]})"
    with _candado:
        d = cargar()
        x = next((y for y in d["negocios"] if y["id"] == n["id"]), None)
        if x:
            x["estado"] = estado if x["estado"] in ("nuevo", "contactado", "respondio", "interesado") else x["estado"]
            if fecha:
                x["fecha_propuesta"] = fecha
            x["historial"].append({"t": time.time(), "que": f"Contestó: {texto[:100]}"})
        if respuesta:
            d["chats"].setdefault(n["id"], []).append({"t": time.time(), "de": "nosotros", "texto": respuesta})
        guardar(d)
    if avisar:
        avisar(f"🌮 {n['nombre']} contestó por WhatsApp: «{texto[:140]}»\n{resumen}"
               + (f"\n📅 Propone: {fecha}" if fecha else "") + ("\n(Ya le contesté.)" if respuesta else ""))
    return True


# ---------- 🎬 Fer: plan de visita ----------
SCHEMA_PLAN = {
    "type": "object",
    "properties": {
        "formato": {"type": "string"}, "gancho": {"type": "string", "description": "Primeros 2 segundos, palabra por palabra"},
        "guion": {"type": "array", "items": {"type": "object", "properties": {
            "momento": {"type": "string"}, "se_ve": {"type": "string"}, "se_dice": {"type": "string"},
            "texto_pantalla": {"type": "string"}}, "required": ["momento", "se_ve", "se_dice", "texto_pantalla"],
            "additionalProperties": False}},
        "tomas": {"type": "array", "items": {"type": "object", "properties": {
            "toma": {"type": "string"}, "equipo": {"type": "string", "enum": ["celular", "camara", "gimbal", "dron", "microfono"]},
            "como": {"type": "string"}, "segundos": {"type": "integer"}},
            "required": ["toma", "equipo", "como", "segundos"], "additionalProperties": False}},
        "preguntas_al_dueno": {"type": "array", "items": {"type": "string"}},
        "textos": {"type": "object", "properties": {"facebook": {"type": "string"}, "instagram": {"type": "string"},
                                                    "tiktok": {"type": "string"}},
                   "required": ["facebook", "instagram", "tiktok"], "additionalProperties": False},
        "llevar": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["formato", "gancho", "guion", "tomas", "preguntas_al_dueno", "textos", "llevar"],
    "additionalProperties": False,
}


def plan_visita(nid: str, notas: str = "") -> dict:
    with _candado:
        d = cargar()
        n = next((x for x in d["negocios"] if x["id"] == nid), None)
        if not n:
            return {"error": "No encontré ese negocio."}
        formato = next((f for f in d["formatos"] if f.get("elegido")), None)
        dron_libres = [x for x in d["dron"] if not x.get("usado")][:6]
        ya = [p.get("formato") for p in d["planes"][-6:]]
    r = claude.json_estructurado(
        "Eres Fer, productor de Tampiqueando (foodie de Tampico, Madero y Altamira) para Facebook, Instagram y TikTok "
        "(video vertical 9:16, 30-60 s). Planeas la visita a un negocio: que el video enganche en 2 s, muestre la comida "
        "como se antoja (vapor, queso, salsa, cortes, primeros bocados), tenga personalidad y cierre con dónde está. "
        "Nada inventado: precios, platillos e historia solo si vienen en los datos o en las notas; si no, ponlos como "
        "'pregúntale al dueño'. Hashtags locales (#Tampico #CiudadMadero #Tampiqueando).",
        f"NEGOCIO: {json.dumps({k: n.get(k) for k in ('nombre', 'categoria', 'direccion', 'zona', 'estrellas', 'resenas', 'web')}, ensure_ascii=False)}\n"
        f"NOTAS DE MIGUEL: {notas or '(ninguna)'}\nFORMATO DEL CANAL: {formato['nombre'] + ' — ' + formato['descripcion'] if formato else 'el que mejor le quede'}\n"
        f"FORMATOS DE LOS ÚLTIMOS VIDEOS (varía): {ya}\n"
        f"TOMAS DE DRON DISPONIBLES (si alguna queda cerca o sirve de apertura de zona, úsala): "
        f"{json.dumps([{k: x.get(k) for k in ('lugar', 'zona', 'toma')} for x in dron_libres], ensure_ascii=False)}\n"
        "Miguel tiene cámara, celular, gimbal, micrófono y dron.",
        SCHEMA_PLAN, tarea="guion", que=f"Tampiqueando: plan de visita a {n['nombre']}")
    plan = {"id": _id(), "negocio": nid, "nombre": n["nombre"], "creado": time.time(), **r}
    with _candado:
        d = cargar()
        d["planes"].append(plan)
        x = next((y for y in d["negocios"] if y["id"] == nid), None)
        if x and x["estado"] in ("nuevo", "contactado", "respondio", "interesado", "sin_numero"):
            x["estado"] = "plan"
            x["historial"].append({"t": time.time(), "que": "Plan de visita listo"})
        guardar(d)
    plan["sala"] = _proyecto_en_sala(plan)
    return plan


def _proyecto_en_sala(plan: dict) -> str:
    """Crea el proyecto de edición en la sala (en la compu prendida) con el guion como primer mensaje."""
    import requests
    from .edicion_remota import SALA_URL
    try:
        compus = requests.get(f"{SALA_URL}/api/estado", timeout=5).json().get("compus") or []
        donde = next((c["id"] for c in compus if c.get("viva")), "")
        r = requests.post(f"{SALA_URL}/api/proyecto", json={"nombre": f"Tampiqueando {plan['nombre']}"[:60],
                                                            "donde": donde}, timeout=10).json()
        pid = r.get("id")
        if not pid:
            return ""
        guion = "\n".join(f"- {g['momento']}: se ve {g['se_ve']} · se dice «{g['se_dice']}» · texto «{g['texto_pantalla']}»"
                          for g in plan["guion"])
        requests.post(f"{SALA_URL}/api/chat", timeout=10, json={"proyecto": pid, "texto": (
            f"Video vertical 9:16 para Tampiqueando (Facebook, Instagram y TikTok), 30-60 s. Formato: {plan['formato']}. "
            f"Gancho: «{plan['gancho']}». Guion:\n{guion}\nSubtítulos grandes, música con ritmo y la dirección al final.")})
        return pid
    except Exception:  # noqa: BLE001 — si la sala no está, el plan sirve igual
        return ""


# ---------- 🚁 dron ----------
SCHEMA_DRON = {
    "type": "object",
    "properties": {"lugares": {"type": "array", "items": {"type": "object", "properties": {
        "lugar": {"type": "string"}, "zona": {"type": "string", "enum": ZONAS},
        "por_que": {"type": "string"}, "toma": {"type": "string", "description": "Movimiento de dron sugerido"},
        "mejor_hora": {"type": "string"}, "precaucion": {"type": "string"}, "fuente": {"type": "string"}},
        "required": ["lugar", "zona", "por_que", "toma", "mejor_hora", "precaucion", "fuente"],
        "additionalProperties": False}}},
    "required": ["lugares"], "additionalProperties": False,
}


def planear_dron(cuantos: int = 8) -> dict:
    with _candado:
        ya = [x["lugar"] for x in cargar()["dron"]]
    resultados, conteo = buscar_web.buscar(["lugares emblemáticos de Tampico", "qué visitar en Ciudad Madero",
                                            "atractivos turísticos de Altamira Tamaulipas", "miradores y parques Tampico",
                                            "Laguna del Carpintero Tampico", "Playa Miramar Ciudad Madero"],
                                           por_consulta=5, max_texto=300) if buscar_web.disponible() else ([], {})
    _gastar(conteo, "Google: lugares para dron")
    r = claude.json_estructurado(
        "Planeas tomas de dron para una cuenta foodie de Tampico, Madero y Altamira. Solo lugares que aparecen en los "
        "resultados (con su URL en 'fuente'). Nunca repitas los que ya se usaron. En 'precaucion' pon lo específico del "
        "lugar (gente, cables, zona de aeropuerto o industrial cercana, viento del mar) sin inventar reglas.",
        f"YA USADOS O PLANEADOS (no repetir): {ya}\n\nRESULTADOS:\n"
        + "\n".join(f"- {x['titulo']} — {x['url']}: {x['texto']}" for x in resultados[:30])
        + f"\n\nPropón {cuantos} lugares distintos, variando zona y tipo (agua, ciudad, naturaleza, atardecer).",
        SCHEMA_DRON, tarea="ideas", que="Tampiqueando: lugares para dron")
    urls = {x["url"] for x in resultados}
    nuevos = 0
    with _candado:
        d = cargar()
        usados = {_clave(x["lugar"]) for x in d["dron"]}
        for x in r["lugares"]:
            if _clave(x["lugar"]) in usados:
                continue
            d["dron"].append({"id": _id(), **x, "fuente": x["fuente"] if x["fuente"] in urls else "", "usado": False,
                              "creado": time.time()})
            usados.add(_clave(x["lugar"]))
            nuevos += 1
        guardar(d)
    return {"ok": True, "nuevos": nuevos, "precauciones": DRON_PRECAUCIONES}


# ---------- 🧪 formatos ----------
SCHEMA_FORMATOS = {
    "type": "object",
    "properties": {
        "lo_que_ya_hay": {"type": "string", "description": "Qué hacen hoy los foodies de la zona (de los resultados)"},
        "formatos": {"type": "array", "items": {"type": "object", "properties": {
            "nombre": {"type": "string"}, "descripcion": {"type": "string"}, "por_que_funciona": {"type": "string"},
            "como_se_graba": {"type": "string"}, "ejemplo_gancho": {"type": "string"}, "serie": {"type": "string"}},
            "required": ["nombre", "descripcion", "por_que_funciona", "como_se_graba", "ejemplo_gancho", "serie"],
            "additionalProperties": False}},
        "recomendado": {"type": "integer", "description": "Índice (desde 0) del que más te late para empezar"},
    },
    "required": ["lo_que_ya_hay", "formatos", "recomendado"], "additionalProperties": False,
}


def proponer_formatos() -> dict:
    resultados, conteo = buscar_web.buscar(["foodie Tampico", "reseñas de comida Tampico TikTok", "dónde comer en Tampico",
                                            "foodies Ciudad Madero Instagram", "food blogger Tampico Facebook"],
                                           por_consulta=6, max_texto=300) if buscar_web.disponible() else ([], {})
    _gastar(conteo, "Google: qué hacen los foodies de Tampico")
    r = claude.json_estructurado(
        "Eres estratega de contenido de comida en redes (Facebook, Instagram, TikTok) con mucho criterio. Primero ves "
        "qué hacen los foodies de Tampico/Madero y luego propones formatos que NO existan ahí, que se puedan volver serie "
        "y que aprovechen que Miguel tiene cámara, gimbal, micrófono y dron. Concretos, grabables por una persona.",
        "RESULTADOS:\n" + ("\n".join(f"- {x['titulo']} — {x['url']}: {x['texto']}" for x in resultados[:30]) or "(sin búsqueda)")
        + "\n\nPropón 5 formatos.", SCHEMA_FORMATOS, tarea="ideas", que="Tampiqueando: formatos nuevos")
    with _candado:
        d = cargar()
        d["formatos"] = [{"id": _id(), **f, "elegido": i == r["recomendado"]} for i, f in enumerate(r["formatos"])]
        d["lo_que_ya_hay"] = r["lo_que_ya_hay"]
        guardar(d)
    return {"ok": True, "formatos": d["formatos"], "lo_que_ya_hay": r["lo_que_ya_hay"]}


# ---------- ♻️ remarketing ----------
def ideas_remarketing() -> dict:
    with _candado:
        d = cargar()
        hechos = [{"negocio": p["nombre"], "formato": p.get("formato")} for p in d["planes"]][-30:]
        pubs = [{k: p.get(k) for k in ("titulo", "redes", "t")} for p in d["publicaciones"]][-30:]
    r = claude.json_estructurado(
        "Eres estratega de redes de Tampiqueando. Propones cómo reusar y re-promocionar lo ya hecho (recopilatorios, "
        "«regresamos a…», top del mes, colaboraciones etiquetando al negocio, historias, encuestas) sin repetir lugares "
        "ni inventar datos.",
        f"VISITAS HECHAS: {json.dumps(hechos, ensure_ascii=False)}\nPUBLICADO: {json.dumps(pubs, ensure_ascii=False)}\n"
        "Da 6 ideas concretas para esta semana.",
        {"type": "object", "properties": {"ideas": {"type": "array", "items": {"type": "object", "properties": {
            "idea": {"type": "string"}, "red": {"type": "string"}, "como": {"type": "string"}},
            "required": ["idea", "red", "como"], "additionalProperties": False}}},
         "required": ["ideas"], "additionalProperties": False}, tarea="ideas", que="Tampiqueando: remarketing")
    with _candado:
        d = cargar()
        d["remarketing"] = [{"id": _id(), **x, "t": time.time()} for x in r["ideas"]]
        guardar(d)
    return {"ok": True, "ideas": d["remarketing"]}


# ---------- 📣 publicar ----------
def meta_listo() -> dict:
    return {"facebook": bool(config.env("TAMPICO_FB_PAGINA") and config.env("TAMPICO_FB_TOKEN")),
            "instagram": bool(config.env("TAMPICO_IG_ID") and config.env("TAMPICO_FB_TOKEN") and config.env("OFICINA_URL")),
            "whatsapp_plantilla": bool(_plantilla())}


def nueva_publicacion(archivo: Path, titulo: str, textos: dict, redes: list[str]) -> dict:
    with _candado:
        d = cargar()
        pub = {"id": _id(), "archivo": archivo.name, "titulo": titulo[:100], "textos": textos, "redes": redes,
               "estado": "pendiente", "resultado": {}, "t": time.time(), "token": secrets.token_urlsafe(16)}
        d["publicaciones"].append(pub)
        guardar(d)
    return pub


def _graph(metodo: str, ruta: str, **kw) -> dict:
    import requests
    r = requests.request(metodo, f"https://graph.facebook.com/v21.0/{ruta}", timeout=600,
                         params={**kw.pop("params", {}), "access_token": config.env("TAMPICO_FB_TOKEN")}, **kw)
    datos = r.json() if r.content else {}
    if r.status_code >= 400:
        raise RuntimeError(datos.get("error", {}).get("message") or r.text[:200])
    return datos


def publicar(pid: str) -> dict:
    """Sube a Facebook (video o foto) e Instagram (Reel); TikTok queda para subirlo tú."""
    with _candado:
        d = cargar()
        pub = next((p for p in d["publicaciones"] if p["id"] == pid), None)
    if not pub:
        return {"error": "No encontré esa publicación."}
    ruta = MEDIOS / pub["archivo"]
    es_video = ruta.suffix.lower() in (".mp4", ".mov", ".m4v")
    res = dict(pub.get("resultado") or {})
    listo = meta_listo()
    if "facebook" in pub["redes"] and listo["facebook"] and not res.get("facebook"):
        try:
            pagina = config.env("TAMPICO_FB_PAGINA")
            with open(ruta, "rb") as f:
                if es_video:
                    r = _graph("POST", f"{pagina}/videos", data={"description": pub["textos"].get("facebook", "")},
                               files={"source": f})
                else:
                    r = _graph("POST", f"{pagina}/photos", data={"caption": pub["textos"].get("facebook", "")},
                               files={"source": f})
            res["facebook"] = r.get("id") or r.get("post_id") or "ok"
        except Exception as exc:  # noqa: BLE001
            res["facebook_error"] = str(exc)[:200]
    if "instagram" in pub["redes"] and listo["instagram"] and not res.get("instagram"):
        try:  # Instagram baja el archivo de una dirección pública (temporal, con clave)
            url = f"{config.env('OFICINA_URL').rstrip('/')}/publico/tampico/{pub['token']}/{pub['archivo']}"
            ig = config.env("TAMPICO_IG_ID")
            cuerpo = ({"media_type": "REELS", "video_url": url} if es_video else {"image_url": url})
            cont = _graph("POST", f"{ig}/media", data={**cuerpo, "caption": pub["textos"].get("instagram", "")})
            for _ in range(60):  # el video tarda en procesarse
                if not es_video or _graph("GET", cont["id"], params={"fields": "status_code"}).get("status_code") == "FINISHED":
                    break
                time.sleep(10)
            res["instagram"] = _graph("POST", f"{ig}/media_publish", data={"creation_id": cont["id"]}).get("id") or "ok"
        except Exception as exc:  # noqa: BLE001
            res["instagram_error"] = str(exc)[:200]
    with _candado:
        d = cargar()
        p = next((x for x in d["publicaciones"] if x["id"] == pid), None)
        if p:
            p["resultado"] = res
            ok = [r for r in ("facebook", "instagram") if r in p["redes"] and res.get(r)]
            p["estado"] = "publicado" if ok else "error" if any(k.endswith("_error") for k in res) else "pendiente"
            guardar(d)
    return {"ok": True, "resultado": res}


def resumen() -> dict:
    """Para la pestaña 🌮 Tampico."""
    d = cargar()
    hoy = _ahora().date().isoformat()
    cuenta = {e: 0 for e in ESTADOS}
    for n in d["negocios"]:
        cuenta[n["estado"]] = cuenta.get(n["estado"], 0) + 1
    return {"negocios": sorted(d["negocios"], key=lambda n: (ESTADOS.index(n["estado"]) if n["estado"] in ESTADOS else 99,
                                                           -(n.get("resenas") or 0)))[:300],
            "cuenta": cuenta, "planes": d["planes"][-30:][::-1], "dron": d["dron"][-60:], "formatos": d["formatos"],
            "lo_que_ya_hay": d.get("lo_que_ya_hay", ""), "remarketing": d["remarketing"],
            "publicaciones": [{k: v for k, v in p.items() if k != "token"} for p in d["publicaciones"][-40:][::-1]],
            "ajustes": d["ajustes"], "conexiones": meta_listo(),
            "enviados_hoy": sum(1 for n in d["negocios"] if n.get("contactado_dia") == hoy),
            "chats": {k: v[-20:] for k, v in d["chats"].items()}, "precauciones_dron": DRON_PRECAUCIONES}
