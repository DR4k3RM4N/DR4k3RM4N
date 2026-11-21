"""🎬 Analizar un video desde el chat: le pasas un enlace (YouTube, TikTok, Instagram, Facebook, X…) y Paola
1. lo baja (hasta 30 min, en calidad baja; solo para verlo),
2. saca lo que se dice: los subtítulos del video si los tiene (YouTube) o, si no, Whisper local (gratis),
3. ve sus imágenes: la miniatura + cuadros repartidos en todo el video,
4. te explica de qué trata, cómo está armado (con tiempos), por qué funciona, cómo se ve y qué le copiarías a tu
   canal, y contesta lo que le preguntes del video.
La transcripción completa se guarda en estilo/analisis/ para que la bajes.
Costo: 1 llamada a Claude con imágenes (tu plan); bajar y transcribir es gratis.
"""
from __future__ import annotations

import html
import json
import re
import subprocess
import tempfile
import time
from pathlib import Path

from . import claude, config

CARPETA = config.ESTILO_DIR / "analisis"
SITIOS = ("youtube.com", "youtu.be", "tiktok.com", "instagram.com", "facebook.com", "fb.watch", "x.com",
          "twitter.com", "vimeo.com", "kwai", "twitch.tv", "dailymotion.com", "threads.net")
MAX_SEGUNDOS = 30 * 60
CUADROS = 16

SCHEMA = {
    "type": "object",
    "properties": {
        "resumen": {"type": "string", "description": "De qué trata el video, en 2-4 frases"},
        "estructura": {"type": "array", "items": {
            "type": "object",
            "properties": {"tiempo": {"type": "string", "description": "mm:ss"},
                           "que_pasa": {"type": "string"}},
            "required": ["tiempo", "que_pasa"], "additionalProperties": False},
            "description": "Las partes del video con su tiempo (gancho, bloques, re-ganchos, cierre)"},
        "gancho": {"type": "string", "description": "Cómo engancha en los primeros segundos y por qué funciona (o no)"},
        "por_que_funciona": {"type": "array", "items": {"type": "string"},
                             "description": "Lo que hace que la gente lo vea y se quede (o lo que le falla)"},
        "visual": {"type": "string", "description": "Cómo se ve: edición, textos en pantalla, ritmo, colores, "
                                                    "b-roll, caras, efectos"},
        "empaque": {"type": "string", "description": "Título y miniatura: qué promete y por qué da (o no) clic"},
        "para_nuestro_canal": {"type": "array", "items": {"type": "string"},
                               "description": "3-6 cosas concretas que copiarías o adaptarías para el canal del jefe"},
        "respuesta": {"type": "string", "description": "Si el jefe preguntó algo del video, la respuesta; si no, vacío"},
    },
    "required": ["resumen", "estructura", "gancho", "por_que_funciona", "visual", "empaque", "para_nuestro_canal",
                 "respuesta"],
    "additionalProperties": False,
}


def es_video(url: str) -> bool:
    return any(s in (url or "").lower() for s in SITIOS)


def enlaces(texto: str) -> list[str]:
    return [u.rstrip(").,;!?»\"'") for u in re.findall(r"https?://\S+", texto or "")]


def _mmss(s: float) -> str:
    s = int(s)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def _vtt(ruta: Path) -> str:
    """Subtítulos .vtt → "[m:ss] texto" sin las repeticiones de los subtítulos automáticos."""
    lineas, ultimo, t = [], "", 0.0
    for bloque in ruta.read_text(encoding="utf-8", errors="replace").split("\n\n"):
        m = re.search(r"(\d+):(\d+):(\d+)[.,]\d+\s+-->", bloque) or re.search(r"(\d+):(\d+)[.,]\d+\s+-->", bloque)
        if not m:
            continue
        g = [int(x) for x in m.groups()]
        t = g[0] * 3600 + g[1] * 60 + g[2] if len(g) == 3 else g[0] * 60 + g[1]
        for linea in bloque.splitlines():  # los subtítulos automáticos repiten el renglón anterior: se salta
            if "-->" in linea or linea.strip().isdigit() or linea.startswith(("WEBVTT", "Kind:", "Language:")):
                continue
            frase = html.unescape(re.sub(r"<[^>]+>", "", linea)).strip()
            if frase and frase != ultimo:
                lineas.append((t, frase))
                ultimo = frase
    # junta en renglones de ~15 s
    salida, actual, inicio = [], [], None
    for t, frase in lineas:
        if inicio is None:
            inicio = t
        actual.append(frase)
        if t - inicio >= 15:
            salida.append(f"[{_mmss(inicio)}] {' '.join(actual)}")
            actual, inicio = [], None
    if actual:
        salida.append(f"[{_mmss(inicio or 0)}] {' '.join(actual)}")
    return "\n".join(salida)


