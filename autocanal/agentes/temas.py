"""Videos de cualquier tema (no solo apps que pagan): videojuegos, películas, tecnología, noticias…

Paola piensa lo que pediste: si dices "hazme un video de Marvel Rivals", busca en Google qué está
buscando la gente sobre eso ahora (preguntas, búsquedas relacionadas, noticias) y te propone varias
ideas de video con enfoques distintos. Si ya diste el enfoque, lo respeta y te sugiere alternativas.

Costo por pedido: ~3 búsquedas (fracciones de centavo) + una llamada a Haiku.
Ids de proyecto: "tema:<slug>" (la carpeta guarda tema, enfoque y formato en origen.json).
"""
from __future__ import annotations

import json
import re
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

from . import buscar_web, claude, config, playstore

FORMATOS = ["top", "guia", "noticias", "analisis", "opinion", "curiosidades", "comparativa", "tutorial", "historia"]


def _slug(t: str, n: int = 40) -> str:
    import unicodedata

    t = "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:n].strip("-") or "tema"


def _gastar(etapa: str, conteo: dict, que: str) -> None:
    gasto = buscar_web.costo(conteo)
    if claude.al_gastar and gasto:
        claude.al_gastar(getattr(claude.contexto, "proyecto", None), etapa, "búsqueda", gasto, 0, 0, que)


# ---------- ideas ----------
SISTEMA_IDEAS = f"""Eres Paola, productora y estratega de contenido de YouTube con mucho olfato para lo que la gente \
quiere ver. Trabajas para el canal "{config.CANAL_NOMBRE}" (público en español, {config.CANAL_PAIS.upper()}).
El jefe te pide un video de un tema. Piensa qué quiso decir y qué video sobre ese tema conseguiría más vistas \
y retención AHORA: usa lo que la gente pregunta y busca en Google y las noticias recientes que te paso.

Reglas:
- Ideas concretas, no genéricas ("Los 5 personajes más rotos de la temporada 4" y no "Video de Marvel Rivals").
- Formatos variados (top, guía, noticias, análisis, opinión, curiosidades, comparativa, tutorial, historia).
- Si el jefe ya dio un enfoque, la idea 1 es exactamente ese enfoque (mejora solo la redacción del título) y \
las demás son alternativas cercanas.
- "por_que": la razón concreta (qué busca la gente, qué pasó recientemente, por qué engancha), en una frase.
- Respeta los gustos del jefe que te paso.
- Que se puedan hacer con investigación en internet, imágenes y narración (y clips del jefe si los graba)."""

SCHEMA_IDEAS = {
    "type": "object",
    "properties": {
        "tema": {"type": "string", "description": "El tema bien escrito (ej. 'Marvel Rivals')"},
        "ideas": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "titulo": {"type": "string", "description": "Título tentativo del video (máx. 70 caracteres)"},
                "formato": {"type": "string", "enum": FORMATOS},
                "por_que": {"type": "string"},
                "potencial_vistas": {"type": "string", "enum": ["alto", "medio", "bajo"]},
            },
            "required": ["titulo", "formato", "por_que", "potencial_vistas"],
            "additionalProperties": False,
        }},
    },
    "required": ["tema", "ideas"],
    "additionalProperties": False,
}


