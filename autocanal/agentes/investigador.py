"""Agente 2 — Investigador: arma el expediente de evidencia de una app.

Junta la ficha de Play Store, reseñas reales, capturas y lo que se dice en internet,
y le pide a Claude un veredicto respaldado por evidencia (nunca inventado).
"""
from __future__ import annotations

import base64
import json
import re
from pathlib import Path

from . import buscar_web, claude, config, playstore

SYSTEM_WEB = """Eres investigador de fraudes en apps móviles para un canal de YouTube en español.
Busca en internet información verificable sobre la app que te pidan: reportes de usuarios \
(Reddit, Trustpilot, foros, comentarios de YouTube), noticias, quién es el desarrollador, si hay \
pruebas de pago reales, el pago mínimo y cuánto tarda en alcanzarse, cambios de nombre o clones.
Reporta hechos con su fuente. Distingue claramente entre lo comprobado y lo que solo dicen usuarios. \
Si no encuentras nada, dilo; no rellenes."""

SYSTEM_LEER_WEB = """Eres investigador de fraudes en apps móviles para un canal de YouTube en español.
Te paso resultados de búsquedas en Google y otros sitios sobre una app. Léelos y saca solo hechos útiles para saber si la app paga o engaña: reportes de usuarios (Reddit, foros, Trustpilot, YouTube), noticias, quién es el desarrollador, pruebas de pago, pago mínimo y cuánto tarda, cambios de nombre o clones.

Reglas:
- Cada hallazgo lleva la URL exacta del resultado de donde sale. No inventes URLs ni datos.
- Distingue lo comprobado (noticia, documento) de lo que solo dicen usuarios.
- Ignora resultados que hablan de otra app con nombre parecido, y la publicidad de la propia app.
- Si casi no hay nada útil, dilo en el informe; no rellenes."""

SCHEMA_WEB = {
    "type": "object",
    "properties": {
        "informe": {"type": "string", "description": "Resumen de lo encontrado, máximo 200 palabras"},
        "comentarios": {"type": "array", "description": "Comentarios de usuarios copiados TAL CUAL de los resultados (máx. 6)",
                        "items": {"type": "object",
                                  "properties": {"autor": {"type": "string"}, "texto": {"type": "string"}, "url": {"type": "string"}},
                                  "required": ["autor", "texto", "url"], "additionalProperties": False}},
        "hallazgos": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "hecho": {"type": "string"},
                "tipo": {"type": "string", "enum": ["comprobado", "reporte_de_usuarios", "dato_del_desarrollador"]},
                "url": {"type": "string"},
            },
            "required": ["hecho", "tipo", "url"],
            "additionalProperties": False,
        }},
    },
    "required": ["informe", "comentarios", "hallazgos"],
    "additionalProperties": False,
}


def consultas_para(ficha: dict) -> list[str]:
    """Qué buscar en Google sobre la app. Como cada búsqueda cuesta casi nada, se busca de varios ángulos."""
    app, dev = ficha["title"].split(":")[0].split(" - ")[0].strip(), (ficha.get("developer") or "").strip()
    consultas = [
        f'"{app}" app paga o es estafa',
        f'"{app}" no paga retiro',
        f'"{app}" reddit',
        f'"{app}" opiniones pago mínimo',
        f'"{app}" scam payout proof',
        f'"{app}" trustpilot OR reclamos OR denuncia',
        f'"{app}" youtube prueba de pago',
    ]
    if dev:
        consultas.append(f'"{dev}" desarrollador apps')
    extra = int(config.env("BUSQUEDAS_INVESTIGACION", str(len(consultas))) or len(consultas))
    return consultas[:max(1, extra)]


