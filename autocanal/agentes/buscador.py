"""Agente 1 — Buscador de ideas: apps "para ganar dinero" que valga la pena investigar, o ideas de cualquier tema (temas.py)."""
from __future__ import annotations

import json
import re

from . import buscar_web, claude, config, playstore

CONSULTAS = [
    "ganar dinero", "gana dinero jugando", "ganar dinero rapido", "apps que pagan",
    "gana dinero viendo videos", "encuestas pagadas", "ganar dinero paypal",
    "gana dinero caminando", "cash rewards", "earn money",
]

SYSTEM = f"""Eres el productor de un canal de YouTube en español ({config.CANAL_PAIS.upper()}) que \
investiga apps que prometen pagar dinero y expone las que no pagan o engañan.
Eliges qué app conviene investigar después. Priorizas:
- Muchas descargas recientes y popularidad (la gente la está buscando ahora).
- Señales de alerta: promesas exageradas, desarrollador desconocido, reseñas que dicen que no paga, \
pago mínimo inalcanzable, muchos anuncios.
- Apps que no se hayan cubierto antes en el canal.
No acuses: solo propones candidatas para investigar."""

SCHEMA = {
    "type": "object",
    "properties": {
        "candidatas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "app_id": {"type": "string"},
                    "titulo": {"type": "string"},
                    "por_que": {"type": "string"},
                    "angulo": {"type": "string", "description": "Idea de video: título tentativo o enfoque"},
                    "potencial_vistas": {"type": "string", "enum": ["alto", "medio", "bajo"]},
                },
                "required": ["app_id", "titulo", "por_que", "angulo", "potencial_vistas"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["candidatas"],
    "additionalProperties": False,
}


def historial() -> list[str]:
    if config.HISTORIAL.exists():
        return json.loads(config.HISTORIAL.read_text(encoding="utf-8"))
    return []


def marcar_hecha(app_id: str) -> None:
    h = historial()
    if app_id not in h:
        h.append(app_id)
        config.HISTORIAL.write_text(json.dumps(h, indent=2), encoding="utf-8")


PEDIDO = {
    "type": "object",
    "properties": {
        "tipo": {"type": "string", "enum": ["idea", "app", "tema", "libre"],
                 "description": "idea = propone un video concreto sobre una app o servicio, con un enfoque; "
                                "app = solo nombra una app para investigar; tema = un tipo de apps o un asunto de dinero; "
                                "libre = cualquier otro tema (videojuego, película, serie, tecnología, noticia, deporte…)"},
        "texto": {"type": "string", "description": "El nombre de la app o servicio (idea/app), o el tema en pocas palabras"},
        "angulo": {"type": "string", "description": "Si es idea o libre y dio un enfoque: el enfoque en sus palabras, como título tentativo; si no, vacío"},
    },
    "required": ["tipo", "texto", "angulo"],
    "additionalProperties": False,
}

SISTEMA_PEDIDO = """Clasificas lo que pide el jefe de un canal de YouTube que analiza apps (que prometen pagar dinero, \
tarjetas, préstamos, inversiones, etc.).
- "idea": propone un video concreto sobre una app o servicio con un enfoque. Ej.: "video, por qué no recomiendas \
Plata Card" → texto "Plata Card", angulo "¿Por qué no recomiendo Plata Card?"; "haz uno de Temu diciendo si paga \
por referidos" → texto "Temu", angulo "¿Temu sí paga por referidos?".
- "app": solo nombra una app para investigar, sin enfoque. Ej.: "Cash Gato".
- "tema": un tipo de apps o un asunto de dinero. Ej.: "apps de encuestas", "préstamos rápidos".
- "libre": cualquier tema que NO sea analizar apps, servicios o formas de ganar dinero: videojuegos, películas, \
series, tecnología, celulares, noticias, deportes, tutoriales… Ej.: "hazme un video de Marvel Rivals" → texto \
"Marvel Rivals", angulo ""; "un video de los mejores personajes de Marvel Rivals para principiantes" → texto \
"Marvel Rivals", angulo "Los mejores personajes de Marvel Rivals para principiantes". OJO: una app de juegos que \
promete pagar dinero NO es libre (es app o idea)."""

ELEGIR_APP = {
    "type": "object",
    "properties": {"app_id": {"type": "string", "description": "El app_id que es esa app; vacío si ninguna lo es"},
                   "razon": {"type": "string"}},
    "required": ["app_id", "razon"],
    "additionalProperties": False,
}

APPS_EN_WEB = {
    "type": "object",
    "properties": {"apps": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "nombre": {"type": "string", "description": "Nombre de la app como aparece en Play Store"},
            "que_dicen": {"type": "string", "description": "Qué se dice de ella en internet, en una frase"},
            "url": {"type": "string"},
        },
        "required": ["nombre", "que_dicen", "url"],
        "additionalProperties": False,
    }}},
    "required": ["apps"],
    "additionalProperties": False,
}


