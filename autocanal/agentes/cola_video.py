"""Turno para editar video: las dos oficinas (YouTube y TikTok Shop) comparten el servidor y editar se come la RAM.

Mientras Edu edita, Cris espera (y al revés). Funciona entre programas distintos con un candado de archivo.
"""
from __future__ import annotations

import fcntl
import time
from contextlib import contextmanager

from . import config

CANDADO = config.BASE.parent / ".cola_video.lock"


@contextmanager
def turno(quien: str, al_esperar=None):
    """Espera a que nadie más esté editando. `al_esperar(texto)` avisa una vez si hay que esperar."""
    with open(CANDADO, "a+") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            f.seek(0)
            otro = f.read().strip() or "otro editor"
            if al_esperar:
                al_esperar(f"Espero mi turno: {otro} está editando un video.")
            fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        f.truncate()
        f.write(quien)
        f.flush()
        try:
            yield
        finally:
            f.seek(0)
            f.truncate()
            fcntl.flock(f, fcntl.LOCK_UN)
            time.sleep(0)
