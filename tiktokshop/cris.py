"""Cris (editor vertical) y Vale (portadas) de la oficina de TikTok Shop.

Miguel graba con su celular y habla en los clips. Cris:
- escucha los clips con Whisper (gratis, corre en el servidor) para saber el segundo exacto de cada palabra,
- ordena las tomas según el guion de Sofi y el gancho elegido (uno o los 3 → un video por gancho),
- quita silencios del principio y del final de cada toma (o, con el video completo, silencios y tomas repetidas),
- parte las tomas largas con acercamientos cada ~2 s (se siente como cambio de toma),
- pone el texto en pantalla de Sofi en la zona segura y subtítulos karaoke con tu voz,
y Vale saca la portada de un cuadro del video con el texto del gancho.
"""
from __future__ import annotations

import difflib
import json
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from agentes import claude as ia
from agentes import config

AQUI = Path(__file__).resolve().parent
SALIDA = AQUI / "salida"
ANCHO, ALTO, FPS = 1080, 1920, 30
BLOQUES = ["puente", "problema", "solucion", "beneficios", "cta"]
EXTENSIONES = {".mp4", ".mov", ".m4v", ".webm", ".3gp", ".mkv"}
RAPIDO = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(FPS), "-threads", "2"]
FINAL = ["-c:v", "libx264", "-preset", "faster", "-crf", "21", "-pix_fmt", "yuv420p", "-r", str(FPS), "-threads", "2",
         "-movflags", "+faststart"]
AUDIO = ["-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2"]
FUENTE = "DejaVu Sans"
FUENTE_TTF = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
MARGEN_DER = int(ANCHO * 0.15) + 24  # zona segura: los botones de TikTok van a la derecha
CORTE = 2.2  # segundos: cada cuánto "cambia de toma" una toma larga


class ErrorEdicion(Exception):
    pass


def _ff(*args: str) -> None:
    r = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args], capture_output=True, text=True)
    if r.returncode:
        raise ErrorEdicion("ffmpeg falló: " + (r.stderr.strip().splitlines() or ["sin detalle"])[-1][:200])


def duracion(ruta: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(ruta)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError as exc:
        raise ErrorEdicion(f"No pude leer el video {ruta.name} (¿está completo?).") from exc


def tiene_audio(ruta: Path) -> bool:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0",
                        str(ruta)], capture_output=True, text=True)
    return bool(r.stdout.strip())


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9 ]+", " ", t).strip()


# ---------- escuchar los clips (Whisper, gratis en el servidor) ----------
_modelo = None
ultimo_error = ""  # si Whisper falla, Cris lo avisa y edita sin subtítulos


def whisper_disponible() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False


def transcribir(ruta: Path, pista: str = "") -> list[dict]:
    """Palabras con su tiempo: [{"w": "hola", "t": 1.2, "d": 0.3}]. Se guarda junto al clip para no repetirlo."""
    cache = ruta.with_name(ruta.name + ".palabras.json")
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    if not tiene_audio(ruta) or not whisper_disponible():
        return []
    global _modelo, ultimo_error
    try:
        from faster_whisper import WhisperModel
        if _modelo is None:  # la primera vez baja el modelo (~500 MB con "small")
            _modelo = WhisperModel(config.env("WHISPER_MODELO", "small") or "small", device="cpu", compute_type="int8",
                                   cpu_threads=2)
        segmentos, _ = _modelo.transcribe(str(ruta), language="es", word_timestamps=True, beam_size=2,
                                          initial_prompt=(pista[:600] or None), condition_on_previous_text=False)
        palabras = [{"w": w.word.strip(), "t": round(w.start, 3), "d": round(max(0.05, w.end - w.start), 3)}
                    for s in segmentos for w in (s.words or []) if w.word.strip()]
    except Exception as exc:  # noqa: BLE001 — sin oído se edita igual, solo sin subtítulos
        ultimo_error = f"No pude escuchar {ruta.name}: {exc}"[:200]
        print("    " + ultimo_error, flush=True)
        return []
    cache.write_text(json.dumps(palabras, ensure_ascii=False), encoding="utf-8")
    return palabras


# ---------- armar el orden de las piezas ----------
def bloque_de(para: str) -> str:
    t = _norm(para)
    m = re.search(r"gancho\s*([abc])\b", t)
    if m:
        return f"gancho_{m.group(1).upper()}"
    for clave, b in (("puente", "puente"), ("problema", "problema"), ("soluc", "solucion"), ("demo", "solucion"),
                     ("benefic", "beneficios"), ("carrito", "cta"), ("llamado", "cta"), ("accion", "cta"), ("cta", "cta")):
        if clave in t:
            return b
    return "solucion"


