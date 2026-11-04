"""Configuración leída del archivo .env."""
from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

BASE = Path(__file__).resolve().parent.parent
if load_dotenv:
    load_dotenv(BASE / ".env")

SALIDA = BASE / "salida"
ENTRADA = BASE / "entrada"
ASSETS = BASE / "assets"
HISTORIAL = BASE / "historial.json"


def env(nombre: str, defecto: str = "") -> str:
    return os.environ.get(nombre, defecto).strip()


AI_MODEL = env("AI_MODEL", "claude-opus-5-5")
CANAL_NOMBRE = env("CANAL_NOMBRE", "Mi Canal")
CANAL_PAIS = env("CANAL_PAIS", "mx")
CANAL_IDIOMA = env("CANAL_IDIOMA", "es")
CANAL_ESTILO = env(
    "CANAL_ESTILO",
    "Directo, con humor, hablo de tú, como amigo que te salva de perder tu tiempo.",
)
