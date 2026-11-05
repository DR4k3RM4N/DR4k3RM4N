"""Búsqueda en internet barata: Serper (resultados de Google) y/o Tavily (texto de las páginas).

Solo traen resultados; quien los lee y resume es Claude Haiku (fracciones de centavo).
Claves en .env: SERPER_API_KEY y/o TAVILY_API_KEY. Con las dos, se combinan.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import requests

from . import config

SERPER = config.env("SERPER_API_KEY")
TAVILY = config.env("TAVILY_API_KEY")
# Costo aproximado por búsqueda para el contador (Tavily trae 1,000 gratis al mes; Serper ~$0.001 después de las gratis).
PRECIO = {"serper": float(config.env("PRECIO_SERPER", "0.001") or 0), "tavily": float(config.env("PRECIO_TAVILY", "0") or 0)}


def disponible() -> bool:
    return bool(SERPER or TAVILY)


def proveedores() -> list[str]:
    return [n for n, k in (("serper", SERPER), ("tavily", TAVILY)) if k]


def _serper(consulta: str, n: int) -> list[dict]:
    r = requests.post("https://google.serper.dev/search", timeout=30,
                      headers={"X-API-KEY": SERPER, "Content-Type": "application/json"},
                      json={"q": consulta, "gl": config.CANAL_PAIS, "hl": config.CANAL_IDIOMA, "num": n})
    r.raise_for_status()
    datos = r.json()
    salida = [{"titulo": x.get("title", ""), "url": x.get("link", ""), "texto": x.get("snippet", ""),
               "fecha": x.get("date", ""), "de": "google"} for x in datos.get("organic", [])[:n]]
    for p in datos.get("peopleAlsoAsk", [])[:3]:  # "La gente también pregunta" suele traer justo la duda
        if p.get("link"):
            salida.append({"titulo": p.get("question", ""), "url": p["link"], "texto": p.get("snippet", ""), "de": "google"})
    return salida


def _tavily(consulta: str, n: int) -> list[dict]:
    r = requests.post("https://api.tavily.com/search", timeout=40,
                      headers={"Authorization": f"Bearer {TAVILY}", "Content-Type": "application/json"},
                      json={"query": consulta, "max_results": n, "search_depth": "basic", "include_answer": False})
    r.raise_for_status()
    return [{"titulo": x.get("title", ""), "url": x.get("url", ""), "texto": x.get("content", ""),
             "fecha": x.get("published_date", ""), "de": "tavily"} for x in r.json().get("results", [])[:n]]


def buscar(consultas: list[str], por_consulta: int = 6, max_texto: int = 700) -> tuple[list[dict], dict]:
    """Corre todas las consultas en paralelo con los proveedores que haya. Devuelve (resultados sin
    repetir, cuántas búsquedas hizo cada proveedor). Un proveedor que falla no detiene a los demás."""
    trabajos = [(p, c) for c in consultas for p in proveedores()]
    conteo = {p: 0 for p in proveedores()}
    errores = []

    def correr(trabajo):
        prov, consulta = trabajo
        try:
            res = (_serper if prov == "serper" else _tavily)(consulta, por_consulta)
            conteo[prov] += 1
            for x in res:
                x["consulta"] = consulta
            return res
        except (requests.RequestException, ValueError) as exc:
            errores.append(f"{prov}: {exc}")
            return []

    with ThreadPoolExecutor(max_workers=6) as pool:
        listas = list(pool.map(correr, trabajos))
    vistos, salida = set(), []
    for lista in listas:
        for x in lista:
            url = (x.get("url") or "").split("#")[0].rstrip("/")
            if not url or url in vistos:
                continue
            vistos.add(url)
            x["texto"] = (x.get("texto") or "")[:max_texto]
            salida.append(x)
    if errores and not salida:
        raise RuntimeError("La búsqueda en internet falló: " + "; ".join(errores[:3]))
    for e in errores[:3]:
        print(f"    aviso búsqueda: {e}", flush=True)
    return salida, conteo


def seo(consulta: str) -> dict:
    """Para el blog: qué pregunta la gente, búsquedas relacionadas y quién sale arriba en Google."""
    salida = {"preguntas": [], "relacionadas": [], "competencia": [], "busquedas": 0}
    if SERPER:
        try:
            r = requests.post("https://google.serper.dev/search", timeout=30,
                              headers={"X-API-KEY": SERPER, "Content-Type": "application/json"},
                              json={"q": consulta, "gl": config.CANAL_PAIS, "hl": config.CANAL_IDIOMA, "num": 10})
            r.raise_for_status()
            d = r.json()
            salida["busquedas"] += 1
            salida["preguntas"] = [p.get("question", "") for p in d.get("peopleAlsoAsk", []) if p.get("question")][:8]
            salida["relacionadas"] = [x.get("query", "") for x in d.get("relatedSearches", []) if x.get("query")][:10]
            salida["competencia"] = [{"titulo": x.get("title", ""), "url": x.get("link", "")} for x in d.get("organic", [])[:6]]
        except (requests.RequestException, ValueError) as exc:
            print(f"    aviso SEO: {exc}", flush=True)
    elif TAVILY:
        try:
            res = _tavily(consulta, 6)
            salida["busquedas"] += 1
            salida["competencia"] = [{"titulo": x["titulo"], "url": x["url"]} for x in res]
        except (requests.RequestException, ValueError) as exc:
            print(f"    aviso SEO: {exc}", flush=True)
    return salida


def costo(conteo: dict) -> float:
    return sum(PRECIO.get(p, 0) * n for p, n in conteo.items())
