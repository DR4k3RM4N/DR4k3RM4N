"""Agente 5 — Editor: arma el video final con ffmpeg.

Escenas con zoom suave, transiciones, voz, subtítulos (estilo shorts o clásicos), barra de progreso,
música, sonido en los cambios de escena y tu intro/outro. Los ajustes salen de la pestaña Estilo.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import threading
from pathlib import Path

from . import config, estilo, graficos

FPS = 30
# Pasadas intermedias en modo rápido y casi sin pérdida; solo la final se comprime con cuidado.
RAPIDO = ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "16", "-pix_fmt", "yuv420p", "-r", str(FPS), "-threads", "2"]
VIDEO = ["-c:v", "libx264", "-preset", "faster", "-crf", "21", "-pix_fmt", "yuv420p", "-r", str(FPS), "-threads", "2"]
AUDIO = ["-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2"]
TRANSICION = 0.35  # segundos
VARIADAS = ["fade", "slideleft", "smoothup", "circleopen", "wipeleft", "smoothright", "fadeblack", "slideup"]
GRUPO = 6  # escenas por grupo al unir con transiciones (abrir todas a la vez se come la memoria)

contexto = threading.local()  # la oficina pone contexto.al_avanzar(paso, fraccion) para ver el avance real


def _avance(paso: str, fraccion: float) -> None:
    cb = getattr(contexto, "al_avanzar", None)
    if cb:
        try:
            cb(paso, max(0.0, min(1.0, fraccion)))
        except Exception:  # noqa: BLE001 — informar nunca debe romper la edición
            pass


def _ff(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args], check=True)


def _ff_avance(args: list[str], duracion: float, paso: str, desde: float, hasta: float) -> None:
    """Corre ffmpeg informando el avance (lee su salida -progress)."""
    p = subprocess.Popen(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-progress", "pipe:1", "-nostats", *args],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    for linea in p.stdout:
        if linea.startswith("out_time_us=") and duracion > 0:
            try:
                t = int(linea.split("=", 1)[1]) / 1e6
            except ValueError:
                continue
            _avance(f"{paso} {min(99, int(t / duracion * 100))}%", desde + (hasta - desde) * min(1, t / duracion))
    err = p.stderr.read()
    if p.wait() != 0:
        raise subprocess.CalledProcessError(p.returncode, "ffmpeg", stderr=err)


def _duracion(ruta: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(ruta)],
                         capture_output=True, text=True, check=True).stdout.strip()
    return float(out or 0)


def _tiene_audio(ruta: Path) -> bool:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                          "-of", "csv=p=0", str(ruta)], capture_output=True, text=True).stdout.strip()
    return bool(out)


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


ZOOM = {"suave": (0.0006, 1.08), "medio": (0.0010, 1.12), "fuerte": (0.0016, 1.18)}


def _segmento_imagen(png: Path, audio: str, dur: float, destino: Path, i: int, extra: float,
                     zoom: str = "suave", corte_cada: float = 0) -> None:
    """`extra`: segundos de más al final para que la transición no corte la voz.
    `corte_cada`: cada cuántos segundos hay un "golpe" de zoom y cambio de encuadre (ritmo de cortes)."""
    total = dur + extra
    frames = int(total * FPS) + 1
    inc, zmax = ZOOM.get(zoom, ZOOM["suave"])
    z = f"min(1+{inc}*on,{zmax})" if i % 2 else f"max({zmax}-{inc}*on,1)"
    x = "iw/2-(iw/zoom/2)"
    if corte_cada and corte_cada < total:
        P = max(15, int(corte_cada * FPS))
        z += f"+if(lt(mod(on,{P}),4),0.06*(1-mod(on,{P})/4),0)"
        x += f"+if(mod(floor(on/{P}),2),iw*0.02,-iw*0.02)"
    _ff("-loop", "1", "-framerate", str(FPS), "-i", str(png), "-i", audio,
        "-filter_complex",
        f"[0]scale=2304:-2,zoompan=z='{z}':x='{x}':y='ih/2-(ih/zoom/2)'"
        f":d={frames}:s=1920x1080:fps={FPS},setsar=1[v];[1:a]apad,aformat=sample_rates=44100:channel_layouts=stereo[a]",
        "-map", "[v]", "-map", "[a]", "-t", f"{total:.3f}", *RAPIDO, *AUDIO, str(destino))


def _segmento_clip(clip: str, audio: str, dur: float, destino: Path, extra: float) -> None:
    """Grabación de pantalla del celular (vertical) sobre fondo desenfocado, sin su audio original."""
    _ff("-stream_loop", "-1", "-i", clip, "-i", audio,
        "-filter_complex",
        "[0:v]split[a][b];"
        "[a]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,boxblur=30:5,eq=brightness=-0.15[bg];"
        f"[b]scale=-2:1020[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1,fps={FPS}[v];"
        "[1:a]apad,aformat=sample_rates=44100:channel_layouts=stereo[au]",
        "-map", "[v]", "-map", "[au]", "-t", f"{dur + extra:.3f}", *RAPIDO, *AUDIO, str(destino))


def _tiempo(s: float) -> str:
    h, r = divmod(s, 3600)
    m, s = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int((s % 1) * 1000):03d}"


def subtitulos(escenas: list[dict], destino: Path, palabras_por_linea: int = 7, mayusculas: bool = False) -> Path:
    """SRT a partir de la narración, repartiendo el tiempo de cada escena por palabras."""
    bloques, t, n = [], 0.0, 1
    for esc in escenas:
        palabras = esc["narracion"].split()
        total = max(len(palabras), 1)
        for k in range(0, len(palabras), palabras_por_linea):
            trozo = palabras[k:k + palabras_por_linea]
            ini = t + esc["duracion"] * k / total
            fin = t + esc["duracion"] * min(k + len(trozo), total) / total
            linea = " ".join(trozo)
            bloques.append(f"{n}\n{_tiempo(ini)} --> {_tiempo(fin)}\n{linea.upper() if mayusculas else linea}\n")
            n += 1
        t += esc["duracion"]
    destino.write_text("\n".join(bloques), encoding="utf-8")
    return destino


def _ass_color(hex_: str) -> str:
    """#RRGGBB → &H00BBGGRR (formato de colores de los subtítulos)."""
    h = (hex_ or "#FFFFFF").lstrip("#")
    return f"&H00{h[4:6]}{h[2:4]}{h[0:2]}".upper()


