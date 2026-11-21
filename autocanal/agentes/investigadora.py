"""🔎 Paola investigadora: le das una instrucción ("investígame apps de préstamo", "temas en tendencia sobre ganar
dinero") y ella primero ESTUDIA qué está funcionando y hasta después propone:

1. Plan: entiende qué quieres y arma búsquedas (Google, YouTube y lo que la gente teclea).
2. Señales recientes (último mes):
   - 📈 YouTube: videos del tema que pegan más de lo normal (vistas ÷ suscriptores, vistas por día) y sus
     comentarios (qué pregunta, qué le pasó, qué pide la gente).
   - ⌨️ Autocompletado de Google y de YouTube: lo que la gente está buscando de verdad.
   - 📰 Google Noticias y Google del último mes: lo que está pasando ahora.
3. Análisis: qué patrón tienen los videos que pegan, qué pregunta la gente que nadie contesta bien (huecos).
4. Ideas: arma el doble de candidatas, se califica cada una como crítica dura (demanda, competencia, encaje con el
   canal) y solo te pasa las que tienen evidencia de al menos 2 señales distintas y sacan 6/10 o más.

Todo con fuentes que de verdad salieron (nada inventado).
Costo: ~11 búsquedas de Google (fracciones de centavo) + 2 llamadas a Claude (tu plan) + YouTube y
autocompletado (gratis).
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from . import buscar_web, claude, config, lecciones, manual

FORMATOS = ["analisis_app", "top", "guia", "noticias", "analisis", "opinion", "comparativa", "tutorial", "historia",
            "alerta_estafa"]
PUNTAJE_MINIMO = 6

SCHEMA_PLAN = {
    "type": "object",
    "properties": {
        "entendi": {"type": "string", "description": "Qué entendiste que quiere el jefe, en una frase"},
        "consultas_google": {"type": "array", "items": {"type": "string"},
                             "description": "6 a 8 búsquedas de Google, variadas (tendencias, noticias, foros, quejas)"},
        "consultas_noticias": {"type": "array", "items": {"type": "string"},
                               "description": "2 o 3 búsquedas para Google Noticias (lo que está pasando este mes)"},
        "consultas_youtube": {"type": "array", "items": {"type": "string"},
                              "description": "3 a 5 búsquedas como las escribe la gente en YouTube"},
        "semillas": {"type": "array", "items": {"type": "string"},
                     "description": "3 a 6 frases cortas (2-4 palabras) como empieza a teclear la gente, para ver el "
                                    "autocompletado de Google y YouTube. Ej.: 'app de prestamo', 'montadeudas'"},
        "quiere_apps": {"type": "boolean", "description": "¿Le sirven apps concretas?"},
        "quiere_temas": {"type": "boolean", "description": "¿Le sirven temas que no son apps?"},
        "regla_permanente": {"type": "string",
                             "description": "Si pidió algo para SIEMPRE ('de ahora en adelante…', 'nunca…', 'siempre…'), "
                                            "la regla en una frase; si no, vacío"},
    },
    "required": ["entendi", "consultas_google", "consultas_noticias", "consultas_youtube", "semillas", "quiere_apps",
                 "quiere_temas", "regla_permanente"],
    "additionalProperties": False,
}

SCHEMA_IDEAS = {
    "type": "object",
    "properties": {
        "analisis": {"type": "object", "properties": {
            "que_pega": {"type": "string", "description": "Qué tienen en común los videos que más pegan (tema, ángulo, "
                                                          "título, emoción), con números"},
            "que_pide_la_gente": {"type": "string", "description": "Lo que la gente busca, pregunta o le pasó (de "
                                                                   "autocompletado y comentarios)"},
            "huecos": {"type": "string", "description": "Lo que la gente quiere y nadie está contando bien"},
        }, "required": ["que_pega", "que_pide_la_gente", "huecos"], "additionalProperties": False},
        "candidatas": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "tipo": {"type": "string", "enum": ["app", "tema"]},
                "nombre": {"type": "string", "description": "app: nombre exacto de la app · tema: el tema en pocas palabras"},
                "titulo_video": {"type": "string", "description": "Título tentativo del video (máx. 70 caracteres)"},
                "formato": {"type": "string", "enum": FORMATOS},
                "por_que": {"type": "string", "description": "Por qué este video funcionaría AHORA, en 1-2 frases"},
                "evidencia": {"type": "array", "items": {"type": "string"},
                              "description": "Las señales que la respaldan, citando la etiqueta y el número: "
                                             "'[V3] 180k vistas en 9 días, x45', '[A] YouTube sugiere «...»', "
                                             "'[N2] noticia de esta semana', '[C] 12 comentarios preguntan ...'"},
                "senales_distintas": {"type": "integer", "description": "Cuántos TIPOS de señal la respaldan "
                                                                         "(video que pega, autocompletado, noticia, "
                                                                         "comentarios, Google): 0 a 5"},
                "demanda": {"type": "integer", "description": "1-10: cuánta gente lo quiere ver ahora"},
                "competencia": {"type": "string", "enum": ["baja", "media", "alta"],
                                "description": "Qué tan cubierto está ya en YouTube en español"},
                "puntaje": {"type": "integer", "description": "1-10, calificación de crítica dura: demanda, hueco, "
                                                              "encaje con el canal y que se pueda hacer bien"},
                "inspiracion": {"type": "string", "description": "URL del video que pega en que se inspira (de la "
                                                                 "lista), o vacío"},
                "fuentes": {"type": "array", "items": {"type": "string"},
                            "description": "URLs de los resultados que lo respaldan"},
            },
            "required": ["tipo", "nombre", "titulo_video", "formato", "por_que", "evidencia", "senales_distintas",
                         "demanda", "competencia", "puntaje", "inspiracion", "fuentes"],
            "additionalProperties": False,
        }},
    },
    "required": ["analisis", "candidatas"],
    "additionalProperties": False,
}


def _sistema() -> str:
    from . import canales
    c = canales.get(canales.actual())
    nombre = c.get("nombre") or config.CANAL_NOMBRE
    nicho = canales.NICHOS.get(c.get("nicho"), "")
    return (f'Eres Paola, productora e investigadora del canal de YouTube "{nombre}" (público de México; tema: {nicho}).\n'
            "Piensas como estratega de YouTube con datos: antes de proponer, estudias qué está pegando AHORA, qué "
            "busca la gente y qué nadie está contando bien. Un video funciona cuando hay demanda real (la gente lo "
            "busca, lo comenta, hay videos chicos que explotan con ese tema) y tú puedes hacerlo mejor o desde otro "
            "ángulo. Eres tu propia crítica más dura: si una idea solo te suena bonita pero no tiene señales, la "
            "descartas. El jefe te da instrucciones en sus palabras: entiende lo que quiere de verdad (a veces es una "
            "búsqueda, a veces un criterio, a veces una regla para siempre). No inventes apps, cifras, videos ni "
            "noticias: todo sale de los datos que te paso.")


def _gastar(conteo: dict, que: str) -> None:
    gasto = buscar_web.costo(conteo)
    if claude.al_gastar and gasto:
        claude.al_gastar(getattr(claude.contexto, "proyecto", None), "ideas", "búsqueda", gasto, 0, 0, que)


def _juntar_senales(plan: dict) -> dict:
    """Corre todas las búsquedas a la vez. Lo que falle se salta (las ideas salen con lo que haya)."""
    from . import tendencias

    def google():
        if not buscar_web.disponible():
            return [], {}
        return buscar_web.buscar(plan["consultas_google"][:8], por_consulta=6, max_texto=350, reciente="m")

    def news():
        return buscar_web.noticias(plan["consultas_noticias"][:3], reciente="m")

    def youtube():
        videos = tendencias.buscar(plan["consultas_youtube"][:5], dias=45, cuantos=15) if plan["consultas_youtube"] else []
        for v in sorted(videos, key=lambda x: x["vistas_por_dia"], reverse=True)[:4]:  # los que más jalan hoy
            v["comentarios"] = tendencias.comentarios(v["id"], 15)
        return videos

    with ThreadPoolExecutor(max_workers=4) as pool:
        f_g, f_n = pool.submit(google), pool.submit(news)
        f_y, f_s = pool.submit(youtube), pool.submit(buscar_web.sugerencias, plan["semillas"][:6])
        senales = {}
        for nombre, fut, vacio in (("google", f_g, ([], {})), ("noticias", f_n, ([], {})), ("videos", f_y, []),
                                   ("sugerencias", f_s, {"google": {}, "youtube": {}})):
            try:
                senales[nombre] = fut.result()
            except Exception as exc:  # noqa: BLE001
                print(f"  · aviso ({nombre}): {exc}", flush=True)
                senales[nombre] = vacio
    resultados, conteo = senales["google"]
    noticias, conteo_n = senales["noticias"]
    for k, v in (conteo_n or {}).items():
        conteo[k] = conteo.get(k, 0) + v
    _gastar(conteo, f"Google ({sum(conteo.values())} búsquedas para ideas)")
    return {"google": resultados, "noticias": noticias, "videos": senales["videos"],
            "sugerencias": senales["sugerencias"]}


def _texto_senales(s: dict) -> str:
    partes = []
    if s["videos"]:
        lineas = []
        for i, v in enumerate(s["videos"], 1):
            lineas.append(f"[V{i}] «{v['titulo']}» — {v['canal']} ({v['suscriptores']:,} subs): {v['vistas']:,} vistas en "
                          f"{v['dias']:.0f} días ({v['vistas_por_dia']:,}/día), x{v['multiplicador']}, "
                          f"{v['minutos']} min, {v.get('comentarios_n', 0):,} comentarios — {v['url']}")
            for c in v.get("comentarios") or []:
                lineas.append(f"      [C{i}] {c}")
        partes.append("📈 VIDEOS QUE PEGAN EN YOUTUBE (últimos 45 días; x = vistas ÷ suscriptores del canal; "
                      "[C] = comentarios de la gente en ese video):\n" + "\n".join(lineas))
    sug = s["sugerencias"]
    if sug.get("google") or sug.get("youtube"):
        lineas = [f"[A] {donde.capitalize()} · «{sem}» → " + " | ".join(lista)
                  for donde in ("youtube", "google") for sem, lista in sug.get(donde, {}).items()]
        partes.append("⌨️ LO QUE LA GENTE ESTÁ TECLEANDO (autocompletado de hoy):\n" + "\n".join(lineas))
    if s["noticias"]:
        partes.append("📰 NOTICIAS DEL ÚLTIMO MES:\n" + "\n".join(
            f"[N{i}] {n['titulo']} — {n['fuente']} {n['fecha']} — {n['url']}\n     {n['texto']}"
            for i, n in enumerate(s["noticias"][:20], 1)))
    if s["google"]:
        partes.append("🔎 GOOGLE (último mes):\n" + "\n".join(
            f"[G{i}] {r['titulo']} — {r['url']}\n     {r.get('fecha', '')} {r['texto']}"
            for i, r in enumerate(s["google"][:45], 1)))
    return "\n\n".join(partes) or "(No conseguí señales: ni Google, ni YouTube, ni autocompletado.)"


def _potencial(puntaje: int) -> str:
    return "alto" if puntaje >= 8 else "medio" if puntaje >= 6 else "bajo"


def investigar(instruccion: str, guia: str = "", cuantas: int = 6, hechas: set | None = None) -> dict:
    """Regresa {"entendi", "regla_permanente", "analisis", "ideas": [propuestas listas para la bandeja]}."""
    from . import buscador

    sistema = _sistema() + "\n\n" + manual.para_agente() + lecciones.para("productora")
    plan = claude.json_estructurado(
        sistema,
        f"INSTRUCCIÓN DEL JEFE: {instruccion}\n" + (f"\nGUSTOS Y REGLAS DEL JEFE:\n{guia}\n" if guia else "")
        + "\nArma tu plan de investigación (en español de México, como busca la gente de verdad; alguna en inglés "
          "solo si ayuda). Piensa en lo que la gente teclea cuando tiene el problema, no en cómo lo diría un experto.",
        SCHEMA_PLAN, tarea="ideas", que="plan de investigación")
    senales = _juntar_senales(plan)
    print(f"  · Paola estudió: {len(senales['videos'])} videos que pegan, "
          f"{sum(len(x) for x in senales['sugerencias'].get('youtube', {}).values())} búsquedas de YouTube, "
          f"{sum(len(x) for x in senales['sugerencias'].get('google', {}).values())} de Google, "
          f"{len(senales['noticias'])} noticias, {len(senales['google'])} resultados de Google", flush=True)
    ya = ", ".join(sorted(hechas or set())[:80])
    r = claude.json_estructurado(
        sistema,
        f"INSTRUCCIÓN DEL JEFE: {instruccion}\nLO QUE ENTENDISTE: {plan['entendi']}\n"
        f"TIPOS QUE QUIERE: {'apps' if plan['quiere_apps'] else ''} {'temas' if plan['quiere_temas'] else ''}\n"
        + (f"\nGUSTOS Y REGLAS DEL JEFE:\n{guia}\n" if guia else "")
        + (f"\nYA HECHOS O EN LA BANDEJA (no los repitas): {ya}\n" if ya else "")
        + "\n" + _texto_senales(senales) + "\n\n"
        "PASO 1 — ANALIZA las señales: qué patrón tienen los videos que más pegan (vistas por día y multiplicador, "
        "no solo vistas totales), qué pregunta o le pasa a la gente (comentarios y autocompletado), y qué huecos hay.\n"
        f"PASO 2 — Arma {cuantas * 2} candidatas de video distintas entre sí. Cada una con su evidencia citando las "
        "etiquetas ([V3], [C2], [A], [N1], [G5]) y números reales.\n"
        "PASO 3 — Califícalas como crítica dura (puntaje 1-10). Baja el puntaje si: solo la respalda un tipo de señal, "
        "el tema ya está muy cubierto sin un ángulo nuevo, es viejo, o no encaja con el canal. Sube si: videos chicos "
        "explotan con eso, la gente lo está tecleando y preguntando, y hay un hueco que tú puedes llenar.\n"
        "Para 'app' usa el nombre exacto como sale en los datos. Las fuentes deben ser URLs de los datos de arriba. "
        "Ordena las candidatas de mejor a peor.",
        SCHEMA_IDEAS, tarea="ideas", que="análisis e ideas")
    urls = {x["url"] for x in senales["google"]} | {n["url"] for n in senales["noticias"]} \
        | {v["url"] for v in senales["videos"]}
    videos = {v["url"]: v for v in senales["videos"]}
    hay_senales = bool(senales["videos"] or senales["noticias"] or senales["google"]
                       or senales["sugerencias"].get("google") or senales["sugerencias"].get("youtube"))
    buenas = [c for c in r["candidatas"]
              if not hay_senales or (c["puntaje"] >= PUNTAJE_MINIMO and c["senales_distintas"] >= 2)]
    if not buenas:  # ninguna pasó el filtro: mejor las 3 menos malas, avisando
        buenas = sorted(r["candidatas"], key=lambda c: c["puntaje"], reverse=True)[:3]
    buenas.sort(key=lambda c: (c["puntaje"], c["demanda"]), reverse=True)
    propuestas = []
    for i in buenas[:cuantas]:
        fuentes = [u for u in i["fuentes"] if u in urls][:4]  # nada de URLs inventadas
        evidencia = "\n".join(f"• {e}" for e in i["evidencia"][:4])
        base = {"angulo": i["titulo_video"][:90], "potencial_vistas": _potencial(i["puntaje"]), "personalizada": True,
                "idea_jefe": instruccion, "fuentes": fuentes, "puntaje": i["puntaje"],
                "por_que": f"🔎 {i['por_que']} (⭐ {i['puntaje']}/10 · competencia {i['competencia']})"
                           + (f"\n📊 {evidencia}" if evidencia else "")}
        if i["inspiracion"] in videos:
            v = videos[i["inspiracion"]]
            base["inspiracion"] = {"url": v["url"], "titulo": v["titulo"], "multiplicador": v["multiplicador"]}
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
    a = r["analisis"]
    descartadas = len(r["candidatas"]) - len(propuestas)
    analisis = (f"📈 Lo que pega: {a['que_pega']}\n🗣️ Lo que pide la gente: {a['que_pide_la_gente']}\n"
                f"🕳️ Huecos: {a['huecos']}" + (f"\n🗑️ Descarté {descartadas} ideas flojas." if descartadas > 0 else ""))
    return {"entendi": plan["entendi"], "regla_permanente": plan["regla_permanente"].strip(), "analisis": analisis,
            "ideas": propuestas}
