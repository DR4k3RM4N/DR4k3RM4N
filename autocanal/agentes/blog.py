"""Agente 6 — Blog: escribe la entrada y la sube a WordPress con imagen destacada y capturas."""
from __future__ import annotations

import json
import mimetypes
import re
from pathlib import Path

import requests

from . import claude, config

SYSTEM = f"""Eres redactora SEO del blog de "{config.CANAL_NOMBRE}", que analiza apps que prometen \
pagar dinero. Escribes en español, claro y útil, para gente que busca en Google "<app> paga o es \
estafa". Si te dan la GUÍA DE ESTILO del creador, escribe como él (tono, estructura, cómo empieza y \
cierra, frases), pero mejor posicionado.

Reglas de contenido:
- Solo usa datos del expediente. Afirmaciones fuertes solo si el veredicto las respalda.
- Estructura con <h2>/<h3>, párrafos cortos, una lista de señales de alerta, una tabla con \
datos clave (desarrollador, descargas, calificación, pago mínimo), veredicto y preguntas frecuentes.

Reglas SEO:
- Elige UNA palabra clave principal (la búsqueda más probable, ej. "<app> paga o es estafa") y 3 a 6 \
secundarias (usa las búsquedas relacionadas que te paso).
- La principal va al inicio del título (máx. 60 caracteres), en el primer párrafo, en al menos un \
<h2>, en el slug (corto, sin palabras vacías) y en el texto alternativo de una captura.
- Meta descripción de 140 a 158 caracteres, con la palabra clave y una razón para hacer clic.
- Sección final "Preguntas frecuentes" con <h3> por pregunta: usa las preguntas reales que hace la \
gente en Google (te las paso) y contéstalas con datos del expediente.
- Supera a la competencia: cubre lo que sus títulos prometen y agrega lo que tú sí tienes (prueba, \
reseñas reales, veredicto).
- Enlaces internos: si te paso entradas del mismo blog, enlaza 2 o 3 relacionadas con texto descriptivo.
- Enlaces externos a las fuentes del expediente.
- Inserta las capturas donde convenga con el marcador exacto {{{{captura_N}}}} en su propio párrafo \
(N empieza en 1). Usa entre 3 y 6.
- Pon el marcador {{{{video}}}} cerca del inicio, donde irá el video de YouTube.
- Cita fuentes web como enlaces cuando las uses.
- HTML simple compatible con el editor de WordPress (sin <html>, <head> ni estilos)."""

SCHEMA = {
    "type": "object",
    "properties": {
        "titulo": {"type": "string"},
        "slug": {"type": "string"},
        "meta_descripcion": {"type": "string"},
        "extracto": {"type": "string"},
        "html": {"type": "string"},
        "etiquetas": {"type": "array", "items": {"type": "string"}},
        "alt_capturas": {"type": "array", "items": {"type": "string"}},
        "palabra_clave": {"type": "string"},
        "palabras_secundarias": {"type": "array", "items": {"type": "string"}},
        "enlaces_internos": {"type": "array", "items": {"type": "string"}, "description": "URLs internas que usaste"},
    },
    "required": ["titulo", "slug", "meta_descripcion", "extracto", "html", "etiquetas", "alt_capturas",
                 "palabra_clave", "palabras_secundarias", "enlaces_internos"],
    "additionalProperties": False,
}


def posts_propios(limite: int = 40) -> list[dict]:
    """Entradas ya publicadas en tu blog, para enlazarlas (se guardan 12 h para no preguntar siempre)."""
    import time

    from . import estilo

    url = config.env("WP_URL").rstrip("/")
    if not url:
        return []
    cache = estilo.DIR / "posts_cache.json"
    if cache.exists() and time.time() - cache.stat().st_mtime < 12 * 3600:
        return json.loads(cache.read_text(encoding="utf-8"))
    try:
        r = requests.get(f"{url}/wp-json/wp/v2/posts", params={"per_page": limite, "_fields": "title,link"}, timeout=30)
        r.raise_for_status()
        posts = [{"titulo": re.sub(r"<[^>]+>", "", p["title"]["rendered"]), "url": p["link"]} for p in r.json()]
    except (requests.RequestException, ValueError, KeyError) as exc:
        print(f"    aviso: no pude leer tus entradas para enlazarlas: {exc}", flush=True)
        return []
    estilo.DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(posts, ensure_ascii=False), encoding="utf-8")
    return posts