def entender_pedido(pedido: str) -> tuple[str, str, str]:
    """¿Qué pidió? Devuelve (tipo, texto, ángulo); tipo: "idea" | "app" | "tema" | "general"."""
    p = (pedido or "").strip()
    if not p:
        return "general", "", ""
    if re.fullmatch(r"[a-z][\w]*(\.[\w]+){1,}", p, flags=re.I):  # com.empresa.app
        return "app", p, ""
    if m := re.match(r"^(?:la\s+)?app\s+(?!(?:de|del|para|que|sobre|con)\b)(?:llamada\s+)?[\"“']?(.+?)[\"”']?$", p, flags=re.I):
        return "app", m.group(1), ""
    if m := re.fullmatch(r"[\"“'](.+)[\"”']", p):
        return "app", m.group(1), ""
    r = claude.json_estructurado(SISTEMA_PEDIDO, f"Pedido: {p}", PEDIDO, tarea="ideas", que="entender pedido")
    return r["tipo"], (r["texto"] or p).strip(), (r.get("angulo") or "").strip()


def encontrar_app(nombre: str, hechas: set) -> dict | None:
    """Busca una app concreta en Play Store (también por id exacto) y confirma cuál es."""
    encontradas = _de_play([nombre], hechas, n=8, incluir_hechas=True)
    if re.fullmatch(r"[a-z][\w]*(\.[\w]+){1,}", nombre, flags=re.I) and nombre not in encontradas:
        try:
            f = playstore.ficha(nombre)
            encontradas[nombre] = {"app_id": nombre, "titulo": f.get("title"), "dev": f.get("developer"),
                                   "score": f.get("score"), "instalaciones": f.get("installs"),
                                   "resumen": (f.get("summary") or "")[:160]}
        except Exception as exc:  # noqa: BLE001
            print(f"  aviso: no encontré {nombre} en Play Store: {exc}")
    if buscar_web.disponible():  # la búsqueda de Play Store falla seguido: buscar el enlace en Google
        for app_id in buscar_web.ids_play_store(nombre)[:3]:
            if app_id in encontradas:
                continue
            try:
                f = playstore.ficha(app_id)
                encontradas[app_id] = {"app_id": app_id, "titulo": f.get("title"), "dev": f.get("developer"),
                                       "score": f.get("score"), "instalaciones": f.get("installs"),
                                       "resumen": (f.get("summary") or "")[:160],
                                       **({"ya_la_hiciste": True} if app_id in hechas else {})}
            except Exception as exc:  # noqa: BLE001
                print(f"  aviso: {app_id} no se pudo abrir en Play Store: {exc}")
    if not encontradas:
        return None
    r = claude.json_estructurado(
        "Identificas apps en resultados de Play Store.",
        f"¿Cuál de estas es la app oficial de «{nombre}»? Si ninguna lo es, deja app_id vacío.\n"
        + json.dumps(list(encontradas.values()), ensure_ascii=False), ELEGIR_APP, tarea="ideas", que="identificar app")
    return encontradas.get(r["app_id"])