def _whisper(video: Path, segundos: int) -> str:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return ""
    with tempfile.TemporaryDirectory() as tmp:
        audio = Path(tmp) / "a.wav"
        r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-t", str(segundos), "-i", str(video), "-vn",
                            "-ac", "1", "-ar", "16000", str(audio)], check=False)
        if r.returncode or not audio.exists():
            return ""
        modelo = WhisperModel(config.env("WHISPER_MODELO", "small"), device="cpu", compute_type="int8")
        partes, _ = modelo.transcribe(str(audio), vad_filter=True)
        return "\n".join(f"[{_mmss(p.start)}] {p.text.strip()}" for p in partes)


class Frenado(ValueError):
    """El sitio no dejó bajar el video desde el servidor (YouTube: «confirma que no eres un bot»)."""


def _id_youtube(url: str) -> str:
    m = re.search(r"(?:youtu\.be/|[?&]v=|/shorts/|/live/|/embed/)([\w-]{11})", url or "")
    return m.group(1) if m and "youtu" in url else ""


def bajar(url: str, carpeta: Path) -> dict:
    """Baja el video (máx. 30 min, ≤480p), sus subtítulos y la miniatura. Regresa los datos del video."""
    import yt_dlp

    opciones = {
        "format": "bv*[height<=480]+ba/b[height<=480]/bv*[height<=720]+ba/b",
        "outtmpl": str(carpeta / "video.%(ext)s"), "noplaylist": True, "quiet": True, "no_warnings": True,
        "noprogress": True, "max_filesize": 600 * 1024 * 1024, "socket_timeout": 30, "merge_output_format": "mp4",
        "download_ranges": yt_dlp.utils.download_range_func(None, [(0, MAX_SEGUNDOS)]),
        "writesubtitles": True, "writeautomaticsub": True, "subtitleslangs": ["es.*", "es", "en.*", "en"],
        "subtitlesformat": "vtt", "writethumbnail": True,
    }
    try:
        with yt_dlp.YoutubeDL(opciones) as ydl:
            info = ydl.extract_info(url, download=True) or {}
    except yt_dlp.utils.DownloadError as exc:
        texto = str(exc)
        if "Unable to connect" in texto or "timed out" in texto or "Failed to establish" in texto or "proxy" in texto:
            raise ValueError("No pude conectarme a ese sitio desde el servidor. Intenta otra vez en un rato.") from exc
        if "Sign in" in texto or "not a bot" in texto or "403" in texto or "429" in texto or "login" in texto.lower():
            raise Frenado("Ese sitio no dejó bajar el video desde el servidor (pide iniciar sesión o es privado). "
                          "Para verlo completo, súbeme el archivo del video con el 📎 del chat.") from exc
        raise ValueError(f"No pude bajar ese video: {texto[-200:]}") from exc
    return info


