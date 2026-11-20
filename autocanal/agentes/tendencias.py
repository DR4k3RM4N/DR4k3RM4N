"""📈 Cazador de tendencias: videos de tu nicho que están pegando más de lo normal (como VidIQ, pero gratis).

Usa la API de YouTube con la conexión de tu canal que ya existe (sin claves nuevas ni costo: la cuota gratis es
de 10,000 unidades al día y cada búsqueda gasta ~100). Busca videos recientes del nicho y calcula su
"multiplicador": vistas ÷ suscriptores del canal. Un canal chico con muchas más vistas que suscriptores = la idea
está pegando por sí sola. Paola copia la IDEA, nunca el video.
"""
from __future__ import annotations

import datetime as dt
import re

from . import config

CONSULTAS_NICHO = ["app para ganar dinero", "app que paga de verdad", "esta app paga o es estafa",
                   "ganar dinero con el celular", "app de encuestas que pagan"]


def disponible() -> bool:
    return (config.BASE / "youtube_token.json").exists()


def _segundos(iso: str) -> int:
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def buscar(consultas: list[str] | None = None, dias: int = 30, cuantos: int = 10, incluir_shorts: bool = False) -> list[dict]:
    """Los videos que más están pegando (ordenados por multiplicador). Lista vacía si no hay conexión."""
    if not disponible():
        return []
    from . import youtube

    consultas = consultas or [q.strip() for q in config.env("NICHO_CONSULTAS", "").split(",") if q.strip()] or CONSULTAS_NICHO
    desde = (dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) - dt.timedelta(days=dias)).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        yt = youtube._servicio(abrir_navegador=False)
        ids = []
        for q in consultas[:5]:
            r = yt.search().list(part="id", q=q, type="video", order="viewCount", publishedAfter=desde,
                                 regionCode=config.CANAL_PAIS.upper(), relevanceLanguage=config.CANAL_IDIOMA,
                                 maxResults=25).execute()
            ids += [x["id"]["videoId"] for x in r.get("items", []) if x.get("id", {}).get("videoId")]
        ids = list(dict.fromkeys(ids))[:100]
        videos = []
        for k in range(0, len(ids), 50):
            r = yt.videos().list(part="snippet,statistics,contentDetails", id=",".join(ids[k:k + 50])).execute()
            videos += r.get("items", [])
        canales = {}
        cids = list(dict.fromkeys(v["snippet"]["channelId"] for v in videos))
        for k in range(0, len(cids), 50):
            r = yt.channels().list(part="statistics", id=",".join(cids[k:k + 50])).execute()
            for c in r.get("items", []):
                canales[c["id"]] = int(c.get("statistics", {}).get("subscriberCount") or 0)
    except Exception as exc:  # noqa: BLE001 — sin tendencias, las ideas salen igual
        print(f"  · no pude revisar tendencias de YouTube: {exc}", flush=True)
        return []
    ahora = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    salida = []
    for v in videos:
        dur = _segundos(v.get("contentDetails", {}).get("duration", ""))
        if not incluir_shorts and dur <= 75:
            continue
        vistas = int(v.get("statistics", {}).get("viewCount") or 0)
        subs = canales.get(v["snippet"]["channelId"], 0)
        try:
            publicado = dt.datetime.strptime(v["snippet"]["publishedAt"][:19], "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            continue
        dias_vivo = max((ahora - publicado).total_seconds() / 86400, 0.5)
        salida.append({
            "titulo": v["snippet"]["title"], "canal": v["snippet"]["channelTitle"], "suscriptores": subs,
            "vistas": vistas, "dias": round(dias_vivo, 1), "vistas_por_dia": int(vistas / dias_vivo),
            "multiplicador": round(vistas / max(subs, 1000), 1), "minutos": round(dur / 60, 1),
            "url": f"https://www.youtube.com/watch?v={v['id']}",
        })
    # lo que más pega: mucho más de lo que el canal suele tener, y que siga sumando vistas
    salida.sort(key=lambda x: (x["multiplicador"] >= 3, x["multiplicador"] * min(x["vistas_por_dia"], 50000)), reverse=True)
    return salida[:cuantos]


def para_paola(lista: list[dict]) -> str:
    if not lista:
        return ""
    return ("VIDEOS QUE ESTÁN PEGANDO EN EL NICHO (últimos 30 días; 'x' = vistas ÷ suscriptores del canal). Úsalos "
            "para saber qué quiere ver la gente: copia la IDEA o el ángulo, nunca el video; si mencionan una app o un "
            "tema de tu lista, súbele prioridad:\n"
            + "\n".join(f"- «{v['titulo']}» — {v['canal']} ({v['suscriptores']:,} subs): {v['vistas']:,} vistas en "
                        f"{v['dias']:.0f} días, x{v['multiplicador']}" for v in lista))