def ideas(tema: str, angulo: str = "", pedido: str = "", guia: str = "", cuantas: int = 5) -> list[dict]:
    contexto = {}
    if buscar_web.disponible():
        s = buscar_web.seo(tema)
        noticias, conteo = buscar_web.buscar([f"{tema} novedades", f"{tema} {angulo}".strip() if angulo else f"{tema} reddit"],
                                             por_consulta=5, max_texto=250)
        conteo = {**conteo}
        prov = "serper" if buscar_web.SERPER else "tavily"
        conteo[prov] = conteo.get(prov, 0) + s["busquedas"]
        _gastar("ideas", conteo, f"Google ({sum(conteo.values())} búsquedas para ideas)")
        contexto = {"lo_que_pregunta_la_gente": s["preguntas"], "busquedas_relacionadas": s["relacionadas"],
                    "lo_que_sale_en_google": [{"titulo": r["titulo"], "fecha": r.get("fecha", ""), "texto": r["texto"]}
                                              for r in noticias[:10]]}
    pedido_ia = (f"PEDIDO DEL JEFE: {pedido or tema}\nTEMA: {tema}\n" + (f"ENFOQUE QUE DIO: {angulo}\n" if angulo else "")
                 + (f"\nGUSTOS DEL JEFE:\n{guia}\n" if guia else "")
                 + (f"\nGOOGLE HOY:\n{json.dumps(contexto, ensure_ascii=False)}\n" if contexto else
                    "\n(No hay búsqueda en Google disponible: usa lo que sabes y marca las ideas como para verificar.)\n")
                 + f"\nPropón {cuantas} ideas de video.")
    r = claude.json_estructurado(SISTEMA_IDEAS, pedido_ia, SCHEMA_IDEAS, tarea="ideas", que="ideas de un tema")
    nombre = (r.get("tema") or tema).strip()[:60]
    salida = []
    for k, i in enumerate(r.get("ideas", [])[:cuantas]):
        titulo = i["titulo"].strip()[:90]
        salida.append({
            "app_id": f"tema:{_slug(nombre, 24)}-{_slug(titulo, 34)}", "titulo": nombre, "angulo": titulo,
            "tema": nombre, "formato": i["formato"], "potencial_vistas": i["potencial_vistas"],
            "por_que": ("💡 Tu enfoque. " if angulo and k == 0 else "💡 ") + i["por_que"],
            "personalizada": True, "idea_jefe": pedido or tema,
        })
    if not salida:
        raise claude.ErrorIA(f"No se me ocurrieron ideas para «{tema}». ¿Me das más detalles?")
    return salida


# ---------- investigación ----------
def recolectar(app_id: str, carpeta: Path, origen: dict) -> dict:
    """Ficha del tema e imágenes de Google Imágenes (sin Play Store)."""
    import requests
    from PIL import Image

    tema, angulo = origen.get("tema") or origen.get("nombre") or app_id[5:], origen.get("angulo", "")
    img = carpeta / "img"
    img.mkdir(parents=True, exist_ok=True)
    capturas, icono = [], None
    if buscar_web.disponible():
        print(f"  · imágenes de «{tema}»")
        candidatas = buscar_web.imagenes(f"{tema} {angulo}"[:120], 12) + buscar_web.imagenes(tema, 10)
        _gastar("investigar", {"serper" if buscar_web.SERPER else "tavily": 2}, "Google Imágenes (2 búsquedas)")
        vistas = set()
        for x in candidatas:
            if len(capturas) >= 8 or x["url"] in vistas:
                continue
            vistas.add(x["url"])
            try:
                r = requests.get(x["url"], timeout=20, headers={"User-Agent": "Mozilla/5.0"})
                r.raise_for_status()
                im = Image.open(BytesIO(r.content)).convert("RGB")
            except Exception:  # noqa: BLE001 — imagen rota o protegida: se salta
                continue
            if min(im.size) < 300:
                continue
            p = img / f"captura_{len(capturas) + 1}.jpg"
            im.save(p, quality=90)
            capturas.append(str(p))
            if icono is None and im.width >= im.height * 0.8:  # recorte cuadrado de la primera buena
                lado = min(im.size)
                x0, y0 = (im.width - lado) // 2, (im.height - lado) // 2
                icono = img / "icono.png"
                im.crop((x0, y0, x0 + lado, y0 + lado)).resize((512, 512)).save(icono)
    ficha = {"appId": app_id, "title": tema, "tema": True, "angulo": angulo, "formato": origen.get("formato", ""),
             "summary": angulo, "description": "", "developer": "", "installs": "", "score": None,
             "screenshots": capturas, "icon": None, "headerImage": None}
    imagenes = {"icono": str(icono) if icono else None, "portada": None, "capturas": capturas}
    playstore.guardar(carpeta, "ficha.json", ficha)
    playstore.guardar(carpeta, "resenas.json", [])
    playstore.guardar(carpeta, "imagenes.json", imagenes)
    return {"ficha": ficha, "resenas": [], "imagenes": imagenes}


SISTEMA_LEER = """Eres investigador de un canal de YouTube en español. Te paso resultados de Google sobre un tema \
y el enfoque del video. Saca lo que sirve para ESE video: datos concretos, cifras, fechas, nombres, cambios \
recientes, opiniones de la comunidad y curiosidades.

Reglas:
- Cada punto lleva la URL exacta del resultado de donde sale. No inventes URLs ni datos.
- Prefiere lo reciente; si algo puede haber cambiado (parches, precios, fechas), anótalo en "por_verificar".
- "comentarios": opiniones de gente copiadas TAL CUAL de los resultados (máx. 6), con su URL.
- Si casi no hay nada útil, dilo en el resumen; no rellenes."""