def _partir(src: Path, ini: float, fin: float, bloque: str) -> list[dict]:
    """Una toma larga se parte en pedazos de ~2 s que alternan acercamiento (parece cambio de toma)."""
    largo = fin - ini
    n = max(1, round(largo / CORTE)) if largo > CORTE * 1.45 else 1
    return [{"src": src, "ini": ini + largo * k / n, "dur": largo / n, "bloque": bloque, "zoom": 1.12 if k % 2 else 1.0}
            for k in range(n)]


def piezas_por_tomas(tomas: list[dict], archivos: dict[str, Path], letra: str | None, pista: str) -> list[dict]:
    """Clips subidos uno por toma → piezas en el orden del guion (gancho elegido + cuerpo)."""
    por_bloque: dict[str, list] = {}
    for t in tomas:  # Diego las da en orden de grabación; dentro de cada bloque se respeta ese orden
        clip = archivos.get(str(t["n"]))
        if clip:
            por_bloque.setdefault(bloque_de(t.get("para", "")), []).append((t, clip))
    orden = ([f"gancho_{letra}"] if letra else []) + BLOQUES
    piezas = []
    for b in orden:
        for t, clip in por_bloque.get(b, []):
            dur = duracion(clip)
            pals = transcribir(clip, pista)
            if pals:  # habla: desde un poquito antes de la primera palabra hasta un poquito después de la última
                ini, fin = max(0.0, pals[0]["t"] - 0.15), min(dur, pals[-1]["t"] + pals[-1]["d"] + 0.3)
            else:  # toma sin voz (la demo, el producto): lo que pidió Diego, sin el arranque movido
                ini = min(0.3, dur * 0.1)
                fin = min(dur, ini + max(1.5, min(float(t.get("segundos") or 3) - 0.5, 5.0)))
            if fin - ini >= 0.4:
                piezas += _partir(clip, ini, fin, b)
    return piezas


CLASIFICA = {
    "type": "object", "additionalProperties": False, "required": ["trozos"],
    "properties": {"trozos": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["i", "parte"],
        "properties": {"i": {"type": "integer"},
                       "parte": {"type": "string", "enum": ["gancho_A", "gancho_B", "gancho_C", *BLOQUES, "descartar"]}}}}},
}


def clasificar(trozos: list[dict], guion: dict) -> list[str]:
    """Con el video completo: Claude Haiku dice qué parte del guion es cada trozo (fracciones de centavo)."""
    lineas = [f"Gancho {g['letra']}: {g['voz'] or g['texto_pantalla']}" for g in guion["ganchos"]]
    lineas += [f"{c['bloque']}: {c['voz']}" for c in guion["cuerpo"]]
    pedido = ("Guion:\n" + "\n".join(lineas) + "\n\nLo que dijo Miguel en su video, en trozos:\n"
              + "\n".join(f"[{i}] {t['texto']}" for i, t in enumerate(trozos))
              + "\n\nDi a qué parte del guion corresponde cada trozo. 'descartar' si es un error, una prueba, algo que "
                "no va (\"¿ya está grabando?\", \"otra vez\"). Si repitió una parte, marca las dos igual.")
    r = ia.json_estructurado("Eres Cris, editor de videos de TikTok Shop.", pedido, CLASIFICA, tarea="tomas_shop",
                             que="ordenar el video completo")
    partes = {t["i"]: t["parte"] for t in r["trozos"]}
    return [partes.get(i, "descartar") for i in range(len(trozos))]


def piezas_por_completo(video: Path, guion: dict, letra: str | None, pista: str) -> list[dict]:
    """Un solo video con todo → quita silencios y tomas repetidas y acomoda las partes según el guion."""
    dur = duracion(video)
    pals = transcribir(video, pista)
    if not pals:  # sin voz que escuchar: el video tal cual, con acercamientos
        return _partir(video, 0.0, dur, "solucion")
    trozos, actual = [], [pals[0]]
    for p in pals[1:]:
        if p["t"] - (actual[-1]["t"] + actual[-1]["d"]) > 0.6:
            trozos.append(actual)
            actual = []
        actual.append(p)
    trozos.append(actual)
    trozos = [{"ini": max(0.0, t[0]["t"] - 0.12), "fin": min(dur, t[-1]["t"] + t[-1]["d"] + 0.25),
               "texto": " ".join(p["w"] for p in t)} for t in trozos]
    partes = clasificar(trozos, guion)
    for t, parte in zip(trozos, partes):
        t["parte"] = parte
    # tomas repetidas: si dijo casi lo mismo dos veces, se queda la última
    for i, t in enumerate(trozos):
        for u in trozos[i + 1:]:
            if t["parte"] != "descartar" and difflib.SequenceMatcher(None, _norm(t["texto"]), _norm(u["texto"])).ratio() > 0.62:
                t["parte"] = "descartar"
                break
    elegidos = [t for t in trozos if t["parte"] == f"gancho_{letra}"] if letra else []
    elegidos += [t for t in trozos if t["parte"] in BLOQUES]
    piezas = []
    for t in elegidos:
        piezas += _partir(video, t["ini"], t["fin"], t["parte"])
    return piezas


