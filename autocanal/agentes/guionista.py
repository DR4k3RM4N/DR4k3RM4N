"""Agente 3 — Guionista: convierte el expediente en guion por escenas + datos de YouTube."""
from __future__ import annotations

import json

from . import claude, config, manual
from . import lecciones

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
- Si el expediente trae "prueba_propia" (alguien usó la app y la grabó), ESE es el corazón del video:
  cuéntalo en primera persona ("la instalé y la usé", "en 10 minutos me salieron 14 anuncios"), usa bastantes
  escenas "grabacion" y en cada una pon en "desde" el segundo del momento que estás narrando (te paso los momentos
  de cada grabación con lo que se ve). Narra lo que se ve en ese momento.
- Títulos de YouTube: curiosos y honestos, sin clickbait falso; máx 70 caracteres.
- Texto de miniatura: 2 a 4 palabras, impactantes."""

SCHEMA = {
    "type": "object",
    "properties": {
        "titulos": {"type": "array", "items": {"type": "string"}, "description": "5 opciones, la que más clics daría PRIMERO"},
        "descripcion": {"type": "string", "description": "Descripción de YouTube; usa {{BLOG_URL}} donde va el enlace al blog"},
        "etiquetas": {"type": "array", "items": {"type": "string"}},
        "texto_miniatura": {"type": "string"},
        "textos_miniatura": {"type": "array", "items": {"type": "string"},
                             "description": "6 opciones distintas de texto para la miniatura, 2 a 5 palabras cada una, la mejor primero"},
        "sello_miniatura": {"type": "string", "enum": ["NO PAGA", "CUIDADO", "SÍ PAGA", "¿PAGA?"]},
        "tipo_gancho": {"type": "string", "enum": ["historia", "dato_impactante", "pregunta_al_espectador",
                                                   "promesa_vs_realidad", "prueba_en_vivo", "caso_de_usuario",
                                                   "advertencia_directa", "contraintuitivo"],
                        "description": "El tipo de gancho que usaste (el que te pido en VARIEDAD)"},
        "escenas": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "narracion": {"type": "string"},
                "visual": {"type": "string", "enum": ["titulo", "captura", "resena", "dato", "grabacion", "veredicto"]},
                "indice": {"type": "integer"},
                "texto": {"type": "string"},
                "momento": {"type": "string", "enum": ["gancho", "desarrollo", "regancho", "cierre"]},
                "voz": {"type": "string", "enum": ["principal", "segunda"]},
                "sonido": {"type": "string", "description": "Qué suena en la escena (efecto o música), corto"},
                "desde": {"type": "number", "description": "Solo en 'grabacion': segundo de la grabación donde empieza la escena; 0 si no"},
            },
            "required": ["narracion", "visual", "indice", "texto", "momento", "voz", "sonido", "desde"],
            "additionalProperties": False,
        }},
    },
    "required": ["titulos", "descripcion", "etiquetas", "texto_miniatura", "textos_miniatura", "sello_miniatura",
                 "tipo_gancho", "escenas"],
    "additionalProperties": False,
}


SYSTEM_TEMA = f"""Eres el guionista del canal de YouTube "{config.CANAL_NOMBRE}". Esta vez el video NO es el \
análisis de una sola app: es de un tema (un método para ganar dinero, un fraude, una plataforma, una noticia, un \
videojuego, tecnología…). Escribes lo que se leerá en voz \
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
                "momento": {"type": "string", "enum": ["gancho", "desarrollo", "regancho", "cierre"]},
                "voz": {"type": "string", "enum": ["principal", "segunda"]},
                "sonido": {"type": "string", "description": "Qué suena en la escena (efecto o música), corto"},
                "desde": {"type": "number", "description": "Solo en 'grabacion': segundo de la grabación donde empieza la escena; 0 si no"},
            },
            "required": ["narracion", "visual", "indice", "texto", "momento", "voz", "sonido", "desde"],
            "additionalProperties": False,
        }},
    },
    "required": SCHEMA["required"],
    "additionalProperties": False,
}