SCHEMA_LEER = {
    "type": "object",
    "properties": {
        "resumen": {"type": "string", "description": "De qué trata y qué se encontró, máx. 120 palabras"},
        "puntos": {"type": "array", "items": {
            "type": "object",
            "properties": {"titulo": {"type": "string"}, "detalle": {"type": "string"}, "url": {"type": "string"}},
            "required": ["titulo", "detalle", "url"], "additionalProperties": False}},
        "curiosidades": {"type": "array", "items": {
            "type": "object",
            "properties": {"dato": {"type": "string"}, "url": {"type": "string"}},
            "required": ["dato", "url"], "additionalProperties": False}},
        "comentarios": {"type": "array", "items": {
            "type": "object",
            "properties": {"autor": {"type": "string"}, "texto": {"type": "string"}, "url": {"type": "string"}},
            "required": ["autor", "texto", "url"], "additionalProperties": False}},
        "por_verificar": {"type": "array", "items": {"type": "string"},
                          "description": "Qué debe revisar el creador antes de publicar"},
    },
    "required": ["resumen", "puntos", "curiosidades", "comentarios", "por_verificar"],
    "additionalProperties": False,
}


def analizar(datos: dict, carpeta: Path, con_web: bool = True) -> dict:
    ficha = datos["ficha"]
    tema, angulo = ficha["title"], ficha.get("angulo", "")
    resultados, conteo = [], {}
    if con_web and buscar_web.disponible():
        consultas = list(dict.fromkeys(q.strip() for q in [
            angulo, f"{tema} {angulo}", f"{tema} novedades", f"{tema} reddit opiniones", f"{tema} guía",
            f"{tema} curiosidades", f"{tema} mejores", f"{tema} 2026"] if q.strip()))[:8]
        print(f"  · buscando en internet ({', '.join(buscar_web.proveedores())}): {len(consultas)} búsquedas")
        resultados, conteo = buscar_web.buscar(consultas)
        _gastar("investigar", conteo, f"Google ({sum(conteo.values())} búsquedas)")
    lista = "\n\n".join(f"[{i}] {r['titulo']} — {r['url']}\n{r.get('fecha', '')} {r['texto']}"
                         for i, r in enumerate(resultados[:60]))
    print("  · armando expediente del tema")
    leido = claude.json_estructurado(
        SISTEMA_LEER,
        f"TEMA: {tema}\nENFOQUE DEL VIDEO: {angulo}\nFORMATO: {ficha.get('formato', '')}\n\n"
        + (f"RESULTADOS DE BÚSQUEDA:\n{lista}" if lista else
           "No hubo búsqueda en internet: usa solo lo que sepas con seguridad, url vacía, y pon en por_verificar "
           "todo lo que pueda estar desactualizado."),
        SCHEMA_LEER, tarea="leer_web", que="investigar tema")
    urls = {r["url"]: r["titulo"] for r in resultados}
    textos = {r["url"]: (r.get("texto") or "").lower() for r in resultados}
    validos = (lambda u: u in urls) if urls else (lambda u: True)
    puntos = [p for p in leido["puntos"] if validos(p["url"])]
    curiosidades = [c for c in leido["curiosidades"] if validos(c["url"])]
    comentarios = []
    for c in leido["comentarios"]:
        frag = c["texto"].lower()[:60]
        if c["url"] in urls and frag and frag in textos.get(c["url"], ""):
            comentarios.append({"usuario": c["autor"] or "Usuario", "estrellas": None, "texto": c["texto"], "likes": 0,
                                "fecha": "", "fuente": urlparse(c["url"]).netloc.replace("www.", ""), "url": c["url"]})
    fuentes, vistas = [], set()
    for u in [p["url"] for p in puntos] + [c["url"] for c in curiosidades]:
        if u in urls and u not in vistas:
            vistas.add(u)
            fuentes.append({"titulo": urls[u] or u, "url": u})
    exp = {"tipo": "tema", "tema": tema, "angulo": angulo, "formato": ficha.get("formato", ""),
           "veredicto": "tema", "resumen": leido["resumen"], "puntos": puntos, "curiosidades": curiosidades,
           "resenas_citadas": comentarios[:6], "senales": [],
           "pendiente_de_probar": leido["por_verificar"][:6] or ["Revisa que los datos sigan vigentes"],
           "fuentes_web": fuentes[:15],
           "investigacion_web": f"hecha: {sum(conteo.values())} búsquedas" if conteo else "sin búsqueda en internet"}
    playstore.guardar(carpeta, "expediente.json", exp)
    return exp
