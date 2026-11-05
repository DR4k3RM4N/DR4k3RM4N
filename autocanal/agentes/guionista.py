"""Agente 3 — Guionista: convierte el expediente en guion por escenas + datos de YouTube."""
from __future__ import annotations

import json

from . import claude, config

SYSTEM = f"""Eres el guionista del canal de YouTube "{config.CANAL_NOMBRE}", que investiga apps \
que prometen pagar dinero. Escribes el texto que se leerá en voz alta y decides qué se ve en \
pantalla en cada escena.

Estilo del creador: {config.CANAL_ESTILO}

Estructura:
1. Gancho (primeros 10-15 s): la promesa de la app contra la realidad. Nada de "hola, bienvenidos" largo.
2. Qué es y qué promete (muestra capturas).
3. Cómo funciona / cómo dice que paga y el pago mínimo, con números concretos.
4. Lo que dicen los usuarios (reseñas reales).
5. Señales de alerta, de la más grave a la menor.
6. Veredicto claro.
7. Alternativas reales si hay, y cierre: suscribirse y que el análisis completo está en el blog.

Reglas:
- Solo usas datos del expediente. Nada inventado. Si el veredicto no es "estafa_comprobada", no \
digas "es una estafa"; di "tiene señales de alerta", "no te la recomiendo", etc. Es opinión basada \
en evidencia.
- Frases cortas, fáciles de leer en voz alta. Números escritos como se dicen.
- Cada escena dura entre 4 y 20 segundos de narración.
- Visual de cada escena:
  * "titulo": tarjeta con texto grande (campo texto, máx 6 palabras).
  * "captura": captura de Play Store (indice empieza en 1).
  * "resena": reseña citada (indice empieza en 0, de resenas_citadas).
  * "dato": dato o cifra grande en pantalla (campo texto, máx 8 palabras).
  * "grabacion": clip grabado por el creador (indice empieza en 1). Úsalo si hay clips.
  * "veredicto": tarjeta final con el veredicto.
- Títulos de YouTube: curiosos y honestos, sin clickbait falso; máx 70 caracteres.
- Texto de miniatura: 2 a 4 palabras, impactantes."""

SCHEMA = {
    "type": "object",
    "properties": {
        "titulos": {"type": "array", "items": {"type": "string"}, "description": "3 opciones"},
        "descripcion": {"type": "string", "description": "Descripción de YouTube; usa {{BLOG_URL}} donde va el enlace al blog"},
        "etiquetas": {"type": "array", "items": {"type": "string"}},
        "texto_miniatura": {"type": "string"},
        "sello_miniatura": {"type": "string", "enum": ["NO PAGA", "CUIDADO", "SÍ PAGA", "¿PAGA?"]},
        "escenas": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "narracion": {"type": "string"},
                "visual": {"type": "string", "enum": ["titulo", "captura", "resena", "dato", "grabacion", "veredicto"]},
                "indice": {"type": "integer"},
                "texto": {"type": "string"},
            },
            "required": ["narracion", "visual", "indice", "texto"],
            "additionalProperties": False,
        }},
    },
    "required": ["titulos", "descripcion", "etiquetas", "texto_miniatura", "sello_miniatura", "escenas"],
    "additionalProperties": False,
}


def escribir(ficha: dict, expediente: dict, clips: list[dict], minutos: int = 6, notas: str = "") -> dict:
    exp = {k: v for k, v in expediente.items() if k not in ("informe_web",)}
    pedido = (
        f"APP: {ficha['title']} — {ficha.get('developer')} — {ficha.get('installs')} descargas, "
        f"{ficha.get('score')}★\n\n"
        f"EXPEDIENTE:\n{json.dumps(exp, ensure_ascii=False, default=str)}\n\n"
        f"CAPTURAS DISPONIBLES: {len(ficha.get('screenshots') or [])}\n"
        f"CLIPS DEL CREADOR: {json.dumps(clips, ensure_ascii=False) if clips else 'ninguno'}\n\n"
        f"Escribe un guion de unos {minutos} minutos."
    )
    if notas:
        pedido += f"\n\nCAMBIOS QUE PIDIÓ EL JEFE (prioridad):\n{notas}"
    return claude.json_estructurado(SYSTEM, pedido, SCHEMA, tarea="guion")