def _xfade(partes: list[Path], duraciones: list[float], tipos: list[str], destino: Path, trabajo: Path,
           nombre: str, extra_final: float) -> None:
    """Une pocas piezas con transiciones en un solo ffmpeg. `duraciones` = lo que dura cada pieza sin el
    relleno de la transición; `extra_final` = relleno que conserva la última pieza."""
    filtros, v_prev, a_prev, offset = [], "[0:v]", "[0:a]", 0.0
    for k in range(1, len(partes)):
        offset += duraciones[k - 1]
        v_sal, a_sal = (f"[v{k}]", f"[a{k}]") if k < len(partes) - 1 else ("[vout]", "[aout]")
        filtros.append(f"{v_prev}[{k}:v]xfade=transition={tipos[k - 1]}:duration={TRANSICION}:offset={offset:.3f}{v_sal}")
        filtros.append(f"{a_prev}[{k}:a]acrossfade=d={TRANSICION}:c1=tri:c2=tri{a_sal}")
        v_prev, a_prev = v_sal, a_sal
    script = trabajo / f"{nombre}.txt"
    script.write_text(";\n".join(filtros), encoding="utf-8")
    entradas = [x for p in partes for x in ("-i", str(p))]
    _ff(*entradas, "-filter_complex_script", str(script), "-map", "[vout]", "-map", "[aout]", *RAPIDO, *AUDIO, str(destino))


def _unir(partes: list[Path], duraciones: list[float], transicion: str, destino: Path, trabajo: Path) -> list[float]:
    """Une las escenas. Con transición las une por grupos pequeños (para no quedarse sin memoria) y luego
    une los grupos. Devuelve en qué segundo empieza cada cambio de escena."""
    cambios, t = [], 0.0
    for d in duraciones[:-1]:
        t += d
        cambios.append(t)
    if transicion == "corte" or len(partes) < 2:
        lista = trabajo / "lista.txt"
        lista.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in partes), encoding="utf-8")
        _ff("-f", "concat", "-safe", "0", "-i", str(lista), "-c", "copy", str(destino))
        return cambios
    tipos_base = {"fundido": ["fade"], "deslizar": ["slideleft"]}.get(transicion, VARIADAS)
    tipos = [tipos_base[k % len(tipos_base)] for k in range(len(partes) - 1)]
    grupos, k = [], 0
    while k < len(partes):
        grupos.append(list(range(k, min(k + GRUPO, len(partes)))))
        k += GRUPO
    piezas, duraciones_piezas = [], []
    for g, idx in enumerate(grupos):
        _avance(f"Uniendo transiciones (grupo {g + 1} de {len(grupos)})", 0.6 + 0.15 * g / len(grupos))
        salida = trabajo / f"grupo_{g:02d}.mp4"
        if len(idx) == 1:
            salida = partes[idx[0]]
        else:
            _xfade([partes[i] for i in idx], [duraciones[i] for i in idx], [tipos[i] for i in idx[:-1]],
                   salida, trabajo, f"grupo_{g:02d}", TRANSICION)
        piezas.append(salida)
        duraciones_piezas.append(sum(duraciones[i] for i in idx))  # el grupo conserva el relleno del final
    if len(piezas) == 1:
        _ff("-i", str(piezas[0]), "-c", "copy", str(destino))
        return cambios
    _avance("Uniendo los grupos", 0.76)
    union = [tipos[grupos[g + 1][0] - 1] for g in range(len(grupos) - 1)]
    _xfade(piezas, duraciones_piezas, union, destino, trabajo, "union", TRANSICION)
    return cambios


