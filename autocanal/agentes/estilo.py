"""Tu estilo: archivos de referencia y guías que los agentes aprenden de ti.

Todo vive en la carpeta estilo/ (no se sube a GitHub):
  estilo/miniaturas/   ejemplos de miniaturas que te gustan (tuyas o de otros)
  estilo/cara.png      tu cara recortada con fondo transparente (para la miniatura)
  estilo/fuente.ttf    tu tipografía
  estilo/musica.mp3    música de fondo · estilo/whoosh.mp3 sonido en los cambios de escena
  estilo/intro.mp4     intro de tu canal · estilo/outro.mp4 cierre
  estilo/estilo.json   lo que aprendieron Dani y Rosa + tus ajustes de edición
"""
from __future__ import annotations

import base64
import html as html_mod
import io
import json
import re
from pathlib import Path
from urllib.parse import urlparse

import requests

from . import claude, config

DIR = config.BASE / "estilo"
REFS = DIR / "miniaturas"
ARCHIVO = DIR / "estilo.json"

# tipo -> (nombre de archivo, extensiones permitidas, MB máximo)
TIPOS = {
    "miniatura": (None, (".jpg", ".jpeg", ".png", ".webp"), 10),
    "cara": ("cara.png", (".png",), 10),
    "fuente": ("fuente_negrita.ttf", (".ttf", ".otf"), 10),
    "musica": ("musica.mp3", (".mp3", ".m4a", ".wav"), 30),
    "whoosh": ("whoosh.mp3", (".mp3", ".wav", ".m4a"), 5),
    "intro": ("intro.mp4", (".mp4", ".mov", ".webm"), 200),
    "outro": ("outro.mp4", (".mp4", ".mov", ".webm"), 200),
}

AJUSTES_DEFECTO = {
    "subtitulos": "grande",      # grande (estilo shorts) · clasico
    "transicion": "variado",     # corte · fundido · deslizar · variado
    "barra_progreso": True,
    "sonido_cambios": True,      # whoosh.mp3 en cada cambio de escena (si lo subiste)
    "opciones_miniatura": 3,
}


def cargar() -> dict:
    datos = json.loads(ARCHIVO.read_text(encoding="utf-8")) if ARCHIVO.exists() else {}
    datos["ajustes"] = {**AJUSTES_DEFECTO, **datos.get("ajustes", {})}
    return datos


def guardar(datos: dict) -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVO.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")


def archivo(tipo: str) -> Path | None:
    """Ruta del archivo de estilo si existe (también busca en assets/, donde vivían antes)."""
    nombre = TIPOS[tipo][0]
    for carpeta in (DIR, config.ASSETS):
        p = carpeta / nombre
        if p.exists():
            return p
    return None


def referencias() -> list[Path]:
    if not REFS.exists():
        return []
    return sorted(p for p in REFS.iterdir() if p.suffix.lower() in TIPOS["miniatura"][1])[:12]


def guardar_archivo(tipo: str, nombre: str, datos: bytes) -> Path:
    if tipo not in TIPOS:
        raise ValueError("Tipo de archivo no válido.")
    fijo, extensiones, mb = TIPOS[tipo]
    ext = Path(nombre).suffix.lower()
    if ext not in extensiones:
        raise ValueError(f"Formato no válido. Usa: {', '.join(extensiones)}")
    if len(datos) > mb * 1024 * 1024:
        raise ValueError(f"El archivo pesa más de {mb} MB.")
    if tipo == "miniatura":
        REFS.mkdir(parents=True, exist_ok=True)
        if len(referencias()) >= 12:
            raise ValueError("Ya hay 12 ejemplos; borra alguno primero.")
        limpio = re.sub(r"[^\w.-]+", "_", Path(nombre).stem)[:40] or "ref"
        destino = REFS / f"{limpio}{ext}"
        n = 1
        while destino.exists():
            destino, n = REFS / f"{limpio}_{n}{ext}", n + 1
    else:
        DIR.mkdir(parents=True, exist_ok=True)
        destino = DIR / fijo
    destino.write_bytes(datos)
    return destino


def borrar(tipo: str, nombre: str = "") -> None:
    if tipo == "miniatura":
        p = (REFS / Path(nombre).name)
        if p.exists() and p.parent == REFS:
            p.unlink()
    elif tipo in TIPOS:
        p = DIR / TIPOS[tipo][0]
        p.unlink(missing_ok=True)


