"""🕵️ ¿Quién MATÓ a…? — la oficina nueva, hecha desde cero para que SÍ termine videos.

Un caso a la vez, en línea recta. Cada paso deja su archivo; si algo se cae (o se reinicia el servidor), se sigue
desde el último paso terminado, nunca desde cero:

  1. investigacion.json  — Claude (Sonnet, tu plan) lee las fuentes y saca hechos con cita
  2. guion.json          — Claude (Opus, tu plan) escribe el guion con la estructura del canal
  3. voz/escena_XX.mp3   — Azure (en el servidor, gratis hasta 480 mil caracteres al mes), escena por escena
  4. material.json       — fotos de la marca (Google Imágenes + Wikimedia), sin gastar Claude
  5. video.mp4           — tus compus con el kit de animación (estilo noir, con la tarjeta de video); si no hay
                           compu lista en 5 min, el servidor arma una versión sencilla con ffmpeg
  6. miniatura.jpg       — plantilla del canal (foto oscura + letras gigantes), en el servidor
  7. YouTube             — se sube en PRIVADO con su fecha de la agenda (tú lo haces público)

Nada se queda «pensando» para siempre: cada paso tiene tiempo límite, todo lo que pasa se anota en la bitácora del
caso, y si un paso falla se reintenta solo (3 veces) o con el botón «Reintentar paso».
"""
from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path

from . import claude, config
from . import expedientes_fabrica as fb

DEMO = bool(__import__("os").environ.get("AUTOCANAL_DEMO"))
CARPETA = config.BASE / "salida" / ("quienmato_demo" if DEMO else "quienmato")  # la sala puede leer de salida/
ESTADO = CARPETA / "oficina.json"
SALA_URL = config.env("SALA_URL", "http://127.0.0.1:8767").rstrip("/")
PASOS = [("investigacion", "Investigación"), ("guion", "Guion"), ("voz", "Voz"), ("material", "Fotos"),
         ("video", "Video"), ("miniatura", "Miniatura"), ("revision", "Revisión del director"), ("youtube", "YouTube (privado)")]
VOZ, VELOCIDAD = "es-MX-JorgeNeural", "+12%"
AZURE_TOPE = int(config.env("AZURE_LIMITE_MES", "480000") or 480000)
_candado = threading.RLock()
_hilo: dict = {}


# ---------------------------------------------------------------- guardar y leer
def _leer(p: Path, defecto):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defecto


def _escribir(p: Path, datos) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)


def estado() -> dict:
    e = _leer(ESTADO, {})
    e.setdefault("activa", True)
    e.setdefault("casos", [])       # ids en orden (el primero sin terminar es el que va)
    e.setdefault("fechas", [])      # fechas de la agenda ya ocupadas por esta oficina
    e.setdefault("azure", {})
    return e


def _guardar_estado(e: dict) -> None:
    with _candado:
        _escribir(ESTADO, e)


def carpeta(cid: str) -> Path:
    return CARPETA / cid


def caso(cid: str) -> dict:
    return _leer(carpeta(cid) / "caso.json", {})


def _poner(cid: str, **campos) -> dict:
    with _candado:
        c = caso(cid)
        c.update(campos)
        _escribir(carpeta(cid) / "caso.json", c)
        return c


def _bitacora(cid: str, texto: str) -> None:
    with _candado:
        c = caso(cid)
        c["log"] = (c.get("log") or [])[-60:] + [{"t": time.time(), "texto": texto[:300]}]
        c["mov"] = time.time()
        _escribir(carpeta(cid) / "caso.json", c)
    print(f"  · quién mató #{caso(cid).get('numero')}: {texto[:160]}", flush=True)


def _paso(cid: str, clave: str, est: str, **extra) -> None:
    with _candado:
        c = caso(cid)
        p = (c.setdefault("pasos", {})).setdefault(clave, {})
        if est == "trabajando" and p.get("estado") != "trabajando":
            p["inicio"] = time.time()
        if est in ("listo", "error"):
            p["fin"] = time.time()
        p["estado"] = est
        p.update(extra)
        c["paso"], c["mov"] = clave, time.time()
        _escribir(carpeta(cid) / "caso.json", c)


