"""Llamadas a Claude compartidas por todos los agentes."""
from __future__ import annotations

import json
import logging

import anthropic

from . import config

log = logging.getLogger(__name__)

FALLBACK_BETA = "server-side-fallback-2026-07-01"
WEB_SEARCH = {"type": "web_search_20260209", "name": "web_search", "max_uses": 8}


class ErrorIA(Exception):
    pass


def _cliente() -> anthropic.Anthropic:
    return anthropic.Anthropic(max_retries=3, timeout=900)


def _revisar(response) -> None:
    if response.stop_reason == "refusal":
        raise ErrorIA("Claude no pudo procesar esta solicitud.")
    if response.stop_reason == "max_tokens":
        raise ErrorIA("La respuesta quedó incompleta (max_tokens).")


def _texto(response) -> str:
    return "\n".join(b.text for b in response.content if b.type == "text").strip()


def json_estructurado(system: str, contenido, schema: dict, effort: str = "medium") -> dict:
    """Pide a Claude un JSON que cumple `schema`. `contenido` puede ser texto o bloques (imágenes)."""
    try:
        with _cliente().beta.messages.stream(
            model=config.AI_MODEL,
            max_tokens=64000,
            betas=[FALLBACK_BETA],
            fallbacks="default",
            system=system,
            output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": contenido}],
        ) as stream:
            response = stream.get_final_message()
    except anthropic.APIStatusError as exc:
        raise ErrorIA(f"Error de la API de Claude {exc.status_code}: {exc.message}") from exc
    except anthropic.APIConnectionError as exc:
        raise ErrorIA("No hubo conexión con la API de Claude.") from exc
    _revisar(response)
    try:
        return json.loads(_texto(response))
    except json.JSONDecodeError as exc:
        raise ErrorIA("Claude devolvió un JSON inválido.") from exc


def investigar_web(system: str, pregunta: str, effort: str = "high") -> tuple[str, list[dict]]:
    """Investiga con búsqueda web. Devuelve (informe en texto, fuentes citadas)."""
    messages = [{"role": "user", "content": pregunta}]
    cliente = _cliente()
    try:
        for _ in range(6):  # pause_turn: el servidor pide continuar búsquedas largas
            with cliente.beta.messages.stream(
                model=config.AI_MODEL,
                max_tokens=64000,
                betas=[FALLBACK_BETA],
                fallbacks="default",
                system=system,
                output_config={"effort": effort},
                tools=[WEB_SEARCH],
                messages=messages,
            ) as stream:
                response = stream.get_final_message()
            if response.stop_reason != "pause_turn":
                break
            messages.append({"role": "assistant", "content": response.content})
    except anthropic.APIStatusError as exc:
        raise ErrorIA(f"Error de la API de Claude {exc.status_code}: {exc.message}") from exc
    except anthropic.APIConnectionError as exc:
        raise ErrorIA("No hubo conexión con la API de Claude.") from exc
    _revisar(response)

    fuentes, vistas = [], set()
    for bloque in response.content:
        if bloque.type == "text":
            for cita in getattr(bloque, "citations", None) or []:
                url = getattr(cita, "url", None)
                if url and url not in vistas:
                    vistas.add(url)
                    fuentes.append({"titulo": getattr(cita, "title", "") or url, "url": url})
        elif bloque.type == "web_search_tool_result" and isinstance(bloque.content, list):
            for r in bloque.content:
                url = getattr(r, "url", None)
                if url and url not in vistas:
                    vistas.add(url)
                    fuentes.append({"titulo": getattr(r, "title", "") or url, "url": url})
    return _texto(response), fuentes
