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
- Cada escena dura entre 4 y 20 segundos de narración. TODAS las escenas llevan narración (nunca vacía).
- La narración es solo texto para leer en voz alta: sin emojis, sin hashtags, sin símbolos.
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
        "textos_miniatura": {"type": "array", "items": {"type": "string"},
                             "description": "3 opciones distintas de texto para la miniatura, 2 a 5 palabras cada una"},
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
    "required": ["titulos", "descripcion", "etiquetas", "texto_miniatura", "textos_miniatura", "sello_miniatura", "escenas"],
    "additionalProperties": False,
}


SYSTEM_TEMA = f"""Eres el guionista del canal de YouTube "{config.CANAL_NOMBRE}". Esta vez el video NO es de \
apps que pagan: es de un tema libre (videojuego, película, tecnología, noticia…). Escribes lo que se leerá en voz \
alta y decides qué se ve en pantalla en cada escena, como un creador experto en ese tema.

Estilo del creador: {config.CANAL_ESTILO}

Estructura (adáptala al formato: top, guía, noticias, análisis, opinión, curiosidades, comparativa, tutorial, historia):
1. Gancho (primeros 10-15 s): la promesa del video o el dato más fuerte. Nada de "hola, bienvenidos" largo.
2. Desarrollo en bloques claros (en un top, del menos al más impactante; en una guía, paso a paso).
3. Lo que opina la comunidad, si hay comentarios reales.
4. Cierre con tu conclusión u opinión, una pregunta para comentarios y suscribirse.

Reglas:
- Usa los datos del expediente; si algo no está ahí, no lo afirmes como dato duro. Puedes opinar, dejando claro \
que es opinión.
- Frases cortas, fáciles de leer en voz alta. Números escritos como se dicen.
- Cada escena dura entre 4 y 20 segundos de narración. TODAS las escenas llevan narración (nunca vacía).
- La narración es solo texto para leer en voz alta: sin emojis, sin hashtags, sin símbolos.
- Visual de cada escena:
  * "titulo": tarjeta con texto grande (campo texto, máx 6 palabras). Úsala para títulos de sección ("Número 3").
  * "imagen": imagen del tema a pantalla completa (indice empieza en 1; texto opcional, máx 5 palabras).
  * "dato": dato o cifra grande en pantalla (campo texto, máx 8 palabras).
  * "resena": comentario real de la comunidad (indice empieza en 0, de resenas_citadas). Solo si hay.
  * "grabacion": clip grabado por el creador (indice empieza en 1). Úsalo bastante si hay clips.
  * "cierre": tarjeta final (campo texto, máx 6 palabras, ej. "¿Tú cuál eliges?").
- Varía los visuales; no repitas la misma imagen dos escenas seguidas.
- Títulos de YouTube: curiosos y honestos, sin clickbait falso; máx 70 caracteres.
- Texto de miniatura: 2 a 4 palabras, impactantes. Sello de miniatura: 1 o 2 palabras (ej. "TOP 5", "NUEVO", \
"GUÍA", "ROTO", "OJO", "REVIEW")."""

SCHEMA_TEMA = {
    "type": "object",
    "properties": {
        **{k: v for k, v in SCHEMA["properties"].items() if k not in ("sello_miniatura", "escenas")},
        "sello_miniatura": {"type": "string", "description": "1 o 2 palabras en mayúsculas"},
        "escenas": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "narracion": {"type": "string"},
                "visual": {"type": "string", "enum": ["titulo", "imagen", "dato", "resena", "grabacion", "cierre"]},
                "indice": {"type": "integer"},
                "texto": {"type": "string"},
            },
            "required": ["narracion", "visual", "indice", "texto"],
            "additionalProperties": False,
        }},
    },
    "required": SCHEMA["required"],
    "additionalProperties": False,
}


def _pedido_tema(ficha: dict, expediente: dict, clips: list[dict], minutos: int, notas: str) -> str:
    exp = {k: v for k, v in expediente.items() if k not in ("informe_web", "fuentes_web")}
    pedido = (
        f"TEMA: {ficha['title']}\nVIDEO: {expediente.get('angulo', '')}\nFORMATO: {expediente.get('formato', '') or 'el que mejor le quede'}\n\n"
        f"EXPEDIENTE:\n{json.dumps(exp, ensure_ascii=False, default=str)}\n\n"
        f"IMÁGENES DISPONIBLES: {len(ficha.get('screenshots') or [])}\n"
        f"CLIPS DEL CREADOR: {json.dumps(clips, ensure_ascii=False) if clips else 'ninguno'}\n\n"
        f"Escribe un guion de unos {minutos} minutos."
    )
    return pedido


def escribir(ficha: dict, expediente: dict, clips: list[dict], minutos: int = 6, notas: str = "") -> dict:
    exp = {k: v for k, v in expediente.items() if k not in ("informe_web",)}
    es_tema = expediente.get("tipo") == "tema"
    pedido = _pedido_tema(ficha, expediente, clips, minutos, notas) if es_tema else (
        f"APP: {ficha['title']} — {ficha.get('developer')} — {ficha.get('installs')} descargas, "
        f"{ficha.get('score')}★\n\n"
        f"EXPEDIENTE:\n{json.dumps(exp, ensure_ascii=False, default=str)}\n\n"
        f"CAPTURAS DISPONIBLES: {len(ficha.get('screenshots') or [])}\n"
        f"CLIPS DEL CREADOR: {json.dumps(clips, ensure_ascii=False) if clips else 'ninguno'}\n\n"
        f"Escribe un guion de unos {minutos} minutos."
    )
    if notas:
        pedido += (f"\n\nINDICACIONES DEL JEFE (prioridad: el video debe seguir este enfoque; "
                   f"los títulos y el gancho van con esta idea):\n{notas}")
    from . import estilo
    mini = estilo.cargar().get("miniaturas")
    if mini:
        pedido += (f"\n\nESTILO DE MINIATURAS DEL CANAL: {mini.get('descripcion', '')} "
                   f"Textos: {mini.get('consejos_texto', '')} Máximo {mini.get('palabras_max', 4)} palabras.")
    if es_tema:
        r = claude.json_estructurado(SYSTEM_TEMA, pedido, SCHEMA_TEMA, tarea="guion")
        r["sello_miniatura"] = (r.get("sello_miniatura") or "").upper()[:14]
        return r
    return claude.json_estructurado(SYSTEM, pedido, SCHEMA, tarea="guion")
