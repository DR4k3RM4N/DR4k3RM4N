"""Integración con Claude para resúmenes y análisis de transcripciones.

Todo es opcional: sin ANTHROPIC_API_KEY la app usa el motor de reglas
(engine.recommendations) y el detector de palabras clave.
"""
from __future__ import annotations

import json
import logging

import anthropic
from django.conf import settings

from lives.models import EVENT_CHOICES

from .models import AIRun

log = logging.getLogger(__name__)

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AIUnavailable(Exception):
    pass


def ai_enabled() -> bool:
    return bool(settings.ANTHROPIC_API_KEY)


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, max_retries=3, timeout=600)


def _call_json(org, kind: str, system: str, user_content: str, schema: dict, effort: str = "medium") -> dict:
    """Llama a Claude pidiendo JSON que cumple `schema` y registra el uso."""
    if not ai_enabled():
        raise AIUnavailable("Configura ANTHROPIC_API_KEY para usar la IA.")
    if org.ai_runs_left() <= 0:
        raise AIUnavailable("Ya usaste todos los análisis con IA de tu plan este mes.")

    run = AIRun(organization=org, kind=kind, model=settings.AI_MODEL)
    try:
        with _client().beta.messages.stream(
            model=settings.AI_MODEL,
            max_tokens=32000,
            betas=[FALLBACK_BETA],
            fallbacks="default",
            system=system,
            output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": user_content}],
        ) as stream:
            response = stream.get_final_message()
        run.input_tokens = response.usage.input_tokens or 0
        run.output_tokens = response.usage.output_tokens or 0
        if response.stop_reason == "refusal":
            raise AIUnavailable("La IA no pudo procesar esta solicitud.")
        if response.stop_reason == "max_tokens":
            raise AIUnavailable("La respuesta de la IA quedó incompleta; intenta con un periodo más corto.")
        text = next((b.text for b in response.content if b.type == "text"), "")
        data = json.loads(text)
        run.save()
        return data
    except AIUnavailable as exc:
        run.ok, run.counted, run.error = False, False, str(exc)
        run.save()
        raise
    except anthropic.APIStatusError as exc:
        log.exception("Error de la API de Claude (%s)", getattr(exc, "status_code", "?"))
        run.ok, run.counted, run.error = False, False, f"{exc.status_code}: {exc.message}"[:2000]
        run.save()
        raise AIUnavailable("El servicio de IA no respondió bien. Intenta de nuevo en unos minutos.") from exc
    except anthropic.APIConnectionError as exc:
        run.ok, run.counted, run.error = False, False, "connection error"
        run.save()
        raise AIUnavailable("No hubo conexión con el servicio de IA.") from exc
    except (json.JSONDecodeError, StopIteration) as exc:
        run.ok, run.counted, run.error = False, False, f"bad json: {exc}"
        run.save()
        raise AIUnavailable("La IA devolvió una respuesta inválida. Intenta de nuevo.") from exc


ANALYST_SYSTEM = """Eres analista senior de live shopping en TikTok Shop México. Trabajas para \
agencias, marcas y creadores que hacen transmisiones en vivo para vender.

Tu trabajo: convertir métricas en decisiones concretas para el próximo live.

Reglas:
- Usa solo los datos que te dan. No inventes cifras ni causas que los datos no respalden.
- Cada grupo trae n (número de lives) y confianza. Si la confianza es baja o n es chico, dilo y \
plantéalo como algo para probar, no como conclusión.
- Distingue correlación de causa. "adjusted_lift" es el efecto controlando los demás factores; si \
difiere mucho del "lift" simple, explica que probablemente otro factor (horario, promoción) es la \
causa real.
- Cuando hables del género u otras características del host, preséntalo como dato de audiencia, \
nunca como juicio sobre personas, y sugiere considerar también estilo y experiencia.
- Escribe en español de México, claro y directo, como le hablarías al equipo de la agencia. \
Montos en pesos.
- Las acciones deben ser específicas y operables: qué hacer, cuándo y cómo medir si funcionó."""

