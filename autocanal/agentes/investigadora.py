"""🔎 Paola investigadora: le das una instrucción ("investígame temas en tendencia sobre ganar dinero, que no sean solo
apps") y ella arma su plan de búsqueda, investiga en Google y en YouTube, y te propone ideas de dos tipos:

- APP: una app concreta (de Play Store o de fuera) → el video de siempre (prueba, reseñas, veredicto).
- TEMA: un tema que no es una app (un método para ganar dinero, un fraude nuevo, una plataforma, una noticia,
  "¿sí se puede ganar con…?") → video de tema con su propia investigación (temas.py).

Cada idea dice de dónde salió, con fuentes que de verdad aparecieron en la búsqueda.
Costo: ~8-10 búsquedas de Google (fracciones de centavo) + 2 llamadas a Claude (tu plan) + YouTube (gratis).
"""
from __future__ import annotations

import json

from . import buscar_web, claude, config, manual

FORMATOS = ["analisis_app", "top", "guia", "noticias", "analisis", "opinion", "comparativa", "tutorial", "historia",
            "alerta_estafa"]

SCHEMA_PLAN = {
    "type": "object",
    "properties": {
        "entendi": {"type": "string", "description": "Qué entendiste que quiere el jefe, en una frase"},
        "consultas_google": {"type": "array", "items": {"type": "string"},
                             "description": "6 a 8 búsquedas de Google, variadas (tendencias, noticias, foros, quejas)"},
        "consultas_youtube": {"type": "array", "items": {"type": "string"},
                              "description": "2 a 4 búsquedas para ver qué videos están pegando en YouTube"},
        "quiere_apps": {"type": "boolean", "description": "¿Le sirven apps concretas?"},
        "quiere_temas": {"type": "boolean", "description": "¿Le sirven temas que no son apps?"},
        "regla_permanente": {"type": "string",
                             "description": "Si pidió algo para SIEMPRE ('de ahora en adelante…', 'nunca…', 'siempre…'), "
                                            "la regla en una frase; si no, vacío"},
    },
    "required": ["entendi", "consultas_google", "consultas_youtube", "quiere_apps", "quiere_temas", "regla_permanente"],
    "additionalProperties": False,
}

SCHEMA_IDEAS = {
    "type": "object",
    "properties": {
        "ideas": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "tipo": {"type": "string", "enum": ["app", "tema"]},
                "nombre": {"type": "string", "description": "app: nombre exacto de la app · tema: el tema en pocas palabras"},
                "titulo_video": {"type": "string", "description": "Título tentativo del video (máx. 70 caracteres)"},
                "formato": {"type": "string", "enum": FORMATOS},
                "por_que": {"type": "string", "description": "Por qué ahora: qué encontraste (tendencia, noticia, quejas, video que pega)"},
                "fuentes": {"type": "array", "items": {"type": "string"}, "description": "URLs de los resultados que lo respaldan"},
                "potencial_vistas": {"type": "string", "enum": ["alto", "medio", "bajo"]},
            },
            "required": ["tipo", "nombre", "titulo_video", "formato", "por_que", "fuentes", "potencial_vistas"],
            "additionalProperties": False,
        }},
    },
    "required": ["ideas"],
    "additionalProperties": False,
}

SISTEMA = f"""Eres Paola, productora e investigadora del canal de YouTube "{config.CANAL_NOMBRE}" (público de México que
quiere ganar dinero con su celular o saber si algo es real o estafa). El jefe te da instrucciones en sus palabras:
entiende lo que quiere de verdad (a veces es una búsqueda, a veces un criterio, a veces una regla para siempre).
Tu trabajo es encontrar videos que la gente quiera ver AHORA, con evidencia: no inventes apps, cifras ni noticias;
todo sale de los resultados que te paso."""


def _gastar(conteo: dict, que: str) -> None:
    gasto = buscar_web.costo(conteo)
    if claude.al_gastar and gasto:
        claude.al_gastar(getattr(claude.contexto, "proyecto", None), "ideas", "búsqueda", gasto, 0, 0, que)


