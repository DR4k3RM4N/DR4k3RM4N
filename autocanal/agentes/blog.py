"""Agente 6 — Blog: escribe la entrada y la sube a WordPress con imagen destacada y capturas."""
from __future__ import annotations

import json
import mimetypes
import re
from pathlib import Path

import requests

from . import claude, config

SYSTEM = f"""Eres redactor SEO del blog de "{config.CANAL_NOMBRE}", que analiza apps que prometen \
pagar dinero. Escribes en español, claro y útil, para gente que busca en Google "<app> paga o es \
estafa".

Reglas:
- Solo usa datos del expediente. Afirmaciones fuertes solo si el veredicto las respalda.
- Estructura con <h2>/<h3>, párrafos cortos, una lista de señales de alerta, una tabla con \
datos clave (desarrollador, descargas, calificación, pago mínimo), veredicto y preguntas frecuentes.
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
    },
    "required": ["titulo", "slug", "meta_descripcion", "extracto", "html", "etiquetas", "alt_capturas"],
    "additionalProperties": False,
}


def escribir(ficha: dict, expediente: dict, n_capturas: int) -> dict:
    exp = {k: v for k, v in expediente.items() if k != "informe_web"}
    return claude.json_estructurado(
        SYSTEM,
        f"APP: {json.dumps({k: v for k, v in ficha.items() if k not in ('description', 'screenshots')}, ensure_ascii=False, default=str)}\n\n"
        f"EXPEDIENTE:\n{json.dumps(exp, ensure_ascii=False, default=str)}\n\n"
        f"Hay {n_capturas} capturas disponibles. Escribe la entrada (1200-1800 palabras).",
        SCHEMA, effort="medium",
    )


class WordPress:
    def __init__(self):
        self.url = config.env("WP_URL").rstrip("/")
        self.auth = (config.env("WP_USUARIO"), config.env("WP_APP_PASSWORD").replace(" ", ""))
        if not (self.url and all(self.auth)):
            raise RuntimeError("Faltan WP_URL, WP_USUARIO o WP_APP_PASSWORD en .env")

    def _api(self, metodo: str, ruta: str, **kw) -> dict:
        r = requests.request(metodo, f"{self.url}/wp-json/wp/v2/{ruta}", auth=self.auth, timeout=120, **kw)
        if r.status_code >= 400:
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
