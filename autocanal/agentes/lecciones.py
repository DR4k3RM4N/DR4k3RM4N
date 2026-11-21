"""📚 Lecciones: lo que el jefe le corrige a cada agente por el chat ("Gabi, deja de empezar con 'hola'",
"Dani, las miniaturas llevan faltas de ortografía", "Iván, no cites blogs de préstamos como fuente").

Se guardan por agente y por canal (o para todos los canales) en estilo/lecciones.json y se pegan en las
instrucciones de ese agente cada vez que trabaja. Así el error no se repite.
"""
from __future__ import annotations

import json
import threading
import time

from . import config

ARCHIVO = config.ESTILO_DIR / "lecciones.json"
_candado = threading.Lock()
AGENTES = {"productora": "Paola (ideas)", "investigador": "Iván (investigación)", "guionista": "Gabi (guion)",
           "locutor": "Leo (voz)", "disenadora": "Dani (miniaturas)", "editor": "Edu (edición y efectos)",
           "redactora": "Rosa (blog)", "community": "Carla (publicar)", "todos": "Todo el equipo"}


def todas() -> list[dict]:
    try:
        return json.loads(ARCHIVO.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def agregar(agente: str, texto: str, canal: str = "") -> dict:
    """canal vacío = para todos los canales."""
    agente = agente if agente in AGENTES else "todos"
    leccion = {"id": f"{int(time.time() * 1000):x}", "agente": agente, "texto": texto.strip()[:300],
               "canal": canal or "", "t": time.time()}
    with _candado:
        lista = [x for x in todas() if not (x["agente"] == agente and x["texto"].lower() == leccion["texto"].lower())]
        lista.append(leccion)
        ARCHIVO.parent.mkdir(parents=True, exist_ok=True)
        ARCHIVO.write_text(json.dumps(lista[-200:], ensure_ascii=False, indent=1), encoding="utf-8")
    return leccion


def quitar(lid: str) -> None:
    with _candado:
        ARCHIVO.write_text(json.dumps([x for x in todas() if x["id"] != lid], ensure_ascii=False, indent=1),
                           encoding="utf-8")


def para(agente: str, *otros: str) -> str:
    """Bloque para las instrucciones del agente (las suyas y las de todo el equipo, de este canal o de todos)."""
    from . import canales

    canal = canales.actual()
    mias = [x["texto"] for x in todas()
            if x["agente"] in (agente, *otros, "todos") and x.get("canal") in ("", None, canal)][-25:]
    if not mias:
        return ""
    return ("\n\nCORRECCIONES DEL JEFE (errores que ya cometiste; no los repitas nunca):\n"
            + "\n".join(f"- {t}" for t in mias))
