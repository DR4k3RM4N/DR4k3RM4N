"""Agente 2 — Investigador: arma el expediente de evidencia de una app.

Junta la ficha de Play Store, reseñas reales, capturas y lo que se dice en internet,
y le pide a Claude un veredicto respaldado por evidencia (nunca inventado).
"""
from __future__ import annotations

import base64
import json
import re
from pathlib import Path

from . import claude, config, playstore

SYSTEM_WEB = """Eres investigador de fraudes en apps móviles para un canal de YouTube en español.
Busca en internet información verificable sobre la app que te pidan: reportes de usuarios \
(Reddit, Trustpilot, foros, comentarios de YouTube), noticias, quién es el desarrollador, si hay \
pruebas de pago reales, el pago mínimo y cuánto tarda en alcanzarse, cambios de nombre o clones.
Reporta hechos con su fuente. Distingue claramente entre lo comprobado y lo que solo dicen usuarios. \
Si no encuentras nada, dilo; no rellenes."""

SYSTEM_EXPEDIENTE = """Eres el editor de investigación de un canal que analiza apps que prometen \
pagar dinero. Con la evidencia que te dan, armas un expediente para el video.

Reglas legales y de credibilidad (importantes):
- Solo afirmas lo que la evidencia respalda. Cada señal lleva su evidencia y de dónde sale.
- Usa el veredicto "estafa_comprobada" solo si hay evidencia fuerte y de varias fuentes de que no \
paga o engaña. Si solo hay quejas, usa "senales_de_alerta". Si paga pero muy poco, \
"paga_pero_no_vale_la_pena". Si paga bien, "legitima". Si no hay datos, "no_concluyente".
- Las reseñas destacadas se eligen por su índice en la lista; no las reescribas.
- En "pendiente_de_probar" lista lo que el creador debe comprobar él mismo en el celular \
(por ejemplo: intentar retirar, ver cuántos anuncios salen, cuánto se gana en 10 minutos).
- Describe qué muestra cada captura de pantalla, para usarlas en el video."""

SCHEMA = {
    "type": "object",
    "properties": {
        "veredicto": {"type": "string", "enum": [
            "estafa_comprobada", "senales_de_alerta", "paga_pero_no_vale_la_pena",
            "legitima", "no_concluyente"]},
        "resumen": {"type": "string"},
        "que_promete": {"type": "string"},
        "como_dice_que_paga": {"type": "string"},
        "pago_minimo": {"type": "string"},
        "senales": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "senal": {"type": "string"},
                "evidencia": {"type": "string"},
                "fuente": {"type": "string", "description": "playstore, resenas, web:<url> o captura"},
                "gravedad": {"type": "string", "enum": ["alta", "media", "baja"]},
            },
            "required": ["senal", "evidencia", "fuente", "gravedad"],
            "additionalProperties": False,
        }},
        "resenas_destacadas": {"type": "array", "items": {"type": "integer"},
                               "description": "Índices de las reseñas más representativas (máx 6)"},
        "capturas": {"type": "array", "items": {
            "type": "object",
            "properties": {"indice": {"type": "integer"}, "muestra": {"type": "string"}},
            "required": ["indice", "muestra"],
            "additionalProperties": False,
        }},
        "pendiente_de_probar": {"type": "array", "items": {"type": "string"}},
        "alternativas_reales": {"type": "array", "items": {"type": "string"},
                                "description": "Opciones legítimas para ganar dinero, si aplica"},
    },
    "required": ["veredicto", "resumen", "que_promete", "como_dice_que_paga", "pago_minimo",
                 "senales", "resenas_destacadas", "capturas", "pendiente_de_probar",
                 "alternativas_reales"],
    "additionalProperties": False,
}


def _imagen(ruta: str) -> dict:
    """Captura reducida (lado mayor 900 px, JPEG): se ve igual de clara y cuesta muchos menos tokens."""
    import io

    from PIL import Image

    try:
        img = Image.open(ruta).convert("RGB")
        img.thumbnail((900, 900))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=80)
        crudo, tipo = buf.getvalue(), "image/jpeg"
    except Exception:  # noqa: BLE001 — si no se puede abrir, se manda tal cual
        crudo, tipo = Path(ruta).read_bytes(), "image/png"
    datos = base64.standard_b64encode(crudo).decode()
    return {"type": "image", "source": {"type": "base64", "media_type": tipo, "data": datos}}


