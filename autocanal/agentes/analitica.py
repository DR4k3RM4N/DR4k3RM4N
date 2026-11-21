"""📊 Resultados: la oficina ve cómo le fue a cada video que publicó y aprende de eso.

Cada 6 horas, por canal (si su permiso incluye estadísticas; ver `canal.py autorizar-youtube --de-nuevo`):
1. Junta los videos que publicó la oficina (salida/*/publicado.json) y pregunta a YouTube Analytics: vistas,
   minutos vistos, duración media, % visto, suscriptores ganados, likes, comentarios, impresiones y CTR
   (cuánta gente le da clic al verlo), y la curva de retención (en qué momento se va la gente).
2. Ubica dónde se va la gente en el GUION (qué escena se estaba diciendo).
3. Con 3 o más videos con datos, Claude compara los que pegaron contra los que no y deja reglas para cada agente
   (Paola: temas · Gabi: gancho y retención · Dani: títulos y miniaturas · Edu: ritmo). Esas reglas se pegan en
   sus instrucciones (vía lecciones.para), así cada video sale mejor que el anterior.
4. 🛟 Rescate de empaque: si un video lleva 2-14 días con un CTR muy por debajo de lo normal del canal, le cambia
   el título (y la miniatura, si el canal puede) por el siguiente paquete que armó el empaque. Una sola vez.

Costo: YouTube Analytics es gratis; 1 llamada a Claude al día por canal (tu plan).
"""
from __future__ import annotations

import datetime as dt
import json
import random
import re
import statistics
import threading
import time
from pathlib import Path

from . import config

ARCHIVO = config.ESTILO_DIR / "analitica.json"
DEMO = False  # lo prende simulado.activar(): datos de ejemplo para probar la pestaña
_candado = threading.Lock()
METRICAS = "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained,likes,comments,shares"
METRICAS_ALCANCE = "videoThumbnailImpressions,videoThumbnailImpressionsClickRate"

SCHEMA_APRENDER = {
    "type": "object",
    "properties": {
        "resumen": {"type": "string", "description": "2-3 frases: qué está funcionando y qué no, con números"},
        "productora": {"type": "array", "items": {"type": "string"}, "description": "2-5 reglas sobre TEMAS e ideas"},
        "guionista": {"type": "array", "items": {"type": "string"},
                      "description": "2-5 reglas sobre gancho, estructura y retención (dónde se va la gente y por qué)"},
        "disenadora": {"type": "array", "items": {"type": "string"},
                       "description": "2-5 reglas sobre títulos y miniaturas (CTR)"},
        "editor": {"type": "array", "items": {"type": "string"}, "description": "0-3 reglas sobre ritmo y duración"},
    },
    "required": ["resumen", "productora", "guionista", "disenadora", "editor"],
    "additionalProperties": False,
}


