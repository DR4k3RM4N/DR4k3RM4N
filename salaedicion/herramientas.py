"""Herramientas del editor (Claude Code en tu compu). Se usan desde la terminal de Claude Code:

    python herramientas.py ficha  [carpeta]            # todos los clips: qué dicen (con tiempos), calidad y hoja de cuadros
    python herramientas.py cuadros CLIP DESDE HASTA [N] # N cuadros de un tramo, para comparar tomas de cerca
    python herramientas.py transcribir ARCHIVO          # palabras con tiempos (JSON) para subtítulos con estilo
    python herramientas.py armar PLAN.json SALIDA.mp4   # el motor de cortes de la sala (silencios, muletillas, música…)
    python herramientas.py motion PROPS.json SALIDA.mp4 # motion graphics (Remotion) encima de un video base
    python herramientas.py revisar VIDEO                # cuadros + lo que se oye del video terminado, para revisarlo
    python herramientas.py codificar                    # qué opciones de ffmpeg usar en esta compu (NVENC si hay)

Todo lo que genera va a la carpeta _editor del proyecto (nunca toca tus clips)."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path[:0] = [str(AQUI), str(AQUI.parent / "tiktokshop"), str(AQUI.parent / "autocanal")]

import compu  # noqa: E402 — trae el ffmpeg de Windows sin ventanas, el análisis y el oído
import cris  # noqa: E402

EXT_VIDEO = compu.EXT_VIDEO
TRABAJO = Path(os.environ.get("SALA_EDITOR_DIR") or Path.cwd())  # la carpeta _editor del proyecto


def _oido() -> None:
    cris.CACHE = compu.CARPETA / "oido"
    cris.CACHE.mkdir(parents=True, exist_ok=True)
    if cris._modelo is None:
        compu.preparar_oido(bool(compu.gpu()))


def _hoja(clip: Path, tiempos: list[float], destino: Path, alto: int = 320, columnas: int = 4) -> list[float]:
    """Pega cuadros de `clip` en esos segundos (izquierda→derecha, arriba→abajo) en un JPG."""
    tmp = destino.parent / f".{destino.stem}_tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    usados = []
    for t in tiempos:
        f = tmp / f"{len(usados):03d}.jpg"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{max(0, t):.2f}", "-i", str(clip), "-frames:v", "1",
                        "-vf", f"scale=-2:{alto}", "-q:v", "4", str(f)], capture_output=True, timeout=60)
        if f.exists():
            usados.append(round(t, 2))
    if usados:
        filas = (len(usados) + columnas - 1) // columnas
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(tmp / "%03d.jpg"), "-vf",
                        f"tile={min(columnas, len(usados))}x{filas}:padding=6:color=white", "-frames:v", "1", "-q:v", "4",
                        str(destino)], capture_output=True, timeout=60)
    shutil.rmtree(tmp, ignore_errors=True)
    return usados


def ficha(carpeta: str = "..") -> None:
    base = (TRABAJO / carpeta).resolve() if not Path(carpeta).is_absolute() else Path(carpeta)
    clips = sorted(f for f in base.iterdir() if f.is_file() and f.suffix.lower() in EXT_VIDEO)
    if not clips:
        return print(f"No hay videos en {base}")
    _oido()
    vistas = TRABAJO / "vistas"
    vistas.mkdir(parents=True, exist_ok=True)
    salida = [f"# Ficha de los clips de {base}\n"]
    for clip in clips:
        a = compu.analizar(clip)
        dur = float(a.get("segundos") or cris.duracion(clip))
        n = 12 if dur > 6 else 8
        tiempos = [dur * (i + 0.5) / n for i in range(n)]
        hoja = vistas / f"{clip.stem}.jpg"
        usados = _hoja(clip, tiempos, hoja)
        malas = [f"{c[0]}-{c[1]} s {c[2]}" for c in a.get("calidad", []) if c[2] != "bien"]
        salida.append(f"## {clip.name} · {dur:.1f} s · {'con audio' if cris.tiene_audio(clip) else 'SIN audio'}\n"
                      f"Hoja de cuadros: vistas/{hoja.name} (segundos {', '.join(f'{t:.1f}' for t in usados)})\n"
                      f"Calidad: {', '.join(malas) if malas else 'bien en todo'}\n"
                      "Dice:\n" + ("\n".join(f"  [{f[0]}-{f[1]} s] {f[2]}" for f in a.get("frases", [])) or "  (no habla)") + "\n")
    (TRABAJO / "ficha.md").write_text("\n".join(salida), encoding="utf-8")
    print("\n".join(salida))
    print(f"(Guardado en {TRABAJO / 'ficha.md'}. Mira cada hoja con Read antes de decidir.)")


def cuadros(clip: str, desde: str, hasta: str, n: str = "8") -> None:
    ruta = (TRABAJO / clip) if not Path(clip).is_absolute() else Path(clip)
    if not ruta.exists():
        ruta = TRABAJO.parent / clip
    a, b, k = float(desde), float(hasta), max(2, min(16, int(n)))
    tiempos = [a + (b - a) * i / (k - 1) for i in range(k)]
    destino = TRABAJO / "vistas" / f"{ruta.stem}_{a:.1f}-{b:.1f}.jpg"
    destino.parent.mkdir(parents=True, exist_ok=True)
    usados = _hoja(ruta, tiempos, destino, alto=420)
    print(f"{destino} — segundos {', '.join(f'{t:.2f}' for t in usados)} (izquierda→derecha, arriba→abajo)")


def transcribir(archivo: str) -> None:
    ruta = (TRABAJO / archivo) if not Path(archivo).is_absolute() else Path(archivo)
    if not ruta.exists():
        ruta = TRABAJO.parent / archivo
    _oido()
    pals = cris.transcribir(ruta) if cris.tiene_audio(ruta) else []
    destino = TRABAJO / f"{ruta.stem}.palabras.json"
    destino.write_text(json.dumps(pals, ensure_ascii=False), encoding="utf-8")
    print(f"{len(pals)} palabras → {destino}")
    print(" ".join(f"[{p['t']:.2f}]{p['w']}" for p in pals))


def armar(plan: str, salida: str) -> None:
    import editor_libre
    editor_libre.analizar = compu.analizar
    _oido()
    datos = json.loads((TRABAJO / plan).read_text(encoding="utf-8"))
    musica = compu.MUSICA if compu.MUSICA.exists() else None
    info: dict = {}
    seg = editor_libre.render(editor_libre.normalizar_plan(datos), TRABAJO.parent,
                              (TRABAJO / salida).resolve(), musica, "", lambda p, f: print(f"  {int(f * 100)}% {p}", flush=True),
                              info=info)
    (TRABAJO / f"{Path(salida).stem}.info.json").write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    print(f"Listo: {salida} ({seg} s). Lo que se oye y dónde quedó cada pedazo: {Path(salida).stem}.info.json")


def motion(props: str, salida: str) -> None:
    ruta_props = (TRABAJO / props).resolve()
    datos = json.loads(ruta_props.read_text(encoding="utf-8"))
    motion_dir = AQUI / "motion"
    if not (motion_dir / "node_modules").exists():
        raise SystemExit("Remotion no está instalado todavía (la compu lo instala sola al arrancar; espera unos minutos).")
    npx = shutil.which("npx") or shutil.which("npx.cmd") or "npx"
    if datos.get("fondo") and not (ruta_props.parent / datos["fondo"]).exists():
        raise SystemExit(f"No encontré el video base {datos['fondo']} junto a {props}.")
    if not datos.get("duracion") and datos.get("fondo"):
        datos["duracion"] = round(cris.duracion(ruta_props.parent / datos["fondo"]), 3)
        ruta_props.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    cmd = [npx, "remotion", "render", "src/index.ts", "Video", str((TRABAJO / salida).resolve()), f"--props={ruta_props}",
           f"--public-dir={ruta_props.parent}", "--log=error", "--concurrency=50%"]
    if os.environ.get("SALA_CHROME"):
        cmd.append(f"--browser-executable={os.environ['SALA_CHROME']}")
    r = subprocess.run(cmd, cwd=motion_dir, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       shell=compu.WINDOWS)
    if r.returncode:
        raise SystemExit("Remotion falló:\n" + (r.stderr or r.stdout)[-1500:])
    print(f"Listo: {salida} con motion graphics.")


def revisar(video: str) -> None:
    ruta = (TRABAJO / video) if not Path(video).is_absolute() else Path(video)
    _oido()
    dur = cris.duracion(ruta)
    tiempos = [x for x in [0.3, 1.0, 2.0] if x < dur] + [3 + (dur - 3.5) * i / 11 for i in range(12) if dur > 4]
    destino = TRABAJO / "vistas" / f"revision_{ruta.stem}.jpg"
    destino.parent.mkdir(parents=True, exist_ok=True)
    usados = _hoja(ruta, tiempos, destino, alto=400, columnas=5)
    pals = cris.transcribir(ruta) if cris.tiene_audio(ruta) else []
    print(f"{ruta.name}: {dur:.1f} s\nCuadros: {destino} — segundos {', '.join(f'{t:.1f}' for t in usados)}")
    print("Se oye: " + (" ".join(f"[{p['t']:.1f}] {p['w']}" if i % 8 == 0 else p["w"] for i, p in enumerate(pals)) or "(nada de voz)"))
    print("Revisa con la lista 'ANTES DE ENTREGAR' del manual. Mira la hoja con Read.")


def codificar() -> None:
    import editor_libre  # noqa: F401
    compu.configurar_editor(compu.nvenc())
    print("Para cortes rápidos:  " + " ".join(cris.RAPIDO))
    print("Para el video final:  " + " ".join(cris.FINAL))
    print("Audio:                " + " ".join(cris.AUDIO))


def main() -> None:
    ordenes = {"ficha": ficha, "cuadros": cuadros, "transcribir": transcribir, "armar": armar, "motion": motion,
               "revisar": revisar, "codificar": codificar}
    if len(sys.argv) < 2 or sys.argv[1] not in ordenes:
        return print(__doc__)
    compu.configurar_editor(compu.nvenc())
    ordenes[sys.argv[1]](*sys.argv[2:])


if __name__ == "__main__":
    main()
