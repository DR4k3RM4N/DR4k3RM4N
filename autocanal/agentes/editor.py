"""Agente 5 — Editor: arma el video final con ffmpeg (escenas + voz + subtítulos + música)."""
from __future__ import annotations

import subprocess
from pathlib import Path

from . import config, graficos

FPS = 30
VIDEO = ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS)]
AUDIO = ["-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2"]


def _ff(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args], check=True)


def _imagen_escena(esc: dict, i: int, ctx: dict, carpeta: Path) -> Path:
    destino = carpeta / f"escena_{i:02d}.png"
    icono = ctx["imagenes"].get("icono")
    tipo, idx = esc["visual"], esc.get("indice", 0)
    if tipo == "captura":
        caps = ctx["imagenes"].get("capturas") or []
        ruta = caps[(max(idx, 1) - 1) % len(caps)] if caps else None
        return graficos.tarjeta_captura(ruta, icono, destino, esc.get("texto", ""))
    if tipo == "resena":
        citadas = ctx["expediente"].get("resenas_citadas") or []
        if citadas:
            return graficos.tarjeta_resena(citadas[idx % len(citadas)], icono, destino)
        return graficos.tarjeta_dato(esc.get("texto") or "Reseñas", icono, destino)
    if tipo == "veredicto":
        return graficos.tarjeta_veredicto(ctx["expediente"]["veredicto"], icono, destino, esc.get("texto", ""))
    if tipo == "dato":
        return graficos.tarjeta_dato(esc.get("texto") or "", icono, destino)
    return graficos.tarjeta_titulo(esc.get("texto") or ctx["ficha"]["title"], icono, destino)


def _segmento_imagen(png: Path, audio: str, dur: float, destino: Path, i: int) -> None:
    frames = int(dur * FPS) + 1
    # Zoom lento alternando entrada/salida para que no se vea estático.
    z = "min(1+0.0006*on,1.08)" if i % 2 else "max(1.08-0.0006*on,1)"
    _ff("-loop", "1", "-framerate", str(FPS), "-i", str(png), "-i", audio,
        "-filter_complex",
        f"[0]scale=2880:-2,zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":d={frames}:s=1920x1080:fps={FPS}[v]",
        "-map", "[v]", "-map", "1:a", "-t", f"{dur:.3f}", *VIDEO, *AUDIO, str(destino))


def _segmento_clip(clip: str, audio: str, dur: float, destino: Path) -> None:
    """Grabación de pantalla del celular (vertical) sobre fondo desenfocado, sin su audio original."""
    _ff("-stream_loop", "-1", "-i", clip, "-i", audio,
        "-filter_complex",
        "[0:v]split[a][b];"
        "[a]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,boxblur=30:5,eq=brightness=-0.15[bg];"
        "[b]scale=-2:1020[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[v]",
        "-map", "[v]", "-map", "1:a", "-t", f"{dur:.3f}", *VIDEO, *AUDIO, str(destino))


def _tiempo(s: float) -> str:
    h, r = divmod(s, 3600)
    m, s = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int((s % 1) * 1000):03d}"


def subtitulos(escenas: list[dict], destino: Path, palabras_por_linea: int = 7) -> Path:
    """SRT a partir de la narración, repartiendo el tiempo de cada escena por palabras."""
    bloques, t, n = [], 0.0, 1
    for esc in escenas:
        palabras = esc["narracion"].split()
        total = max(len(palabras), 1)
        for k in range(0, len(palabras), palabras_por_linea):
            trozo = palabras[k:k + palabras_por_linea]
            ini = t + esc["duracion"] * k / total
            fin = t + esc["duracion"] * min(k + len(trozo), total) / total
            bloques.append(f"{n}\n{_tiempo(ini)} --> {_tiempo(fin)}\n{' '.join(trozo)}\n")
            n += 1
        t += esc["duracion"]
    destino.write_text("\n".join(bloques), encoding="utf-8")
    return destino


def editar(escenas: list[dict], ctx: dict, carpeta: Path, clips: list[str]) -> Path:
    trabajo = carpeta / "edicion"
    trabajo.mkdir(parents=True, exist_ok=True)
    partes = []
    for i, esc in enumerate(escenas, 1):
        seg = trabajo / f"seg_{i:02d}.mp4"
        if esc["visual"] == "grabacion" and clips:
            _segmento_clip(clips[(max(esc.get("indice", 1), 1) - 1) % len(clips)], esc["audio"], esc["duracion"], seg)
        else:
            png = _imagen_escena(esc, i, ctx, trabajo)
            _segmento_imagen(png, esc["audio"], esc["duracion"], seg, i)
        partes.append(seg)
        print(f"  · escena {i}/{len(escenas)} lista")

    lista = trabajo / "lista.txt"
    lista.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in partes), encoding="utf-8")
    unido = trabajo / "unido.mp4"
    _ff("-f", "concat", "-safe", "0", "-i", str(lista), "-c", "copy", str(unido))

    srt = subtitulos(escenas, carpeta / "subtitulos.srt")
    estilo = ("FontName=DejaVu Sans,Bold=1,FontSize=13,PrimaryColour=&H00FFFFFF,"
              "OutlineColour=&H00000000,BackColour=&H99000000,BorderStyle=3,Outline=6,Shadow=0,MarginV=24")
    # Rutas para el filtro subtitles (escapar ':' en Windows).
    srt_filtro = srt.resolve().as_posix().replace(":", r"\:")
    vf = f"subtitles='{srt_filtro}':force_style='{estilo}'"

    final = carpeta / "video.mp4"
    musica = config.ASSETS / "musica.mp3"
    if musica.exists():
        _ff("-i", str(unido), "-stream_loop", "-1", "-i", str(musica),
            "-filter_complex", f"[0:v]{vf}[v];[1:a]volume=0.07[m];[0:a][m]amix=inputs=2:duration=first:normalize=0[a]",
            "-map", "[v]", "-map", "[a]", *VIDEO, *AUDIO, "-movflags", "+faststart", str(final))
    else:
        _ff("-i", str(unido), "-vf", vf, *VIDEO, "-c:a", "copy", "-movflags", "+faststart", str(final))
    return final