SYSTEM_TEMA = f"""Eres redactora SEO del blog de "{config.CANAL_NOMBRE}". Esta entrada NO es de apps que pagan: es de un \
tema libre (videojuego, película, tecnología, noticia…). Escribes en español, claro y útil, para gente que busca ese \
tema en Google. Si te dan la GUÍA DE ESTILO del creador, escribe como él, pero mejor posicionado.

Reglas de contenido:
- Usa los datos del expediente (puntos, curiosidades, comentarios); no inventes cifras ni fechas.
- Estructura con <h2>/<h3>, párrafos cortos, listas o tablas donde ayuden, tu conclusión y preguntas frecuentes.

Reglas SEO:
- Palabra clave principal = la búsqueda más probable para el enfoque del video; 3 a 6 secundarias (usa las \
búsquedas relacionadas que te paso).
- La principal va al inicio del título (máx. 60 caracteres), en el primer párrafo, en al menos un <h2>, en el slug \
y en el texto alternativo de una imagen.
- Meta descripción de 140 a 158 caracteres, con la palabra clave y una razón para hacer clic.
- "Preguntas frecuentes" con <h3> por pregunta: usa las preguntas reales de Google que te paso.
- Enlaces internos: si te paso entradas del mismo blog, enlaza 2 o 3 relacionadas. Enlaces externos a las fuentes.
- Inserta imágenes con el marcador exacto {{{{captura_N}}}} en su propio párrafo (N empieza en 1). Usa entre 2 y 5.
- Pon el marcador {{{{video}}}} cerca del inicio, donde irá el video de YouTube.
- HTML simple compatible con el editor de WordPress (sin <html>, <head> ni estilos)."""


def escribir(ficha: dict, expediente: dict, n_capturas: int) -> dict:
    from . import buscar_web, estilo

    exp = {k: v for k, v in expediente.items() if k != "informe_web"}
    es_tema = expediente.get("tipo") == "tema"
    app = ficha["title"].split(":")[0].split(" - ")[0].strip()
    partes = [
        (f"TEMA: {app} — VIDEO: {expediente.get('angulo', '')}" if es_tema else
         f"APP: {json.dumps({k: v for k, v in ficha.items() if k not in ('description', 'screenshots', 'icon', 'headerImage', 'histogram')}, ensure_ascii=False, default=str)}"),
        f"EXPEDIENTE:\n{json.dumps(exp, ensure_ascii=False, default=str)}",
    ]
    guia = estilo.cargar().get("blog")
    largo = "1200-1800"
    if guia:
        partes.append("GUÍA DE ESTILO DEL CREADOR (escribe así):\n" + json.dumps(
            {k: guia[k] for k in ("resumen", "tono", "estructura", "como_empieza", "como_cierra", "recursos",
                                  "frases_tipicas", "mejoras_seo") if k in guia}, ensure_ascii=False))
        if guia.get("longitud_palabras"):
            n = int(guia["longitud_palabras"])
            largo = f"{max(900, int(n * 0.9))}-{max(1300, int(n * 1.2))}"
    if buscar_web.disponible():
        s = buscar_web.seo(expediente.get("angulo") or app if es_tema else f"{app} paga o es estafa")
        if s["busquedas"] and claude.al_gastar:
            claude.al_gastar(getattr(claude.contexto, "proyecto", None), "blog", "búsqueda",
                             buscar_web.costo({"serper" if buscar_web.SERPER else "tavily": s["busquedas"]}), 0, 0,
                             f"Google SEO ({s['busquedas']} búsqueda)")
        partes.append("INVESTIGACIÓN SEO EN GOOGLE:\n" + json.dumps(
            {"lo_que_pregunta_la_gente": s["preguntas"], "busquedas_relacionadas": s["relacionadas"],
             "competencia_en_primera_pagina": s["competencia"]}, ensure_ascii=False))
    internos = [p for p in posts_propios() if app.lower() not in p["titulo"].lower()][:25]
    if internos:
        partes.append("ENTRADAS DEL MISMO BLOG (para enlaces internos):\n" + json.dumps(internos, ensure_ascii=False))
    partes.append(f"Hay {n_capturas} {'imágenes' if es_tema else 'capturas'} disponibles. Escribe la entrada ({largo} palabras).")
    return claude.json_estructurado(SYSTEM_TEMA if es_tema else SYSTEM, "\n\n".join(partes), SCHEMA, tarea="blog",
                                    que="escribir post")


def cabecera_respaldo(usuario: str, clave: str) -> dict:
    """Muchos hostings borran la cabecera Authorization. Mandamos los mismos datos también en una cabecera propia
    que lee el plugin «AutoCanal – Conexión» (se instala desde wp-admin, sin tocar .htaccess). WordPress revisa
    la contraseña de aplicación igual que siempre."""
    import base64
    return {"X-AutoCanal-Auth": base64.b64encode(f"{usuario}:{clave}".encode()).decode()}