# ---------------------------------------------------------------- casos y temas
def nuevo_caso(tema: dict, numero: str | None = None, desde: Path | None = None) -> str:
    if not numero:  # el siguiente número libre, contando la oficina vieja y esta
        usados = [int(fb._siguiente_numero()) - 1] + [int(x[:3]) for x in estado()["casos"] if x[:3].isdigit()]
        numero = f"{max(usados) + 1:03d}"
    cid = f"{numero}-{re.sub(r'[^a-z0-9]+', '-', tema['marca'].lower()).strip('-')[:30]}"
    d = carpeta(cid)
    d.mkdir(parents=True, exist_ok=True)
    if desde:  # 📦 un caso de la oficina vieja: se aprovecha su investigación y su guion (ya costaron plan)
        for n in ("investigacion.json", "guion.json"):
            if (desde / n).exists():
                shutil.copyfile(desde / n, d / n)
    _escribir(d / "caso.json", {"id": cid, "numero": cid[:3], "marca": tema["marca"], "gancho": tema.get("gancho", ""),
                                "tema_id": tema.get("id"), "creado": time.time(), "pasos": {}, "log": [], "paso": None})
    with _candado:
        e = estado()
        e["casos"].append(cid)
        _guardar_estado(e)
    _bitacora(cid, f"Nuevo caso: ¿Quién MATÓ a {tema['marca']}?" + (" (con la investigación y el guion que ya había)" if desde else ""))
    return cid


def _migrar_viejos() -> None:
    """Una vez: lo que la oficina vieja dejó a medias con guion hecho pasa aquí (y su render viejo se cancela)."""
    e = estado()
    if e.get("migrado") or DEMO:
        return
    e["migrado"] = True
    _guardar_estado(e)
    try:
        from . import expedientes as ex
        import requests
        for x in ex.lista():
            f = ex.trabajo(x["id"]).get("fabrica") or {}
            if not f or f.get("subida") == "listo":
                continue
            if f.get("render_tid"):
                try:
                    requests.post(f"{SALA_URL}/interno/cancelar/{f['render_tid']}", json={}, timeout=5)
                except requests.RequestException:
                    pass
            fab_dir = ex.carpeta(x["id"]) / "fabrica"
            if (fab_dir / "guion.json").exists() and not any(caso(c).get("marca") == f.get("marca") for c in estado()["casos"]):
                nuevo_caso({"marca": f.get("marca") or x.get("marca"), "id": f.get("tema")}, str(f.get("numero") or "")[:3] or None, fab_dir)
        old = fb.estado()
        old["activa"] = False  # la fábrica vieja ya no arranca nada
        fb._guardar_estado(old)
    except Exception as exc:  # noqa: BLE001
        print(f"  · quién mató: no pude migrar lo viejo: {exc}", flush=True)


def _siguiente_tema() -> dict | None:
    with fb._candado:
        lista = fb.temas()
        t = next((x for x in lista if x["estado"] == "pendiente"), None)
        if t:
            t["estado"] = "produciendo"
            fb._guardar_temas(lista)
    return t


def _tema_hecho(c: dict, est: str = "hecho") -> None:
    with fb._candado:
        lista = fb.temas()
        for x in lista:
            if x["id"] == c.get("tema_id"):
                x["estado"] = est
        fb._guardar_temas(lista)


# ---------------------------------------------------------------- los pasos
def _plan() -> bool:
    return DEMO or fb._plan_disponible()


def paso_investigacion(cid: str, c: dict) -> None:
    if (carpeta(cid) / "investigacion.json").exists():
        return
    _bitacora(cid, "Investigando: busco y leo fuentes (Claude, tu plan)")
    inv = fb.investigar({"marca": c["marca"], "gancho": c.get("gancho", ""), "id": c.get("tema_id")})
    _escribir(carpeta(cid) / "investigacion.json", inv)
    _bitacora(cid, f"Investigación lista: {len(inv.get('hechos') or [])} hechos con cita")


def paso_guion(cid: str, c: dict) -> None:
    if (carpeta(cid) / "guion.json").exists():
        return
    inv = _leer(carpeta(cid) / "investigacion.json", {})
    siguiente = next((x["marca"] for x in fb.temas() if x["estado"] == "pendiente"), "otra marca")
    _bitacora(cid, "Escribiendo el guion (Claude Opus, tu plan)")
    from . import director
    instrucciones = director.guia("expedientes")  # 🎯 lo que el director aprendió de los videos anteriores
    if instrucciones:
        _bitacora(cid, "El director le pasó sus instrucciones a la guionista")
    g = fb.escribir_guion({"marca": c["marca"], "gancho": c.get("gancho", "")}, inv, c["numero"], siguiente, instrucciones)
    if len(g.get("escenas") or []) < 3:
        raise RuntimeError("El guion salió demasiado corto.")
    try:
        fb._arreglar_dudosas(g, inv, fb._revisar_cifras(g, inv))
    except Exception as exc:  # noqa: BLE001
        _bitacora(cid, f"No pude revisar las cifras ({exc}); sigo")
    _escribir(carpeta(cid) / "guion.json", g)
    _bitacora(cid, f"Guion listo: {len(g['escenas'])} escenas")


def _texto_escena(esc: dict) -> str:
    return " ".join(f["texto"].strip() for f in esc.get("frases") or [] if f.get("texto"))


