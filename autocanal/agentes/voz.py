"""Agente 4 — Voz: narra cada escena (Edge TTS gratis o ElevenLabs con tu voz clonada)."""
from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import time
from pathlib import Path

import requests

from . import config


def duracion(ruta: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(ruta)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out)


def tiempos(audio: Path | str) -> Path:
    """Archivo con el segundo exacto en que se dice cada palabra (para los subtítulos karaoke y los efectos)."""
    return Path(audio).with_suffix(".palabras.json")


def _edge(texto: str, destino: Path) -> None:
    import edge_tts

    voz, rate = config.env("VOZ_EDGE", "es-MX-JorgeNeural"), config.env("VOZ_VELOCIDAD", "+8%")
    try:
        com = edge_tts.Communicate(texto, voz, rate=rate, boundary="WordBoundary")
    except TypeError:  # edge-tts viejito: sin tiempos por palabra
        com = edge_tts.Communicate(texto, voz, rate=rate)
    palabras = []

    async def run():
        with open(destino, "wb") as f:
            async for trozo in com.stream():
                if trozo["type"] == "audio":
                    f.write(trozo["data"])
                elif trozo["type"] == "WordBoundary":
                    palabras.append({"t": round(trozo["offset"] / 1e7, 3), "d": round(trozo["duration"] / 1e7, 3),
                                     "w": trozo["text"]})
    asyncio.run(run())
    if palabras:
        tiempos(destino).write_text(json.dumps(palabras, ensure_ascii=False), encoding="utf-8")
    else:
        tiempos(destino).unlink(missing_ok=True)


def _elevenlabs(texto: str, destino: Path) -> None:
    voz = config.env("ELEVENLABS_VOICE_ID")
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voz}",
        headers={"xi-api-key": config.env("ELEVENLABS_API_KEY"), "accept": "audio/mpeg"},
        json={"text": texto, "model_id": config.env("ELEVENLABS_MODELO", "eleven_multilingual_v2")},
        timeout=300,
    )
    r.raise_for_status()
    destino.write_bytes(r.content)


def _silencio(texto: str, destino: Path) -> None:
    """Solo para pruebas sin internet: silencio con la duración aproximada de la narración."""
    segundos = max(2.5, len(texto.split()) / 2.6)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    "anullsrc=r=44100:cl=mono", "-t", f"{segundos:.2f}", "-q:a", "4", str(destino)],
                   check=True)


MOTORES = {"edge": _edge, "elevenlabs": _elevenlabs, "silencio": _silencio}
VOZ_RESPALDO = "es-MX-DaliaNeural"  # si la voz principal de Edge no responde


def limpiar(texto: str) -> str:
    """Deja solo lo que se puede leer en voz alta (sin emojis ni símbolos raros)."""
    t = (texto or "").replace("&", " y ").replace("%", " por ciento").replace("#", " ")
    t = re.sub(r"[^\w\s.,;:¿?¡!'\"()\-$/áéíóúüñÁÉÍÓÚÜÑ]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t if re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]", t) else ""


def _valido(ruta: Path) -> bool:
    """¿El audio existe y tiene sonido? (un intento fallido puede dejar un archivo vacío)."""
    if not ruta.exists() or ruta.stat().st_size < 1000:
        return False
    try:
        return duracion(ruta) > 0.3
    except (subprocess.CalledProcessError, ValueError):
        return False


def _silencio_fijo(destino: Path, segundos: float = 1.5) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                    "-t", f"{segundos:.2f}", "-q:a", "4", str(destino)], check=True)


def _narrar_una(fn, motor: str, texto: str, destino: Path, i: int) -> None:
    ultimo = None
    for intento in range(3):
        try:
            fn(texto, destino)
            if _valido(destino):
                return
            ultimo = "no llegó audio"
        except Exception as exc:  # noqa: BLE001 — se reintenta
            ultimo = exc
        destino.unlink(missing_ok=True)
        print(f"    voz: escena {i} falló ({ultimo}); reintento {intento + 1}/3", flush=True)
        time.sleep(2 * 2 ** intento)
    if motor == "edge":  # última opción: otra voz de Edge
        anterior = os.environ.get("VOZ_EDGE")
        os.environ["VOZ_EDGE"] = VOZ_RESPALDO
        try:
            _edge(texto, destino)
            if _valido(destino):
                print(f"    voz: escena {i} salió con la voz de respaldo ({VOZ_RESPALDO})", flush=True)
                return
        except Exception as exc:  # noqa: BLE001
            ultimo = exc
        finally:
            if anterior is None:
                os.environ.pop("VOZ_EDGE", None)
            else:
                os.environ["VOZ_EDGE"] = anterior
        destino.unlink(missing_ok=True)
    raise RuntimeError(f"La voz falló en la escena {i} («{texto[:60]}…»): {ultimo}. Dale Reintentar en unos minutos; "
                       "si sigue, puede que el servicio gratis de Microsoft esté fallando y conviene usar ElevenLabs.")


def narrar(escenas: list[dict], carpeta: Path, motor: str | None = None) -> list[dict]:
    motor = motor or config.env("VOZ_MOTOR", "edge")
    fn = MOTORES[motor]
    audio = carpeta / "audio"
    audio.mkdir(parents=True, exist_ok=True)
    for i, esc in enumerate(escenas, 1):
        destino = audio / f"escena_{i:02d}.mp3"
        if not _valido(destino):
            destino.unlink(missing_ok=True)
            tiempos(destino).unlink(missing_ok=True)
            texto = limpiar(esc.get("narracion", ""))
            if not texto:
                print(f"    voz: la escena {i} no tiene texto para leer; va un silencio corto", flush=True)
                _silencio_fijo(destino)
            else:
                _narrar_una(fn, motor, texto, destino, i)
        esc["audio"] = str(destino)
        esc["duracion"] = duracion(destino)
        esc.pop("palabras", None)  # los tiempos viven junto al audio (escena_XX.palabras.json)
        print(f"  · escena {i}/{len(escenas)} ({esc['duracion']:.1f}s)")
    return escenas