class WordPress:
    def __init__(self):
        self.url = config.env("WP_URL").rstrip("/")
        self.auth = (config.env("WP_USUARIO"), config.env("WP_APP_PASSWORD").replace(" ", ""))
        if not (self.url and all(self.auth)):
            raise RuntimeError("Faltan WP_URL, WP_USUARIO o WP_APP_PASSWORD en .env")

    def _api(self, metodo: str, ruta: str, **kw) -> dict:
        kw["headers"] = {**cabecera_respaldo(*self.auth), **(kw.get("headers") or {})}
        r = requests.request(metodo, f"{self.url}/wp-json/wp/v2/{ruta}", auth=self.auth, timeout=120, **kw)
        if r.status_code >= 400:
            if r.status_code in (401, 403) and any(c in r.text for c in ("rest_cannot_create", "rest_not_logged_in",
                                                                         "rest_cannot_upload", "rest_forbidden")):
                raise RuntimeError("Tu blog no recibió el usuario y la contraseña (tu hosting borra la cabecera de acceso). "
                                   "Instala el plugin «AutoCanal – Conexión» (Proyectos → Plugin para el blog) y dale «Subir blog».")
            raise RuntimeError(f"WordPress {r.status_code}: {r.text[:300]}")
        return r.json()

    def subir_imagen(self, ruta: str, nombre: str, alt: str = "") -> dict:
        tipo = mimetypes.guess_type(ruta)[0] or "image/png"
        media = self._api("POST", "media", data=Path(ruta).read_bytes(), headers={
            "Content-Disposition": f'attachment; filename="{nombre}"', "Content-Type": tipo})
        if alt:
            self._api("POST", f"media/{media['id']}", json={"alt_text": alt})
        return media

    def etiquetas(self, nombres: list[str]) -> list[int]:
        ids = []
        for n in nombres[:10]:
            existentes = self._api("GET", "tags", params={"search": n})
            match = next((t for t in existentes if t["name"].lower() == n.lower()), None)
            ids.append(match["id"] if match else self._api("POST", "tags", json={"name": n})["id"])
        return ids

    def publicar(self, entrada: dict, imagenes: dict, miniatura: str | None, slug_base: str) -> dict:
        caps = imagenes.get("capturas") or []
        html = entrada["html"]
        for n in sorted({int(m) for m in re.findall(r"\{\{captura_(\d+)\}\}", html)}):
            if 1 <= n <= len(caps):
                alt = (entrada["alt_capturas"][n - 1] if n - 1 < len(entrada["alt_capturas"])
                       else f"Captura {n} de la app")
                media = self.subir_imagen(caps[n - 1], f"{slug_base}-captura-{n}.png", alt)
                bloque = (f'<figure class="wp-block-image aligncenter size-large">'
                          f'<img src="{media["source_url"]}" alt="{alt}" class="wp-image-{media["id"]}"/></figure>')
            else:
                bloque = ""
            html = re.sub(rf"(<p>\s*)?\{{\{{captura_{n}\}}\}}(\s*</p>)?", bloque, html)
        html = re.sub(r"(<p>\s*)?\{\{video\}\}(\s*</p>)?", "<!--VIDEO-->", html)

        modo = config.env("WP_IMAGEN_DESTACADA", "playstore")
        destacada = (miniatura if modo == "miniatura" else None) or imagenes.get("portada") or imagenes.get("icono")
        datos = {
            "title": entrada["titulo"], "slug": entrada["slug"], "content": html,
            "excerpt": entrada["extracto"], "status": config.env("WP_ESTADO", "draft"),
            "tags": self.etiquetas(entrada["etiquetas"]),
        }
        if destacada:
            datos["featured_media"] = self.subir_imagen(destacada, f"{slug_base}-destacada.png",
                                                        entrada["titulo"])["id"]
        if config.env("WP_CATEGORIA_ID"):
            datos["categories"] = [int(config.env("WP_CATEGORIA_ID"))]
        post = self._api("POST", "posts", json=datos)
        return {"id": post["id"], "link": post["link"], "estado": post["status"]}

    def insertar_video(self, post_id: int, youtube_url: str) -> None:
        post = self._api("GET", f"posts/{post_id}", params={"context": "edit"})
        html = post["content"]["raw"]
        embed = (f'<!-- wp:embed {{"url":"{youtube_url}","type":"video","providerNameSlug":"youtube"}} -->\n'
                 f'<figure class="wp-block-embed is-type-video is-provider-youtube"><div class="wp-block-embed__wrapper">\n'
                 f'{youtube_url}\n</div></figure>\n<!-- /wp:embed -->')
        html = html.replace("<!--VIDEO-->", embed) if "<!--VIDEO-->" in html else embed + "\n" + html
        self._api("POST", f"posts/{post_id}", json={"content": html})