def analizar(url: str, pregunta: str = "", canal: str | None = None, archivo: Path | None = None) -> dict:
    """Regresa {"titulo", "texto" (para el chat), "transcripcion" (ruta web), "segundos"}.
    `archivo`: un video que subiste al chat (📎) en lugar de un enlace."""
    from . import canales, estilo

    if archivo is None and not re.match(r"https?://", url or ""):
        raise ValueError("Pásame un enlace que empiece con https://")
    CARPETA.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        if archivo is not None:
            import shutil
            shutil.copyfile(archivo, tmp / f"video{archivo.suffix.lower()}")
            nombre_original = re.sub(r"^\d{8}_\d{6}_", "", archivo.stem)  # sin la fecha con que se guardó
            info, url = {"title": nombre_original.replace("_", " ")}, url or "(archivo que subiste)"
        else:
            try:
                info = bajar(url, tmp)
            except Frenado:
                if _id_youtube(url):  # YouTube no deja bajarlo: lo que sí deja ver su API oficial
                    return _sin_video(url, pregunta, canal)
                raise
        videos = [p for p in tmp.iterdir() if p.name.startswith("video.") and p.suffix in (".mp4", ".mkv", ".webm", ".mov")]
        if not videos:
            raise ValueError("No pude bajar ese video.")
        video = videos[0]
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                    str(video)], capture_output=True, text=True).stdout.strip() or 0)
        dur_total = float(info.get("duration") or dur)
        # 1) lo que se dice: subtítulos del video (español primero) o Whisper
        subs = sorted(tmp.glob("video*.vtt"), key=lambda p: (".es" not in p.name, p.name))
        dicho, fuente = "", ""
        if subs:
            dicho, fuente = _vtt(subs[0]), "subtítulos del video"
        if not dicho.strip():
            try:
                dicho, fuente = _whisper(video, int(min(dur, MAX_SEGUNDOS))), "Whisper (transcripción automática)"
            except Exception as exc:  # noqa: BLE001
                print(f"  · no pude transcribir: {exc}", flush=True)
                dicho = ""
        # 2) lo que se ve: miniatura + cuadros repartidos
        contenido = []
        mini = next((p for p in tmp.iterdir() if p.name.startswith("video.") and p.suffix in (".jpg", ".webp", ".png")), None)
        if mini:
            jpg = tmp / "mini.jpg"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mini), "-vf", "scale=640:-2", str(jpg)],
                           check=False)
            if jpg.exists():
                contenido += [{"type": "text", "text": "MINIATURA del video:"}, estilo.imagen_bloque(jpg, 640)]
        for k in range(CUADROS):
            t = max(dur, 1) * (k + 0.5) / CUADROS
            p = tmp / f"c{k:02d}.jpg"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1",
                            "-vf", "scale=512:-2", str(p)], check=False)
            if p.exists():
                contenido += [{"type": "text", "text": f"Cuadro en {_mmss(t)}:"}, estilo.imagen_bloque(p, 512)]
    titulo = info.get("title") or "video"
    datos = {k: info.get(k) for k in ("title", "uploader", "channel_follower_count", "view_count", "like_count",
                                      "comment_count", "upload_date", "duration")}
    # 3) guardar la transcripción completa
    nombre = re.sub(r"[^a-z0-9]+", "-", titulo.lower())[:50].strip("-") or "video"
    archivo = CARPETA / f"{time.strftime('%Y%m%d-%H%M')}-{nombre}.txt"
    archivo.write_text(f"{titulo}\n{url}\n{json.dumps(datos, ensure_ascii=False)}\n\nTRANSCRIPCIÓN ({fuente or 'no disponible'}):\n\n"
                       + (dicho or "(No se pudo transcribir: el video no trae subtítulos y Whisper no está instalado.)"),
                       encoding="utf-8")
    # 4) que Claude lo vea y lo explique
    info_canal = canales.get(canal or canales.actual())
    contenido.insert(0, {"type": "text", "text": (
        f"VIDEO: «{titulo}» de {info.get('uploader') or '?'} "
        f"({info.get('channel_follower_count') or '?'} suscriptores) · {info.get('view_count') or '?'} vistas · "
        f"{info.get('like_count') or '?'} likes · {info.get('comment_count') or '?'} comentarios · publicado "
        f"{info.get('upload_date') or '?'} · dura {_mmss(dur_total)}"
        + (f" (vi los primeros {_mmss(dur)})" if dur_total > dur + 5 else "") + f"\nEnlace: {url}")})
    contenido.append({"type": "text", "text": (
        (f"LO QUE SE DICE ({fuente}):\n{dicho[:16000]}" if dicho else "No hay transcripción: analiza solo lo visual.")
        + f"\n\nEL CANAL DEL JEFE: «{info_canal.get('nombre')}» — {canales.NICHOS.get(info_canal.get('nicho'), '')}"
        + (f"\n\nLO QUE PREGUNTA EL JEFE: {pregunta}" if pregunta.strip() else "")
        + "\n\nAnaliza el video: de qué trata, cómo está armado (con tiempos), por qué funciona o no, cómo se ve y su "
          "empaque, y qué le copiarías al canal del jefe. Solo lo que se ve y se dice aquí; nada inventado.")})
    r = claude.json_estructurado(
        "Eres Paola, productora de YouTube con 30 años de experiencia en guion, edición y estrategia. Ves un video "
        "(cuadros + transcripción) y lo explicas claro, en español de México, al grano.",
        contenido, SCHEMA, tarea="estilo", que="analizar video")
    web = f"/estilo/analisis/{archivo.name}"
    partes = [f"🎬 «{titulo}»" + (f" — {info.get('view_count'):,} vistas" if info.get("view_count") else ""),
              f"📝 {r['resumen']}"]
    if r["respuesta"].strip():
        partes.append(f"💬 {r['respuesta']}")
    partes.append(f"🪝 Gancho: {r['gancho']}")
    if r["estructura"]:
        partes.append("🧱 Cómo está armado:\n" + "\n".join(f"• {e['tiempo']} — {e['que_pasa']}" for e in r["estructura"][:12]))
    partes.append("✅ Por qué funciona:\n" + "\n".join(f"• {x}" for x in r["por_que_funciona"][:6]))
    partes.append(f"🎨 Cómo se ve: {r['visual']}")
    partes.append(f"🖼️ Título y miniatura: {r['empaque']}")
    partes.append("📌 Para tu canal:\n" + "\n".join(f"• {x}" for x in r["para_nuestro_canal"][:6]))
    partes.append(f"📄 Transcripción completa ({fuente or 'no disponible'}): {web}" if dicho
                  else "📄 No pude transcribirlo (no trae subtítulos y falta Whisper en el servidor).")
    (CARPETA / (archivo.stem + ".analisis.json")).write_text(json.dumps({"url": url, **r}, ensure_ascii=False, indent=1),
                                                             encoding="utf-8")
    return {"titulo": titulo, "texto": "\n\n".join(partes), "transcripcion": web if dicho else "", "segundos": dur}


