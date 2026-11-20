"""Llamadas a Claude compartidas por todos los agentes.

Dos motores (MOTOR_IA en .env):
  - "suscripcion": usa TU plan de Claude (Pro/Max) a través de Claude Code instalado en el servidor
    (`claude -p`, con el token de `claude setup-token` en CLAUDE_CODE_OAUTH_TOKEN). No gasta créditos de la
    API; cuenta para los límites de uso de tu plan (los mismos que usas en el chat).
  - "api": créditos de la API (ANTHROPIC_API_KEY), cobrados por token.
  - "auto" (por defecto): suscripción si está configurada; si se acaba el límite o falla, la API de respaldo.

Cada tarea usa su propio modelo: con la API, lo más barato (Haiku; se cambia con MODELO_<TAREA>); con la
suscripción, mejor calidad (Sonnet en lo creativo; se cambia con SUSCRIPCION_MODELO_<TAREA>).
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
import threading
import time

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


# Con la suscripción no se paga por token: lo creativo va en Sonnet (mejor guion, ideas y edición).
TAREAS_SUSCRIPCION = {
    "ideas": "sonnet", "investigar": "sonnet", "guion": "sonnet", "blog": "sonnet", "edicion": "sonnet",
    "estilo": "sonnet", "leer_web": "haiku", "whatsapp": "haiku", "miniatura": "haiku",
}
LIMITE_PALABRAS = ("usage limit", "rate limit", "limit reached", "out of extra usage", "5-hour", "weekly limit")
_suscripcion_pausada_hasta = 0.0  # si se acabó el límite del plan, se usa la API un rato


def motor() -> str:
    """"suscripcion", "api" o "auto"."""
    m = config.env("MOTOR_IA", "auto").lower()
    return m if m in ("suscripcion", "api", "auto") else "auto"


def claude_cli() -> str | None:
    return config.env("CLAUDE_CLI") or shutil.which("claude") or next(
        (p for p in ("/usr/local/bin/claude", os.path.expanduser("~/.local/bin/claude")) if os.path.exists(p)), None)


def suscripcion_lista() -> bool:
    return bool(config.env("CLAUDE_CODE_OAUTH_TOKEN") and claude_cli())


def usar_suscripcion() -> bool:
    m = motor()
    if m == "api" or not suscripcion_lista():
        return False
    if m == "auto" and time.time() < _suscripcion_pausada_hasta and config.env("ANTHROPIC_API_KEY"):
        return False
    return True


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


def _env_suscripcion() -> dict:
    """Entorno para Claude Code: sin la clave de la API (si no, cobraría créditos en vez de usar tu plan) y con
    su propia carpeta de trabajo (no lee el CLAUDE.md del repo ni guarda nada dentro del código)."""
    casa = config.BASE / ".claude_casa"
    casa.mkdir(exist_ok=True)
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    env.update({"HOME": str(casa), "CLAUDE_CODE_OAUTH_TOKEN": config.env("CLAUDE_CODE_OAUTH_TOKEN"),
                "DISABLE_AUTOUPDATER": "1", "DISABLE_TELEMETRY": "1"})
    return env


def _bloques(contenido) -> list[dict]:
    if isinstance(contenido, str):
        return [{"type": "text", "text": contenido}]
    return list(contenido)


def _por_suscripcion(system: str, contenido, schema: dict, tarea: str, que: str, effort: str,
                     espera: int = 600) -> dict:
    """Una llamada con tu plan de Claude (Claude Code en modo automático, sin herramientas)."""
    global _suscripcion_pausada_hasta
    modelo = config.env(f"SUSCRIPCION_MODELO_{tarea.upper()}", TAREAS_SUSCRIPCION.get(tarea, "sonnet"))
    entrada = json.dumps({"type": "user", "message": {"role": "user", "content": _bloques(contenido)}}, ensure_ascii=False)
    with tempfile.TemporaryDirectory() as vacio:  # carpeta vacía: nada de archivos del proyecto
        try:
            p = subprocess.run(
                [claude_cli(), "-p", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
                 "--model", modelo, "--effort", effort, "--json-schema", json.dumps(schema), "--system-prompt", system,
                 "--tools", "", "--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence",
                 "--setting-sources", ""],
                input=entrada + "\n", capture_output=True, text=True, cwd=vacio, env=_env_suscripcion(), timeout=espera)
        except subprocess.TimeoutExpired as exc:
            # con un token inválido Claude Code se queda reintentando: se descansa la suscripción un rato
            _suscripcion_pausada_hasta = time.time() + 900
            raise ErrorIA("Claude (suscripción) no contestó a tiempo. Si pasa seguido, revisa el token con "
                          "oficina.py --configurar-suscripcion") from exc
    resultado = None
    for linea in p.stdout.splitlines():
        try:
            d = json.loads(linea)
        except json.JSONDecodeError:
            continue
        if d.get("type") == "result":
            resultado = d
    if resultado is None or resultado.get("is_error") or resultado.get("structured_output") is None:
        detalle = ((resultado or {}).get("result") or p.stderr or p.stdout or "sin respuesta")[-300:]
        if any(x in detalle.lower() for x in LIMITE_PALABRAS):
            _suscripcion_pausada_hasta = time.time() + 3600
            raise ErrorIA(f"Se acabó el límite de tu plan de Claude por ahora: {detalle}")
        if "auth" in detalle.lower() or "login" in detalle.lower() or "401" in detalle:
            raise ErrorIA("El token de tu suscripción no sirve o caducó. Corre en el servidor: "
                          "oficina.py --configurar-suscripcion")
        raise ErrorIA(f"Claude (suscripción) no respondió bien: {detalle}")
    equivalente = float(resultado.get("total_cost_usd") or 0)
    print(f"    [suscripción · {modelo}] {que}: en la API habría costado ≈ ${equivalente:.4f}", flush=True)
    if al_gastar:
        try:
            al_gastar(getattr(contexto, "proyecto", None), getattr(contexto, "etapa", None), f"suscripción ({modelo})",
                      0.0, 0, 0, f"{que} · con tu plan (en API ≈ ${equivalente:.3f})")
        except Exception:  # noqa: BLE001
            log.exception("al registrar gasto")
    return resultado["structured_output"]


def json_estructurado(system: str, contenido, schema: dict, tarea: str = "guion", effort: str | None = None,
                      que: str | None = None) -> dict:
    """Pide a Claude un JSON que cumple `schema`. `contenido` puede ser texto o bloques (imágenes).
    Usa tu suscripción si está configurada; si no (o si se acabó el límite), la API."""
    modelo, esfuerzo = modelo_de(tarea)
    if usar_suscripcion():
        try:
            return _por_suscripcion(system, contenido, schema, tarea, que or tarea, effort or esfuerzo)
        except ErrorIA as exc:
            if motor() == "suscripcion" or not config.env("ANTHROPIC_API_KEY"):
                raise
            print(f"    · {exc} → sigo con la API ({modelo})", flush=True)
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
