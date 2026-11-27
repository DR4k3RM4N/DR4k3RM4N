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
import threading
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
            # CREATE_NO_WINDOW + prioridad «debajo de normal»: tu compu sigue fluida mientras edita (los hijos la heredan)
            kwargs["creationflags"] = kwargs.get("creationflags", 0) | 0x08000000 | 0x00004000
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
CARPETA = (Path(os.environ["SALA_CARPETA"]) if os.environ.get("SALA_CARPETA")
           else Path(os.environ.get("LOCALAPPDATA", Path.home())) / "SalaEdicion" if WINDOWS
           else Path.home() / ".salaedicion")
# 🖥️ el servidor también edita: la sala lo prende como una «compu» más (sin oído, sin cel, sin actualizarse solo)
SERVIDOR = os.environ.get("SALA_SERVIDOR") == "1"
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


_cpu_antes: list = []


def uso_equipo() -> dict:
    """📊 Cuánto está trabajando esta compu: procesador, memoria y tarjeta de video (en %). Sin librerías extra."""
    uso = {}
    try:
        if WINDOWS:
            import ctypes

            class FT(ctypes.Structure):
                _fields_ = [("lo", ctypes.c_uint32), ("hi", ctypes.c_uint32)]
            i, k, u = FT(), FT(), FT()
            ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(i), ctypes.byref(k), ctypes.byref(u))
            val = lambda x: (x.hi << 32) | x.lo  # noqa: E731
            idle, total = val(i), val(k) + val(u)  # el tiempo de kernel ya incluye el ocioso

            class MEM(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_uint32), ("dwMemoryLoad", ctypes.c_uint32)] + \
                           [(n, ctypes.c_uint64) for n in ("t1", "a1", "t2", "a2", "t3", "a3", "a4")]
            m = MEM()
            m.dwLength = ctypes.sizeof(MEM)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            uso["ram"] = int(m.dwMemoryLoad)
        else:
            campos = [int(x) for x in open("/proc/stat").readline().split()[1:]]
            idle, total = campos[3] + (campos[4] if len(campos) > 4 else 0), sum(campos)
            info = dict(ln.split(":", 1) for ln in open("/proc/meminfo") if ":" in ln)
            tot, disp = int(info["MemTotal"].split()[0]), int(info.get("MemAvailable", info["MemFree"]).split()[0])
            uso["ram"] = round(100 * (tot - disp) / max(1, tot))
        if _cpu_antes:
            d_total, d_idle = total - _cpu_antes[1], idle - _cpu_antes[0]
            uso["cpu"] = max(0, min(100, round(100 * (d_total - d_idle) / max(1, d_total))))
        _cpu_antes[:] = [idle, total]
    except Exception:  # noqa: BLE001 — medir es un extra
        pass
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            g, mu, mt = (float(x) for x in r.stdout.strip().splitlines()[0].split(","))
            uso.update(gpu=round(g), vram=round(100 * mu / max(1, mt)))
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    uso["hilos"] = os.cpu_count() or 0
    return uso


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


PS_ELEGIR = r"""
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$f = New-Object System.Windows.Forms.Form
$f.TopMost = $true; $f.ShowInTaskbar = $true; $f.Text = 'Sala de edicion'
$f.StartPosition = 'CenterScreen'; $f.Size = New-Object System.Drawing.Size(1,1); $f.Opacity = 0
$f.Show(); $f.Activate(); $f.BringToFront()
$d = New-Object System.Windows.Forms.FolderBrowserDialog
$d.Description = 'Sala de edicion: elige la carpeta con tus clips'
$d.ShowNewFolderButton = $true
$d.SelectedPath = [Environment]::GetFolderPath('Desktop')
if ($d.ShowDialog($f) -eq [System.Windows.Forms.DialogResult]::OK) { [Console]::Out.Write($d.SelectedPath) }
$f.Close()
"""


def elegir_carpeta(pedido: str) -> None:
    """La oficina pidió elegir una carpeta: se abre en esta compu la ventana de Windows (encima de todo) para escogerla."""
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    of = Oficina(cfg["servidor"], cfg["token"])
    try:  # «ya la abrí»: en la oficina te dice que la busques
        of.post("carpeta_elegida", {"id": pedido, "estado": "abierta"}, timeout=15)
    except requests.RequestException:
        pass
    ruta, error = "", ""
    log("Abriendo la ventana para elegir carpeta…")
    if WINDOWS:
        try:
            r = _PopenOriginal(["powershell", "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass", "-Command", PS_ELEGIR],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=0x08000000)  # sin consola
            salida, err = r.communicate(timeout=900)
            ruta = salida.decode("utf-8", "replace").strip().lstrip("\ufeff")
            if r.returncode and not ruta:
                error = "No pude abrir la ventana de Windows: " + err.decode("utf-8", "replace").strip()[-150:]
        except Exception as exc:  # noqa: BLE001
            error = f"No pude abrir la ventana de Windows: {exc}"[:200]
    if not WINDOWS or (error and not ruta):  # respaldo: tkinter
        try:
            import tkinter as tk
            from tkinter import filedialog
            raiz = tk.Tk()
            raiz.attributes("-topmost", True)
            raiz.geometry("1x1+200+200")
            raiz.lift()
            raiz.focus_force()
            raiz.update()
            inicio = Path(os.environ.get("USERPROFILE") or Path.home()) / "Desktop"
            ruta = filedialog.askdirectory(parent=raiz, title="Sala de edición: elige la carpeta con tus clips",
                                           initialdir=str(inicio if inicio.is_dir() else Path.home()), mustexist=True) or ""
            raiz.destroy()
            error = ""
        except Exception as exc:  # noqa: BLE001
            error = error or f"No pude abrir la ventana para elegir carpeta: {exc}"[:200]
    if error:
        log(error)
    if ruta and WINDOWS:
        ruta = ruta.replace("/", "\\")
    log(f"Carpeta elegida: {ruta or '(ninguna)'}")
    try:
        of.post("carpeta_elegida", {"id": pedido, "ruta": ruta, "error": error}, timeout=20)
    except requests.RequestException as exc:
        log(f"No pude avisar qué carpeta elegiste: {exc}")