def resumen() -> dict:
    datos = cargar()
    return {
        "ajustes": datos["ajustes"],
        "miniaturas": datos.get("miniaturas"),
        "blog": datos.get("blog"),
        "blog_urls": datos.get("blog_urls", []),
        "referencias": [p.name for p in referencias()],
        "archivos": {t: bool(archivo(t)) for t in TIPOS if t != "miniatura"},
    }


# ---------- Dani estudia tus miniaturas ----------
HEX = {"type": "string", "description": "Color en formato #RRGGBB"}
SCHEMA_MINIATURAS = {
    "type": "object",
    "properties": {
        "descripcion": {"type": "string", "description": "Cómo es el estilo, en 2-3 frases"},
        "fondo": {"type": "string", "enum": ["captura_desenfocada", "color_solido", "degradado"]},
        "color_fondo": HEX, "color_fondo_2": HEX,
        "color_texto": HEX, "color_borde_texto": HEX, "color_acento": HEX,
        "posicion_texto": {"type": "string", "enum": ["derecha", "izquierda", "arriba", "abajo"]},
        "mayusculas": {"type": "boolean"},
        "tamano_texto": {"type": "string", "enum": ["grande", "enorme"]},
        "lado_icono": {"type": "string", "enum": ["izquierda", "derecha", "centro"]},
        "lado_cara": {"type": "string", "enum": ["izquierda", "derecha", "ninguno"]},
        "elementos": {"type": "array", "items": {"type": "string", "enum": ["flecha", "circulo", "marco", "sombra_texto"]}},
        "palabras_max": {"type": "integer"},
        "inclinacion_icono": {"type": "integer", "description": "Grados, entre -15 y 15"},
        "consejos_texto": {"type": "string", "description": "Cómo deben ser los textos de la miniatura (tono, palabras)"},
    },
    "required": ["descripcion", "fondo", "color_fondo", "color_fondo_2", "color_texto", "color_borde_texto",
                 "color_acento", "posicion_texto", "mayusculas", "tamano_texto", "lado_icono", "lado_cara",
                 "elementos", "palabras_max", "inclinacion_icono", "consejos_texto"],
    "additionalProperties": False,
}


def imagen_bloque(ruta: Path | str, lado: int = 640) -> dict:
    from PIL import Image

    img = Image.open(ruta).convert("RGB")
    img.thumbnail((lado, lado))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=82)
    return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                        "data": base64.standard_b64encode(buf.getvalue()).decode()}}


def estudiar_miniaturas() -> dict:
    refs = referencias()
    if not refs:
        raise ValueError("Primero sube algunos ejemplos de miniaturas.")
    contenido = [imagen_bloque(p) for p in refs[:8]]
    contenido.append({"type": "text", "text": (
        f"Estas son {len(contenido)} miniaturas de YouTube que le gustan al creador. Describe el estilo que "
        "tienen en común para reproducirlo: tipo de fondo, colores (hex), dónde va el texto, si usa "
        "mayúsculas, qué tan grande, dónde va el elemento principal y la cara, y elementos gráficos. "
        "Si varían, quédate con lo más repetido.")})
    spec = claude.json_estructurado(
        "Eres diseñadora de miniaturas de YouTube. Analizas referencias y describes su estilo con precisión.",
        contenido, SCHEMA_MINIATURAS, tarea="estilo", que="estudiar miniaturas")
    for k in ("color_fondo", "color_fondo_2", "color_texto", "color_borde_texto", "color_acento"):
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", spec.get(k, "")):
            spec[k] = {"color_texto": "#FFD60A", "color_borde_texto": "#000000"}.get(k, "#FF3B30")
    spec["inclinacion_icono"] = max(-15, min(15, int(spec.get("inclinacion_icono", 0))))
    spec["palabras_max"] = max(2, min(6, int(spec.get("palabras_max", 4))))
    datos = cargar()
    datos["miniaturas"] = spec
    guardar(datos)
    return spec


# ---------- Rosa estudia tus entradas ----------
SCHEMA_BLOG = {
    "type": "object",
    "properties": {
        "resumen": {"type": "string", "description": "Cómo escribe el creador, en 2-3 frases"},
        "tono": {"type": "string"},
        "estructura": {"type": "array", "items": {"type": "string"}, "description": "Secciones típicas en orden"},
        "longitud_palabras": {"type": "integer"},
        "como_empieza": {"type": "string"},
        "como_cierra": {"type": "string"},
        "recursos": {"type": "array", "items": {"type": "string"}, "description": "Listas, tablas, negritas, citas…"},
        "frases_tipicas": {"type": "array", "items": {"type": "string"}},
        "mejoras_seo": {"type": "array", "items": {"type": "string"},
                        "description": "Qué le falta a sus entradas para posicionar mejor en Google"},
    },
    "required": ["resumen", "tono", "estructura", "longitud_palabras", "como_empieza", "como_cierra",
                 "recursos", "frases_tipicas", "mejoras_seo"],
    "additionalProperties": False,
}


