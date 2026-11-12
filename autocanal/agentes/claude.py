"""Llamadas a Claude compartidas por todos los agentes.

Cada tarea usa su propio modelo (lo más barato que da buen resultado) y se mide lo que cuesta.
Se cambia por tarea en .env: MODELO_IDEAS, MODELO_INVESTIGAR, MODELO_GUION, MODELO_BLOG.
"""
from __future__ import annotations

import json
import logging
import threading

import anthropic

from . import config

log = logging.getLogger(__name__)

FALLBACK_BETA = "server-side-fallback-2026-07-01"

# Modelo y esfuerzo de pensamiento por tarea. El esfuerzo bajo gasta menos tokens.
TAREAS = {
    "ideas": ("claude-haiku-5-5", "low"),          # elegir apps de una lista: sencillo
    "investigar": ("claude-haiku-5-5", "low"),      # armar el expediente con la evidencia ya juntada
    "guion": ("claude-haiku-5-5", "medium"),        # lo que se escucha en el video (súbelo a Sonnet si sale flojo)
    "blog": ("claude-haiku-5-5", "low"),            # ordenar la investigación en un post
    "whatsapp": ("claude-haiku-5-5", "low"),        # entender lo que escribes por WhatsApp
    "leer_web": ("claude-haiku-5-5", "low"),        # leer resultados de Google y sacar hechos con fuente
    "estilo": ("claude-sonnet-5-5", "low"),         # estudiar tus miniaturas y entradas (una sola vez)
    "miniatura": ("claude-haiku-5-5", "low"),       # elegir la opción de miniatura más parecida a tu estilo
    "edicion": ("claude-haiku-5-5", "medium"),      # plan de motion graphics escena por escena (fracciones de centavo)
    # oficina de TikTok Shop
    "ficha_shop": ("claude-haiku-5-5", "low"),      # Toño: ordenar lo que salió en Google del producto
    "guion_shop": ("claude-haiku-5-5", "medium"),   # Sofi: guion que vende con 3 ganchos
    "tomas_shop": ("claude-haiku-5-5", "low"),      # Diego: lista de tomas para grabar con el celular
    # sala de edición
    "sala": ("claude-sonnet-5-5", "medium"),        # editores de la sala: ven tus clips y arman la edición. Sonnet edita
                                                     # mucho mejor que Haiku (~3-5 ¢ por mensaje); MODELO_SALA=claude-haiku-5-5 para ahorrar
    "sala_aprender": ("claude-haiku-5-5", "low"),   # ordenar el cuaderno de estilo cuando crece (fracción de centavo)
}

# Precios en USD por millón de tokens: (entrada, salida). Haiku cambia de tarifa arriba de 100K de entrada.
PRECIOS = {
    "claude-opus-5-5": (4.0, 20.0), "claude-opus-5": (5.0, 25.0), "claude-sonnet-5-5": (2.0, 10.0),
    "claude-sonnet-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50), "claude-fable-5-1": (10.0, 50.0),
}
PRECIO_BUSQUEDA = 10.0 / 1000  # USD por búsqueda web

# Quién está gastando (la oficina lo pone en cada hilo de trabajo) y a quién avisar del gasto.
contexto = threading.local()
al_gastar = None  # función(proyecto, etapa, modelo, costo_usd, tokens_entrada, tokens_salida, que)
antes_de_llamar = None  # función sin argumentos; la oficina la usa para el tope de gasto diario


class ErrorIA(Exception):
    pass


def modelo_de(tarea: str) -> tuple[str, str]:
    modelo, esfuerzo = TAREAS.get(tarea, (config.AI_MODEL, "medium"))
    return config.env(f"MODELO_{tarea.upper()}", modelo) or modelo, esfuerzo


def costo(modelo: str, usage) -> float:
    base_in, base_out = PRECIOS.get(modelo, PRECIOS.get(config.AI_MODEL, (4.0, 20.0)))
    entrada = getattr(usage, "input_tokens", 0) or 0
    escribe = getattr(usage, "cache_creation_input_tokens", 0) or 0
    lee = getattr(usage, "cache_read_input_tokens", 0) or 0
    salida = getattr(usage, "output_tokens", 0) or 0
    if modelo.startswith("claude-haiku-5-5") and entrada + escribe + lee > 100_000:
        base_in, base_out = 0.50, 2.50
    stu = getattr(usage, "server_tool_use", None)
    busquedas = getattr(stu, "web_search_requests", 0) or 0
    return ((entrada + escribe * 1.25 + lee * 0.1) * base_in + salida * base_out) / 1e6 + busquedas * PRECIO_BUSQUEDA