def _de_play(consultas: list[str], hechas: set, n: int = 20, incluir_hechas: bool = False) -> dict[str, dict]:
    encontradas: dict[str, dict] = {}
    for q in consultas:
        try:
            for r in playstore.buscar(q, n):
                if r.get("appId") and (incluir_hechas or r["appId"] not in hechas):
                    encontradas.setdefault(r["appId"], {
                        "app_id": r["appId"], "titulo": r.get("title"), "dev": r.get("developer"),
                        "score": r.get("score"), "instalaciones": r.get("installs"),
                        "resumen": (r.get("summary") or r.get("description") or "")[:160],
                        **({"ya_la_hiciste": True} if r["appId"] in hechas else {}),
                    })
        except Exception as exc:  # noqa: BLE001 — una consulta fallida no detiene la búsqueda
            print(f"  aviso: búsqueda '{q}' falló: {exc}")
    return encontradas


def _de_internet(consultas: list[str], hechas: set) -> dict[str, dict]:
    """Busca en Google qué apps se están mencionando y las localiza en Play Store."""
    resultados, conteo = buscar_web.buscar(consultas, por_consulta=8, max_texto=400)
    gasto = buscar_web.costo(conteo)
    if claude.al_gastar and gasto:
        claude.al_gastar(None, "ideas", "búsqueda", gasto, 0, 0, f"Google ({sum(conteo.values())} búsquedas)")
    if not resultados:
        return {}
    lista = "\n".join(f"- {r['titulo']} ({r['url']}): {r['texto']}" for r in resultados[:50])
    r = claude.json_estructurado(
        "Lees resultados de Google y sacas las apps para ganar dinero que se mencionan (máximo 10). "
        "Solo apps concretas de celular con su nombre, no páginas ni listas genéricas.",
        f"RESULTADOS:\n{lista}", APPS_EN_WEB, tarea="ideas", que="apps en internet")
    salida: dict[str, dict] = {}
    for app in r["apps"][:10]:
        try:
            for x in playstore.buscar(app["nombre"], 3):
                palabras = {w for w in re.findall(r"\w{3,}", app["nombre"].lower())}
                if x.get("appId") and x["appId"] not in hechas and palabras & set(re.findall(r"\w{3,}", (x.get("title") or "").lower())):
                    salida[x["appId"]] = {
                        "app_id": x["appId"], "titulo": x.get("title"), "dev": x.get("developer"),
                        "score": x.get("score"), "instalaciones": x.get("installs"),
                        "resumen": (x.get("summary") or "")[:160],
                        "en_internet": f"{app['que_dicen']} ({app['url']})",
                    }
                    break
        except Exception as exc:  # noqa: BLE001
            print(f"  aviso: no encontré '{app['nombre']}' en Play Store: {exc}")
    return salida


def fuera_de_play(nombre: str) -> dict | None:
    """La app no está en Play Store (se baja por APK o es una página): se investiga solo con Google."""
    if not buscar_web.disponible():
        return None
    slug = re.sub(r"[^a-z0-9]+", "-", nombre.lower()).strip("-")[:50]
    print(f"  · «{nombre}» no está en Play Store: la investigo con Google")
    return {"app_id": f"web:{slug}", "titulo": nombre, "fuera_de_play": True, "resumen": "Fuera de Play Store"}