REGLAS_TABLA = """
GUION EN TABLA (así trabaja el canal):
- Cada escena es una fila: lo que se dice (narracion) · lo que se ve (visual + texto) · lo que suena (sonido).
- La PRIMERA escena es el gancho (momento "gancho"): su primera frase se escribe palabra por palabra y se dice en
  menos de 4 segundos (máximo 10 palabras). Empieza a media acción; nunca saludes.
- Más o menos cada 60 segundos pon una escena con momento "regancho": una frase que deja con ganas de lo que
  sigue ("y espérate a ver lo que pasó cuando quise retirar…").
- La última escena es el "cierre". Las demás, "desarrollo".
- Largo: 150 palabras por minuto de video (te digo cuántas en el pedido).
- Cada frase debe poder ilustrarse con lo que hay (capturas, imágenes, datos, reseñas); si no, reescríbela.
- Voz: casi todo lo dice la voz "principal". Si te indico DOS VOCES, de vez en cuando (máximo 1 de cada 4
  escenas) una escena corta con voz "segunda" que pregunta o reacciona como el público ("¿neta?", "¿y sí pagó?"),
  y la siguiente escena le contesta. Nunca dos escenas seguidas de la segunda voz. Sin DOS VOCES: todo "principal".
"""

SYSTEM += REGLAS_TABLA
SYSTEM_TEMA += REGLAS_TABLA


def _pedido_tema(ficha: dict, expediente: dict, clips: list[dict], minutos: int, notas: str) -> str:
    exp = {k: v for k, v in expediente.items() if k not in ("informe_web", "fuentes_web")}
    pedido = (
        f"TEMA: {ficha['title']}\nVIDEO: {expediente.get('angulo', '')}\nFORMATO: {expediente.get('formato', '') or 'el que mejor le quede'}\n\n"
        f"EXPEDIENTE:\n{json.dumps(exp, ensure_ascii=False, default=str)}\n\n"
        f"IMÁGENES DISPONIBLES: {len(ficha.get('screenshots') or [])}\n"
        f"CLIPS DEL CREADOR: {json.dumps(clips, ensure_ascii=False) if clips else 'ninguno'}\n\n"
        f"Escribe un guion de unos {minutos} minutos (≈{minutos * 150} palabras en total)."
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
        f"Escribe un guion de unos {minutos} minutos (≈{minutos * 150} palabras en total)."
    )
    if notas:
        pedido += (f"\n\nINDICACIONES DEL JEFE (prioridad: el video debe seguir este enfoque; "
                   f"los títulos y el gancho van con esta idea):\n{notas}")
    from . import estilo
    if estilo.cargar()["ajustes"].get("dos_voces"):
        pedido += "\n\nDOS VOCES: sí (usa la segunda voz como se explica)."
    mini = estilo.cargar().get("miniaturas")
    if mini:
        pedido += (f"\n\nESTILO DE MINIATURAS DEL CANAL: {mini.get('descripcion', '')} "
                   f"Textos: {mini.get('consejos_texto', '')} Máximo {mini.get('palabras_max', 4)} palabras.")
    from . import canales, empaque, variedad
    canal = canales.actual()
    try:  # 🎲 que no se parezca a los anteriores
        pedido += variedad.para_guionista(canal)
    except Exception as exc:  # noqa: BLE001
        print(f"  · aviso variedad: {exc}", flush=True)
    base = SYSTEM_TEMA if es_tema else SYSTEM
    nombre = canales.get(canal).get("nombre")
    if canal != canales.PRINCIPAL and nombre:  # el guion es para el canal del video
        base = base.replace(f'"{config.CANAL_NOMBRE}"', f'"{nombre}"')
    sistema = (base + empaque.para_guionista(canal) + "\n\n" + manual.para_agente()
               + lecciones.para("guionista", "disenadora"))
    if es_tema:
        r = claude.json_estructurado(sistema, pedido, SCHEMA_TEMA, tarea="guion")
        r["sello_miniatura"] = (r.get("sello_miniatura") or "").upper()[:14]
    else:
        r = claude.json_estructurado(sistema, pedido, SCHEMA, tarea="guion")
    # 🎁 el empaque: 3 paquetes de título + miniatura, calificados con la guía y con tus números
    try:
        resumen = (f"{'Tema' if es_tema else 'App'}: {ficha['title']}. Enfoque: {expediente.get('angulo', '')}. "
                   f"Veredicto: {expediente.get('veredicto', '')}. "
                   + " ".join(e.get("narracion", "") for e in r["escenas"][:6])[:1500])
        r = empaque.empacar(r, resumen, canal, notas)
    except Exception as exc:  # noqa: BLE001 — sin empaque se quedan los títulos de Gabi
        print(f"  · aviso empaque: {exc}", flush=True)
    return r