def _duracion(p: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True, timeout=60)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def _tiempos(texto: str, dur: float) -> list[dict]:
    """Tiempo aproximado de cada palabra (por su largo) para los subtítulos y para que las capas caigan a tiempo."""
    palabras = texto.split()
    pesos = [len(w) + 2 for w in palabras]
    total, t, util = sum(pesos) or 1, 0.15, max(0.5, dur - 0.3)
    out = []
    for w, p in zip(palabras, pesos):
        d = util * p / total
        out.append({"w": w, "t": round(t, 3), "d": round(d * 0.92, 3)})
        t += d
    return out


def _azure_tts(texto: str, salida: Path) -> None:
    import urllib.error
    import urllib.request
    from xml.sax.saxutils import escape
    az = fb._azure()
    if not az:
        raise RuntimeError("Falta la clave de Azure en el servidor (AZURE_SPEECH_KEY en el .env).")
    ssml = (f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="es-MX"><voice name="{VOZ}">'
            f'<prosody rate="{VELOCIDAD}">{escape(texto)}</prosody></voice></speak>')
    url = f"https://{az['region']}.tts.speech.microsoft.com/cognitiveservices/v1"
    cab = {"Ocp-Apim-Subscription-Key": az["clave"], "Content-Type": "application/ssml+xml",
           "X-Microsoft-OutputFormat": "audio-24khz-96kbitrate-mono-mp3", "User-Agent": "QuienMato"}
    for intento in range(6):
        try:
            req = urllib.request.Request(url, data=ssml.encode("utf-8"), method="POST", headers=cab)
            with urllib.request.urlopen(req, timeout=120) as r:
                salida.write_bytes(r.read())
            time.sleep(3.2)  # el plan gratis aguanta ~20 por minuto
            return
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 503) and intento < 5:
                time.sleep(10 * (intento + 1))
                continue
            raise RuntimeError(f"Azure contestó {exc.code}") from exc
        except urllib.error.URLError as exc:
            if intento < 5:
                time.sleep(10)
                continue
            raise RuntimeError(f"No pude conectar con Azure ({exc})") from exc


def paso_voz(cid: str, c: dict) -> None:
    g = _leer(carpeta(cid) / "guion.json", {})
    vdir = carpeta(cid) / "voz"
    vdir.mkdir(exist_ok=True)
    escenas = g.get("escenas") or []
    for i, esc in enumerate(escenas, 1):
        mp3, tiempos = vdir / f"escena_{i:02d}.mp3", vdir / f"escena_{i:02d}.palabras.json"
        if mp3.exists() and tiempos.exists():
            continue  # ♻️ ya estaba
        texto = _texto_escena(esc)
        if DEMO:
            dur = max(2.0, len(texto.split()) / 2.7)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
                            "-t", f"{dur:.2f}", "-q:a", "9", str(mp3)], check=True, timeout=60)
        else:
            mes = dt.date.today().strftime("%Y-%m")
            with _candado:
                e = estado()
                uso = e["azure"] if e["azure"].get("mes") == mes else {"mes": mes, "chars": 0}
                if uso["chars"] + len(texto) > AZURE_TOPE:
                    raise RuntimeError(f"Se acabó la voz gratis de Azure este mes ({uso['chars']:,} caracteres): sigue el día 1.")
                uso["chars"] += len(texto)
                e["azure"] = uso
                _guardar_estado(e)
            _azure_tts(texto, mp3)
        _escribir(tiempos, _tiempos(texto, _duracion(mp3)))
        _bitacora(cid, f"Voz escena {i} de {len(escenas)} lista")


def paso_material(cid: str, c: dict) -> None:
    if (carpeta(cid) / "material.json").exists():
        return
    g = _leer(carpeta(cid) / "guion.json", {})
    _bitacora(cid, "Buscando fotos de la marca (sin gastar Claude)")
    m = fb.buscar_material({"marca": c["marca"]}, g, carpeta(cid))
    fotos = [x for x in m.get("lista") or [] if not x.get("video") and (carpeta(cid) / x["archivo"]).exists()]
    _escribir(carpeta(cid) / "material.json", {"fotos": fotos})
    _bitacora(cid, f"{len(fotos)} fotos listas" + ("" if fotos else " (el video usará fondos oscuros con texto)"))


# ---------- 5. el video ----------
def _fotos_por_escena(cid: str, n: int) -> list[list[str]]:
    fotos = _leer(carpeta(cid) / "material.json", {}).get("fotos") or []
    por = [[] for _ in range(n)]
    sobrantes = []
    for f in fotos:
        es = [e for e in f.get("escenas") or [] if 1 <= e <= n]
        if es:
            por[es[0] - 1].append(f["archivo"])
        else:
            sobrantes.append(f["archivo"])
    todas = [f["archivo"] for f in fotos]
    for i in range(n):  # que ninguna escena se quede sin foto (si hay fotos)
        if not por[i] and todas:
            por[i] = [todas[(i * 2) % len(todas)], todas[(i * 2 + 1) % len(todas)]]
    return por