def investigar_google(ficha: dict) -> tuple[str, list[dict], int]:
    """Busca en Google/Tavily y Haiku lee los resultados. Devuelve (informe, fuentes, búsquedas)."""
    investigar_google.comentarios = []
    consultas = consultas_para(ficha)
    print(f"  · buscando en internet ({', '.join(buscar_web.proveedores())}): {len(consultas)} búsquedas")
    resultados, conteo = buscar_web.buscar(consultas)
    gasto = buscar_web.costo(conteo)
    if claude.al_gastar and gasto:
        claude.al_gastar(getattr(claude.contexto, "proyecto", None), getattr(claude.contexto, "etapa", None),
                         "búsqueda", gasto, 0, 0, f"Google ({sum(conteo.values())} búsquedas)")
    if not resultados:
        return "No se encontró nada en internet sobre esta app.", [], sum(conteo.values())
    lista = "\n\n".join(f"[{i}] {r['titulo']} — {r['url']}\n{r.get('fecha', '')} {r['texto']}"
                         for i, r in enumerate(resultados[:60]))
    leido = claude.json_estructurado(
        SYSTEM_LEER_WEB,
        f"APP: {ficha['title']} ({ficha['appId']}) de {ficha.get('developer')}\n"
        f"Qué promete: {ficha.get('summary')}\n\nRESULTADOS DE BÚSQUEDA:\n{lista}",
        SCHEMA_WEB, tarea="leer_web", que="leer resultados")
    urls = {r["url"]: r["titulo"] for r in resultados}
    fuentes, vistas = [], set()
    for h in leido["hallazgos"]:
        if h["url"] in urls and h["url"] not in vistas:  # solo URLs que de verdad salieron en la búsqueda
            vistas.add(h["url"])
            fuentes.append({"titulo": urls[h["url"]] or h["url"], "url": h["url"]})
    hallazgos = "\n".join(f"- [{h['tipo']}] {h['hecho']} ({h['url']})" for h in leido["hallazgos"] if h["url"] in urls)
    # comentarios de usuarios: solo si de verdad aparecen en los resultados (nada inventado)
    textos = {r["url"]: (r.get("texto") or "").lower() for r in resultados}
    comentarios = []
    for c in leido.get("comentarios", []):
        frag = c["texto"].lower()[:60]
        if c["url"] in urls and frag and frag in textos.get(c["url"], ""):
            from urllib.parse import urlparse
            comentarios.append({"usuario": c["autor"] or "Usuario", "estrellas": None, "texto": c["texto"], "likes": 0,
                                "fecha": "", "fuente": urlparse(c["url"]).netloc.replace("www.", ""), "url": c["url"]})
    investigar_google.comentarios = comentarios[:6]
    return f"{leido['informe']}\n\nHALLAZGOS:\n{hallazgos}", fuentes[:15], sum(conteo.values())


SYSTEM_EXPEDIENTE = """Eres el editor de investigación de un canal que analiza apps que prometen \
pagar dinero. Con la evidencia que te dan, armas un expediente para el video.

Reglas legales y de credibilidad (importantes):
- Solo afirmas lo que la evidencia respalda. Cada señal lleva su evidencia y de dónde sale.
- Usa el veredicto "estafa_comprobada" solo si hay evidencia fuerte y de varias fuentes de que no \
paga o engaña. Si solo hay quejas, usa "senales_de_alerta". Si paga pero muy poco, \
"paga_pero_no_vale_la_pena". Si paga bien, "legitima". Si no hay datos, "no_concluyente".
- Las reseñas destacadas se eligen por su índice en la lista; no las reescribas.
- En "pendiente_de_probar" lista lo que el creador debe comprobar él mismo en el celular \
(por ejemplo: intentar retirar, ver cuántos anuncios salen, cuánto se gana en 10 minutos).
- Describe qué muestra cada captura de pantalla, para usarlas en el video."""