def _registrar(response, modelo_pedido: str, que: str = "") -> None:
    modelo = getattr(response, "model", None) or modelo_pedido
    usd = costo(modelo, response.usage)
    entrada = response.usage.input_tokens or 0
    salida = response.usage.output_tokens or 0
    busquedas = getattr(getattr(response.usage, "server_tool_use", None), "web_search_requests", 0) or 0
    print(f"    [{modelo}] {que}: {entrada:,} tokens de entrada, {salida:,} de salida"
          + (f", {busquedas} búsquedas" if busquedas else "") + f" ≈ ${usd:.4f}", flush=True)
    if al_gastar:
        try:
            al_gastar(getattr(contexto, "proyecto", None), getattr(contexto, "etapa", None), modelo, usd, entrada, salida,
                      que + (f" ({busquedas} búsquedas)" if busquedas else ""))
        except Exception:  # noqa: BLE001 — medir nunca debe romper el trabajo
            log.exception("al registrar gasto")


def _cliente() -> anthropic.Anthropic:
    return anthropic.Anthropic(max_retries=3, timeout=900)


def _extras(modelo: str) -> dict:
    """Respaldo automático si el modelo rechaza la petición (Haiku no lo admite)."""
    if "haiku" in modelo:
        return {}
    return {"betas": [FALLBACK_BETA], "fallbacks": "default"}


def _revisar(response) -> None:
    if response.stop_reason == "refusal":
        raise ErrorIA("Claude no pudo procesar esta solicitud.")
    if response.stop_reason == "max_tokens":
        raise ErrorIA("La respuesta quedó incompleta (max_tokens).")


def _texto(response) -> str:
    return "\n".join(b.text for b in response.content if b.type == "text").strip()


def json_estructurado(system: str, contenido, schema: dict, tarea: str = "guion", effort: str | None = None,
                      que: str | None = None) -> dict:
    """Pide a Claude un JSON que cumple `schema`. `contenido` puede ser texto o bloques (imágenes)."""
    modelo, esfuerzo = modelo_de(tarea)
    if antes_de_llamar:
        antes_de_llamar()
    try:
        with _cliente().beta.messages.stream(
            model=modelo,
            max_tokens=32000,
            system=system,
            output_config={"effort": effort or esfuerzo, "format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": contenido}],
            **_extras(modelo),
        ) as stream:
            response = stream.get_final_message()
    except anthropic.APIStatusError as exc:
        raise ErrorIA(f"Error de la API de Claude {exc.status_code}: {exc.message}") from exc
    except anthropic.APIConnectionError as exc:
        raise ErrorIA("No hubo conexión con la API de Claude.") from exc
    _registrar(response, modelo, que or tarea)
    _revisar(response)
    try:
        return json.loads(_texto(response))
    except json.JSONDecodeError as exc:
        raise ErrorIA("Claude devolvió un JSON inválido.") from exc


def investigar_web(system: str, pregunta: str, tarea: str = "investigar", max_busquedas: int = 3) -> tuple[str, list[dict]]:
    """Investiga con búsqueda web. Devuelve (informe en texto, fuentes citadas)."""
    modelo, esfuerzo = modelo_de(tarea)
    # La búsqueda con filtrado dinámico es de Sonnet/Opus; otros modelos usan la versión básica.
    tipo = "web_search_20250305" if "haiku" in modelo else "web_search_20260209"
    herramienta = {"type": tipo, "name": "web_search", "max_uses": max_busquedas}
    if antes_de_llamar:
        antes_de_llamar()
    messages = [{"role": "user", "content": pregunta}]
    cliente = _cliente()
    try:
        for _ in range(4):  # pause_turn: el servidor pide continuar búsquedas largas
            with cliente.beta.messages.stream(
                model=modelo,
                max_tokens=16000,
                system=system,
                output_config={"effort": esfuerzo},
                tools=[herramienta],
                messages=messages,
                **_extras(modelo),
            ) as stream:
                response = stream.get_final_message()
            _registrar(response, modelo, "búsqueda web")
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
    return _texto(response), fuentes[:12]