# ---------- el cerebro: Claude Code en esta compu (con tu plan de Claude, sin gastar de la API) ----------
def claude_code() -> str:
    """Ruta de Claude Code si está instalado; vacío si no."""
    candidatos = [shutil.which("claude"), Path.home() / ".local" / "bin" / ("claude.exe" if WINDOWS else "claude")]
    if WINDOWS:
        candidatos.append(Path(os.environ.get("APPDATA", "")) / "npm" / "claude.cmd")
    for c in candidatos:
        if c and Path(c).is_file():
            return str(c)
    return ""


def estado_claude() -> str:
    """'listo' (instalado y con sesión), 'sin_sesion' o '' (no instalado)."""
    if not claude_code():
        return ""
    cuenta = Path.home() / ".claude.json"
    try:
        con_cuenta = cuenta.exists() and '"oauthAccount"' in cuenta.read_text(encoding="utf-8", errors="replace")
    except OSError:
        con_cuenta = False
    sesion = (Path.home() / ".claude" / ".credentials.json").exists() or con_cuenta or bool(os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"))
    return "listo" if sesion or platform.system() == "Darwin" else "sin_sesion"


INSTRUCCION = ("Lee el archivo instrucciones.md de esta carpeta y haz exactamente lo que pide. Mira con Read cada imagen "
               "que mencione. Tu respuesta final va SOLO en el archivo {salida} (JSON válido). No hagas nada más.")


def preguntar_a_claude(carpeta: Path, salida: str = "respuesta.json", minutos: int = 8) -> dict:
    """Corre Claude Code (sin ventana) en `carpeta`, que ya tiene instrucciones.md, y regresa el JSON que escribió."""
    ruta = claude_code()
    if not ruta:
        raise RuntimeError("Claude Code no está instalado en esta compu.")
    (carpeta / salida).unlink(missing_ok=True)
    cmd = [ruta, "-p", INSTRUCCION.format(salida=salida), "--output-format", "json", "--max-turns", "40",
           "--permission-mode", "acceptEdits", "--allowedTools", "Read,Write,Edit,Glob"]
    if os.environ.get("SALA_MODELO_CLAUDE"):  # p. ej. "opus" o "sonnet"; si no, el que tenga tu plan por defecto
        cmd += ["--model", os.environ["SALA_MODELO_CLAUDE"]]
    try:
        r = subprocess.run(cmd, cwd=carpeta, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=minutos * 60)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Claude Code tardó más de {minutos} min.") from None
    try:
        info = json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {}
    except ValueError:
        info = {}
    texto = str(info.get("result") or "")
    if info.get("is_error") or (r.returncode and not (carpeta / salida).exists()):
        motivo = texto or r.stderr.strip()[-200:] or f"salió con código {r.returncode}"
        if "login" in motivo.lower() or "api key" in motivo.lower():
            motivo = "no tiene la sesión abierta (abre «Claude Code» del escritorio una vez e inicia sesión)"
        elif "limit" in motivo.lower():
            motivo = "llegaste al límite de tu plan por ahora"
        raise RuntimeError(f"Claude Code: {motivo}"[:240])
    archivo = carpeta / salida
    crudo = archivo.read_text(encoding="utf-8", errors="replace") if archivo.exists() else texto
    m = re.search(r"\{.*\}", crudo, re.S)
    if not m:
        raise RuntimeError("Claude Code no dejó una respuesta que se pueda leer.")
    try:
        return json.loads(m.group(0))
    except ValueError as exc:
        raise RuntimeError(f"Claude Code dejó un JSON chueco ({exc})"[:200]) from None


def pensar(of: "Oficina", t: dict, temporal: Path, avance) -> None:
    """La sala te manda lo que pidió Miguel + los cuadros de los clips; Claude Code arma la respuesta y el plan."""
    tid, par = t["id"], t["parametros"]
    temporal.mkdir(parents=True, exist_ok=True)
    for e in t["entradas"]:  # las hojas de cuadros de cada clip
        of.bajar(tid, e["n"], temporal / e["nombre"])
    (temporal / "instrucciones.md").write_text(par["instrucciones"], encoding="utf-8")
    (temporal / "formato.json").write_text(json.dumps(par["schema"], ensure_ascii=False, indent=1), encoding="utf-8")
    avance("Pensando con Claude Code", 0.3)
    inicio = time.time()
    respuesta = preguntar_a_claude(temporal, minutos=int(par.get("minutos") or 8))
    of.post(f"terminar/{tid}", {"ok": True, "resultado": {"json": respuesta, "segundos": round(time.time() - inicio)}})
    log(f"Pensé «{t.get('etiqueta')}» con Claude Code en {round(time.time() - inicio)} s.")


def revisar(video: Path, plan: dict, info: dict, par: dict, clips: Path, temporal: Path) -> dict:
    """Mira el borrador terminado (cuadros + lo que se oye) y, si algo está mal, regresa un plan corregido."""
    import editor_libre
    from manual_edicion import MANUAL
    carpeta = temporal / "revision"
    shutil.rmtree(carpeta, ignore_errors=True)
    carpeta.mkdir(parents=True)
    total = max(1.0, float(info.get("segundos") or 1))
    tiempos = sorted({round(x, 1) for x in [0.3, 1.2, 2.5] + [3 + (total - 3.5) * i / 8 for i in range(9)] if x < total - 0.1})
    cuadros = []
    for x in tiempos:
        nombre = f"cuadro_{x:05.1f}s.jpg"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{x}", "-i", str(video), "-frames:v", "1",
                        "-vf", "scale=360:-2", "-q:v", "4", str(carpeta / nombre)], capture_output=True, timeout=60)
        if (carpeta / nombre).exists():
            cuadros.append(nombre)
    dicho = " ".join(f"[{w['t']:.1f}] {w['w']}" if i % 8 == 0 else w["w"]
                     for i, w in enumerate(info.get("palabras") or []) if w.get("w"))
    pedazos = "\n".join(f"- {p['desde']}-{p['hasta']} s: {p['clip']} (desde su segundo {p['del_segundo']})"
                        + (f", viéndose {p['apoyo']}" if p.get("apoyo") else "") for p in info.get("pedazos") or [])
    (carpeta / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    (carpeta / "formato_plan.json").write_text(json.dumps(editor_libre.PLAN_SCHEMA, ensure_ascii=False, indent=1), encoding="utf-8")
    (carpeta / "instrucciones.md").write_text(
        f"# Revisa tu borrador antes de mandárselo a Miguel\n\nEres el editor. Ya hiciste un borrador de "
        f"{total:.1f} s con el plan de plan.json. Revísalo como lo haría un editor exigente, con este manual:\n\n{MANUAL}\n\n"
        f"## Lo que pidió Miguel y lo que sabes de los clips\n{par.get('contexto') or '(sin más contexto)'}\n\n"
        f"## Cómo quedó\nCuadros del video final (míralos TODOS con Read): {', '.join(cuadros)} — el nombre dice el segundo.\n"
        f"Pedazos en orden:\n{pedazos}\n\nLo que se oye (con segundos): {dicho[:6000] or '(no se habla)'}\n\n"
        "## Qué hacer\nRevisa la lista 'ANTES DE ENTREGAR' del manual. Solo cuenta lo que de verdad se ve mal o se oye mal "
        "(gancho flojo o que arranca con saludo, partes repetidas, tomas movidas/oscuras/borrosas, texto que tapa caras o "
        "con faltas, final que se alarga, silencio o palabra cortada, algo que Miguel pidió y no está). No cambies gustos "
        "por cambiar, y respeta lo que Miguel pidió.\n\nEscribe revision.json con: {\"ok\": true/false, \"problemas\": "
        "[frases cortas en español de lo que corregiste], \"plan\": el plan completo corregido (mismo formato que plan.json "
        "y formato_plan.json; solo clips que existen)}. Si está bien, ok=true, problemas=[] y plan = el mismo de plan.json.",
        encoding="utf-8")
    r = preguntar_a_claude(carpeta, "revision.json", minutos=6)
    nombres = {f.name for f in clips.iterdir() if f.is_file()}
    nuevo = editor_libre.normalizar_plan(r.get("plan") or {}, nombres)
    problemas = [str(x)[:160] for x in (r.get("problemas") or []) if str(x).strip()][:6]
    if r.get("ok") or not problemas or not nuevo.get("clips"):
        return {"problemas": [], "plan": None, "revisado": True}
    return {"problemas": problemas, "plan": nuevo, "revisado": True}


def carpeta_del_proyecto(of: "Oficina", t: dict, avance) -> Path:
    """La carpeta de clips del proyecto en esta compu; baja ahí (y a Musica) lo que subiste desde la oficina."""
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
    return clips


MOTION = AQUI / "motion"
ESTADO_MOTION = {"texto": ""}


def preparar_motion() -> str:
    """Instala Remotion (motion graphics) la primera vez o cuando cambia; necesita Node.js."""
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm:
        return "sin_node"
    lock = MOTION / "package-lock.json"
    firma = hashlib.sha1(lock.read_bytes()).hexdigest()[:12] if lock.exists() else "x"
    marca = MOTION / "node_modules" / ".firma_sala"
    if marca.exists() and marca.read_text() == firma:
        return "listo"
    log("Instalando Remotion para los motion graphics (la primera vez tarda unos minutos)…")
    r = subprocess.run([npm, "ci", "--no-audit", "--no-fund"], cwd=MOTION, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=1800, shell=WINDOWS)
    if r.returncode:
        log(f"No pude instalar Remotion: {(r.stderr or r.stdout)[-300:]}")
        return "error"
    marca.write_text(firma)
    return "listo"


def editar_libre(of: "Oficina", t: dict, temporal: Path, avance) -> None:
    """Editor IA: Claude Code edita con las manos libres en la carpeta del proyecto y entrega la versión."""
    import editor_ia
    par, tid = t["parametros"], t["id"]
    claude = claude_code()
    if not claude or estado_claude() != "listo":
        raise RuntimeError("Claude Code no está listo en esta compu (instálalo o inicia sesión con INSTALAR_SALA.bat).")
    clips = carpeta_del_proyecto(of, t, avance)
    nombre = _limpio(par.get("nombre") or par["carpeta"])
    mesa = editor_ia.preparar(clips, nombre, par.get("formato") or "", MUSICA, claude, ESTADO_MOTION["texto"] == "listo",
                              par.get("estilo") or "", par.get("recetas") or [])
    (mesa / "resultado.json").unlink(missing_ok=True)
    n = par["version"]
    historial = "\n".join(par.get("historial") or [])
    pendientes = "\n".join(f"- {x['texto']}" for x in par.get("por_aprender") or [])
    correccion = par.get("modo") == "correccion"
    prompt = (f"Mensaje de Miguel desde la oficina: «{par['mensaje']}»\n"
              + (f"(Plática reciente en la oficina:\n{historial})\n" if historial else "")
              + ("Es una CORRECCIÓN sobre la versión anterior: sigue la sección «Ahorra el uso» al pie de la letra.\n"
                 if correccion else "")
              + (f"Calificaciones de Miguel por aprender (conviértelas en reglas en «aprendido» si dicen algo de su gusto):\n"
                 f"{pendientes}\n" if pendientes else "")
              + f"Si editas, esta entrega es la versión {n}: guárdala como ../Ediciones/{nombre} v{n}.mp4. "
              "Sigue CLAUDE.md y al final escribe resultado.json.")
    avance("Leyendo lo que pediste", 0.03)
    inicio = time.time()
    # el modelo: las correcciones con Haiku (gasta mucho menos de tu plan); lo nuevo con Sonnet. Si Haiku falla, Sonnet.
    modelo = (os.environ.get("SALA_MODELO_CORRECCION", "haiku") if correccion
              else os.environ.get("SALA_MODELO_CLAUDE", "sonnet"))
    try:
        final = editor_ia.correr(mesa, claude, prompt, avance, modelo=modelo)
    except RuntimeError as exc:
        if not correccion or "límite" in str(exc) or "sesión" in str(exc):
            raise
        log(f"La corrección con {modelo} falló ({exc}); la intento con el editor fuerte.")
        modelo = os.environ.get("SALA_MODELO_CLAUDE", "sonnet")
        final = editor_ia.correr(mesa, claude, prompt, avance, modelo=modelo)
    try:
        res = json.loads((mesa / "resultado.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        res = {}
    respuesta = str(res.get("respuesta") or "Listo.")[:2000]
    video_rel = str(res.get("video") or "")
    video = (clips / video_rel) if video_rel else None
    if video is None or not video.is_file():  # por si no lo apuntó: la entrega con el número de esta versión
        candidato = clips / "Ediciones" / f"{nombre} v{n}.mp4"
        video = candidato if candidato.is_file() and candidato.stat().st_mtime > inicio else None
    resultado = {"respuesta": respuesta, "cambios": [str(c)[:200] for c in (res.get("cambios") or [])][:8],
                 "segundos_trabajo": round(time.time() - inicio),
                 "aprendido": [str(x)[:200] for x in (res.get("aprendido") or []) if str(x).strip()][:6],
                 "tipo": str(res.get("tipo") or "")[:30], "descripcion": str(res.get("descripcion") or "")[:160],
                 "uso": {"modelo": modelo, "pasos": final.get("num_turns"), "usd": final.get("total_cost_usd")}}
    receta = {}
    for archivo in ("plan.json", "props.json"):  # lo que usó: si le das 👍, se vuelve receta para los videos parecidos
        f = mesa / archivo
        if f.exists() and f.stat().st_size < 120_000:
            try:
                receta[archivo[:-5]] = json.loads(f.read_text(encoding="utf-8"))
            except ValueError:
                pass
    if receta:
        if isinstance(receta.get("props"), dict) and isinstance(receta["props"].get("subtitulos"), dict):
            receta["props"] = {**receta["props"], "subtitulos": {**receta["props"]["subtitulos"], "palabras": []}}
        resultado["receta"] = receta
    if video:
        avance("Subiendo tu video", 0.97)
        salida = temporal / "salida"
        salida.mkdir(parents=True, exist_ok=True)
        copia = salida / f"v{n}.mp4"
        shutil.copyfile(video, copia)
        cuadro = salida / f"v{n}.cuadro.jpg"
        dur = cris.duracion(copia)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{dur * 0.4:.2f}", "-i", str(copia), "-frames:v", "1",
                        "-q:v", "3", str(cuadro)], capture_output=True, timeout=60)
        of.subir(tid, copia)
        if cuadro.exists():
            of.subir(tid, cuadro)
        resultado.update(video=copia.name, cuadro=cuadro.name if cuadro.exists() else None, segundos=round(dur, 1))
    of.post(f"terminar/{tid}", {"ok": True, "resultado": resultado})
    log(f"Editor IA «{nombre}»: {'v' + str(n) if video else 'sin video'} en {round(time.time() - inicio)} s.")


def editar_edu(of: "Oficina", t: dict, temporal: Path, avance, con_claude: bool = False) -> None:
    """🎬 Un video de YouTube de la oficina: esta compu lo edita y lo regresa. Con `con_claude` (trabajo "edu_ia")
    lo dirige Claude Code con el kit Edu de Remotion; si no queda bien, se hace con la plantilla de Edu."""
    tid, m = t["id"], t["parametros"]["manifiesto"]
    mesa = temporal / "mesa"
    mesa.mkdir(parents=True, exist_ok=True)
    total = len(t["entradas"])
    for e in t["entradas"]:  # bajar y acomodar cada archivo donde lo espera el editor
        avance(f"Bajando materiales ({e['n'] + 1} de {total})", 0.05 * e["n"] / max(1, total))
        relativa = m["mapa"].get(e["nombre"])
        if not relativa or ".." in Path(relativa).parts:
            continue
        destino = mesa / relativa
        destino.parent.mkdir(parents=True, exist_ok=True)
        of.bajar(tid, e["n"], destino)
    (mesa / "manifiesto.json").write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    def entregar(final: Path, editor: str, aviso: str) -> None:
        shutil.copyfile(final, mesa / "video.mp4")
        avance("Subiendo el video a la oficina", 0.96)
        of.subir(tid, mesa / "video.mp4")
        of.post(f"terminar/{tid}", {"ok": True, "resultado": {"video": "video.mp4", "editor": editor}})
        log(aviso)

    listo_motion = ESTADO_MOTION["texto"] == "listo"
    estilo = m.get("estilo_edicion")
    # 🧠 Claude dirige mientras haya plan (puliendo la base del director); si el plan se acaba, entra el director
    quiere_claude = (m.get("cerebro") in ("hibrido", "claude") or (con_claude and not m.get("cerebro"))) and estilo != "lana"
    if quiere_claude and claude_code() and listo_motion and not plan_pausado():
        import editor_youtube
        final = editor_youtube.editar(mesa, m, claude_code(), avance, log)
        if final:
            return entregar(final, "claude", f"Claude editó «{t.get('etiqueta')}».")
        if editor_youtube.ULTIMO["limite"]:
            pausar_plan()
            avance("Se acabó tu plan de Claude: edita el director automático", 0.5)
        else:
            avance("Claude no terminó: edita el director automático", 0.5)
    if estilo in ("lana", "pro") and listo_motion:  # 🎬 director automático: no gasta plan
        import editor_youtube
        final = editor_youtube.editar_auto(mesa, m, avance, log)
        if final:
            return entregar(final, "director", f"Edité «{t.get('etiqueta')}» con el director automático.")
        avance("El director no pudo: lo edito con la plantilla", 0.5)
    entorno = {**os.environ, "AUTOCANAL_ESTILO": str(mesa / "estilo"), "AUTOCANAL_SIN_COLA": "1",
               "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    proceso = subprocess.Popen([sys.executable, "-m", "agentes.edicion_remota", str(mesa)], cwd=str(REPO / "autocanal"),
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                               errors="replace", env=entorno, creationflags=0x08000000 if WINDOWS else 0)
    ultimas = []
    for linea in proceso.stdout:
        linea = linea.strip()
        ultimas = (ultimas + [linea])[-15:]
        if linea.startswith("AVANCE "):
            _, fraccion, *paso = linea.split(" ")
            try:
                avance(" ".join(paso)[:60], 0.05 + 0.9 * float(fraccion))
            except ValueError:
                pass
    proceso.wait()
    video = mesa / "video.mp4"
    if proceso.returncode or not video.exists():
        raise RuntimeError("El editor falló: " + " | ".join(x for x in ultimas if x)[-260:])
    avance("Subiendo el video a la oficina", 0.96)
    of.subir(tid, video)
    of.post(f"terminar/{tid}", {"ok": True, "resultado": {"video": "video.mp4"}})
    log(f"Edu: edité «{t.get('etiqueta')}».")


def probar_ssh(of: "Oficina", t: dict) -> None:
    """Prueba fija: entra al servidor por SSH con la llave de esta compu (sin contraseña) y sale. No corre nada más."""
    import re as _re
    host = str(t["parametros"].get("host") or "")
    if not _re.fullmatch(r"[A-Za-z0-9.-]{3,80}", host):
        raise RuntimeError("Dirección del servidor no válida.")
    ssh = shutil.which("ssh") or r"C:\Windows\System32\OpenSSH\ssh.exe"
    if not Path(ssh).exists() and not shutil.which("ssh"):
        raise RuntimeError("Esta compu no tiene el cliente SSH (Configuración → Aplicaciones → Características opcionales → Cliente OpenSSH).")
    llave = Path.home() / ".ssh" / "id_ed25519"
    r = subprocess.run([ssh, "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=15",
                        *(["-i", str(llave)] if llave.exists() else []), f"ubuntu@{host}", "echo ENTRE_OK"],
                       capture_output=True, text=True, timeout=60, creationflags=0x08000000 if WINDOWS else 0)
    salida = (r.stdout + r.stderr).strip()
    if "ENTRE_OK" in r.stdout:
        of.post(f"terminar/{t['id']}", {"ok": True, "resultado": {"ssh": "ok", "llave": llave.exists()}})
        log("SSH: esta compu ya entra al servidor con su llave ✔")
        return
    motivo = ("el servidor todavía no tiene la llave de esta compu" if "Permission denied" in salida
              else "esta compu no tiene llave (corre ssh-keygen -t ed25519)" if not llave.exists()
              else f"no pude conectar: {salida[-160:]}")
    raise RuntimeError(f"SSH: {motivo}")


def hacer_proyecto(of: "Oficina", t: dict, temporal: Path, avance) -> None:
    """Un proyecto de la sala: los clips están en su carpeta de esta compu (lo que subiste al servidor se baja ahí)."""
    import editor_libre
    editor_libre.analizar = analizar  # para saltarse partes movidas/borrosas
    par, tid = t["parametros"], t["id"]
    clips = carpeta_del_proyecto(of, t, avance)
    n = par["version"]
    video = temporal / "salida" / f"v{n}.mp4"
    video.parent.mkdir(parents=True, exist_ok=True)
    inicio = time.time()
    info, revision = {}, {"problemas": [], "plan": None}
    segundos = editor_libre.render(par["plan"], clips, video, MUSICA, "", avance, info=info)
    if par.get("revisar") and estado_claude() == "listo":  # lo ve antes de mandártelo y, si algo está mal, lo corrige
        try:
            avance("Revisando mi borrador", 0.9)
            revision = revisar(video, par["plan"], info, par, clips, temporal)
            if revision["plan"]:
                avance("Corrigiendo lo que vi", 0.92)
                segundos = editor_libre.render(revision["plan"], clips, video, MUSICA, "", avance)
        except Exception as exc:  # noqa: BLE001 — si la revisión falla, se manda el borrador como está
            log(f"No pude revisar el borrador: {exc}")
            revision = {"problemas": [], "plan": None, "error": str(exc)[:160]}
    avance("Subiendo tu video", 0.97)
    of.subir(tid, video)
    cuadro = video.with_name(f"v{n}.cuadro.jpg")
    if cuadro.exists():
        of.subir(tid, cuadro)
    copia = clips / "Ediciones" / f"{_limpio(par['carpeta'])} v{n}.mp4"  # y una copia en tu compu
    copia.parent.mkdir(exist_ok=True)
    shutil.copyfile(video, copia)
    of.post(f"terminar/{tid}", {"ok": True, "resultado": {"video": video.name, "cuadro": cuadro.name if cuadro.exists() else None,
                                                         "segundos": segundos, "revision": revision}})
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
        if t["tipo"] == "pensar":
            return pensar(of, t, carpeta, avance)
        if t["tipo"] == "claude_libre":
            return editar_libre(of, t, carpeta, avance)
        if t["tipo"] in ("edu", "edu_ia", "edu_estilo"):  # 🎬 un video de YouTube de la oficina (edu_ia: lo dirige Claude)
            return editar_edu(of, t, carpeta, avance, con_claude=t["tipo"] == "edu_ia")
        if t["tipo"] == "expediente":  # 🕵️ un video de «¿Quién MATÓ a…?» con el motor de canal-youtube
            return render_expediente(of, t, carpeta, avance)
        if t["tipo"] == "probar_ssh":  # 🔑 ¿esta compu ya entra al servidor con su llave?
            return probar_ssh(of, t)
        if t["tipo"] == "probar_app":  # 📱 el robot prueba la app en tu Android
            import robot_cel
            return robot_cel.probar(of, t, carpeta, avance, claude_code(), log)
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


# ---------- 🕵️ Expedientes: el motor de video de «¿Quién MATÓ a…?» (canal-youtube/motor, en el repo) ----------
CANAL_YT = REPO / "canal-youtube"
_PY_MOTOR: list = []


def python_motor() -> list[str] | None:
    """El Python que tiene OpenCV/NumPy/Pillow (el motor los necesita). Prueba el de la sala y luego el de Windows."""
    if _PY_MOTOR and (_PY_MOTOR[0] or time.time() - _PY_MOTOR[1] < 600):  # si no hubo, se vuelve a probar cada 10 min
        return _PY_MOTOR[0]
    _PY_MOTOR[:] = [None, time.time()]
    import editor_ia
    for cand in ([editor_ia.python_exe()], ["py", "-3"], ["python"]):
        try:
            r = subprocess.run([*cand, "-c", "import cv2, numpy, PIL"], capture_output=True, timeout=60,
                               creationflags=0x08000000 if WINDOWS else 0)
            if r.returncode == 0:
                _PY_MOTOR[:] = [cand, time.time()]
                return cand
        except (OSError, subprocess.SubprocessError):
            continue
    return None


def motor_expedientes() -> dict:
    """¿Esta compu puede hacer videos de Expedientes? (Windows con sus fuentes, motor en el repo y clave de Azure)."""
    if not (CANAL_YT / "motor" / "motor.py").exists():
        return {"listo": False, "texto": "falta el motor (actualiza la sala)"}
    if not python_motor():
        return {"listo": False, "texto": "falta OpenCV (pip install opencv-python numpy pillow)"}
    return {"listo": True, "texto": "listo"}


def render_expediente(of: "Oficina", t: dict, temporal: Path, avance) -> None:
    """Baja el paquete del caso (guion + storyboard + manifiestos), baja el material libre, hace la voz con Azure y
    el video con el motor, saca las miniaturas y regresa todo a la oficina."""
    import re as _re
    import zipfile as _zip
    tid, par = t["id"], t["parametros"]
    nombre_dir = str(par.get("carpeta") or "")
    if not _re.fullmatch(r"[0-9]{2}-[a-z0-9-]{1,40}", nombre_dir):
        raise RuntimeError("Nombre de carpeta del episodio inválido.")
    py = python_motor()
    if not py:
        raise RuntimeError("Esta compu no tiene OpenCV para el motor (pip install opencv-python numpy pillow).")
    clave = CANAL_YT / ".azure_speech"
    prestada = False
    if not clave.exists():  # la oficina presta la clave de Azure para este video y se borra al terminar
        azure = par.get("azure") or {}
        if not azure.get("clave"):
            raise RuntimeError("No hay clave de Azure: ponla en el .env del servidor (AZURE_SPEECH_KEY).")
        clave.write_text(f"{azure['clave']}\n{azure.get('region') or 'eastus'}\n", encoding="utf-8")
        prestada = True
    try:
        _render_expediente(of, t, temporal, avance, nombre_dir, py)
    finally:
        if prestada:
            clave.unlink(missing_ok=True)


def _render_expediente(of, t, temporal, avance, nombre_dir, py) -> None:
    import re as _re
    import zipfile as _zip
    tid = t["id"]
    avance("Bajando el caso", 0.01)
    paquete = temporal / "caso.zip"
    of.bajar(tid, 0, paquete)
    ep = CANAL_YT / nombre_dir
    ep.mkdir(parents=True, exist_ok=True)
    with _zip.ZipFile(paquete) as z:
        for n in z.namelist():
            if _re.fullmatch(r"material/fotos/[a-z0-9._-]+\.(jpg|json)", n):  # fotos ya revisadas en el servidor
                (ep / "material" / "fotos").mkdir(parents=True, exist_ok=True)
                (ep / n).write_bytes(z.read(n))
                continue
            if "/" in n or "\\" in n or n.startswith(".") or not n.endswith((".md", ".py", ".json", ".jpg")):
                continue
            (ep / n).write_bytes(z.read(n))
    shutil.rmtree(ep / "render", ignore_errors=True)
    sin_ventana = 0x08000000 if WINDOWS else 0

    def correr(cmd, desde, hasta, que):
        p = subprocess.Popen([*py, "-E", "-P", *cmd], cwd=str(CANAL_YT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, encoding="utf-8", errors="replace", creationflags=sin_ventana)
        ultimas, va, señal, motivo = [], desde, [time.time()], []

        def vigilante():  # 🐕 si la oficina lo canceló o lleva 20 min sin decir nada, se mata (y la compu queda libre)
            while p.poll() is None:
                time.sleep(30)
                if p.poll() is not None:
                    break
                try:
                    r = of.post(f"avance/{tid}", {"paso": f"{que}…", "avance": va})
                except Exception:  # noqa: BLE001
                    r = {}
                if r.get("cancelado"):
                    motivo.append("la oficina lo canceló")
                elif time.time() - señal[0] > 1200:
                    motivo.append("se quedó 20 min sin avanzar")
                if motivo:
                    p.kill()
                    break
        threading.Thread(target=vigilante, daemon=True).start()
        for linea in p.stdout:
            linea = linea.strip()
            if not linea:
                continue
            señal[0] = time.time()
            ultimas = (ultimas + [linea])[-15:]
            m = _re.search(r"(\d+)/(\d+)", linea)
            if m:
                va = max(va, desde + (hasta - desde) * min(1, int(m.group(1)) / max(1, int(m.group(2)))))
            avance(f"{que}: {linea[:70]}", va)
        if p.wait() != 0:
            raise RuntimeError(f"{que} falló: " + (motivo[0] if motivo else " | ".join(ultimas[-4:])[-400:]))

    for sub in ("fotos", "videos"):
        man = ep / f"manifiesto-{sub}.json"
        if man.exists() and json.loads(man.read_text(encoding="utf-8")):
            correr(["motor/fuentes_libres.py", "descargar", str(man), str(ep / "material" / sub)], 0.03, 0.2,
                   f"Bajando {sub} libres")
    correr(["motor/motor.py", nombre_dir, "--render"], 0.2, 0.93, "Haciendo el video")
    correr([f"{nombre_dir}/miniatura.py"], 0.93, 0.96, "Miniaturas")
    render = ep / "render"
    video = next((v for v in sorted(render.glob("*.mp4")) if "solo-video" not in v.name), None)
    if not video:
        raise RuntimeError("El motor terminó pero no encontré el MP4.")
    avance("Subiendo el video a la oficina", 0.96)
    for f in [video, *render.glob("*.srt"), *render.glob("*-capitulos.txt"), *render.glob("*-creditos.txt"),
              *render.glob("miniatura-*.jpg")]:
        of.subir(tid, f)
    log(f"Expediente {nombre_dir}: video listo ({round(video.stat().st_size / 1e6)} MB).")


PLAN_PAUSA = CARPETA / "plan_pausado.txt"


def plan_pausado() -> bool:
    """¿Se acabó el plan de Claude hace poco? (se vuelve a probar a la hora)."""
    try:
        return time.time() < float(PLAN_PAUSA.read_text().strip() or 0)
    except (OSError, ValueError):
        return False


def pausar_plan(segundos: int = 3600) -> None:
    try:
        PLAN_PAUSA.parent.mkdir(parents=True, exist_ok=True)
        PLAN_PAUSA.write_text(str(time.time() + segundos))
        log("Se acabó el plan de Claude: el director automático edita la siguiente hora.")
    except OSError:
        pass


def actualizarme() -> None:
    """Cada rato revisa si hay versión nueva en GitHub; si la hay (y no está editando), se actualiza y se reinicia."""
    if SERVIDOR:  # en el servidor el código lo actualiza su propio servicio
        return
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
    # 🎮 que todo lo que edita (motor de Expedientes, plantilla, Remotion) use la tarjeta en vez del procesador
    if con_nvenc:
        os.environ["SALA_NVENC"] = "1"
    if tarjeta:
        os.environ["SALA_GPU"] = "1"
    cris.CACHE = CARPETA / "oido"
    cris.CACHE.mkdir(parents=True, exist_ok=True)
    datos = {"gpu": tarjeta or platform.processor()[:60], "nvenc": con_nvenc, "oido": "preparando…", "version": version(),
             "tipos": ["cris", "libre"], "con_carpetas": True}

    def cerebro():  # ¿Claude Code instalado y con sesión? Entonces esta compu también piensa
        import robot_cel
        datos["claude_code"] = estado_claude()
        cel = robot_cel.celular()  # 📱 ¿tu Android viejo está conectado? Entonces también prueba apps
        datos["celular"] = cel.get("modelo") or ("falta autorizar" if cel.get("pendiente")
                                                  else robot_cel.MOTIVOS.get(cel.get("motivo"), ""))
        datos["expedientes"] = motor_expedientes()["texto"]
        datos["tipos"] = ["cris", "libre", "edu", "probar_ssh", *(["pensar", "claude_libre"] if datos["claude_code"] == "listo" else []),
                          *(["expediente"] if motor_expedientes()["listo"] else []),
                          *(["edu_ia"] if datos["claude_code"] == "listo" and ESTADO_MOTION["texto"] == "listo" else []),
                          *(["edu_estilo"] if ESTADO_MOTION["texto"] == "listo" else []),  # 🐑 estilo fijo: sin Claude
                          # 📱 el robot paso a paso no necesita Claude Code aquí (lo piensa la oficina)
                          *(["probar_app"] if cel.get("serie") and (os.environ.get("ROBOT_MODO") != "claude_code"
                                                                    or datos["claude_code"] == "listo") else [])]
        datos["motion"] = ESTADO_MOTION["texto"]
        if SERVIDOR:  # el servidor solo hace videos (nada de Claude Code, oído ni cel: eso es de tus compus)
            datos["tipos"] = [x for x in datos["tipos"] if x in ("edu", "edu_estilo", "expediente")]
            datos["claude_code"], datos["celular"] = "", ""
    cerebro()
    listo = threading.Event()
    # 📱 carril del cel: la prueba del robot corre aparte, así la compu sigue editando mientras graba
    carril_cel = {"tid": None, "hilo": None}
    of_cel = Oficina(cfg["servidor"], cfg["token"])

    def cel_libre() -> bool:
        return not (carril_cel["hilo"] and carril_cel["hilo"].is_alive())

    def atender_cel(r: dict) -> None:
        t = r.get("trabajo_cel")
        if t and cel_libre() and carril_cel["tid"] != t["id"]:
            carril_cel["tid"] = t["id"]
            carril_cel["hilo"] = threading.Thread(target=hacer, args=(of_cel, t), daemon=True)
            carril_cel["hilo"].start()

    def pulso():  # "sigo prendida" cada 10 s, aunque esté ocupada analizando o editando
        of2 = Oficina(cfg["servidor"], cfg["token"])
        vueltas = 0
        while True:
            vueltas += 1
            if vueltas % 30 == 0:  # cada 5 min: por si ya instalaste o iniciaste sesión en Claude Code
                cerebro()
            elif vueltas % 3 == 0:  # cada 30 s: ¿conectaste o autorizaste el cel? (es rápido)
                try:
                    import robot_cel
                    c = robot_cel.celular()
                    nuevo = c.get("modelo") or ("falta autorizar" if c.get("pendiente")
                                                else robot_cel.MOTIVOS.get(c.get("motivo"), ""))
                    if bool(c.get("serie")) != ("probar_app" in datos.get("tipos", [])) or nuevo != datos.get("celular"):
                        cerebro()
                except Exception:  # noqa: BLE001
                    pass
            try:
                atender_cel(of2.post("latido", {**datos, "libre": False, "pulso": True, "libre_cel": cel_libre(), "uso": uso_equipo(),
                                                "estado": ESTADO_COMPU["texto"]}, timeout=20))
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

    def motion():  # Remotion para los motion graphics del editor IA (aparte: la primera vez tarda)
        ESTADO_MOTION["texto"] = "instalando"
        try:
            ESTADO_MOTION["texto"] = preparar_motion()
        except Exception as exc:  # noqa: BLE001
            log(f"No pude preparar los motion graphics: {exc}")
            ESTADO_MOTION["texto"] = "error"
        cerebro()

    def adb():  # las herramientas para manejar el Android por cable (la primera vez se instalan solas)
        import robot_cel
        try:
            if robot_cel.instalar_adb():
                cerebro()
        except Exception as exc:  # noqa: BLE001
            log(f"No pude preparar adb para el celular: {exc}")

    if SERVIDOR:  # sin oído ni cel; motion solo si ya está instalado
        listo.set()
        datos["oido"] = "no aplica"
        ESTADO_COMPU["texto"] = "Lista"
        if (AQUI / "motion" / "node_modules").exists():
            ESTADO_MOTION["texto"] = "listo"
            cerebro()
    for f in ((pulso,) if SERVIDOR else (pulso, preparar, carpetas, motion, adb)):
        threading.Thread(target=f, daemon=True).start()
    # 🖥️ varios videos a la vez: cuántos aguanta esta compu (SALA_A_LA_VEZ en el .env de la compu manda)
    capacidad = int(os.environ.get("SALA_A_LA_VEZ") or 0) or (3 if con_nvenc else 2 if (os.cpu_count() or 4) >= 12 else 1)
    corriendo: dict = {}  # id del trabajo → hilo
    os.environ["SALA_CAPACIDAD"] = str(capacidad)  # Remotion reparte los núcleos entre los videos a la vez
    log(f"Esta compu edita hasta {capacidad} video(s) a la vez.")

    def libres() -> int:
        for tid in [k for k, h in corriendo.items() if not h.is_alive()]:
            corriendo.pop(tid, None)
        return max(0, capacidad - len(corriendo))

    def arrancar(t: dict) -> None:
        if t["id"] in corriendo:
            return
        hilo = threading.Thread(target=hacer, args=(Oficina(cfg["servidor"], cfg["token"]), t), daemon=True)
        corriendo[t["id"]] = hilo
        hilo.start()

    espera, revisado = 5, time.time()
    while True:
        if time.time() - revisado > 1800 and not corriendo and cel_libre():  # cada 30 min, sin nada a medias
            revisado = time.time()
            actualizarme()
        try:
            n_libres = libres()
            r = of.post("latido", {**datos, "libre": n_libres > 0, "capacidad": capacidad, "libres": n_libres, "uso": uso_equipo(),
                                   "oido_listo": listo.is_set(), "libre_cel": cel_libre(),
                                   "estado": ESTADO_COMPU["texto"]}, timeout=20)
            espera = 5
            atender_cel(r)
            if r.get("pedir_carpeta"):  # «📂 Elegir carpeta…» desde la oficina
                threading.Thread(target=elegir_carpeta, args=(r["pedir_carpeta"]["id"],), daemon=True).start()
            if "carpetas" in r and not pedido["evento"].is_set():
                pedido["carpetas"] = (r["carpetas"], r.get("proyectos"))
                pedido["evento"].set()
            # sala nueva: lista de trabajos; sala vieja: uno solo
            for t in (r.get("trabajos") or ([r["trabajo"]] if r.get("trabajo") else [])):
                arrancar(t)
            n = len([h for h in corriendo.values() if h.is_alive()])
            if n:
                ESTADO_COMPU["texto"] = f"Editando {n} video(s) a la vez"
                espera = 3
            elif ESTADO_COMPU["texto"].startswith("Editando"):
                ESTADO_COMPU["texto"] = "Lista"
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