def recolectar(app_id: str, carpeta: Path) -> dict:
    """Paso sin IA: baja ficha, reseñas e imágenes de Play Store."""
    print("  · ficha de Play Store")
    ficha = playstore.ficha(app_id)
    print("  · reseñas")
    resenas = playstore.resenas(app_id)
    print("  · imágenes")
    imagenes = playstore.descargar_imagenes(ficha, carpeta)
    playstore.guardar(carpeta, "ficha.json", ficha)
    playstore.guardar(carpeta, "resenas.json", resenas)
    playstore.guardar(carpeta, "imagenes.json", imagenes)
    return {"ficha": ficha, "resenas": resenas, "imagenes": imagenes}


QUEJAS = re.compile(r"no pag|nunca pag|no me pag|no me han pag|estafa|fraude|scam|enga[ñn]|mentira|no deja (retirar|cobrar)|"
                    r"no puedo (retirar|cobrar)|retir|no llega|nunca llega|pura publicidad|demasiados anuncios", re.I)


def necesita_web(resenas: list[dict]) -> tuple[bool, str]:
    """Las reseñas son gratis; internet cuesta. Si ya hay muchas quejas claras, con eso basta.

    INVESTIGACION_WEB en .env: auto (por defecto) · siempre · nunca."""
    modo = config.env("INVESTIGACION_WEB", "auto").lower()
    if modo == "siempre":
        return True, "siempre activada en .env"
    if modo == "nunca":
        return False, "desactivada en .env"
    malas = [r for r in resenas if (r.get("estrellas") or 5) <= 2]
    quejas = [r for r in malas if QUEJAS.search(r.get("texto") or "")]
    minimo = int(config.env("QUEJAS_SUFICIENTES", "8") or 8)
    if len(quejas) >= minimo:
        return False, f"{len(quejas)} reseñas ya reportan que no paga o engaña"
    return True, f"solo {len(quejas)} quejas claras en reseñas; falta evidencia"


def analizar(datos: dict, carpeta: Path, con_web: bool = True) -> dict:
    ficha, resenas, imagenes = datos["ficha"], datos["resenas"], datos["imagenes"]

    informe_web, fuentes = "", []
    usar_web, motivo = necesita_web(resenas) if con_web else (False, "sin búsqueda web")
    print(f"  · internet: {'sí' if usar_web else 'no'} ({motivo})")
    if usar_web:
        print("  · investigando en internet (Claude + búsqueda web)")
        informe_web, fuentes = claude.investigar_web(
            SYSTEM_WEB,
            f"App: {ficha['title']} ({ficha['appId']}) de {ficha.get('developer')}.\n"
            f"Sitio del desarrollador: {ficha.get('developerWebsite')}\n"
            f"Qué promete: {ficha.get('summary')}\n"
            "¿Paga de verdad? ¿Qué reportan los usuarios? ¿Quién está detrás?\n"
            "Responde en máximo 250 palabras, solo hechos con su fuente.",
        )

    # Reseñas: priorizamos las de 1-2 estrellas con más likes, más una muestra del resto.
    malas = sorted([r for r in resenas if (r["estrellas"] or 5) <= 2], key=lambda r: -r["likes"])[:30]
    buenas = sorted([r for r in resenas if (r["estrellas"] or 0) >= 4], key=lambda r: -r["likes"])[:10]
    muestra = malas + buenas
    lista = "\n".join(f"[{i}] {r['estrellas']}★ ({r['likes']} likes, {r['fecha']}) {r['texto'][:300]}"
                      for i, r in enumerate(muestra))

    contenido = [_imagen(p) for p in imagenes["capturas"][:3]]
    datos_ficha = {k: v for k, v in ficha.items() if k not in ("screenshots", "icon", "headerImage")}
    datos_ficha["description"] = (datos_ficha.get("description") or "")[:1500]
    contenido.append({"type": "text", "text": (
        f"FICHA DE PLAY STORE:\n{json.dumps(datos_ficha, ensure_ascii=False, default=str)}\n\n"
        f"RESEÑAS (índice entre corchetes):\n{lista}\n\n"
        f"INVESTIGACIÓN WEB:\n{informe_web or '(no se hizo)'}\n\n"
        f"FUENTES WEB:\n{json.dumps(fuentes, ensure_ascii=False)}\n\n"
        f"Las imágenes de arriba son las capturas 1 a {len(contenido)} en orden. Arma el expediente."
    )})
    print("  · armando expediente")
    exp = claude.json_estructurado(SYSTEM_EXPEDIENTE, contenido, SCHEMA, tarea="investigar", que="expediente")
    exp["resenas_citadas"] = [muestra[i] for i in exp["resenas_destacadas"] if 0 <= i < len(muestra)][:6]
    exp["fuentes_web"] = fuentes
    exp["informe_web"] = informe_web
    exp["investigacion_web"] = ("hecha" if usar_web else "omitida") + f": {motivo}"
    playstore.guardar(carpeta, "expediente.json", exp)
    return exp