def _texto_de_html(crudo: str) -> str:
    """Saca el texto del artículo conservando títulos y listas."""
    m = re.search(r"<article[^>]*>(.*?)</article>", crudo, flags=re.S | re.I) or \
        re.search(r'<div[^>]+class="[^"]*entry-content[^"]*"[^>]*>(.*)', crudo, flags=re.S | re.I)
    cuerpo = m.group(1) if m else crudo
    cuerpo = re.sub(r"<(script|style|nav|footer|aside|form)[^>]*>.*?</\1>", " ", cuerpo, flags=re.S | re.I)
    cuerpo = re.sub(r"<h([1-4])[^>]*>", lambda x: "\n\n" + "#" * int(x.group(1)) + " ", cuerpo, flags=re.I)
    cuerpo = re.sub(r"<li[^>]*>", "\n- ", cuerpo, flags=re.I)
    cuerpo = re.sub(r"<(p|br|tr|table|ul|ol)[^>]*>", "\n", cuerpo, flags=re.I)
    cuerpo = re.sub(r"<(strong|b)[^>]*>(.*?)</\1>", r"**\2**", cuerpo, flags=re.S | re.I)
    cuerpo = re.sub(r"<[^>]+>", " ", cuerpo)
    cuerpo = html_mod.unescape(cuerpo)
    cuerpo = re.sub(r"[ \t]+", " ", cuerpo)
    return re.sub(r"\n\s*\n+", "\n\n", cuerpo).strip()


def _leer_entrada(url: str) -> tuple[str, str]:
    """(título, texto). Si es tu WordPress usa su API (más limpio); si no, lee la página."""
    wp = config.env("WP_URL").rstrip("/")
    partes = urlparse(url)
    slug = partes.path.strip("/").split("/")[-1] if partes.path.strip("/") else ""
    if wp and slug and urlparse(wp).netloc == partes.netloc:
        try:
            r = requests.get(f"{wp}/wp-json/wp/v2/posts", params={"slug": slug, "_fields": "title,content"}, timeout=30)
            if r.ok and r.json():
                post = r.json()[0]
                return html_mod.unescape(post["title"]["rendered"]), _texto_de_html(post["content"]["rendered"])
        except (requests.RequestException, ValueError, KeyError):
            pass
    r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0 (compatible; OficinaAutoCanal)"})
    r.raise_for_status()
    titulo = re.search(r"<title[^>]*>(.*?)</title>", r.text, flags=re.S | re.I)
    return (html_mod.unescape(titulo.group(1)).strip() if titulo else url), _texto_de_html(r.text)


def estudiar_blog(urls: list[str]) -> dict:
    urls = [u.strip() for u in urls if u.strip().startswith(("http://", "https://"))][:6]
    if not urls:
        raise ValueError("Pega al menos un enlace a una de tus entradas.")
    textos, fallidas = [], []
    for u in urls:
        try:
            titulo, texto = _leer_entrada(u)
            textos.append(f"=== {titulo} ({u})\n{texto[:6000]}")
        except Exception as exc:  # noqa: BLE001
            fallidas.append(f"{u}: {exc}")
    if not textos:
        raise ValueError("No pude leer ninguna entrada: " + "; ".join(fallidas))
    guia = claude.json_estructurado(
        "Eres editora SEO. Estudias entradas de blog de un creador para que otra redactora escriba igual que él, "
        "pero mejor posicionadas en Google.",
        "ENTRADAS DEL CREADOR:\n\n" + "\n\n".join(textos), SCHEMA_BLOG, tarea="estilo", que="estudiar blog")
    guia["leidas"] = len(textos)
    guia["fallidas"] = fallidas
    datos = cargar()
    datos["blog"], datos["blog_urls"] = guia, urls
    guardar(datos)
    return guia


def ajustar(cambios: dict) -> dict:
    datos = cargar()
    validos = {
        "subtitulos": ("grande", "clasico"), "transicion": ("corte", "fundido", "deslizar", "variado"),
        "barra_progreso": (True, False), "sonido_cambios": (True, False), "opciones_miniatura": (1, 2, 3),
    }
    for k, v in cambios.items():
        if k in validos and v in validos[k]:
            datos["ajustes"][k] = v
    guardar(datos)
    return datos["ajustes"]
