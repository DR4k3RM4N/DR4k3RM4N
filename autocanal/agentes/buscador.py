"""Agente 1 — Buscador de ideas: encuentra apps "para ganar dinero" que valga la pena investigar."""
from __future__ import annotations

import json

from . import claude, config, playstore

CONSULTAS = [
    "ganar dinero", "gana dinero jugando", "ganar dinero rapido", "apps que pagan",
    "gana dinero viendo videos", "encuestas pagadas", "ganar dinero paypal",
    "gana dinero caminando", "cash rewards", "earn money",
]

SYSTEM = f"""Eres el productor de un canal de YouTube en español ({config.CANAL_PAIS.upper()}) que \
investiga apps que prometen pagar dinero y expone las que no pagan o engañan.
Eliges qué app conviene investigar después. Priorizas:
- Muchas descargas recientes y popularidad (la gente la está buscando ahora).
- Señales de alerta: promesas exageradas, desarrollador desconocido, reseñas que dicen que no paga, \
pago mínimo inalcanzable, muchos anuncios.
- Apps que no se hayan cubierto antes en el canal.
No acuses: solo propones candidatas para investigar."""

SCHEMA = {
    "type": "object",
    "properties": {
        "candidatas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "app_id": {"type": "string"},
                    "titulo": {"type": "string"},
                    "por_que": {"type": "string"},
                    "potencial_vistas": {"type": "string", "enum": ["alto", "medio", "bajo"]},
                },
                "required": ["app_id", "titulo", "por_que", "potencial_vistas"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["candidatas"],
    "additionalProperties": False,
}


def historial() -> list[str]:
    if config.HISTORIAL.exists():
        return json.loads(config.HISTORIAL.read_text(encoding="utf-8"))
    return []


def marcar_hecha(app_id: str) -> None:
    h = historial()
    if app_id not in h:
        h.append(app_id)
        config.HISTORIAL.write_text(json.dumps(h, indent=2), encoding="utf-8")


def ideas(cuantas: int = 5) -> list[dict]:
    hechas = set(historial())
    encontradas: dict[str, dict] = {}
    for q in CONSULTAS:
        try:
            for r in playstore.buscar(q, 20):
                if r.get("appId") and r["appId"] not in hechas:
                    encontradas.setdefault(r["appId"], {
                        "app_id": r["appId"], "titulo": r.get("title"), "dev": r.get("developer"),
                        "score": r.get("score"), "instalaciones": r.get("installs"),
                        "resumen": r.get("summary") or (r.get("description") or "")[:300],
                    })
        except Exception as exc:  # noqa: BLE001 — una consulta fallida no detiene la búsqueda
            print(f"  aviso: búsqueda '{q}' falló: {exc}")
    if not encontradas:
        raise claude.ErrorIA("No se encontraron apps en Play Store.")
    datos = json.dumps(list(encontradas.values()), ensure_ascii=False)
    res = claude.json_estructurado(
        SYSTEM,
        f"Apps encontradas hoy en Play Store:\n{datos}\n\nElige las {cuantas} mejores para investigar.",
        SCHEMA, effort="medium",
    )
    return res["candidatas"][:cuantas]
