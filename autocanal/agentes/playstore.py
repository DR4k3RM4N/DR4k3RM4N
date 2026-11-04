"""Datos de Google Play: ficha, capturas, icono y reseñas."""
from __future__ import annotations

import json
from pathlib import Path

import requests

from . import config


def ficha(app_id: str) -> dict:
    from google_play_scraper import app

    d = app(app_id, lang=config.CANAL_IDIOMA, country=config.CANAL_PAIS)
    campos = [
        "appId", "title", "summary", "description", "installs", "realInstalls", "score",
        "ratings", "histogram", "developer", "developerEmail", "developerWebsite",
        "developerAddress", "privacyPolicy", "released", "lastUpdatedOn", "updated",
        "version", "genre", "containsAds", "offersIAP", "icon", "headerImage",
        "screenshots", "url",
    ]
    return {k: d.get(k) for k in campos}


def resenas(app_id: str, cuantas: int = 150) -> list[dict]:
    from google_play_scraper import Sort, reviews

    salida = []
    for orden in (Sort.NEWEST, Sort.MOST_RELEVANT):
        lote, _ = reviews(app_id, lang=config.CANAL_IDIOMA, country=config.CANAL_PAIS,
                          sort=orden, count=cuantas)
        salida.extend(lote)
    vistas, unicas = set(), []
    for r in salida:
        if r["reviewId"] in vistas:
            continue
        vistas.add(r["reviewId"])
        unicas.append({
            "usuario": r.get("userName") or "Usuario",
            "estrellas": r.get("score"),
            "texto": (r.get("content") or "").strip(),
            "likes": r.get("thumbsUpCount", 0),
            "fecha": str(r.get("at", ""))[:10],
            "respuesta_dev": (r.get("replyContent") or "").strip(),
        })
    return unicas


def buscar(consulta: str, n: int = 30) -> list[dict]:
    from google_play_scraper import search

    return search(consulta, lang=config.CANAL_IDIOMA, country=config.CANAL_PAIS, n_hits=n)


def descargar(url: str, destino: Path, ancho: int | None = None) -> Path | None:
    if not url:
        return None
    if ancho and "googleusercontent" in url and "=" not in url.rsplit("/", 1)[-1]:
        url = f"{url}=w{ancho}"
    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
    except requests.RequestException:
        return None
    destino.write_bytes(r.content)
    return destino


def descargar_imagenes(datos: dict, carpeta: Path, max_capturas: int = 8) -> dict:
    """Guarda icono, portada y capturas en carpeta/img. Devuelve rutas locales."""
    img = carpeta / "img"
    img.mkdir(parents=True, exist_ok=True)
    rutas = {
        "icono": descargar(datos.get("icon"), img / "icono.png", 512),
        "portada": descargar(datos.get("headerImage"), img / "portada.png", 1280),
        "capturas": [],
    }
    for i, url in enumerate((datos.get("screenshots") or [])[:max_capturas], 1):
        p = descargar(url, img / f"captura_{i}.png", 1080)
        if p:
            rutas["capturas"].append(p)
    return {k: ([str(x) for x in v] if isinstance(v, list) else (str(v) if v else None))
            for k, v in rutas.items()}


def guardar(carpeta: Path, nombre: str, datos) -> Path:
    carpeta.mkdir(parents=True, exist_ok=True)
    p = carpeta / nombre
    p.write_text(json.dumps(datos, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return p