# ---------- textos y subtítulos ----------
def _ass_tiempo(s: float) -> str:
    s = max(0.0, s)
    h, r = divmod(s, 3600)
    m, r = divmod(r, 60)
    return f"{int(h)}:{int(m):02d}:{r:05.2f}"


def _ass_texto(t: str) -> str:
    return (t or "").replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def _subtitulos(destino: Path, tramos: list[tuple], palabras: list[dict], guion: dict, letra: str | None) -> None:
    """Texto en pantalla de Sofi arriba (zona segura) y karaoke de tu voz abajo, sin tapar los botones de TikTok."""
    textos = {f"gancho_{g['letra']}": [g["texto_pantalla"]] for g in guion["ganchos"]}
    for c in guion["cuerpo"]:
        textos.setdefault(c["bloque"], []).append(c["texto_pantalla"])
    eventos = []
    for bloque, ini, fin in tramos:
        lista = [t for t in textos.get(bloque, []) if t]
        for k, t in enumerate(lista):
            a, b = ini + (fin - ini) * k / len(lista), ini + (fin - ini) * (k + 1) / len(lista)
            eventos.append(f"Dialogue: 1,{_ass_tiempo(a)},{_ass_tiempo(b)},Texto,,0,0,0,,"
                           f"{{\\fscx70\\fscy70\\t(0,140,\\fscx100\\fscy100)}}{_ass_texto(t.upper())}")
    for k in range(0, len(palabras), 3):  # karaoke: 3 palabras por línea, la que dices se ilumina y salta
        grupo = palabras[k:k + 3]
        fin_grupo = min(palabras[k + 3]["t"] if k + 3 < len(palabras) else grupo[-1]["t"] + grupo[-1]["d"] + 0.5,
                        grupo[-1]["t"] + grupo[-1]["d"] + 0.5)
        ws = [_ass_texto(p["w"].upper()) for p in grupo]
        for j, p in enumerate(grupo):
            a = grupo[0]["t"] if j == 0 else p["t"]
            b = grupo[j + 1]["t"] if j + 1 < len(grupo) else fin_grupo
            linea = " ".join((f"{{\\c&H003FD2FF&\\fscx115\\fscy115\\t(0,90,\\fscx106\\fscy106)}}{w}{{\\r}}" if q == j else w)
                             for q, w in enumerate(ws))
            if b > a:
                eventos.append(f"Dialogue: 0,{_ass_tiempo(a)},{_ass_tiempo(b)},Karaoke,,0,0,0,,{linea}")
    cabeza = (f"[Script Info]\nScriptType: v4.00+\nPlayResX: {ANCHO}\nPlayResY: {ALTO}\nWrapStyle: 0\n"
              "ScaledBorderAndShadow: yes\n\n[V4+ Styles]\n"
              "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
              "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
              "MarginR, MarginV, Encoding\n"
              # texto en pantalla: arriba, debajo del 15 % de arriba, en caja negra como en TikTok
              f"Style: Texto,{FUENTE},66,&H00FFFFFF,&H00FFFFFF,&H30000000,&H00000000,-1,0,0,0,100,100,0,0,3,16,0,8,"
              f"60,{MARGEN_DER},{int(ALTO * 0.17)},1\n"
              # karaoke: arriba del 20 % de abajo
              f"Style: Karaoke,{FUENTE},70,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,6,2,2,"
              f"60,{MARGEN_DER},{int(ALTO * 0.24)},1\n\n[Events]\n"
              "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    destino.write_text(cabeza + "\n".join(eventos) + "\n", encoding="utf-8")


# ---------- render ----------
def render(piezas: list[dict], guion: dict, letra: str | None, destino: Path, pista: str, al_avanzar=None) -> float:
    if not piezas:
        raise ErrorEdicion("No hay tomas que usar. Sube al menos un clip.")
    trabajo = destino.parent / f"edicion_{letra or 'x'}"
    shutil.rmtree(trabajo, ignore_errors=True)
    trabajo.mkdir(parents=True)
    partes, palabras, tramos, t0 = [], [], [], 0.0
    for k, p in enumerate(piezas):
        if al_avanzar:
            al_avanzar(f"Cortando toma {k + 1} de {len(piezas)}", 0.05 + 0.75 * k / len(piezas))
        z = p["zoom"]
        w, h = int(ANCHO * z) // 2 * 2, int(ALTO * z) // 2 * 2
        vf = (f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={ANCHO}:{ALTO},setsar=1,fps={FPS},format=yuv420p")
        salida = trabajo / f"p{k:03d}.mp4"
        if tiene_audio(p["src"]):
            _ff("-ss", f"{p['ini']:.3f}", "-t", f"{p['dur']:.3f}", "-i", str(p["src"]), "-vf", vf,
                "-af", "aformat=sample_rates=44100:channel_layouts=stereo", *RAPIDO, *AUDIO, str(salida))
        else:
            _ff("-ss", f"{p['ini']:.3f}", "-t", f"{p['dur']:.3f}", "-i", str(p["src"]), "-f", "lavfi",
                "-i", "anullsrc=r=44100:cl=stereo", "-vf", vf, "-map", "0:v", "-map", "1:a", "-shortest",
                *RAPIDO, *AUDIO, str(salida))
        real = duracion(salida)
        for x in transcribir(p["src"], pista):  # las palabras de esta pieza, en el tiempo del video final
            if p["ini"] <= x["t"] < p["ini"] + p["dur"]:
                palabras.append({**x, "t": t0 + x["t"] - p["ini"]})
        if tramos and tramos[-1][0] == p["bloque"]:
            tramos[-1] = (p["bloque"], tramos[-1][1], t0 + real)
        else:
            tramos.append((p["bloque"], t0, t0 + real))
        partes.append(salida)
        t0 += real
    lista = trabajo / "lista.txt"
    lista.write_text("".join(f"file '{x.name}'\n" for x in partes), encoding="utf-8")
    base = trabajo / "base.mp4"
    _ff("-f", "concat", "-safe", "0", "-i", str(lista), "-c", "copy", str(base))
    # cuadro limpio (sin textos) para la portada de Vale: a la mitad de la demo
    momento = next(((a + b) / 2 for bloque, a, b in tramos if bloque == "solucion"), t0 * 0.45)
    _ff("-ss", f"{momento:.2f}", "-i", str(base), "-frames:v", "1", "-q:v", "2",
        str(destino.with_name(f"{destino.stem}.cuadro.jpg")))
    subs = trabajo / "textos.ass"
    _subtitulos(subs, tramos, palabras, guion, letra)
    if al_avanzar:
        al_avanzar("Poniendo textos y subtítulos", 0.85)
    # ass= se resuelve desde la carpeta de trabajo (evita problemas con rutas raras)
    r = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", "base.mp4", "-vf", "ass=textos.ass",
                        "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", *FINAL, *AUDIO, str(destino.resolve())],
                       cwd=trabajo, capture_output=True, text=True)
    if r.returncode:
        raise ErrorEdicion("ffmpeg falló al poner los textos: " + (r.stderr.strip().splitlines() or [""])[-1][:200])
    shutil.rmtree(trabajo, ignore_errors=True)
    return t0


