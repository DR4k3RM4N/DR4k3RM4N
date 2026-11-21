"""Entiende lo que el jefe escribe por chat (WhatsApp) y lo convierte en acciones de la oficina.

Primero prueba con comandos simples (gratis); si no, le pregunta a Claude Haiku (muy barato).
"""
from __future__ import annotations

import json
import re

from . import claude

AYUDA = (
    "Puedes escribirme normal, como en un chat. Por ejemplo:\n"
    "• *ideas* o *busca apps de encuestas* → busco ideas nuevas (en Google y Play Store)\n"
    "• *busca la app Cash Gato* → busco esa app en Play Store\n"
    "• *video: por qué no recomiendo Plata Card* → preparo tu idea con ese enfoque\n"
    "• *pendientes* → te paso las ideas y videos que esperan tu respuesta\n"
    "• *sí 1* / *dale a la 2* → arranco ese video\n"
    "• *no 3 ya la hicimos* → la descarto (y aprendo por qué)\n"
    "• *opino 1 enfócalo en el pago mínimo* → se lo paso al equipo\n"
    "• *¿cómo van?* → te digo qué está haciendo cada quien\n"
    "• *Gabi, deja de empezar los guiones con 'hola'* → el equipo aprende la corrección y no lo repite\n"
    "• *al video 2 quítale la parte del final* → se rehace ese video con tu cambio\n"
    "Para publicar un video entra a la oficina: ahí lo ves y das el visto bueno final."
)

SYSTEM = """Eres Paola, la productora de un canal de YouTube que investiga apps que prometen pagar dinero.
Tu jefe te escribe por chat (WhatsApp o Telegram). Conviertes su mensaje en acciones para el equipo y le contestas.

Reglas:
- Las ideas pendientes están numeradas. Usa ese número en "numero". Si no queda claro a cuál se refiere,
  no hagas la acción y pregúntale.
- "aprobar" = hacer el video de esa idea. "rechazar" = descartarla (pon el motivo en "texto" si lo dio).
  "comentar" = darle una opinión o indicación sobre una idea sin decidir todavía.
- "pedir_ideas" = buscar apps nuevas; pon el tema en "texto" si lo dio. Si pidió una app concreta,
  pon "la app <nombre>" en "texto". Si propone una IDEA DE VIDEO concreta (ej. "haz un video de por qué no
  recomiendo Plata Card"), pon su idea completa, tal cual, en "texto".
- "estado" = quiere saber cómo va el trabajo. "pendientes" = quiere ver lo que espera su respuesta.
- "corregir" = el jefe señala un ERROR o algo que no le gusta de cómo trabaja el equipo, para que NO se repita
  ("las miniaturas tienen faltas", "Gabi siempre empieza igual", "no cites blogs de préstamos", "la voz dice mal
  Condusef"). Pon en "agente" a quién va (productora=Paola ideas, investigador=Iván, guionista=Gabi guion,
  locutor=Leo voz, disenadora=Dani miniaturas, editor=Edu edición/efectos/subtítulos, redactora=Rosa blog,
  community=Carla publicar, todos=si es para todo el equipo) y en "texto" la lección como instrucción clara y
  general, en segunda persona ("Nunca empieces el guion con un saludo; arranca con el gancho"). En "canal" el id
  del canal si la corrección es solo para ese canal; vacío si aplica a todos.
- "cambios" = quiere cambiar UN video que está en revisión o con problema (usa su número de la lista de videos en
  "numero" y el cambio en "texto"). Si además es algo que no debe repetirse, agrega también un "corregir".
- Publicar un video NO se hace por chat: dile que entre a la oficina para revisarlo.
- Si solo saluda o platica, contesta breve y amable, sin acciones.
- "respuesta": 1 o 2 frases en español de México, cálida y directa, como compañera de trabajo."""

SCHEMA = {
    "type": "object",
    "properties": {
        "respuesta": {"type": "string"},
        "acciones": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "tipo": {"type": "string", "enum": ["aprobar", "rechazar", "comentar", "pedir_ideas", "estado",
                                                     "pendientes", "corregir", "cambios"]},
                "numero": {"type": "integer", "description": "Número de la idea o del video; 0 si no aplica"},
                "texto": {"type": "string"},
                "agente": {"type": "string", "enum": ["", "productora", "investigador", "guionista", "locutor",
                                                      "disenadora", "editor", "redactora", "community", "todos"]},
                "canal": {"type": "string", "description": "id del canal si aplica solo a uno; vacío si no"},
            },
            "required": ["tipo", "numero", "texto", "agente", "canal"],
            "additionalProperties": False,
        }},
    },
    "required": ["respuesta", "acciones"],
    "additionalProperties": False,
}

SI = r"(?:s[ií]|dale|hazlo|ok|va|apruebo|aprobada?)"


def rapido(texto: str) -> dict | None:
    """Comandos comunes sin gastar en IA."""
    t = texto.strip().lower()
    if re.fullmatch(r"(ayuda|help|\?|comandos|men[uú])", t):
        return {"respuesta": AYUDA, "acciones": []}
    if re.fullmatch(r"(estado|status|c[oó]mo van\??|¿c[oó]mo van\??|qu[eé] hacen\??)", t):
        return {"respuesta": "", "acciones": [{"tipo": "estado", "numero": 0, "texto": "", "agente": "", "canal": ""}]}
    if re.fullmatch(r"(pendientes|bandeja|ideas pendientes|qu[eé] hay\??)", t):
        return {"respuesta": "", "acciones": [{"tipo": "pendientes", "numero": 0, "texto": ""}]}
    if m := re.fullmatch(rf"{SI}\s*(?:a la\s*)?#?(\d+)", t):
        return {"respuesta": "", "acciones": [{"tipo": "aprobar", "numero": int(m.group(1)), "texto": ""}]}
    if m := re.fullmatch(r"no\s*#?(\d+)[\s,:.-]*(.*)", t):
        return {"respuesta": "", "acciones": [{"tipo": "rechazar", "numero": int(m.group(1)), "texto": texto.strip()[m.start(2):].strip()}]}
    if m := re.fullmatch(r"opino\s*#?(\d+)[\s,:.-]+(.+)", t, flags=re.S):
        return {"respuesta": "", "acciones": [{"tipo": "comentar", "numero": int(m.group(1)), "texto": texto.strip()[m.start(2):].strip()}]}
    if m := re.fullmatch(r"(?:ideas|busca(?:r)?(?: ideas)?|nuevas ideas)\s*(?:de\s+)?(.*)", t):
        return {"respuesta": "", "acciones": [{"tipo": "pedir_ideas", "numero": 0, "texto": texto.strip()[m.start(1):].strip()}]}
    return None


def interpretar(texto: str, ideas: list[dict], proyectos: list[dict], canales: list[dict] | None = None) -> dict:
    r = rapido(texto)
    if r is not None:
        return r
    contexto = {
        "ideas_pendientes": [{"numero": p.get("num", i), "titulo": p["titulo"], "video": p.get("angulo", "")} for i, p in enumerate(ideas, 1)],
        "videos": [{"numero": i, "titulo": p["titulo"], "estado": p["estado"], "canal": p.get("canal", "principal")}
                   for i, p in enumerate(proyectos[:10], 1)],
        "canales": [{"id": c["id"], "nombre": c.get("nombre")} for c in canales or []],
    }
    return claude.json_estructurado(
        SYSTEM, f"CONTEXTO:\n{json.dumps(contexto, ensure_ascii=False)}\n\nMENSAJE DEL JEFE:\n{texto[:1500]}",
        SCHEMA, tarea="whatsapp")
