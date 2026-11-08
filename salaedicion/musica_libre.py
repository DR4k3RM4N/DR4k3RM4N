"""Música libre para tus videos: busca en Openverse (el buscador abierto de WordPress), gratis y sin clave.

Openverse junta audio con licencias libres de Jamendo, Freesound, Wikimedia y otros. Aquí solo se piden pistas que
se pueden usar en videos con monetización y se pueden editar (license_type=commercial,modification).
Si la licencia pide crédito (CC BY), se arma el texto para la descripción.
(Pixabay no tiene API para su música, solo para imágenes y videos; por eso no se usa.)
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import requests

API = "https://api.openverse.org/v1/audio/"
NOMBRE_LICENCIA = {"cc0": "CC0 (dominio público)", "pdm": "Dominio público", "by": "CC BY", "by-sa": "CC BY-SA"}


def _seguro(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "-", t).strip("-")[:50] or "pista"


def credito(o: dict) -> str:
    """Texto para la descripción (vacío si es dominio público)."""
    if o.get("licencia") in ("cc0", "pdm"):
        return ""
    lic = f"{NOMBRE_LICENCIA.get(o['licencia'], o['licencia'].upper())} {o.get('version') or ''}".strip()
    return f"Música: «{o['titulo']}» de {o['autor']} ({lic}) {o.get('pagina') or ''}".strip()


def buscar(consulta: str, segundos_min: float = 0, cuantas: int = 3) -> list[dict]:
    """Pistas de música (no efectos) que se pueden usar con monetización y editar."""
    r = requests.get(API, timeout=25, headers={"User-Agent": "SalaDeEdicion/1.0"},
                     params={"q": consulta[:80], "license_type": "commercial,modification", "category": "music",
                             "page_size": 20, "mature": "false"})
    r.raise_for_status()
    opciones = []
    for x in r.json().get("results", []):
        dur = (x.get("duration") or 0) / 1000
        if not x.get("url") or (segundos_min and 0 < dur < min(segundos_min, 60) * 0.6):
            continue
        opciones.append({"titulo": (x.get("title") or "Sin título")[:80], "autor": (x.get("creator") or "Desconocido")[:60],
                         "licencia": (x.get("license") or "").lower(), "version": x.get("license_version") or "",
                         "url": x["url"], "pagina": x.get("foreign_landing_url") or "", "segundos": round(dur),
                         "fuente": x.get("source") or x.get("provider") or "", "id": x.get("id", "")})
        if len(opciones) >= cuantas:
            break
    for i, o in enumerate(opciones, 1):
        o["n"], o["credito"] = i, credito(o)
    return opciones


def descargar(o: dict, carpeta: Path) -> str:
    """Baja la pista a `carpeta` y regresa el nombre del archivo."""
    carpeta.mkdir(parents=True, exist_ok=True)
    ext = Path(o["url"].split("?")[0]).suffix.lower()
    ext = ext if ext in (".mp3", ".ogg", ".wav", ".m4a", ".flac") else ".mp3"
    nombre = f"{_seguro(o['titulo'])}_{_seguro(o['autor'])[:20]}_{str(o.get('id', ''))[:6]}{ext}"
    destino = carpeta / nombre
    if not destino.exists():
        with requests.get(o["url"], stream=True, timeout=(15, 120), headers={"User-Agent": "SalaDeEdicion/1.0"}) as r:
            r.raise_for_status()
            total = 0
            with open(destino, "wb") as f:
                for trozo in r.iter_content(256 * 1024):
                    total += len(trozo)
                    if total > 40 * 1024 * 1024:
                        raise RuntimeError("La pista pesa demasiado.")
                    f.write(trozo)
    return nombre