# ---------- Vale: portada ----------
def _fuente(tam: int):
    try:
        return ImageFont.truetype(FUENTE_TTF, tam)
    except OSError:
        return ImageFont.load_default(tam)


def portada(video: Path, texto: str, destino: Path) -> None:
    """Un cuadro de la demo (o de la mitad) con el texto del gancho, grande y en la zona segura."""
    cuadro = video.with_name(f"{video.stem}.cuadro.jpg")  # lo deja render(), sin textos encima
    if not cuadro.exists():
        _ff("-ss", f"{duracion(video) * 0.45:.2f}", "-i", str(video), "-frames:v", "1", "-q:v", "2", str(cuadro))
    img = Image.open(cuadro).convert("RGB").resize((ANCHO, ALTO))
    sombra = Image.new("L", (ANCHO, ALTO), 0)
    d = ImageDraw.Draw(sombra)
    for y in range(int(ALTO * 0.55)):  # oscurece arriba para que el texto se lea
        d.line([(0, y), (ANCHO, y)], fill=int(150 * (1 - y / (ALTO * 0.55))))
    img = Image.composite(Image.new("RGB", (ANCHO, ALTO), (0, 0, 0)), img, sombra)
    texto = (texto or "").upper().strip()
    ancho_max = ANCHO - 60 - MARGEN_DER
    for tam in range(118, 54, -6):
        f = _fuente(tam)
        lineas, linea = [], ""
        for palabra in texto.split():
            prueba = f"{linea} {palabra}".strip()
            if f.getlength(prueba) <= ancho_max or not linea:
                linea = prueba
            else:
                lineas.append(linea)
                linea = palabra
        lineas.append(linea)
        if len(lineas) <= 4:
            break
    d = ImageDraw.Draw(img)
    y = int(ALTO * 0.2)
    for linea in lineas:
        x = 60 + (ancho_max - f.getlength(linea)) / 2
        d.text((x, y), linea, font=f, fill=(255, 210, 63), stroke_width=max(6, tam // 11), stroke_fill=(0, 0, 0))
        y += int(tam * 1.18)
    img.save(destino, "JPEG", quality=90)
    cuadro.unlink(missing_ok=True)