def investigar(instruccion: str, guia: str = "", cuantas: int = 6, hechas: set | None = None) -> dict:
    """Regresa {"entendi", "regla_permanente", "ideas": [propuestas listas para la bandeja]}."""
    from . import buscador, tendencias

    plan = claude.json_estructurado(
        SISTEMA + "\n\n" + manual.para_agente(),
        f"INSTRUCCIÓN DEL JEFE: {instruccion}\n" + (f"\nGUSTOS Y REGLAS DEL JEFE:\n{guia}\n" if guia else "")
        + "\nArma tu plan de búsqueda (en español de México, y alguna en inglés si ayuda).",
        SCHEMA_PLAN, tarea="ideas", que="plan de investigación")
    resultados, conteo = ([], {})
    if buscar_web.disponible():
        resultados, conteo = buscar_web.buscar(plan["consultas_google"][:8], por_consulta=6, max_texto=400)
        _gastar(conteo, f"Google ({sum(conteo.values())} búsquedas para ideas)")
    pegando = tendencias.buscar(plan["consultas_youtube"][:4]) if plan["consultas_youtube"] else []
    print(f"  · Paola investigó: {len(resultados)} resultados de Google, {len(pegando)} videos que pegan", flush=True)
    lista = "\n\n".join(f"[{i}] {r['titulo']} — {r['url']}\n{r.get('fecha', '')} {r['texto']}"
                         for i, r in enumerate(resultados[:60]))
    ya = ", ".join(sorted(hechas or set())[:80])
    r = claude.json_estructurado(
        SISTEMA + "\n\n" + manual.para_agente(),
        f"INSTRUCCIÓN DEL JEFE: {instruccion}\nLO QUE ENTENDISTE: {plan['entendi']}\n"
        f"TIPOS QUE QUIERE: {'apps' if plan['quiere_apps'] else ''} {'temas' if plan['quiere_temas'] else ''}\n"
        + (f"\nGUSTOS Y REGLAS DEL JEFE:\n{guia}\n" if guia else "")
        + (f"\nYA HECHOS O EN LA BANDEJA (no los repitas): {ya}\n" if ya else "")
        + (f"\nRESULTADOS DE GOOGLE:\n{lista}\n" if lista else "\n(Sin búsqueda de Google disponible.)\n")
        + (f"\n{tendencias.para_paola(pegando)}\n" if pegando else "")
        + f"\nPropón {cuantas} ideas de video distintas entre sí, las mejores primero. Para 'app' usa el nombre "
          "exacto como sale en los resultados. Las fuentes deben ser URLs de los resultados de arriba.",
        SCHEMA_IDEAS, tarea="ideas", que="ideas investigadas")
    urls = {x["url"] for x in resultados} | {v["url"] for v in pegando}
    propuestas = []
    for i in r["ideas"][:cuantas]:
        fuentes = [u for u in i["fuentes"] if u in urls][:4]  # nada de URLs inventadas
        base = {"angulo": i["titulo_video"][:90], "potencial_vistas": i["potencial_vistas"], "personalizada": True,
                "idea_jefe": instruccion, "por_que": "🔎 " + i["por_que"], "fuentes": fuentes}
        if i["tipo"] == "app":
            try:
                app = buscador.encontrar_app(i["nombre"], hechas or set()) or buscador.fuera_de_play(i["nombre"])
            except Exception as exc:  # noqa: BLE001 — si no se encuentra, se intenta como tema
                print(f"  · no encontré la app «{i['nombre']}»: {exc}", flush=True)
                app = None
            if app:
                propuestas.append({**base, "app_id": app["app_id"], "titulo": app["titulo"],
                                   "fuera_de_play": bool(app.get("fuera_de_play"))})
                continue
        from . import temas
        nombre = i["nombre"].strip()[:60]
        propuestas.append({**base, "app_id": f"tema:{temas._slug(nombre, 24)}-{temas._slug(i['titulo_video'], 34)}",
                           "titulo": nombre, "tema": nombre, "formato": i["formato"]})
    return {"entendi": plan["entendi"], "regla_permanente": plan["regla_permanente"].strip(), "ideas": propuestas}