# ---------- guardar / leer ----------
def _leer() -> dict:
    try:
        return json.loads(ARCHIVO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _guardar(datos: dict) -> None:
    ARCHIVO.parent.mkdir(parents=True, exist_ok=True)
    ARCHIVO.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")


def _json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def video_id(url: str) -> str:
    m = re.search(r"(?:youtu\.be/|v=|/shorts/)([\w-]{6,})", url or "")
    return m.group(1) if m else ""


def publicados(canal: str | None = None) -> list[dict]:
    """Los videos que subió la oficina: [{id, app_id, canal, carpeta}]."""
    from . import canales
    salida = []
    for pub_f in config.SALIDA.glob("*/publicado.json"):
        pub = _json(pub_f)
        vid = video_id(pub.get("youtube") or "")
        if not vid or (pub.get("demo") and not DEMO):
            continue
        c = pub.get("canal") or canales.PRINCIPAL
        if canal and c != canal:
            continue
        salida.append({"id": vid, "app_id": pub_f.parent.name, "canal": c, "carpeta": pub_f.parent})
    return salida


# ---------- 1) traer números ----------
def _por_video(ana, ids: list[str], desde: str, hasta: str, metricas: str) -> dict:
    r = ana.reports().query(ids="channel==MINE", startDate=desde, endDate=hasta, metrics=metricas,
                            dimensions="video", filters="video==" + ",".join(ids), maxResults=200,
                            sort="-" + metricas.split(",")[0]).execute()
    cols = [c["name"] for c in r.get("columnHeaders", [])]
    return {fila[0]: dict(zip(cols[1:], fila[1:])) for fila in r.get("rows") or []}


def _retencion(ana, vid: str, desde: str, hasta: str) -> list[list[float]]:
    r = ana.reports().query(ids="channel==MINE", startDate=desde, endDate=hasta,
                            metrics="audienceWatchRatio,relativeRetentionPerformance",
                            dimensions="elapsedVideoTimeRatio", filters=f"video=={vid}").execute()
    return [[float(f[0]), float(f[1]), float(f[2])] for f in r.get("rows") or []]


def _escena_en(carpeta: Path, fraccion: float) -> tuple[int, str]:
    """Qué escena del guion se estaba diciendo en esa fracción del video (por palabras narradas)."""
    escenas = (_json(carpeta / "guion.json").get("escenas") or [])
    palabras = [len((e.get("narracion") or "").split()) for e in escenas]
    total = sum(palabras) or 1
    acumulado = 0
    for i, n in enumerate(palabras):
        acumulado += n
        if acumulado / total >= fraccion:
            return i + 1, (escenas[i].get("narracion") or "")[:140]
    return len(escenas), ""


def _caidas(curva: list[list[float]], duracion: int, carpeta: Path) -> dict:
    """Retención a los 30 s y las 3 caídas más fuertes (sin contar el arranque), con su escena."""
    if len(curva) < 10 or not duracion:
        return {}
    pts = sorted(curva)
    base = pts[0][1] or 1
    rel = [(x, y / base) for x, y, _ in pts]
    t30 = min(30 / duracion, 1.0)
    a30 = next((y for x, y in rel if x >= t30), rel[-1][1])
    ventanas = []
    for i in range(2, len(rel) - 3):
        x0, y0 = rel[i]
        x1, y1 = rel[i + 3]
        ventanas.append((y0 - y1, x0))
    ventanas.sort(reverse=True)
    elegidas = []
    for caida, x in ventanas:
        if caida < 0.03 or any(abs(x - e["fraccion"]) < 0.08 for e in elegidas):
            continue
        n, texto = _escena_en(carpeta, x)
        seg = int(x * duracion)
        elegidas.append({"fraccion": round(x, 3), "segundo": seg, "minuto": f"{seg // 60}:{seg % 60:02d}",
                         "se_fue": round(caida * 100), "escena": n, "texto": texto})
        if len(elegidas) == 3:
            break
    rendimiento = statistics.mean(r for _, _, r in pts) if pts else 0
    return {"a_los_30s": round(a30 * 100), "caidas": elegidas, "final": round(rel[-1][1] * 100),
            "vs_similares": round(rendimiento, 2)}


def actualizar(canal: str) -> dict:
    """Trae los números de los videos de un canal y los guarda. Regresa {"videos": n, "error": ...}."""
    from . import tendencias, youtube

    lista = publicados(canal)
    if not lista:
        return {"videos": 0}
    if DEMO:
        return _demo(canal, lista)
    if not youtube.tiene_analitica(canal):
        return {"videos": 0, "error": "falta_permiso"}
    yt, ana = youtube._servicio(abrir_navegador=False, canal=canal), youtube.analitica(canal)
    info = {}
    ids = [v["id"] for v in lista]
    for k in range(0, len(ids), 50):
        r = yt.videos().list(part="snippet,statistics,contentDetails,status", id=",".join(ids[k:k + 50])).execute()
        for it in r.get("items", []):
            info[it["id"]] = it
    hoy = dt.date.today().isoformat()
    publicos = [v for v in lista if v["id"] in info and info[v["id"]]["status"].get("privacyStatus") == "public"]
    if not publicos:
        return {"videos": 0}
    desde = min(info[v["id"]]["snippet"]["publishedAt"][:10] for v in publicos)
    basicos = {}
    for k in range(0, len(publicos), 100):
        basicos.update(_por_video(ana, [v["id"] for v in publicos[k:k + 100]], desde, hoy, METRICAS))
    alcance, sin_ctr = {}, False
    try:
        for k in range(0, len(publicos), 100):
            alcance.update(_por_video(ana, [v["id"] for v in publicos[k:k + 100]], desde, hoy, METRICAS_ALCANCE))
    except Exception as exc:  # noqa: BLE001 — si YouTube no da el CTR por la API, seguimos sin él
        sin_ctr = True
        print(f"  · aviso: YouTube no me dio el CTR ({str(exc)[:120]})", flush=True)
    with _candado:
        datos = _leer()
        videos = datos.setdefault("videos", {})
        for v in publicos:
            it = info[v["id"]]
            pub_dia = it["snippet"]["publishedAt"][:10]
            dias = max((dt.date.today() - dt.date.fromisoformat(pub_dia)).days, 0)
            dur = tendencias._segundos(it.get("contentDetails", {}).get("duration", ""))
            guion = _json(v["carpeta"] / "guion.json")
            b, a = basicos.get(v["id"], {}), alcance.get(v["id"], {})
            previo = videos.get(v["id"], {})
            fila = {**previo, "id": v["id"], "canal": canal, "app_id": v["app_id"], "titulo": it["snippet"]["title"],
                    "publicado": pub_dia, "dias": dias, "duracion": dur,
                    "vistas": int(b.get("views") or it.get("statistics", {}).get("viewCount") or 0),
                    "minutos_vistos": round(float(b.get("estimatedMinutesWatched") or 0)),
                    "duracion_media": round(float(b.get("averageViewDuration") or 0)),
                    "pct_visto": round(float(b.get("averageViewPercentage") or 0), 1),
                    "subs": int(b.get("subscribersGained") or 0), "likes": int(b.get("likes") or 0),
                    "comentarios": int(b.get("comments") or 0),
                    "impresiones": int(a["videoThumbnailImpressions"]) if a.get("videoThumbnailImpressions") is not None else previo.get("impresiones"),
                    "ctr": round(float(a["videoThumbnailImpressionsClickRate"]), 2) if a.get("videoThumbnailImpressionsClickRate") is not None else previo.get("ctr"),
                    "texto_miniatura": guion.get("texto_miniatura", ""),
                    "gancho": ((guion.get("escenas") or [{}])[0].get("narracion") or "")[:160],
                    "formato": _json(v["carpeta"] / "expediente.json").get("formato") or ("tema" if v["app_id"].startswith("tema:") else "app"),
                    "t": time.time()}
            fila["vistas_dia"] = round(fila["vistas"] / max(dias, 1))
            # la curva de retención se pide una vez al día (YouTube la tiene lista a los 2-3 días)
            if dias >= 2 and time.time() - previo.get("t_retencion", 0) > 20 * 3600:
                try:
                    fila["retencion"] = _caidas(_retencion(ana, v["id"], pub_dia, hoy), dur, v["carpeta"])
                    fila["t_retencion"] = time.time()
                except Exception as exc:  # noqa: BLE001
                    print(f"  · aviso retención {v['id']}: {str(exc)[:100]}", flush=True)
            videos[v["id"]] = fila
        datos.setdefault("actualizado", {})[canal] = time.time()
        datos.setdefault("sin_ctr", {})[canal] = sin_ctr
        _guardar(datos)
    return {"videos": len(publicos)}


# ---------- 2) aprender ----------
def _tabla(videos: list[dict]) -> str:
    lineas = []
    for v in sorted(videos, key=lambda x: -x["vistas_dia"]):
        r = v.get("retencion") or {}
        caidas = "; ".join(f"en {c['minuto']} se fue {c['se_fue']}% (escena {c['escena']}: «{c['texto'][:90]}»)"
                           for c in r.get("caidas", []))
        lineas.append(
            f"- «{v['titulo']}» [{v['formato']}] miniatura: «{v.get('texto_miniatura', '')}» · {v['dias']} días · "
            f"{v['vistas']:,} vistas ({v['vistas_dia']:,}/día) · CTR {v['ctr'] if v.get('ctr') is not None else '?'}% "
            f"de {v.get('impresiones') or '?'} impresiones · vio {v['pct_visto']}% ({v['duracion_media']} s de "
            f"{v['duracion']} s) · +{v['subs']} subs · {v['comentarios']} comentarios"
            + (f"\n    retención: a los 30 s quedaba {r['a_los_30s']}%, al final {r['final']}%; {caidas}" if r else "")
            + f"\n    gancho: «{v['gancho']}»")
    return "\n".join(lineas)


def aprender(canal: str, forzar: bool = False) -> dict | None:
    """Claude compara los videos que pegaron contra los que no y deja reglas para cada agente."""
    from . import canales, claude

    with _candado:
        datos = _leer()
    videos = [v for v in (datos.get("videos") or {}).values() if v["canal"] == canal and v["dias"] >= 2]
    previo = (datos.get("aprendizajes") or {}).get(canal) or {}
    if len(videos) < 3 or (not forzar and time.time() - previo.get("t", 0) < 20 * 3600):
        return None
    if DEMO:
        nuevo = {"resumen": "(Demo) Los videos con cifra concreta en el título y gancho de historia jalan el doble.",
                 "productora": ["(Demo) Las alertas de apps con miles de descargas pegan más que los temas generales."],
                 "guionista": ["(Demo) La gente se va en la escena de 'qué es la app': entra directo a la prueba."],
                 "disenadora": ["(Demo) Las miniaturas con la cara de Lanudo asustado tienen mejor CTR."],
                 "editor": []}
    else:
        info = canales.get(canal)
        claude.contexto.canal = canal
        nuevo = claude.json_estructurado(
            f"Eres analista de YouTube del canal «{info.get('nombre')}». Lees los números reales de sus videos y "
            "sacas reglas concretas para el equipo. Solo conclusiones que los datos sostienen (compara los que "
            "pegaron contra los que no; con pocos videos, dilo con cautela). Cada regla cita números.",
            f"VIDEOS DEL CANAL (de más a menos vistas por día):\n{_tabla(videos)}\n\n"
            "CTR normal en YouTube: 2-10%. Retención: lo que importa es no perder a la gente en los primeros 30 s y "
            "que no haya caídas fuertes en medio. Escribe reglas accionables para cada agente.",
            SCHEMA_APRENDER, tarea="ideas", que="aprender de los resultados")
    nuevo["t"], nuevo["videos"] = time.time(), len(videos)
    with _candado:
        datos = _leer()
        datos.setdefault("aprendizajes", {})[canal] = nuevo
        _guardar(datos)
    return nuevo


def para(*agentes: str, canal: str | None = None) -> str:
    """Bloque para las instrucciones de los agentes: lo que dicen los números de este canal."""
    from . import canales
    canal = canal or canales.actual()
    a = (_leer().get("aprendizajes") or {}).get(canal)
    if not a:
        return ""
    reglas = [r for ag in agentes for r in a.get(ag) or []]
    if not reglas:
        return ""
    return (f"\n\nLO QUE DICEN LOS NÚMEROS DE TUS VIDEOS ({a['videos']} videos analizados; síguelo):\n"
            + "\n".join(f"- {r}" for r in dict.fromkeys(reglas)))


def titulos_que_jalan(canal: str, n: int = 5) -> tuple[list[str], list[str]]:
    """(los títulos con mejor CTR/vistas por día, los peores) del canal, para el empaque."""
    vids = [v for v in (_leer().get("videos") or {}).values() if v["canal"] == canal and v["dias"] >= 2]
    if len(vids) < 3:
        return [], []
    clave = (lambda v: v["ctr"]) if all(v.get("ctr") is not None for v in vids) else (lambda v: v["vistas_dia"])
    vids.sort(key=clave, reverse=True)
    fmt = lambda v: f"«{v['titulo']}» (miniatura «{v.get('texto_miniatura', '')}», CTR {v.get('ctr', '?')}%, {v['vistas_dia']}/día)"
    return [fmt(v) for v in vids[:n]], [fmt(v) for v in vids[-n:][::-1]]


# ---------- 3) rescate de empaque ----------
def rescatar(canal: str, avisar=None) -> list[str]:
    """Cambia título (y miniatura) de los videos con CTR muy bajo por su siguiente paquete. Una vez por video."""
    from . import canales, estilo, youtube

    if not estilo.cargar()["ajustes"].get("rescate_empaque", True) or DEMO:
        return []
    with _candado:
        datos = _leer()
    vids = [v for v in (datos.get("videos") or {}).values() if v["canal"] == canal and v.get("ctr") is not None]
    if not vids:
        return []
    otros = [v["ctr"] for v in vids if v["dias"] >= 3 and (v.get("impresiones") or 0) >= 300]
    referencia = statistics.median(otros) * 0.7 if len(otros) >= 3 else 2.5
    hechos = []
    for v in vids:
        if not (2 <= v["dias"] <= 14 and (v.get("impresiones") or 0) >= 300 and v["ctr"] < referencia):
            continue
        if v.get("rescatado"):
            continue
        carpeta = config.SALIDA / v["app_id"]
        guion = _json(carpeta / "guion.json")
        paquetes = guion.get("paquetes") or []
        siguiente = next((p for p in paquetes[1:] if p.get("titulo") and p["titulo"] != v["titulo"]), None)
        if not siguiente:
            continue
        try:
            yt = youtube._servicio(abrir_navegador=False, canal=canal)
            it = yt.videos().list(part="snippet", id=v["id"]).execute()["items"][0]
            sn = it["snippet"]
            cuerpo = {"title": siguiente["titulo"][:100], "description": sn.get("description", ""),
                      "categoryId": sn.get("categoryId", "22"), "tags": sn.get("tags", []),
                      "defaultLanguage": sn.get("defaultLanguage") or config.CANAL_IDIOMA}
            yt.videos().update(part="snippet", body={"id": v["id"], "snippet": cuerpo}).execute()
            mini = carpeta / (siguiente.get("archivo") or "")
            con_mini = False
            if siguiente.get("archivo") and mini.exists():
                try:
                    youtube.poner_miniatura(f"https://youtu.be/{v['id']}", mini, canal=canal)
                    con_mini = True
                except Exception:  # noqa: BLE001 — el canal principal no puede poner miniaturas
                    pass
        except Exception as exc:  # noqa: BLE001
            print(f"  · aviso rescate {v['id']}: {str(exc)[:120]}", flush=True)
            continue
        with _candado:
            datos = _leer()
            datos["videos"][v["id"]].update(rescatado={"t": time.time(), "antes": v["titulo"],
                                                       "ctr_antes": v["ctr"], "ahora": siguiente["titulo"],
                                                       "miniatura": con_mini})
            _guardar(datos)
        msg = (f"🛟 «{v['titulo']}» tenía CTR {v['ctr']}% (lo normal del canal ~{round(referencia / 0.7, 1)}%). "
               f"Le cambié el título a «{siguiente['titulo']}»" + (" y la miniatura." if con_mini else "."))
        hechos.append(msg)
        if avisar:
            avisar(msg)
    return hechos


# ---------- 4) para la oficina ----------
def ciclo(canal: str, avisar=None) -> dict:
    r = actualizar(canal)
    if r.get("videos"):
        try:
            nuevo = aprender(canal)
            if nuevo and avisar:
                avisar(f"📊 Aprendí de {nuevo['videos']} videos: {nuevo['resumen']}")
        except Exception as exc:  # noqa: BLE001
            print(f"  · aviso aprender: {exc}", flush=True)
        rescatar(canal, avisar)
    return r


def resumen() -> dict:
    """Para la pestaña 📊 Resultados: por canal, los videos, lo aprendido y si falta el permiso."""
    from . import canales, youtube
    datos = _leer()
    salida = {}
    for c in canales.lista():
        cid = c["id"]
        vids = sorted((v for v in (datos.get("videos") or {}).values() if v["canal"] == cid),
                      key=lambda v: v["publicado"], reverse=True)
        salida[cid] = {"nombre": c.get("nombre"), "conectado": canales.conectado(cid),
                       "permiso": DEMO or youtube.tiene_analitica(cid), "videos": vids[:60],
                       "aprendizajes": (datos.get("aprendizajes") or {}).get(cid),
                       "actualizado": (datos.get("actualizado") or {}).get(cid),
                       "sin_ctr": (datos.get("sin_ctr") or {}).get(cid, False),
                       "publicados": len(publicados(cid))}
    return salida


def _demo(canal: str, lista: list[dict]) -> dict:
    """Números de ejemplo (solo modo demo) para ver la pestaña funcionando."""
    with _candado:
        datos = _leer()
        videos = datos.setdefault("videos", {})
        for i, v in enumerate(lista):
            rnd = random.Random(v["id"])
            guion = _json(v["carpeta"] / "guion.json")
            dias = 2 + i * 3
            vistas = rnd.randint(300, 40000)
            dur = rnd.randint(300, 540)
            curva = [[k / 100, max(0.15, 1 - 0.004 * k - (0.12 if k > 8 else 0) - (0.1 if k > 45 else 0)), 0.5]
                     for k in range(1, 101)]
            videos[v["id"]] = {"id": v["id"], "canal": canal, "app_id": v["app_id"],
                               "titulo": (guion.get("titulos") or [v["app_id"]])[0], "publicado": (
                    dt.date.today() - dt.timedelta(days=dias)).isoformat(), "dias": dias, "duracion": dur,
                               "vistas": vistas, "vistas_dia": round(vistas / dias), "minutos_vistos": vistas * 2,
                               "duracion_media": int(dur * 0.38), "pct_visto": round(rnd.uniform(25, 55), 1),
                               "subs": rnd.randint(0, 120), "likes": rnd.randint(5, 900),
                               "comentarios": rnd.randint(0, 200), "impresiones": vistas * rnd.randint(8, 25),
                               "ctr": round(rnd.uniform(1.5, 9), 1), "texto_miniatura": guion.get("texto_miniatura", ""),
                               "gancho": ((guion.get("escenas") or [{}])[0].get("narracion") or "")[:160],
                               "formato": "app", "retencion": _caidas(curva, dur, v["carpeta"]), "t": time.time()}
        datos.setdefault("actualizado", {})[canal] = time.time()
        _guardar(datos)
    return {"videos": len(lista)}
