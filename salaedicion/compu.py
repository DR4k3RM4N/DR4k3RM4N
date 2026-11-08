"""El programa que corre en tus compus (sala de edición).

Le pregunta a tu oficina cada pocos segundos "¿hay algo que editar?". Si hay, baja los clips, edita con tu tarjeta
de video (NVENC para el video, Whisper grande en la GPU para los subtítulos) y sube el resultado. No abre puertos.

    python compu.py --vincular 123456 --servidor https://tu-oficina --nombre "PC 3070"   # una sola vez
    python compu.py                                                                     # queda trabajando

Lo instala solo INSTALAR_SALA.bat (Windows) y arranca al prender la compu.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import os
import platform
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

AQUI = Path(__file__).resolve().parent
REPO = AQUI.parent
sys.path[:0] = [str(REPO / "autocanal"), str(REPO / "tiktokshop")]
WINDOWS = os.name == "nt"
if WINDOWS:
    # Sin esto, cada ffmpeg/ffprobe/git abre una ventanita negra de CMD que parpadea (una por clip y por corte).
    _PopenOriginal = subprocess.Popen

    class _SinVentana(_PopenOriginal):
        def __init__(self, *args, **kwargs):
            kwargs["creationflags"] = kwargs.get("creationflags", 0) | 0x08000000  # CREATE_NO_WINDOW
            info = kwargs.get("startupinfo") or subprocess.STARTUPINFO()
            info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            info.wShowWindow = 0  # SW_HIDE: por si el programa abre otra ventana por su cuenta
            kwargs["startupinfo"] = info
            super().__init__(*args, **kwargs)

    subprocess.Popen = _SinVentana

    def _ffmpeg_real() -> None:
        """winget deja ffmpeg como un "acceso directo" en AppData\\Local\\Microsoft\\WinGet\\Links que abre su propia
        ventana al lanzar el ffmpeg de verdad. Se busca el ffmpeg real y se pone primero en el PATH."""
        base = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
        candidatos = sorted(base.glob("Gyan.FFmpeg*/**/bin/ffmpeg.exe")) if base.exists() else []
        enlace = shutil.which("ffmpeg")
        if enlace:
            try:
                candidatos.insert(0, Path(os.path.realpath(enlace)))
            except OSError:
                pass
        for c in candidatos:
            if c.exists() and "Links" not in c.parts and (c.parent / "ffprobe.exe").exists():
                os.environ["PATH"] = str(c.parent) + os.pathsep + os.environ.get("PATH", "")
                return

    _ffmpeg_real()
CARPETA = (Path(os.environ.get("LOCALAPPDATA", Path.home())) / "SalaEdicion" if WINDOWS
           else Path.home() / ".salaedicion")
CONFIG = CARPETA / "config.json"
TRABAJOS = CARPETA / "trabajos"
LOG = CARPETA / "compu.log"
# Tu carpeta de clips: aquí pasas lo que grabaste. Los clips NO se suben al servidor; solo el video terminado.
CLIPS = Path(os.environ.get("SALA_CLIPS") or (Path(os.environ.get("USERPROFILE", Path.home())) / "Videos" / "Sala de edicion"))
EXT_VIDEO = {".mp4", ".mov", ".m4v", ".webm", ".3gp", ".mkv"}
EXT_AUDIO = {".mp3", ".m4a", ".wav", ".aac", ".ogg"}
MUSICA = CLIPS / "Musica"  # tu música para los videos (el editor la elige de aquí)


def log(texto: str) -> None:
    linea = f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {texto}"
    print(linea, flush=True)
    try:
        CARPETA.mkdir(parents=True, exist_ok=True)
        if LOG.exists() and LOG.stat().st_size > 2_000_000:
            LOG.replace(LOG.with_suffix(".log.anterior"))
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(linea + "\n")
    except OSError:
        pass


def _dlls_nvidia() -> None:
    """En Windows, Whisper en la GPU necesita las librerías de NVIDIA que instala pip (cuBLAS y cuDNN)."""
    if not WINDOWS:
        return
    import site
    for base in [*site.getsitepackages(), site.getusersitepackages()]:
        for sub in ("cublas", "cudnn", "cuda_nvrtc", "cuda_runtime"):
            d = Path(base) / "nvidia" / sub / "bin"
            if d.is_dir():
                os.add_dll_directory(str(d))
                os.environ["PATH"] = str(d) + os.pathsep + os.environ.get("PATH", "")


_dlls_nvidia()

import requests  # noqa: E402

import cris  # noqa: E402


# ---------- qué puede hacer esta compu ----------
def gpu() -> str:
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], capture_output=True, text=True,
                           timeout=10)
        return r.stdout.strip().splitlines()[0] if r.returncode == 0 and r.stdout.strip() else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def nvenc() -> bool:
    """¿ffmpeg puede codificar con la tarjeta (NVENC)? Se prueba de verdad con un video chiquito."""
    try:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "color=s=640x360:d=0.2",
                            "-c:v", "h264_nvenc", "-f", "null", "-"], capture_output=True, text=True, timeout=30)
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def preparar_oido(tiene_gpu: bool) -> str:
    """Whisper grande en la GPU (mucho mejor en español); si la GPU no jala, Whisper chico en el procesador."""
    if not cris.whisper_disponible():
        return "sin oído"
    if tiene_gpu:
        try:
            from faster_whisper import WhisperModel
            modelo = os.environ.get("WHISPER_MODELO_GPU", "large-v3-turbo")
            cris._modelo = WhisperModel(modelo, device="cuda", compute_type="float16")
            cris.OIDO.update(modelo=modelo, dispositivo="cuda", computo="float16")
            return f"{modelo} (GPU)"
        except Exception as exc:  # noqa: BLE001
            log(f"Whisper en la GPU no arrancó ({exc}); uso el procesador.")
            cris._modelo = None
    cris.OIDO.update(modelo=os.environ.get("WHISPER_MODELO", "small"), dispositivo="cpu", computo="int8",
                     hilos=max(2, (os.cpu_count() or 4) - 2))
    return f"{cris.OIDO['modelo']} (CPU)"


def configurar_editor(con_nvenc: bool) -> None:
    hilos = str(max(2, (os.cpu_count() or 4) - 2))
    if con_nvenc:
        cris.RAPIDO = ["-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr", "-cq", "18", "-b:v", "0", "-pix_fmt", "yuv420p",
                       "-r", str(cris.FPS)]
        cris.FINAL = ["-c:v", "h264_nvenc", "-preset", "p6", "-rc", "vbr", "-cq", "21", "-b:v", "0", "-pix_fmt", "yuv420p",
                      "-r", str(cris.FPS), "-movflags", "+faststart"]
    else:
        cris.RAPIDO = [*cris.RAPIDO[:-1], hilos]
        cris.FINAL = [x if x != "2" else hilos for x in cris.FINAL]
    if WINDOWS:  # fuentes de Windows para los textos y la portada
        cris.FUENTE, cris.FUENTE_TTF = "Arial", r"C:\Windows\Fonts\arialbd.ttf"


def version() -> str:
    try:
        return subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                              timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


# ---------- hablar con la oficina ----------
class Oficina:
    def __init__(self, servidor: str, token: str):
        self.base = servidor.rstrip("/") + "/sala/api/maquina"
        self.s = requests.Session()
        self.s.headers["X-Compu-Token"] = token

    def post(self, ruta: str, datos: dict, timeout: float = 30) -> dict:
        r = self.s.post(f"{self.base}/{ruta}", json=datos, timeout=timeout)
        j = r.json()
        if r.status_code == 401 and j.get("sin_alta"):
            raise SystemExit("Esta compu ya no está dada de alta en tu oficina. Vuelve a correr INSTALAR_SALA.bat.")
        return j

    def bajar(self, tid: str, n: int, destino: Path) -> None:
        with self.s.get(f"{self.base}/archivo/{tid}/{n}", stream=True, timeout=(15, 600)) as r:
            r.raise_for_status()
            with open(destino, "wb") as f:
                for trozo in r.iter_content(1024 * 1024):
                    f.write(trozo)

    def subir(self, tid: str, archivo: Path) -> None:
        with open(archivo, "rb") as f:
            r = self.s.post(f"{self.base}/subir/{tid}", params={"nombre": archivo.name}, data=f, timeout=(15, 1800),
                            headers={"Content-Type": "application/octet-stream"})
        if r.status_code != 200:
            raise RuntimeError(f"No pude subir {archivo.name}: {r.text[:120]}")


# ---------- carpetas de clips en esta compu ----------
def _limpio(nombre: str) -> str:
    return re.sub(r'[<>:"/\\|?*]+', " ", nombre).strip(" .")[:60] or "producto"


def carpeta_de(pid: str) -> Path | None:
    """La carpeta de un producto: «Nombre [abcd]» (abcd = final del id)."""
    marca = f"[{pid[-4:]}]"
    for d in CLIPS.iterdir() if CLIPS.exists() else []:
        if d.is_dir() and d.name.endswith(marca):
            return d
    return None


def preparar_carpetas(pedidas: list[dict], proyectos: list | None = None) -> None:
    CLIPS.mkdir(parents=True, exist_ok=True)
    MUSICA.mkdir(exist_ok=True)
    for pr in proyectos or []:  # proyectos que creaste desde la oficina (los que usan tu propia carpeta no se tocan)
        if isinstance(pr, dict) and pr.get("ruta"):
            continue
        nombre = _limpio(pr["carpeta"] if isinstance(pr, dict) else pr)
        if nombre and not (CLIPS / nombre).exists():
            (CLIPS / nombre).mkdir()
    leeme = CLIPS / "LEEME.txt"
    if not leeme.exists():
        leeme.write_text("Sala de edición\r\n\r\nPasa aquí los clips que grabaste, en la carpeta del producto.\r\n"
                         "En tu oficina (pestaña Shop → el producto) le dices a cada clip qué toma es, y Cris lo edita en\r\n"
                         "esta compu. Los clips NO se suben al servidor: solo el video terminado.\r\n", encoding="utf-8")
    for p in pedidas:
        if not carpeta_de(p["id"]):
            (CLIPS / f"{_limpio(p['nombre'])} [{p['id'][-4:]}]").mkdir(exist_ok=True)


def analizar(clip: Path) -> dict:
    """Lo que el editor necesita para elegir bien (se hace una vez por clip y se guarda):
    - frases: qué dices y cuándo (Whisper), para escoger la mejor toma cuando repites;
    - calidad segundo a segundo: 'movido', 'borroso', 'oscuro' o 'bien';
    - hoja: tira de 4 cuadros del clip (JPG) para que el editor VEA qué hay en él."""
    firma = hashlib.sha1(f"{clip.resolve()}|{clip.stat().st_mtime}|{clip.stat().st_size}".encode()).hexdigest()[:16]
    guardado = CARPETA / "analisis" / f"{firma}.json"
    if guardado.exists():
        return json.loads(guardado.read_text(encoding="utf-8"))
    guardado.parent.mkdir(parents=True, exist_ok=True)
    try:
        dur = cris.duracion(clip)
    except cris.ErrorEdicion:
        return {}
    res = {"segundos": round(dur, 1), "frases": [], "calidad": [], "hoja": ""}
    # qué dices
    pals = cris.transcribir(clip) if cris.tiene_audio(clip) else []
    if pals:
        grupo = [pals[0]]
        for p in pals[1:] + [None]:
            if p is None or p["t"] - (grupo[-1]["t"] + grupo[-1]["d"]) > 0.6:
                res["frases"].append([round(grupo[0]["t"], 1), round(grupo[-1]["t"] + grupo[-1]["d"], 1),
                                      " ".join(x["w"] for x in grupo)[:200]])
                grupo = []
            if p is not None:
                grupo.append(p)
    # calidad: cuadros chiquitos en gris, 2 por segundo
    try:
        import numpy as np
        crudo = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(clip), "-vf",
                                "fps=2,scale=96:96,format=gray", "-f", "rawvideo", "-"], capture_output=True, timeout=300).stdout
        cuadros = np.frombuffer(crudo, dtype=np.uint8)[: len(crudo) // 9216 * 9216].reshape(-1, 96, 96).astype(np.float32)
        if len(cuadros) >= 2:
            luz = cuadros.mean(axis=(1, 2))
            lap = np.abs(4 * cuadros[:, 1:-1, 1:-1] - cuadros[:, :-2, 1:-1] - cuadros[:, 2:, 1:-1]
                         - cuadros[:, 1:-1, :-2] - cuadros[:, 1:-1, 2:]).mean(axis=(1, 2))
            mov = np.concatenate([[0], np.abs(np.diff(cuadros, axis=0)).mean(axis=(1, 2))])
            nitidez_tipica = float(np.median(lap)) or 1.0
            for seg in range(int(np.ceil(len(cuadros) / 2))):
                sl = slice(seg * 2, seg * 2 + 2)
                if float(luz[sl].mean()) < 35:
                    etiqueta = "oscuro"
                elif float(mov[sl].mean()) > 22:
                    etiqueta = "movido"
                elif float(lap[sl].mean()) < nitidez_tipica * 0.55:
                    etiqueta = "borroso"
                else:
                    etiqueta = "bien"
                if res["calidad"] and res["calidad"][-1][2] == etiqueta:
                    res["calidad"][-1][1] = min(round(dur, 1), seg + 1)
                else:
                    res["calidad"].append([seg, min(round(dur, 1), seg + 1), etiqueta])
    except Exception as exc:  # noqa: BLE001 — sin numpy o con un clip raro, se sigue sin esto
        log(f"No pude medir la calidad de {clip.name}: {exc}")
    # tira de 4 cuadros para que el editor vea el clip
    hoja = guardado.with_suffix(".jpg")
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(clip), "-vf",
                    f"fps={4 / max(dur, 0.5):.4f},scale=-2:200,tile=4x1", "-frames:v", "1", "-q:v", "6", str(hoja)],
                   capture_output=True, timeout=120)
    if hoja.exists():
        res["hoja"] = base64.b64encode(hoja.read_bytes()).decode()
        hoja.unlink()
    guardado.write_text(json.dumps(res), encoding="utf-8")
    return res


def _miniatura(clip: Path) -> tuple[str, float, bool]:
    """(jpg en base64, segundos, tiene audio). Se guarda para no repetirla."""
    firma = hashlib.sha1(f"{clip.resolve()}|{clip.stat().st_mtime}|{clip.stat().st_size}".encode()).hexdigest()[:16]
    guardada = CARPETA / "miniaturas" / f"{firma}.json"
    if guardada.exists():
        d = json.loads(guardada.read_text(encoding="utf-8"))
        return d["jpg"], d["segundos"], d["audio"]
    guardada.parent.mkdir(parents=True, exist_ok=True)
    try:
        segundos = cris.duracion(clip)
    except cris.ErrorEdicion:
        return "", 0.0, False
    jpg = guardada.with_suffix(".jpg")
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{min(1.0, segundos / 3):.2f}", "-i", str(clip),
                    "-frames:v", "1", "-vf", "scale=-2:200", "-q:v", "7", str(jpg)], capture_output=True, timeout=60)
    datos = base64.b64encode(jpg.read_bytes()).decode() if jpg.exists() else ""
    jpg.unlink(missing_ok=True)
    d = {"jpg": datos, "segundos": round(segundos, 1), "audio": cris.tiene_audio(clip)}
    guardada.write_text(json.dumps(d), encoding="utf-8")
    return d["jpg"], d["segundos"], d["audio"]


_ultimo_reporte = {"firma": "", "t": 0.0, "con_miniatura": set()}
ESTADO_COMPU = {"texto": "Arrancando…"}  # lo que se ve en la oficina («Analizando 3 de 12 clips»)


def lugares() -> list[dict]:
    """Carpetas que ya tienes (Escritorio, Videos, Descargas, Imágenes, Documentos) para elegirlas como proyecto."""
    casa = Path(os.environ.get("USERPROFILE") or Path.home())
    bases = [("Escritorio", casa / "Desktop"), ("Escritorio", casa / "OneDrive" / "Desktop"),
             ("Escritorio", casa / "OneDrive" / "Escritorio"), ("Videos", casa / "Videos"), ("Descargas", casa / "Downloads"),
             ("Imágenes", casa / "Pictures"), ("Documentos", casa / "Documents")]
    salida, vistos = [], set()
    for nombre, base in bases:
        try:
            if not base.is_dir():
                continue
            for d in sorted(base.iterdir()):
                if not d.is_dir() or d.name.startswith(".") or d == CLIPS or d.resolve() in vistos:
                    continue
                vistos.add(d.resolve())
                try:
                    videos = sum(1 for f in d.iterdir() if f.is_file() and f.suffix.lower() in EXT_VIDEO)
                except OSError:
                    continue
                salida.append({"ruta": str(d), "nombre": f"{nombre} › {d.name}", "videos": videos})
        except OSError:
            continue
    salida.sort(key=lambda x: (-x["videos"], x["nombre"].lower()))
    return salida[:80]


def reportar_carpetas(of: "Oficina", pedidas: list[dict], proyectos: list | None = None, analizar_ahora: bool = True) -> None:
    """Le dice a la oficina qué clips hay en cada carpeta (nombre, duración y miniatura chiquita, nunca el video):
    las de productos de TikTok y cualquier otra carpeta (cada una es un proyecto de la sala).
    Primero manda la lista con miniaturas (al momento) y después analiza los clips uno por uno."""
    preparar_carpetas(pedidas, proyectos)
    de_productos = {}
    for p in pedidas:
        d = carpeta_de(p["id"])
        if d:
            de_productos[d.name] = p["id"]
    lugares_ = [(de_productos.get(d.name) or f"carpeta:{d.name}", d) for d in sorted(CLIPS.iterdir())
                if d.is_dir() and not d.name.startswith(".") and d != MUSICA]
    errores = {}
    for pr in proyectos or []:  # proyectos con una carpeta tuya fuera de la sala
        if isinstance(pr, dict) and pr.get("ruta"):
            ruta = Path(str(pr["ruta"]).strip().strip('"').strip())
            if ruta.is_dir():
                lugares_.append((f"proyecto:{pr['id']}", ruta))
            else:
                errores[f"proyecto:{pr['id']}"] = f"No encontré la carpeta «{ruta}» en esta compu. Revisa la ruta."
    carpetas, firmas = {}, list(errores)
    for clave, d in lugares_:
        clips = []
        try:
            archivos = sorted(d.iterdir())
        except OSError as exc:
            errores[clave] = f"No pude abrir la carpeta ({exc.__class__.__name__})."
            archivos = []
        for f in archivos:
            if f.is_file() and f.suffix.lower() in EXT_VIDEO and not f.name.startswith("."):
                firma = f"{f.stat().st_size}-{int(f.stat().st_mtime)}"
                firmas.append(f"{clave}/{f.name}/{firma}")
                clips.append((f, firma))
        carpetas[clave] = clips
    musica = sorted(f.name for f in MUSICA.iterdir() if f.is_file() and f.suffix.lower() in EXT_AUDIO) if MUSICA.exists() else []
    firmas += [f"musica/{m}" for m in musica]
    resumen = "|".join(firmas)
    pendientes = [(pid, f, firma) for pid, clips in carpetas.items() if pid.startswith(("carpeta:", "proyecto:"))
                  for f, firma in clips if f"{pid}/{f.name}/{firma}" not in _ultimo_reporte.get("con_analisis", set())]
    if resumen == _ultimo_reporte["firma"] and time.time() - _ultimo_reporte["t"] < 120 and not (pendientes and analizar_ahora):
        return  # nada cambió (y se repite cada 2 min por si la sala se reinició)

    def mandar(analizado: dict) -> None:
        envio = {}
        for pid, clips in carpetas.items():
            envio[pid] = []
            for f, firma in clips:
                jpg, segundos, audio = _miniatura(f)
                ya = f"{pid}/{f.name}/{firma}" in _ultimo_reporte["con_miniatura"]
                dato = {"nombre": f.name, "mb": round(f.stat().st_size / 1024 / 1024, 1), "segundos": segundos,
                        "tiene_audio": audio, "firma": firma, "miniatura": "" if ya else jpg}
                if (pid, f.name) in analizado:
                    dato.update(analizado[(pid, f.name)])
                envio[pid].append(dato)
        r = of.post("carpetas", {"carpetas": envio, "ruta": str(CLIPS), "musica": musica, "lugares": lugares(),
                                 "errores": errores}, timeout=60)
        _ultimo_reporte.update(firma=resumen, t=time.time(), con_miniatura=set(r.get("con_miniatura") or []),
                               con_analisis=set(r.get("con_analisis") or []))

    mandar({})  # al momento: la oficina ya ve tus clips con sus miniaturas
    if not analizar_ahora:
        return
    for k, (pid, f, firma) in enumerate(pendientes, 1):  # luego, uno por uno: qué dices y cómo se ve
        ESTADO_COMPU["texto"] = f"Analizando tus clips ({k} de {len(pendientes)}) · {f.name[:30]}"
        try:
            a = analizar(f)
            mandar({(pid, f.name): {"analisis": {x: a.get(x) for x in ("frases", "calidad")}, "hoja": a.get("hoja", "")}})
        except Exception as exc:  # noqa: BLE001
            log(f"No pude analizar {f.name}: {exc}")
    ESTADO_COMPU["texto"] = "Lista"


def elegir_carpeta(pedido: str) -> None:
    """La oficina pidió elegir una carpeta: se abre en esta compu la ventana normal de Windows para escogerla."""
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    ruta, error = "", ""
    try:
        import tkinter as tk
        from tkinter import filedialog
        raiz = tk.Tk()
        raiz.withdraw()
        raiz.attributes("-topmost", True)  # que salga encima de todo
        raiz.update()
        inicio = Path(os.environ.get("USERPROFILE") or Path.home()) / "Desktop"
        ruta = filedialog.askdirectory(parent=raiz, title="Sala de edición: elige la carpeta con tus clips",
                                       initialdir=str(inicio if inicio.is_dir() else Path.home()), mustexist=True) or ""
        raiz.destroy()
    except Exception as exc:  # noqa: BLE001
        error = f"No pude abrir la ventana para elegir carpeta: {exc}"[:200]
        if WINDOWS:  # respaldo: la ventana de Windows (sin tkinter), con PowerShell
            try:
                script = ("Add-Type -AssemblyName System.Windows.Forms;"
                          "$d = New-Object System.Windows.Forms.FolderBrowserDialog;"
                          "$d.Description = 'Sala de edicion: elige la carpeta con tus clips';"
                          "$f = New-Object System.Windows.Forms.Form; $f.TopMost = $true;"
                          "if ($d.ShowDialog($f) -eq 'OK') { [Console]::Out.Write($d.SelectedPath) }")
                r = _PopenOriginal(["powershell", "-NoProfile", "-STA", "-Command", script], stdout=subprocess.PIPE,
                                   creationflags=0x08000000, text=True)  # sin consola, pero la ventana sí se ve
                ruta = (r.communicate(timeout=600)[0] or "").strip()
                error = ""
            except Exception as exc2:  # noqa: BLE001
                error = f"No pude abrir la ventana para elegir carpeta: {exc2}"[:200]
        if error:
            log(error)
    if ruta and WINDOWS:
        ruta = ruta.replace("/", "\\")
    try:
        Oficina(cfg["servidor"], cfg["token"]).post("carpeta_elegida", {"id": pedido, "ruta": ruta, "error": error}, timeout=20)
    except requests.RequestException as exc:
        log(f"No pude avisar qué carpeta elegiste: {exc}")


def hacer_proyecto(of: "Oficina", t: dict, temporal: Path, avance) -> None:
    """Un proyecto de la sala: los clips están en su carpeta de esta compu (lo que subiste al servidor se baja ahí)."""
    import editor_libre
    editor_libre.analizar = analizar  # para saltarse partes movidas/borrosas
    par, tid = t["parametros"], t["id"]
    if par.get("ruta"):  # tu propia carpeta (fuera de la sala)
        clips = Path(str(par["ruta"]).strip().strip('"').strip())
        if not clips.is_dir():
            raise RuntimeError(f"No encontré tu carpeta {par['ruta']} en esta compu.")
    else:
        clips = CLIPS / _limpio(par["carpeta"])
        clips.mkdir(parents=True, exist_ok=True)
    musica_nueva = set(par.get("musica_entradas") or [])
    MUSICA.mkdir(parents=True, exist_ok=True)
    for e in t["entradas"]:  # clips que subiste desde la oficina: quedan en la carpeta de tu compu
        destino = (MUSICA if e["nombre"] in musica_nueva else clips) / e["nombre"]
        if not destino.exists() or destino.stat().st_size != e.get("bytes"):
            avance(f"Bajando {e['nombre']}", 0.01)
            of.bajar(tid, e["n"], destino)
    n = par["version"]
    video = temporal / "salida" / f"v{n}.mp4"
    video.parent.mkdir(parents=True, exist_ok=True)
    inicio = time.time()
    segundos = editor_libre.render(par["plan"], clips, video, MUSICA, "", avance)
    avance("Subiendo tu video", 0.97)
    of.subir(tid, video)
    cuadro = video.with_name(f"v{n}.cuadro.jpg")
    if cuadro.exists():
        of.subir(tid, cuadro)
    copia = clips / "Ediciones" / f"{_limpio(par['carpeta'])} v{n}.mp4"  # y una copia en tu compu
    copia.parent.mkdir(exist_ok=True)
    shutil.copyfile(video, copia)
    of.post(f"terminar/{tid}", {"ok": True, "resultado": {"video": video.name, "cuadro": cuadro.name if cuadro.exists() else None,
                                                         "segundos": segundos}})
    log(f"Proyecto «{par['carpeta']}» v{n} listo en {round(time.time() - inicio)} s ({segundos} s de video).")


def hacer(of: Oficina, t: dict) -> None:
    tid = t["id"]
    carpeta = TRABAJOS / tid
    shutil.rmtree(carpeta, ignore_errors=True)
    (carpeta / "clips").mkdir(parents=True)
    log(f"Trabajo {tid}: {t.get('etiqueta')} ({len(t['entradas'])} clips)")
    ultimo = [0.0]

    def avance(paso: str, fraccion: float) -> None:
        if time.time() - ultimo[0] < 1.0 and fraccion < 0.999:
            return
        ultimo[0] = time.time()
        r = of.post(f"avance/{tid}", {"paso": paso, "avance": fraccion})
        if r.get("cancelado"):
            raise InterruptedError("La oficina canceló el trabajo.")

    def clasificar(trozos, guion):  # Claude se pide a la oficina (la clave y el gasto se quedan allá)
        r = of.post(f"clasificar/{tid}", {"trozos": trozos, "guion": guion}, timeout=180)
        if "error" in r:
            raise RuntimeError(r["error"])
        return r["partes"]

    try:
        if t["tipo"] == "libre":
            return hacer_proyecto(of, t, carpeta, avance)
        if t["tipo"] != "cris":
            raise RuntimeError(f"Esta versión no sabe hacer trabajos de tipo {t['tipo']}.")
        if t.get("local"):  # tus clips ya están en esta compu: no se baja nada
            clips = carpeta_de(t["local"]["producto"])
            if not clips:
                raise RuntimeError("No encontré la carpeta del producto en esta compu.")
            faltan = [n for n in [*(t["parametros"]["archivos"].get("tomas") or {}).values(), t["parametros"]["archivos"].get("completo")]
                      if n and not (clips / n).exists()]
            if faltan:
                raise RuntimeError(f"Ya no están en la carpeta: {', '.join(faltan[:3])}")
        else:
            clips = carpeta / "clips"
            total = len(t["entradas"])
            for e in t["entradas"]:
                avance(f"Bajando clip {e['n'] + 1} de {total}", 0.02 * e["n"] / max(1, total))
                of.bajar(tid, e["n"], clips / e["nombre"])
        cris.clasificar = clasificar
        salida = carpeta / "salida"
        inicio = time.time()
        videos = cris.editar_todo(clips, t["parametros"], salida, avance)
        avance("Subiendo tus videos", 0.97)
        for v in videos:
            of.subir(tid, salida / v["video"])
            cuadro = salida / f"{Path(v['video']).stem}.cuadro.jpg"
            if cuadro.exists():
                of.subir(tid, cuadro)
        of.post(f"terminar/{tid}", {"ok": True, "resultado": {"videos": videos, "segundos": round(time.time() - inicio)}})
        log(f"Trabajo {tid} listo en {round(time.time() - inicio)} s: {len(videos)} video(s).")
    except InterruptedError as exc:
        log(str(exc))
    except Exception as exc:  # noqa: BLE001 — se avisa a la oficina y ella edita en el servidor
        log("Falló:\n" + traceback.format_exc())
        try:
            of.post(f"terminar/{tid}", {"ok": False, "error": str(exc)[:280]})
        except requests.RequestException:
            pass
    finally:
        shutil.rmtree(carpeta, ignore_errors=True)


def actualizarme() -> None:
    """Cada rato revisa si hay versión nueva en GitHub; si la hay (y no está editando), se actualiza y se reinicia."""
    try:
        rama = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True,
                              timeout=20).stdout.strip()
        if not rama or rama == "HEAD":
            return
        subprocess.run(["git", "-C", str(REPO), "fetch", "-q", "--depth", "1", "origin", rama], capture_output=True, timeout=120)
        actual = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=20).stdout.strip()
        nueva = subprocess.run(["git", "-C", str(REPO), "rev-parse", "FETCH_HEAD"], capture_output=True, text=True, timeout=20).stdout.strip()
        if nueva and actual and nueva != actual:
            subprocess.run(["git", "-C", str(REPO), "reset", "-q", "--hard", "FETCH_HEAD"], capture_output=True, timeout=60)
            log("Hay versión nueva del programa de la sala: me actualizo y me reinicio.")
            subprocess.Popen([sys.executable, *sys.argv], cwd=str(REPO), close_fds=True)
            os._exit(0)
    except (OSError, subprocess.SubprocessError) as exc:
        log(f"No pude buscar actualizaciones ({exc}); sigo con esta versión.")


def trabajar() -> None:
    if not CONFIG.exists():
        raise SystemExit("Esta compu no está dada de alta. Corre INSTALAR_SALA.bat (o compu.py --vincular CODIGO).")
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    of = Oficina(cfg["servidor"], cfg["token"])
    import threading
    tarjeta = gpu()
    con_nvenc = bool(tarjeta) and nvenc()
    configurar_editor(con_nvenc)
    cris.CACHE = CARPETA / "oido"
    cris.CACHE.mkdir(parents=True, exist_ok=True)
    datos = {"gpu": tarjeta or platform.processor()[:60], "nvenc": con_nvenc, "oido": "preparando…", "version": version(),
             "tipos": ["cris", "libre"], "con_carpetas": True}
    listo = threading.Event()

    def pulso():  # "sigo prendida" cada 10 s, aunque esté ocupada analizando o editando
        of2 = Oficina(cfg["servidor"], cfg["token"])
        while True:
            try:
                of2.post("latido", {**datos, "libre": False, "pulso": True, "estado": ESTADO_COMPU["texto"]}, timeout=20)
            except (requests.RequestException, ValueError):
                pass
            except SystemExit as exc:
                log(str(exc))
                os._exit(1)
            time.sleep(10)

    def preparar():  # el oído grande (la primera vez baja ~1.5 GB): sin frenar el pulso
        ESTADO_COMPU["texto"] = "Preparando el oído (la primera vez baja ~1.5 GB)…"
        datos["oido"] = preparar_oido(bool(tarjeta))
        ESTADO_COMPU["texto"] = "Lista"
        log(f"Sala de edición: {cfg.get('nombre')} · {datos['gpu'] or 'sin tarjeta NVIDIA'} · NVENC {'sí' if con_nvenc else 'no'}"
            f" · oído {datos['oido']} · tus clips en {CLIPS}")
        listo.set()

    pedido = {"carpetas": None, "evento": threading.Event()}

    def carpetas():  # revisar carpetas y analizar clips, aparte (puede tardar la primera vez)
        of3 = Oficina(cfg["servidor"], cfg["token"])
        while True:
            pedido["evento"].wait()
            pedido["evento"].clear()
            try:  # la lista de clips va al momento; el análisis, cuando el oído ya está listo
                reportar_carpetas(of3, *pedido["carpetas"], analizar_ahora=listo.is_set())
            except Exception as exc:  # noqa: BLE001 — las carpetas nunca deben frenar la edición
                log(f"No pude revisar las carpetas de clips: {exc}")
                ESTADO_COMPU["texto"] = "Lista"

    for f in (pulso, preparar, carpetas):
        threading.Thread(target=f, daemon=True).start()
    espera, revisado = 5, time.time()
    while True:
        if time.time() - revisado > 1800:  # cada 30 min, entre trabajos
            revisado = time.time()
            actualizarme()
        try:
            r = of.post("latido", {**datos, "libre": listo.is_set(), "estado": ESTADO_COMPU["texto"]}, timeout=20)
            espera = 5
            if r.get("pedir_carpeta"):  # «📂 Elegir carpeta…» desde la oficina
                threading.Thread(target=elegir_carpeta, args=(r["pedir_carpeta"]["id"],), daemon=True).start()
            if "carpetas" in r and not pedido["evento"].is_set():
                pedido["carpetas"] = (r["carpetas"], r.get("proyectos"))
                pedido["evento"].set()
            if r.get("trabajo"):
                antes = ESTADO_COMPU["texto"]
                ESTADO_COMPU["texto"] = f"Editando {r['trabajo'].get('etiqueta', '')}"[:60]
                hacer(of, r["trabajo"])
                ESTADO_COMPU["texto"] = antes if antes.startswith("Analizando") else "Lista"
                espera = 1
        except requests.RequestException as exc:
            log(f"Sin conexión con la oficina ({exc.__class__.__name__}); reintento en {espera} s.")
            espera = min(60, espera * 2)
        time.sleep(espera)


def vincular(codigo: str, servidor: str, nombre: str) -> None:
    servidor = servidor.strip().rstrip("/")
    if not servidor.startswith(("https://", "http://")):
        servidor = "https://" + servidor
    r = requests.post(f"{servidor}/sala/api/maquina/vincular", timeout=30,
                      json={"codigo": codigo, "nombre": nombre, "gpu": gpu(), "sistema": f"{platform.system()} {platform.release()}"})
    try:
        j = r.json()
    except ValueError:
        raise SystemExit(f"Tu oficina no contestó bien ({r.status_code}). ¿La dirección es correcta?") from None
    if "error" in j:
        raise SystemExit(j["error"])
    CARPETA.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps({"servidor": servidor, "token": j["token"], "nombre": j["nombre"], "id": j["id"]}),
                      encoding="utf-8")
    log(f"✔ {j['nombre']} quedó dada de alta en tu sala de edición.")


def main() -> None:
    a = argparse.ArgumentParser(description="Sala de edición: esta compu edita los videos de tu oficina")
    a.add_argument("--vincular", metavar="CODIGO", help="dar de alta esta compu con el código de la pestaña Sala")
    a.add_argument("--servidor", default="https://51-195-201-84.sslip.io")
    a.add_argument("--nombre", default=platform.node() or "Mi compu")
    args = a.parse_args()
    if args.vincular:
        return vincular(args.vincular, args.servidor, args.nombre)
    while True:  # si algo truena, se levanta solo
        try:
            trabajar()
        except SystemExit:
            raise
        except Exception:  # noqa: BLE001
            log("Se cayó el programa; vuelvo a arrancar en 20 s:\n" + traceback.format_exc())
            time.sleep(20)


if __name__ == "__main__":
    main()