def _sin_video(url: str, pregunta: str, canal: str | None) -> dict:
    """YouTube no deja bajar videos al servidor: con su API oficial (la de tus canales) se ve el título, la
    descripción (a veces con capítulos), los números, la miniatura y los comentarios. Sin transcripción ni cuadros."""
    import requests

    from . import canales, estilo, tendencias, youtube

    vid = _id_youtube(url)
    try:
        yt = youtube._servicio(abrir_navegador=False)
        items = yt.videos().list(part="snippet,statistics,contentDetails", id=vid).execute().get("items") or []
    except Exception as exc:  # noqa: BLE001
        raise ValueError("YouTube no deja bajar videos al servidor y no pude usar su API "
                         f"({str(exc)[:100]}). Súbeme el archivo con el 📎 del chat.") from exc
    if not items:
        raise ValueError("No encontré ese video en YouTube (¿es privado?).")
    v = items[0]
    sn, st = v["snippet"], v.get("statistics", {})
    comentarios = tendencias.comentarios(vid, 25)
    dur = tendencias._segundos(v.get("contentDetails", {}).get("duration", ""))
    contenido = [{"type": "text", "text": (
        f"VIDEO: «{sn['title']}» de {sn.get('channelTitle')} · {st.get('viewCount', '?')} vistas · "
        f"{st.get('likeCount', '?')} likes · {st.get('commentCount', '?')} comentarios · publicado "
        f"{sn.get('publishedAt', '')[:10]} · dura {_mmss(dur)}\nEnlace: {url}")}]
    miniaturas = sn.get("thumbnails") or {}
    mini_url = next((miniaturas[k]["url"] for k in ("maxres", "standard", "high", "medium") if k in miniaturas), "")
    with tempfile.TemporaryDirectory() as tmp:
        if mini_url:
            try:
                ruta = Path(tmp) / "mini.jpg"
                ruta.write_bytes(requests.get(mini_url, timeout=20).content)
                contenido += [{"type": "text", "text": "MINIATURA del video:"}, estilo.imagen_bloque(ruta, 640)]
            except (requests.RequestException, OSError, ValueError):
                pass
        info_canal = canales.get(canal or canales.actual())
        contenido.append({"type": "text", "text": (
            f"DESCRIPCIÓN:\n{(sn.get('description') or '')[:3000]}\n\nCOMENTARIOS MÁS RELEVANTES:\n"
            + ("\n".join(f"- {c}" for c in comentarios) or "(sin comentarios)")
            + f"\n\nEL CANAL DEL JEFE: «{info_canal.get('nombre')}» — {canales.NICHOS.get(info_canal.get('nicho'), '')}"
            + (f"\n\nLO QUE PREGUNTA EL JEFE: {pregunta}" if pregunta.strip() else "")
            + "\n\nNO tienes el video ni lo que se dice: solo título, miniatura, descripción y comentarios. Analiza "
              "el empaque, de qué trata según eso y lo que dice la gente. En 'estructura' pon solo los capítulos de la "
              "descripción si los hay; en 'gancho' y 'visual', lo que se pueda deducir de la miniatura o di que no lo "
              "viste. Nada inventado.")})
        r = claude.json_estructurado(
            "Eres Paola, productora de YouTube con 30 años de experiencia. Explicas claro, en español de México.",
            contenido, SCHEMA, tarea="estilo", que="analizar video (con la API de YouTube)")
    vistas = int(st.get("viewCount") or 0)
    partes = [f"🎬 «{sn['title']}»" + (f" — {vistas:,} vistas" if vistas else ""),
              "ℹ️ YouTube no deja bajar sus videos al servidor, así que vi su miniatura, título, descripción y "
              "comentarios. Para verlo completo (transcripción e imágenes), súbeme el archivo con el 📎 del chat.",
              f"📝 {r['resumen']}"]
    if r["respuesta"].strip():
        partes.append(f"💬 {r['respuesta']}")
    if r["estructura"]:
        partes.append("🧱 Capítulos:\n" + "\n".join(f"• {e['tiempo']} — {e['que_pasa']}" for e in r["estructura"][:12]))
    partes.append(f"🖼️ Título y miniatura: {r['empaque']}")
    partes.append("✅ Lo que se nota:\n" + "\n".join(f"• {x}" for x in r["por_que_funciona"][:6]))
    partes.append("📌 Para tu canal:\n" + "\n".join(f"• {x}" for x in r["para_nuestro_canal"][:6]))
    return {"titulo": sn["title"], "texto": "\n\n".join(partes), "transcripcion": "", "segundos": 0}