def _manifiesto(cid: str, c: dict) -> tuple[list[str], dict]:
    """El paquete para tu compu: audios con sus tiempos, fotos y el guion (estilo noir del kit de animación)."""
    g = _leer(carpeta(cid) / "guion.json", {})
    escenas = g.get("escenas") or []
    por = _fotos_por_escena(cid, len(escenas))
    entradas, mapa = [], {}

    def poner(origen: Path, relativa: str) -> str:
        nombre = f"f{len(entradas):03d}_{Path(relativa).name}"
        entradas.append(str(origen))
        mapa[nombre] = relativa
        return relativa

    esc_m = []
    for i, esc in enumerate(escenas, 1):
        audio = poner(carpeta(cid) / "voz" / f"escena_{i:02d}.mp3", f"audio/escena_{i:02d}.mp3")
        poner(carpeta(cid) / "voz" / f"escena_{i:02d}.palabras.json", f"audio/escena_{i:02d}.palabras.json")
        fotos = [poner(carpeta(cid) / f, f"img/e{i:02d}_{k}{Path(f).suffix}") for k, f in enumerate(por[i - 1][:4])]
        esc_m.append({"audio": audio, "narracion": _texto_escena(esc), "momento": "gancho" if i == 1 else "cierre" if i == len(escenas) else "desarrollo",
                      "visual": "imagen", "texto": esc.get("capitulo") or esc.get("titulo", ""), "fotos": fotos,
                      "frases": [len(f["texto"].split()) for f in esc.get("frases") or []],
                      "texto_pantalla": esc.get("texto_pantalla") or []})
    sfx = config.BASE / "estilo" / "sfx"
    for f in sorted(sfx.glob("*")) if sfx.exists() else []:
        poner(f, f"estilo/sfx/{f.name}")
    m = {"escenas": esc_m, "mapa": mapa, "estilo_edicion": "noir", "cerebro": "auto", "acento": "#FFD60A",
         "ctx": {"ficha": {"title": f"¿Quién MATÓ a {c['marca']}?"}}, "marca": c["marca"], "numero": c["numero"]}
    return entradas, m


def _compus_noir() -> int:
    import requests
    try:
        return int(requests.get(f"{SALA_URL}/interno/disponible", params={"tipo": "edu_estilo"}, timeout=4).json().get("compus") or 0)
    except (requests.RequestException, ValueError):
        return 0


def paso_video(cid: str, c: dict) -> None:
    import requests
    final = carpeta(cid) / "video.mp4"
    if final.exists():
        return
    salida = carpeta(cid) / "render-salida"
    tid = c.get("tid")
    if not tid and not c.get("servidor") and not DEMO and _compus_noir():
        entradas, m = _manifiesto(cid, c)
        shutil.rmtree(salida, ignore_errors=True)
        salida.mkdir(parents=True)
        r = requests.post(f"{SALA_URL}/interno/trabajo", timeout=15, json={
            "tipo": "edu_estilo", "origen": "expedientes", "categoria": "expedientes",
            "etiqueta": f"🕵️ #{c['numero']} ¿Quién MATÓ a {c['marca']}?"[:80],
            "parametros": {"manifiesto": m}, "entradas": entradas, "salida": str(salida)}).json()
        if not r.get("id"):
            _bitacora(cid, f"La sala no lo aceptó ({r.get('error')}): lo hace el servidor")
            _poner(cid, servidor=True)
        else:
            tid = r["id"]
            _poner(cid, tid=tid, tid_desde=time.time(), tid_mov=time.time(), tid_avance=0)
            _bitacora(cid, "Mandado a la sala de edición: lo toma la primera compu libre (con la tarjeta de video)")
    if tid:  # esperar a la compu, con vigilante
        desde = c.get("tid_desde") or time.time()
        while True:
            try:
                e = requests.get(f"{SALA_URL}/interno/trabajo/{tid}", timeout=8).json()
            except (requests.RequestException, ValueError):
                e = {"estado": "?"}
            c = caso(cid)
            est = e.get("estado")
            if est == "listo":
                v = next(iter(sorted(salida.glob("*.mp4"))), None)
                if not v:
                    raise RuntimeError("La compu terminó pero no llegó el video.")
                v.replace(final)
                _bitacora(cid, f"Video listo en {e.get('compu') or 'tu compu'} ({round(final.stat().st_size / 1e6)} MB)")
                _poner(cid, tid=None)
                return
            if e.get("avance") != c.get("tid_avance") or e.get("paso") != c.get("tid_paso"):
                _poner(cid, tid_avance=e.get("avance"), tid_paso=e.get("paso"), tid_mov=time.time(), tid_compu=e.get("compu"))
                _paso(cid, "video", "trabajando", detalle=f"{e.get('compu') or 'Compu'}: {e.get('paso') or ''}", avance=e.get("avance") or 0)
            quieto = time.time() - (caso(cid).get("tid_mov") or desde)
            sin_tomar = est == "en_cola" and time.time() - desde > 300
            if est in ("error", "cancelado") or sin_tomar or quieto > 1500:
                motivo = ("ninguna compu lo tomó en 5 min" if sin_tomar else f"la compu no avanzó en 25 min" if quieto > 1500
                          else f"la compu falló: {e.get('error') or est}")
                try:
                    requests.post(f"{SALA_URL}/interno/cancelar/{tid}", json={}, timeout=5)
                except requests.RequestException:
                    pass
                _bitacora(cid, f"{motivo[:200]} → lo hace el servidor")
                _poner(cid, tid=None, servidor=True)
                break
            time.sleep(15)
    _render_servidor(cid)


