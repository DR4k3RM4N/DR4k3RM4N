"""Agente 4 — Voz: narra cada escena (Edge TTS gratis o ElevenLabs con tu voz clonada)."""
from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

import requests

from . import config


def duracion(ruta: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(ruta)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out)


def _edge(texto: str, destino: Path) -> None:
    import edge_tts

    async def run():
        await edge_tts.Communicate(texto, config.env("VOZ_EDGE", "es-MX-JorgeNeural"),
                                   rate=config.env("VOZ_VELOCIDAD", "+8%")).save(str(destino))
    asyncio.run(run())


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


def narrar(escenas: list[dict], carpeta: Path, motor: str | None = None) -> list[dict]:
    motor = motor or config.env("VOZ_MOTOR", "edge")
    fn = MOTORES[motor]
    audio = carpeta / "audio"
    audio.mkdir(parents=True, exist_ok=True)
    for i, esc in enumerate(escenas, 1):
        destino = audio / f"escena_{i:02d}.mp3"
        if not destino.exists():
            fn(esc["narracion"], destino)
        esc["audio"] = str(destino)
        esc["duracion"] = duracion(destino)
        print(f"  · escena {i}/{len(escenas)} ({esc['duracion']:.1f}s)")
    return escenas