def _normalizar(entrada: Path, destino: Path) -> Path:
    """Intro/outro al mismo formato que el video (1920x1080, 30 fps, audio estéreo) para poder unirlos."""
    v = (f"[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black,"
         f"setsar=1,fps={FPS}[v]")
    if _tiene_audio(entrada):
        _ff("-i", str(entrada), "-filter_complex", v + ";[0:a]aformat=sample_rates=44100:channel_layouts=stereo[a]",
            "-map", "[v]", "-map", "[a]", *VIDEO, *AUDIO, str(destino))
    else:
        _ff("-i", str(entrada), "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-filter_complex", v,
            "-map", "[v]", "-map", "1:a", "-shortest", *VIDEO, *AUDIO, str(destino))
    return destino


def editar(escenas: list[dict], ctx: dict, carpeta: Path, clips: list[str]) -> Path:
    datos = estilo.cargar()
    ajustes, spec = datos["ajustes"], {**graficos.ESTILO_DEFECTO, **(datos.get("miniaturas") or {})}
    extra = 0.0 if ajustes["transicion"] == "corte" else TRANSICION
    trabajo = carpeta / "edicion"
    trabajo.mkdir(parents=True, exist_ok=True)
    partes, duraciones = [], []
    for i, esc in enumerate(escenas, 1):
        # nombre según lo que lleva la escena: si nada cambió y ya existe, se reutiliza
        firma = hashlib.sha1(json.dumps([esc.get("narracion"), esc.get("visual"), esc.get("indice"), esc.get("texto"),
                                         round(esc["duracion"], 3), extra, ajustes.get("zoom"), ajustes.get("corte_cada"),
                                         spec.get("color_acento")], ensure_ascii=False).encode()).hexdigest()[:10]
        seg = trabajo / f"seg_{i:02d}_{firma}.mp4"
        _avance(f"Escena {i} de {len(escenas)}", 0.6 * (i - 1) / len(escenas))
        try:
            if seg.exists() and _duracion(seg) >= esc["duracion"] + extra - 0.2:
                partes.append(seg)
                duraciones.append(esc["duracion"])
                print(f"  · escena {i}/{len(escenas)} ya estaba hecha")
                continue
        except (subprocess.CalledProcessError, ValueError):
            pass
        seg.unlink(missing_ok=True)
        if esc["visual"] == "grabacion" and clips:
            _segmento_clip(clips[(max(esc.get("indice", 1), 1) - 1) % len(clips)], esc["audio"], esc["duracion"], seg, extra)
        else:
            png = _imagen_escena(esc, i, ctx, trabajo)
            _segmento_imagen(png, esc["audio"], esc["duracion"], seg, i, extra,
                             ajustes.get("zoom", "suave"), float(ajustes.get("corte_cada") or 0))
        partes.append(seg)
        duraciones.append(esc["duracion"])
        print(f"  · escena {i}/{len(escenas)} lista")

    unido = trabajo / "unido.mp4"
    cambios = _unir(partes, duraciones, ajustes["transicion"], unido, trabajo)
    duracion = _duracion(unido)

    # subtítulos
    grande = ajustes["subtitulos"] == "grande"
    palabras = int(ajustes.get("palabras_subtitulo") or 0) or (3 if grande else 7)
    srt = subtitulos(escenas, carpeta / "subtitulos.srt", palabras, bool(ajustes.get("mayusculas_subtitulo")))
    color_sub = ajustes.get("color_subtitulo") or spec["color_texto"]
    borde_sub = ajustes.get("color_borde_subtitulo") or "#000000"
    centro = ajustes.get("posicion_subtitulo") == "centro"
    fuente_propia = estilo.archivo("fuente")
    nombre_fuente = "DejaVu Sans"
    if fuente_propia:
        try:
            nombre_fuente = graficos.ImageFont.truetype(str(fuente_propia), 20).getname()[0]
        except OSError:
            fuente_propia = None
    if grande:
        sub = (f"FontName={nombre_fuente},Bold=1,FontSize=24,PrimaryColour={_ass_color(color_sub)},"
               f"OutlineColour={_ass_color(borde_sub)},BorderStyle=1,Outline=3,Shadow=1,"
               f"Alignment=2,MarginV={125 if centro else 70}")
    else:
        sub = (f"FontName={nombre_fuente},Bold=1,FontSize=13,PrimaryColour={_ass_color(ajustes.get('color_subtitulo') or '#FFFFFF')},"
               f"OutlineColour=&H00000000,BackColour=&H99000000,BorderStyle=3,Outline=6,Shadow=0,"
               f"Alignment=2,MarginV={125 if centro else 24}")
    srt_filtro = srt.resolve().as_posix().replace(":", r"\:")
    vf = f"subtitles='{srt_filtro}':force_style='{sub}'"
    if fuente_propia:
        vf += f":fontsdir='{fuente_propia.parent.resolve().as_posix()}'"

    entradas = ["-i", str(unido)]
    filtros = [f"[0:v]{vf}[vs]"]
    v_final = "[vs]"
    if ajustes["barra_progreso"]:
        color = spec["color_acento"].lstrip("#")
        filtros.append(f"color=c=0x{color}:s=1920x10:r={FPS}[barra]")
        filtros.append(f"[vs][barra]overlay=x='-w+w*t/{duracion:.3f}':y=H-h:shortest=1[vb]")
        v_final = "[vb]"
    mezcla = ["[0:a]"]
    musica = estilo.archivo("musica")
    if musica:
        entradas += ["-stream_loop", "-1", "-i", str(musica)]
        filtros.append(f"[{entradas.count('-i') - 1}:a]volume=0.07[m]")
        mezcla.append("[m]")
    whoosh = estilo.archivo("whoosh")
    if ajustes["sonido_cambios"] and whoosh and cambios:
        entradas += ["-i", str(whoosh)]
        idx = entradas.count("-i") - 1
        filtros.append(f"[{idx}:a]volume=0.5,asplit={len(cambios)}" + "".join(f"[w{k}]" for k in range(len(cambios))))
        for k, t in enumerate(cambios):
            ms = max(0, int((t - 0.15) * 1000))
            filtros.append(f"[w{k}]adelay={ms}|{ms}[wd{k}]")
            mezcla.append(f"[wd{k}]")
    if len(mezcla) > 1:
        filtros.append("".join(mezcla) + f"amix=inputs={len(mezcla)}:duration=first:normalize=0[a]")
        a_final = "[a]"
    else:
        a_final = "0:a"
    script = trabajo / "final.txt"
    script.write_text(";\n".join(filtros), encoding="utf-8")
    principal = trabajo / "principal.mp4"
    _ff_avance([*entradas, "-filter_complex_script", str(script), "-map", v_final, "-map", a_final,
                "-t", f"{duracion:.3f}", *VIDEO, *AUDIO, str(principal)], duracion, "Subtítulos y música", 0.8, 0.97)
    _avance("Últimos detalles", 0.98)

    # intro y outro del canal
    final = carpeta / "video.mp4"
    piezas = []
    for tipo in ("intro", None, "outro"):
        if tipo is None:
            piezas.append(principal)
        elif estilo.archivo(tipo):
            piezas.append(_normalizar(estilo.archivo(tipo), trabajo / f"{tipo}.mp4"))
    if len(piezas) > 1:
        lista = trabajo / "piezas.txt"
        lista.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in piezas), encoding="utf-8")
        _ff("-f", "concat", "-safe", "0", "-i", str(lista), "-c", "copy", "-movflags", "+faststart", str(final))
    else:
        _ff("-i", str(principal), "-c", "copy", "-movflags", "+faststart", str(final))
    (carpeta / "edicion.json").write_text(json.dumps({"ajustes": ajustes, "cambios": cambios, "duracion": duracion,
                                                      "intro": bool(estilo.archivo("intro")), "outro": bool(estilo.archivo("outro"))},
                                                     ensure_ascii=False, indent=1), encoding="utf-8")
    # Los pedazos ya no sirven (se regeneran si se re-edita) y ocupan mucho disco.
    for f in trabajo.glob("*.mp4"):
        f.unlink(missing_ok=True)
    _avance("Listo", 1.0)
    return final