def _fuente() -> str:
    for f in ("/usr/share/fonts/truetype/roboto/unhinted/RobotoCondensed-Bold.ttf", "/usr/share/fonts/truetype/roboto/hinted/RobotoCondensed-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/arialbd.ttf"):
        if Path(f).exists():
            return f
    return ""


def _render_servidor(cid: str) -> None:
    """🖥️ Versión sencilla en el servidor (ffmpeg): por escena, fotos con movimiento lento y oscurecidas, el capítulo en
    grande al inicio y la voz. Más ligera que el kit de animación, pero nunca deja el caso sin video."""
    c = caso(cid)
    g = _leer(carpeta(cid) / "guion.json", {})
    escenas = g.get("escenas") or []
    por = _fotos_por_escena(cid, len(escenas))
    tmp = carpeta(cid) / "render-servidor"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()
    fuente = _fuente()
    partes = []
    for i, esc in enumerate(escenas, 1):
        _paso(cid, "video", "trabajando", detalle=f"Servidor: escena {i} de {len(escenas)}", avance=(i - 1) / max(1, len(escenas)))
        audio = carpeta(cid) / "voz" / f"escena_{i:02d}.mp3"
        dur = max(1.0, _duracion(audio))
        titulo = tmp / f"t{i}.txt"
        titulo.write_text((esc.get("capitulo") or esc.get("titulo") or "").upper()[:40], encoding="utf-8")
        texto = (f",drawtext=fontfile='{fuente}':textfile='{titulo}':fontsize=82:fontcolor=0xFFD60A:x=80:y=h-220:"
                 f"box=1:boxcolor=0x000000@0.55:boxborderw=24:enable='lt(t,3.5)'") if fuente else ""
        fotos = [carpeta(cid) / f for f in por[i - 1] if (carpeta(cid) / f).exists()][:3]
        seg = tmp / f"s{i:02d}.mp4"
        if fotos:
            cada = dur / len(fotos)
            ins, filtros = [], []
            for k, f in enumerate(fotos):
                ins += ["-loop", "1", "-t", f"{cada:.3f}", "-i", str(f)]
                filtros.append(f"[{k}:v]scale=2112:1188:force_original_aspect_ratio=increase,crop=2112:1188,"
                               f"zoompan=z='min(zoom+0.0006,1.1)':d={int(cada * 30) + 1}:s=1920x1080:fps=30,"
                               f"eq=brightness=-0.12:saturation=0.75,setsar=1[v{k}]")
            filtro = ";".join(filtros) + ";" + "".join(f"[v{k}]" for k in range(len(fotos))) + f"concat=n={len(fotos)}:v=1:a=0[base];[base]null{texto}[v]"
            cmd = ["ffmpeg", "-y", "-loglevel", "error", *ins, "-i", str(audio), "-filter_complex", filtro,
                   "-map", "[v]", "-map", f"{len(fotos)}:a"]
        else:
            cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c=0x121212:s=1920x1080:r=30:d={dur:.3f}",
                   "-i", str(audio), "-filter_complex", f"[0:v]null{texto}[v]", "-map", "[v]", "-map", "1:a"]
        subprocess.run([*cmd, "-t", f"{dur:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "160k", "-ar", "48000", str(seg)], check=True, capture_output=True, timeout=1800)
        partes.append(seg)
    lista = tmp / "lista.txt"
    lista.write_text("".join(f"file '{p.name}'\n" for p in partes), encoding="utf-8")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lista), "-c", "copy",
                    "-movflags", "+faststart", str(carpeta(cid) / "video.mp4")], check=True, capture_output=True, timeout=900, cwd=tmp)
    shutil.rmtree(tmp, ignore_errors=True)
    _bitacora(cid, "Video listo (hecho en el servidor)")