SCHEMA = {
    "type": "object",
    "properties": {
        "veredicto": {"type": "string", "enum": [
            "estafa_comprobada", "senales_de_alerta", "paga_pero_no_vale_la_pena",
            "legitima", "no_concluyente"]},
        "resumen": {"type": "string"},
        "que_promete": {"type": "string"},
        "como_dice_que_paga": {"type": "string"},
        "pago_minimo": {"type": "string"},
        "senales": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "senal": {"type": "string"},
                "evidencia": {"type": "string"},
                "fuente": {"type": "string", "description": "playstore, resenas, web:<url> o captura"},
                "gravedad": {"type": "string", "enum": ["alta", "media", "baja"]},
            },
            "required": ["senal", "evidencia", "fuente", "gravedad"],
            "additionalProperties": False,
        }},
        "resenas_destacadas": {"type": "array", "items": {"type": "integer"},
                               "description": "Índices de las reseñas más representativas (máx 6)"},
        "capturas": {"type": "array", "items": {
            "type": "object",
            "properties": {"indice": {"type": "integer"}, "muestra": {"type": "string"}},
            "required": ["indice", "muestra"],
            "additionalProperties": False,
        }},
        "pendiente_de_probar": {"type": "array", "items": {"type": "string"}},
        "alternativas_reales": {"type": "array", "items": {"type": "string"},
                                "description": "Opciones legítimas para ganar dinero, si aplica"},
    },
    "required": ["veredicto", "resumen", "que_promete", "como_dice_que_paga", "pago_minimo",
                 "senales", "resenas_destacadas", "capturas", "pendiente_de_probar",
                 "alternativas_reales"],
    "additionalProperties": False,
}


def _imagen(ruta: str) -> dict:
    """Captura reducida (lado mayor 900 px, JPEG): se ve igual de clara y cuesta muchos menos tokens."""
    import io

    from PIL import Image

    try:
        img = Image.open(ruta).convert("RGB")
        img.thumbnail((900, 900))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=80)
        crudo, tipo = buf.getvalue(), "image/jpeg"
    except Exception:  # noqa: BLE001 — si no se puede abrir, se manda tal cual
        crudo, tipo = Path(ruta).read_bytes(), "image/png"
    datos = base64.standard_b64encode(crudo).decode()
    return {"type": "image", "source": {"type": "base64", "media_type": tipo, "data": datos}}


