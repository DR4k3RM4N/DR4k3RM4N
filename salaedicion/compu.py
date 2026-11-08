"""El programa que corre en tus compus (sala de edición).

Le pregunta a tu oficina cada pocos segundos "¿hay algo que editar?". Si hay, baja los clips, edita con tu tarjeta
de video (NVENC para el video, Whisper grande en la GPU para los subtítulos) y sube el resultado. No abre puertos.

    python compu.py --vincular 123456 --servidor https://tu-oficina --nombre "PC 3070"   # una sola vez
    python compu.py                                                                     # queda trabajando

Lo instala solo INSTALAR_SALA.bat (Windows) y arranca al prender la compu.
"""
from __future__ import annotations

import argparse
import json
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
CARPETA = (Path(os.environ.get("LOCALAPPDATA", Path.home())) / "SalaEdicion" if WINDOWS
           else Path.home() / ".salaedicion")
CONFIG = CARPETA / "config.json"
TRABAJOS = CARPETA / "trabajos"
LOG = CARPETA / "compu.log"


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
        total = len(t["entradas"])
        for e in t["entradas"]:
            avance(f"Bajando clip {e['n'] + 1} de {total}", 0.02 * e["n"] / max(1, total))
            of.bajar(tid, e["n"], carpeta / "clips" / e["nombre"])
        if t["tipo"] != "cris":
            raise RuntimeError(f"Esta versión no sabe hacer trabajos de tipo {t['tipo']}.")
        cris.clasificar = clasificar
        salida = carpeta / "salida"
        inicio = time.time()
        videos = cris.editar_todo(carpeta / "clips", t["parametros"], salida, avance)
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


def trabajar() -> None:
    if not CONFIG.exists():
        raise SystemExit("Esta compu no está dada de alta. Corre INSTALAR_SALA.bat (o compu.py --vincular CODIGO).")
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    of = Oficina(cfg["servidor"], cfg["token"])
    tarjeta = gpu()
    con_nvenc = bool(tarjeta) and nvenc()
    configurar_editor(con_nvenc)
    oido = preparar_oido(bool(tarjeta))
    datos = {"gpu": tarjeta or platform.processor()[:60], "nvenc": con_nvenc, "oido": oido, "version": version(),
             "tipos": ["cris"]}
    log(f"Sala de edición: {cfg.get('nombre')} · {datos['gpu'] or 'sin tarjeta NVIDIA'} · NVENC {'sí' if con_nvenc else 'no'}"
        f" · oído {oido}")
    espera = 5
    while True:
        try:
            r = of.post("latido", {**datos, "libre": True}, timeout=20)
            espera = 5
            if r.get("trabajo"):
                hacer(of, r["trabajo"])
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