def ideas(cuantas: int = 5, guia: str = "", pedido: str = "") -> list[dict]:
    """`guia` = gustos del jefe que Paola aprendió; `pedido` = lo que pidió esta vez.

    - Pidió una app concreta → se busca solo en Play Store.
    - Pidió un tema (o nada) → Play Store + lo que se dice en Google (si hay SERPER/TAVILY)."""
    hechas = set(historial())
    tipo, texto, angulo = entender_pedido(pedido)
    print(f"  · pedido: {tipo}" + (f" ({texto})" if texto else "") + (f" — {angulo}" if angulo else ""))
    if tipo == "libre":  # cualquier tema: Paola propone varios enfoques con lo que se busca en Google
        from . import temas
        return temas.ideas(texto, angulo, pedido, guia, cuantas)
    if tipo == "idea":  # tu idea de video: se respeta tal cual, sin filtrar como "app nueva"
        app = encontrar_app(texto, hechas) or fuera_de_play(texto)
        if not app:
            raise claude.ErrorIA(f"No encontré «{texto}» ni en Play Store ni en Google. ¿Me pasas el nombre exacto?")
        return [{"app_id": app["app_id"], "titulo": app["titulo"], "angulo": angulo or pedido,
                 "por_que": f"💡 Idea tuya: {pedido}" + (" (ya hiciste un video de esta app)" if app.get("ya_la_hiciste") else "")
                 + (" · No está en Play Store: la investigo solo con Google." if app.get("fuera_de_play") else ""),
                 "fuera_de_play": bool(app.get("fuera_de_play")),
                 "potencial_vistas": "alto", "personalizada": True, "idea_jefe": pedido}]
    if tipo == "app":
        app = encontrar_app(texto, hechas) or fuera_de_play(texto)
        if not app:
            raise claude.ErrorIA(f"No encontré «{texto}» ni en Play Store ni en Google.")
        return [{"app_id": app["app_id"], "titulo": app["titulo"], "angulo": f"¿{app['titulo']} paga o es estafa?",
                 "por_que": "La pediste tú." + (" No está en Play Store: la investigo solo con Google." if app.get("fuera_de_play") else ""),
                 "fuera_de_play": bool(app.get("fuera_de_play")), "potencial_vistas": "alto", "personalizada": True}]
    if True:  # un tema o búsqueda general
        consultas_play = ([texto, f"{texto} ganar dinero", f"{texto} que pagan", f"gana dinero {texto}"]
                          if tipo == "tema" else CONSULTAS)
        encontradas = _de_play(consultas_play, hechas)
        if buscar_web.disponible():
            consultas_web = ([f"app {texto} para ganar dinero paga o estafa", f"app {texto} no paga reddit",
                              f"nuevas apps de {texto} que pagan opiniones", f"{texto} app ganar dinero denuncias"]
                             if tipo == "tema" else
                             ["apps para ganar dinero que no pagan", "app para ganar dinero estafa denuncias",
                              "app viral ganar dinero tiktok paga o no", "nueva app que paga por jugar reclamos",
                              "earn money app scam not paying reddit"])
            try:
                for k, v in _de_internet(consultas_web, hechas).items():
                    encontradas[k] = {**encontradas.get(k, {}), **v}
            except Exception as exc:  # noqa: BLE001 — si falla internet, se sigue con Play Store
                print(f"  aviso: búsqueda en internet falló: {exc}")
        instruccion = (f"Elige las {cuantas} mejores para investigar" + (f" sobre el tema «{texto}»" if tipo == "tema" else "")
                       + ". Dale prioridad a las que se mencionan en internet ('en_internet').")
    if not encontradas:
        raise claude.ErrorIA("No encontré esa app en Play Store." if tipo == "app" else "No se encontraron apps.")
    datos = json.dumps(list(encontradas.values()), ensure_ascii=False)
    res = claude.json_estructurado(
        SYSTEM,
        f"Apps encontradas:\n{datos}\n\n"
        + (f"Indicaciones y gustos del jefe (respétalos):\n{guia}\n\n" if guia else "")
        + instruccion,
        SCHEMA, tarea="ideas",
    )
    validas = [c for c in res["candidatas"] if c["app_id"] in encontradas]  # nada de ids inventados
    if tipo == "app":  # la pidió el jefe: no se descarta aunque ya esté en la bandeja o ya se haya hecho
        for c in validas:
            c["personalizada"] = True
    return validas[:cuantas]