def recolectar_web(app_id: str, nombre: str, carpeta: Path) -> dict:
    """Sin Play Store: arma la ficha con Google (sitio oficial, de qué se trata) e imágenes de Google Imágenes."""
    from io import BytesIO
    from urllib.parse import urlparse

    import requests
    from PIL import Image

    print(f"  · {nombre} no está en Play Store: datos desde Google")
    resultados, conteo = buscar_web.buscar([f'"{nombre}"', f'"{nombre}" app descargar apk', f'"{nombre}" sitio oficial'], por_consulta=6)
    grandes = ("youtube.", "reddit.", "facebook.", "tiktok.", "instagram.", "play.google.", "x.com", "twitter.", "wikipedia.")
    oficial = next((r for r in resultados if not any(g in r["url"] for g in grandes)), resultados[0] if resultados else {})
    dominio = urlparse(oficial.get("url", "")).netloc.replace("www.", "")
    img = carpeta / "img"
    img.mkdir(parents=True, exist_ok=True)
    capturas, icono = [], None
    candidatas = buscar_web.imagenes(f"{nombre} app", 12)
    gasto = buscar_web.costo(conteo) + buscar_web.PRECIO.get("serper", 0)
    if claude.al_gastar and gasto:
        claude.al_gastar(getattr(claude.contexto, "proyecto", None), "investigar", "búsqueda", gasto, 0, 0,
                         f"Google ({sum(conteo.values()) + 1} búsquedas e imágenes)")
    for x in candidatas:
        if len(capturas) >= 6:
            break
        try:
            r = requests.get(x["url"], timeout=20, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            im = Image.open(BytesIO(r.content)).convert("RGB")
        except Exception:  # noqa: BLE001 — imagen rota o protegida: se salta
            continue
        if min(im.size) < 200:
            continue
        p = img / f"captura_{len(capturas) + 1}.png"
        im.save(p)
        capturas.append(str(p))
        if icono is None and 0.85 < im.width / im.height < 1.18:  # la primera cuadrada sirve de icono
            icono = img / "icono.png"
            im.resize((512, 512)).save(icono)
    if icono is None and dominio:
        try:
            r = requests.get(f"https://www.google.com/s2/favicons?domain={dominio}&sz=256", timeout=20)
            r.raise_for_status()
            icono = img / "icono.png"
            Image.open(BytesIO(r.content)).convert("RGBA").resize((512, 512)).save(icono)
        except Exception:  # noqa: BLE001
            icono = None
    ficha = {"appId": app_id, "title": nombre, "summary": oficial.get("texto", "")[:300], "description": "",
             "developer": dominio or "desconocido", "developerWebsite": oficial.get("url"), "installs": "N/D (fuera de Play Store)",
             "score": None, "url": oficial.get("url"), "screenshots": capturas, "icon": None, "headerImage": None,
             "fuera_de_play_store": True}
    imagenes = {"icono": str(icono) if icono else None, "portada": None, "capturas": capturas}
    playstore.guardar(carpeta, "ficha.json", ficha)
    playstore.guardar(carpeta, "resenas.json", [])
    playstore.guardar(carpeta, "imagenes.json", imagenes)
    return {"ficha": ficha, "resenas": [], "imagenes": imagenes}


def recolectar(app_id: str, carpeta: Path, nombre: str = "") -> dict:
    """Paso sin IA: baja ficha, reseñas e imágenes de Play Store (o de Google si no está en Play Store)."""
    if app_id.startswith("web:"):
        return recolectar_web(app_id, nombre or app_id[4:].replace("-", " "), carpeta)
    print("  · ficha de Play Store")
    ficha = playstore.ficha(app_id)
    print("  · reseñas")
    resenas = playstore.resenas(app_id)
    print("  · imágenes")
    imagenes = playstore.descargar_imagenes(ficha, carpeta)
    playstore.guardar(carpeta, "ficha.json", ficha)
    playstore.guardar(carpeta, "resenas.json", resenas)
    playstore.guardar(carpeta, "imagenes.json", imagenes)
    return {"ficha": ficha, "resenas": resenas, "imagenes": imagenes}


QUEJAS = re.compile(r"no pag|nunca pag|no me pag|no me han pag|estafa|fraude|scam|enga[ñn]|mentira|no deja (retirar|cobrar)|"
                    r"no puedo (retirar|cobrar)|retir|no llega|nunca llega|pura publicidad|demasiados anuncios", re.I)


def necesita_web(resenas: list[dict]) -> tuple[bool, str]:
    """Las reseñas son gratis; internet cuesta. Si ya hay muchas quejas claras, con eso basta.

    INVESTIGACION_WEB en .env: auto (por defecto) · siempre · nunca."""
    modo = config.env("INVESTIGACION_WEB", "auto").lower()
    if modo == "siempre":
        return True, "siempre activada en .env"
    if modo == "nunca":
        return False, "desactivada en .env"
    malas = [r for r in resenas if (r.get("estrellas") or 5) <= 2]
    quejas = [r for r in malas if QUEJAS.search(r.get("texto") or "")]
    minimo = int(config.env("QUEJAS_SUFICIENTES", "8") or 8)
    if len(quejas) >= minimo:
        return False, f"{len(quejas)} reseñas ya reportan que no paga o engaña"
    return True, f"solo {len(quejas)} quejas claras en reseñas; falta evidencia"


def analizar(datos: dict, carpeta: Path, con_web: bool = True) -> dict:
    ficha, resenas, imagenes = datos["ficha"], datos["resenas"], datos["imagenes"]

    informe_web, fuentes = "", []
    modo = config.env("INVESTIGACION_WEB", "auto").lower()
    if con_web and modo != "nunca" and buscar_web.disponible():
        # Búsqueda barata (Serper/Tavily + Haiku): siempre vale la pena
        informe_web, fuentes, n = investigar_google(ficha)
        if ficha.get("fuera_de_play_store") and getattr(investigar_google, "comentarios", None):
            resenas = list(investigar_google.comentarios)  # comentarios reales de la web, con su fuente
        usar_web, motivo = True, f"{n} búsquedas en Google/Tavily"
    else:
        usar_web, motivo = necesita_web(resenas) if con_web else (False, "sin búsqueda web")
    print(f"  · internet: {'sí' if usar_web else 'no'} ({motivo})")
    if usar_web and not informe_web:
        print("  · investigando en internet (Claude + búsqueda web)")
        informe_web, fuentes = claude.investigar_web(
            SYSTEM_WEB,
            f"App: {ficha['title']} ({ficha['appId']}) de {ficha.get('developer')}.\n"
            f"Sitio del desarrollador: {ficha.get('developerWebsite')}\n"
            f"Qué promete: {ficha.get('summary')}\n"
            "¿Paga de verdad? ¿Qué reportan los usuarios? ¿Quién está detrás?\n"
            "Responde en máximo 250 palabras, solo hechos con su fuente.",
        )

    # Reseñas: priorizamos las de 1-2 estrellas con más likes, más una muestra del resto.
    malas = sorted([r for r in resenas if (r["estrellas"] or 5) <= 2], key=lambda r: -r["likes"])[:30]
    buenas = sorted([r for r in resenas if (r["estrellas"] or 0) >= 4], key=lambda r: -r["likes"])[:10]
    muestra = malas + buenas
    if ficha.get("fuera_de_play_store"):  # comentarios de internet (sin estrellas)
        muestra = resenas[:20]
    lista = "\n".join((f"[{i}] {r['estrellas']}★ ({r['likes']} likes, {r['fecha']}) " if r.get("estrellas")
                       else f"[{i}] (comentario en {r.get('fuente', 'internet')}) ") + r["texto"][:300]
                      for i, r in enumerate(muestra))

    contenido = [_imagen(p) for p in imagenes["capturas"][:3]]
    datos_ficha = {k: v for k, v in ficha.items() if k not in ("screenshots", "icon", "headerImage")}
    datos_ficha["description"] = (datos_ficha.get("description") or "")[:1500]
    contenido.append({"type": "text", "text": (
        f"FICHA DE PLAY STORE:\n{json.dumps(datos_ficha, ensure_ascii=False, default=str)}\n\n"
        f"RESEÑAS (índice entre corchetes):\n{lista}\n\n"
        f"INVESTIGACIÓN WEB:\n{informe_web or '(no se hizo)'}\n\n"
        f"FUENTES WEB:\n{json.dumps(fuentes, ensure_ascii=False)}\n\n"
        f"Las imágenes de arriba son las capturas 1 a {len(contenido)} en orden. Arma el expediente."
    )})
    print("  · armando expediente")
    if ficha.get("fuera_de_play_store"):
        contenido[-1]["text"] += ("\n\nOJO: esta app NO está en Play Store (se descarga por fuera, APK o página web). "
                                  "Las 'reseñas' son comentarios de usuarios en internet, con su sitio. No estar en Play Store "
                                  "es un dato relevante para el usuario (menos controles, riesgo al instalar APK).")
    exp = claude.json_estructurado(SYSTEM_EXPEDIENTE, contenido, SCHEMA, tarea="investigar", que="expediente")
    exp["resenas_citadas"] = [muestra[i] for i in exp["resenas_destacadas"] if 0 <= i < len(muestra)][:6]
    exp["fuentes_web"] = fuentes
    exp["informe_web"] = informe_web
    exp["investigacion_web"] = ("hecha" if usar_web else "omitida") + f": {motivo}"
    playstore.guardar(carpeta, "expediente.json", exp)
    return exp