REPORT_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string", "description": "Una frase con lo más importante del periodo"},
        "summary": {"type": "string", "description": "2-4 frases de contexto"},
        "what_worked": {"type": "array", "items": {"type": "string"}},
        "what_to_fix": {"type": "array", "items": {"type": "string"}},
        "next_actions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "why": {"type": "string"},
                    "how_to_measure": {"type": "string"},
                },
                "required": ["action", "why", "how_to_measure"],
                "additionalProperties": False,
            },
        },
        "experiment_idea": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "variant_a": {"type": "string"},
                "variant_b": {"type": "string"},
                "hypothesis": {"type": "string"},
            },
            "required": ["name", "variant_a", "variant_b", "hypothesis"],
            "additionalProperties": False,
        },
        "data_caveats": {"type": "string"},
    },
    "required": ["headline", "summary", "what_worked", "what_to_fix", "next_actions", "experiment_idea",
                 "data_caveats"],
    "additionalProperties": False,
}


def summarize_report(report) -> dict:
    scope = report.brand.name if report.brand else f"todas las marcas de {report.organization.name}"
    content = (
        f"Reporte {report.get_period_display().lower()} de {scope}, del {report.start} al {report.end}.\n"
        "Datos (JSON). 'kpis' compara contra el periodo anterior; 'history_factors' usa hasta 90 días para "
        "detectar patrones; 'events' son momentos dentro del live y el cambio en pedidos en los 5 minutos "
        "siguientes; 'recommendations' son las del motor de reglas, puedes mejorarlas o descartarlas.\n\n"
        f"{json.dumps(report.data, ensure_ascii=False, default=str)}\n\n"
        "Escribe el resumen ejecutivo del periodo con 3 a 5 acciones para el siguiente periodo y una idea de "
        "prueba A/B."
    )
    return _call_json(report.organization, "report", ANALYST_SYSTEM, content, REPORT_SCHEMA)


EVENT_KINDS = [k for k, _ in EVENT_CHOICES]

TRANSCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string", "description": "Cómo fue el live, en 3-5 frases"},
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "minute": {"type": "integer"},
                    "kind": {"type": "string", "enum": EVENT_KINDS},
                    "description": {"type": "string"},
                    "quote": {"type": "string", "description": "Frase textual del host (corta)"},
                },
                "required": ["minute", "kind", "description", "quote"],
                "additionalProperties": False,
            },
        },
        "host_strengths": {"type": "array", "items": {"type": "string"}},
        "host_improvements": {"type": "array", "items": {"type": "string"}},
        "replicable_lines": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Frases o recursos del host que conviene repetir en otros lives",
        },
    },
    "required": ["summary", "events", "host_strengths", "host_improvements", "replicable_lines"],
    "additionalProperties": False,
}

EVENT_GUIDE = "\n".join(f"- {k}: {label}" for k, label in EVENT_CHOICES)


def analyze_transcript(live, segments: list[dict], minutes: list[dict]) -> dict:
    lines = [f"[min {int(s['start'] // 60)}] {s['text']}" for s in segments]
    sales = ""
    if minutes:
        sales = "\n\nPedidos y espectadores por minuto (minuto: pedidos / espectadores):\n" + "\n".join(
            f"{m['minute']}: {m['orders']} / {m['viewers']}" for m in minutes)
    content = (
        f"Live de la marca {live.brand.name}, host {live.host.name if live.host else 'sin registrar'}, "
        f"duración {live.duration_minutes} min, ventas ${float(live.gmv):,.0f}, {live.orders} pedidos.\n\n"
        "Transcripción con minuto aproximado:\n" + "\n".join(lines) + sales + "\n\n"
        "Identifica los momentos clave (eventos) usando estos tipos:\n" + EVENT_GUIDE + "\n\n"
        "Marca un evento cuando el host realmente hace la acción, no cuando solo la menciona de pasada. "
        "Si hay datos de pedidos, señala en la descripción si los pedidos subieron después. Da retroalimentación "
        "concreta para el host."
    )
    return _call_json(live.organization, "transcript", ANALYST_SYSTEM, content, TRANSCRIPT_SCHEMA)