# ---------- 6. miniatura ----------
def paso_miniatura(cid: str, c: dict) -> None:
    from PIL import Image, ImageDraw, ImageEnhance, ImageFont
    destino = carpeta(cid) / "miniatura.jpg"
    if destino.exists():
        return
    g = _leer(carpeta(cid) / "guion.json", {})
    fotos = [carpeta(cid) / f["archivo"] for f in _leer(carpeta(cid) / "material.json", {}).get("fotos") or []]
    fotos = [f for f in fotos if f.exists()]
    lienzo = Image.new("RGB", (1280, 720), "#121212")
    if fotos:
        f = max(fotos, key=lambda p: p.stat().st_size)
        im = Image.open(f).convert("RGB")
        im = im.resize((1280, int(im.height * 1280 / im.width))) if im.width / im.height < 16 / 9 else im.resize((int(im.width * 720 / im.height), 720))
        im = im.crop(((im.width - 1280) // 2, (im.height - 720) // 2, (im.width - 1280) // 2 + 1280, (im.height - 720) // 2 + 720))
        im = ImageEnhance.Brightness(ImageEnhance.Color(im).enhance(0.6)).enhance(0.55)
        lienzo.paste(im)
    d = ImageDraw.Draw(lienzo)
    fuente = _fuente()
    grande = ImageFont.truetype(fuente, 128) if fuente else ImageFont.load_default()
    chica = ImageFont.truetype(fuente, 46) if fuente else ImageFont.load_default()
    d.rectangle([0, 0, 1280, 64], fill="#E63946")
    d.text((40, 6), "¿QUIÉN MATÓ A…?", font=chica, fill="#F5F5F5")
    lineas = [x for x in (g.get("miniatura_a") or [c["marca"].upper()]) if x][:3]
    y = 150
    for k, ln in enumerate(lineas):
        d.text((60 + 5, y + 5), ln.upper(), font=grande, fill="#000")
        d.text((60, y), ln.upper(), font=grande, fill="#FFD60A" if k == len(lineas) - 1 else "#F5F5F5")
        y += 150
    d.rectangle([0, 700, 1280, 720], fill="#FFD60A")
    lienzo.save(destino, quality=92)
    _bitacora(cid, "Miniatura lista")


# ---------- 7. YouTube ----------
def _canal() -> dict:
    return next((x for x in fb.agenda.lista() if x["id"] == "quien_mato"), {})


def _capitulos(cid: str, g: dict) -> str:
    t, lineas = 0.0, []
    for i, esc in enumerate(g.get("escenas") or [], 1):
        lineas.append(f"{int(t // 60):02d}:{int(t % 60):02d} {esc.get('capitulo') or esc.get('titulo') or f'Parte {i}'}")
        t += _duracion(carpeta(cid) / "voz" / f"escena_{i:02d}.mp3")
    return "\n".join(lineas)


def _creditos(cid: str) -> str:
    cr = _leer(carpeta(cid) / "material" / "fotos" / "creditos.json", {})
    return "\n".join(f"- {v.get('fuente') or v.get('pagina') or k}" for k, v in list(cr.items())[:30] if isinstance(v, dict))


def paso_youtube(cid: str, c: dict) -> None:
    if c.get("url"):
        return
    from . import youtube
    g = _leer(carpeta(cid) / "guion.json", {})
    canal = _canal()
    titulo = (canal.get("plantilla") or "¿Quién MATÓ a [Marca]?").replace("[Marca]", c["marca"])[:100]
    desc = (g.get("descripcion", "").strip() + "\n\n⏱️ CAPÍTULOS\n" + _capitulos(cid, g)
            + ("\n\n📷 CRÉDITOS DEL MATERIAL\n" + _creditos(cid) if _creditos(cid) else "")
            + "\n\nEste video es de análisis y opinión; no está patrocinado ni afiliado a ninguna de las marcas mencionadas. "
              "Las cifras vienen de las fuentes citadas.")[:4900]
    e = estado()
    libres = [f for f in fb._fechas_libres("quien_mato") if f"{f['fecha']} {f['hora']}" not in e["fechas"]]
    fecha = libres[0] if libres else None
    publicar_en = None
    if fecha:
        from zoneinfo import ZoneInfo
        local = dt.datetime.fromisoformat(f"{fecha['fecha']}T{fecha['hora']}:00").replace(tzinfo=fb.agenda.ZONA)
        publicar_en = local.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")
    if DEMO:
        vid = "demo-" + uuid.uuid4().hex[:6]
    else:
        if not canal.get("canal_youtube"):
            raise RuntimeError("Falta elegir el canal de YouTube de la serie (pestaña Canales de Expedientes).")
        _bitacora(cid, "Subiendo a YouTube en privado…")
        vid = youtube.subir(carpeta(cid) / "video.mp4", carpeta(cid) / "miniatura.jpg", titulo, desc, (g.get("etiquetas") or [])[:30],
                            sintetico=True, privacidad="private", publicar_en=publicar_en, canal=canal["canal_youtube"])
    with _candado:
        e = estado()
        if fecha:
            e["fechas"].append(f"{fecha['fecha']} {fecha['hora']}")
        _guardar_estado(e)
    _poner(cid, url=f"https://youtu.be/{vid}", programado=f"{fecha['fecha']} {fecha['hora']}" if fecha else "", hecho=time.time())
    _bitacora(cid, f"✔ Subido en PRIVADO" + (f", se publica solo el {fecha['fecha']} a las {fecha['hora']}" if fecha else ""))


def paso_revision(cid: str, c: dict) -> None:
    """🔍 El director revisa el video antes de subirlo: lo técnico siempre; el contenido con su cerebro si hay plan.
    Si lo técnico salió mal, se rehace el video (una vez); lo creativo se anota para que el siguiente salga mejor."""
    if c.get("revision"):
        return
    from . import director
    g = _leer(carpeta(cid) / "guion.json", {})
    video = carpeta(cid) / "video.mp4"
    voz = sum(_duracion(p) for p in sorted((carpeta(cid) / "voz").glob("escena_*.mp3")))
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", str(video)],
                       capture_output=True, text=True, timeout=60)
    tecnico = {"duracion": round(_duracion(video), 1), "voz": round(voz, 1), "audio": bool(r.stdout.strip()) or DEMO,
               "mb": round(video.stat().st_size / 1e6, 1) if video.exists() else 0, "escenas": len(g.get("escenas") or []),
               "fotos": len(_leer(carpeta(cid) / "material.json", {}).get("fotos") or [])}
    if DEMO:
        tecnico["mb"] = max(tecnico["mb"], 2)
    guion = "\n\n".join(f"## {e.get('capitulo') or e.get('titulo')}\n{_texto_escena(e)}" for e in g.get("escenas") or [])
    rev = director.revisar_video("expedientes", f"¿Quién MATÓ a {c['marca']}?", guion, tecnico)
    if rev.get("rehacer") and not c.get("rehecho"):
        video.unlink(missing_ok=True)
        _poner(cid, rehecho=True, tid=None, servidor=False)
        _paso(cid, "video", "pendiente", error=None, intentos=0)
        raise RuntimeError("El director pidió rehacer el video: " + "; ".join(rev.get("problemas") or [])[:200])
    _poner(cid, revision={"nota": rev.get("nota"), "problemas": rev.get("problemas"), "aciertos": rev.get("aciertos")})
    _bitacora(cid, f"🔍 Revisión del director: nota {rev.get('nota') if rev.get('nota') is not None else 'técnica ✔'}"
                   + (f" · a mejorar: {'; '.join(rev.get('problemas') or [])[:160]}" if rev.get("problemas") else ""))


FUNCIONES = {"investigacion": paso_investigacion, "guion": paso_guion, "voz": paso_voz, "material": paso_material,
             "video": paso_video, "miniatura": paso_miniatura, "revision": paso_revision, "youtube": paso_youtube}
NECESITA_PLAN = {"investigacion", "guion"}


# ---------------------------------------------------------------- el trabajador: un caso, paso por paso
def _caso_actual() -> str | None:
    return next((x for x in estado()["casos"] if not caso(x).get("hecho") and not caso(x).get("saltado")), None)


def _trabajar() -> None:
    """Hace los pasos del caso que va, en orden; si un paso falla se anota y se reintenta solo (3 veces)."""
    while True:
        e = estado()
        if not e["activa"]:
            return
        cid = _caso_actual()
        if not cid:
            from . import director
            if not director.permitido("expedientes") or not _plan():
                return
            t = _siguiente_tema()
            if not t:
                return
            cid = nuevo_caso(t)
        c = caso(cid)
        for clave, nombre in PASOS:
            p = (c.get("pasos") or {}).get(clave) or {}
            if p.get("estado") == "listo":
                continue
            if p.get("estado") == "error" and (p.get("intentos") or 0) >= 3:
                return  # espera a que le des «Reintentar paso»
            if p.get("estado") == "error" and time.time() - (p.get("fin") or 0) < 600:
                return  # se reintenta solo en 10 min
            if clave in NECESITA_PLAN and not _plan():
                _paso(cid, clave, "esperando", detalle="Esperando a que se restablezca tu plan de Claude")
                return
            _paso(cid, clave, "trabajando", detalle=nombre)
            try:
                FUNCIONES[clave](cid, caso(cid))
                _paso(cid, clave, "listo", detalle="", error=None, intentos=0)
            except Exception as exc:  # noqa: BLE001 — se anota y se reintenta
                n = (p.get("intentos") or 0) + 1
                _paso(cid, clave, "error", error=str(exc)[:300], intentos=n)
                _bitacora(cid, f"⚠️ {nombre} falló ({n}/3): {str(exc)[:200]}")
                return
            c = caso(cid)
        _tema_hecho(caso(cid))
        _bitacora(cid, "🎉 Caso cerrado: listo y programado")


def vuelta() -> None:
    h = _hilo.get("trabajo")
    if h and h.is_alive():
        return
    _hilo["trabajo"] = threading.Thread(target=_trabajar, daemon=True)
    _hilo["trabajo"].start()


def iniciar() -> None:
    if _hilo.get("ciclo"):
        return
    CARPETA.mkdir(parents=True, exist_ok=True)

    def ciclo():
        time.sleep(15)
        _migrar_viejos()
        while True:
            try:
                vuelta()
            except Exception as exc:  # noqa: BLE001
                print(f"  · quién mató: {exc}", flush=True)
            time.sleep(30)
    _hilo["ciclo"] = threading.Thread(target=ciclo, daemon=True)
    _hilo["ciclo"].start()


# ---------------------------------------------------------------- acciones y resumen para la página
def accion(d: dict) -> dict:
    a = d.get("accion")
    cid = str(d.get("caso") or _caso_actual() or "")
    if a in ("prender", "pausar"):
        e = estado()
        e["activa"] = a == "prender"
        _guardar_estado(e)
    elif a == "reintentar" and cid:  # vuelve a intentar el paso que falló, ya (sin esperar)
        c = caso(cid)
        for clave, _ in PASOS:
            p = (c.get("pasos") or {}).get(clave) or {}
            if p.get("estado") in ("error", "esperando"):
                _paso(cid, clave, "pendiente", error=None, intentos=0)
        _bitacora(cid, "▶ Reintentar: sigo desde el paso que iba")
    elif a == "rehacer_video" and cid:
        for n in ("video.mp4",):
            (carpeta(cid) / n).unlink(missing_ok=True)
        _poner(cid, tid=None, servidor=False)
        _paso(cid, "video", "pendiente", error=None, intentos=0)
        _bitacora(cid, "🔁 Rehago el video")
    elif a == "saltar" and cid:
        c = _poner(cid, saltado=True)
        _tema_hecho(c, "saltado")
        _bitacora(cid, "⏭ Saltado por el jefe")
    else:
        return {"error": "¿Qué hago?"}
    vuelta()
    return {"ok": True}


def continuar() -> dict:
    """▶ Para la sala central y el director: reintenta lo que falló y prende la oficina."""
    e = estado()
    e["activa"] = True
    _guardar_estado(e)
    cid = _caso_actual()
    if cid:
        accion({"accion": "reintentar", "caso": cid})
    else:
        vuelta()
    return {"ok": True, "reintentos": 1 if cid else 0}


def resumen() -> dict:
    e = estado()
    casos = []
    for cid in reversed(e["casos"][-30:]):
        c = caso(cid)
        if not c:
            continue
        pasos = []
        for clave, nombre in PASOS:
            p = (c.get("pasos") or {}).get(clave) or {}
            pasos.append({"clave": clave, "nombre": nombre, "estado": p.get("estado") or "pendiente", "detalle": p.get("detalle"),
                          "error": p.get("error"), "inicio": p.get("inicio"), "fin": p.get("fin"), "avance": p.get("avance"),
                          "intentos": p.get("intentos")})
        casos.append({"id": cid, "numero": c.get("numero"), "marca": c.get("marca"), "paso": c.get("paso"), "pasos": pasos,
                      "log": (c.get("log") or [])[-25:], "mov": c.get("mov"), "url": c.get("url"), "programado": c.get("programado"),
                      "hecho": c.get("hecho"), "saltado": c.get("saltado"),
                      "video": (carpeta(cid) / "video.mp4").exists(), "miniatura": (carpeta(cid) / "miniatura.jpg").exists()})
    temas = [{"marca": x["marca"], "gancho": x.get("gancho", ""), "estado": x["estado"]} for x in fb.temas()
             if x["estado"] in ("pendiente", "produciendo")][:12]
    actual = _caso_actual()
    return {"activa": e["activa"], "actual": actual, "casos": casos, "temas": temas, "ahora": time.time(),
            "trabajando": bool(_hilo.get("trabajo") and _hilo["trabajo"].is_alive()), "plan": _plan(),
            "azure": bool(fb._azure()) or DEMO, "canal": bool(_canal().get("canal_youtube")) or DEMO,
            "compus": _compus_noir()}


def archivo(cid: str, nombre: str) -> Path | None:
    if nombre not in ("video.mp4", "miniatura.jpg") or "/" in cid or ".." in cid:
        return None
    p = carpeta(cid) / nombre
    return p if p.exists() else None
