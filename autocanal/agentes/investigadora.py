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
        "una_app_por_video": {"type": "boolean",
                              "description": "true si pide apps de un TIPO (ej. 'apps de préstamo montadeudas', 'las "
                                             "peores apps de…', 'apps que no pagan') y conviene un video por app con su "
                                             "nombre; false si pide temas, tendencias o ideas en general"},
        "criterio": {"type": "string", "enum": ["peores", "mejores", "populares", "nuevas"],
                     "description": "Cómo ordenar las apps si una_app_por_video (montadeudas, estafas → peores)"},
        "consultas_nombres": {"type": "array", "items": {"type": "string"},
                              "description": "Si una_app_por_video: 5 o 6 búsquedas de Google para sacar NOMBRES de "
                                             "apps concretas: listas oficiales, quejas, foros, noticias. Usa operadores "
                                             "y las palabras de la gente. Si no, vacío"},
        "consultas_play": {"type": "array", "items": {"type": "string"},
                           "description": "Si una_app_por_video: 2 o 3 búsquedas para Play Store (como las teclea la "
                                          "gente, ej. 'prestamo rapido sin buro'). Si no, vacío"},
        "quiere_apps": {"type": "boolean", "description": "¿Le sirven apps concretas?"},
        "quiere_temas": {"type": "boolean", "description": "¿Le sirven temas que no son apps?"},
        "regla_permanente": {"type": "string",
                             "description": "Si pidió algo para SIEMPRE ('de ahora en adelante…', 'nunca…', 'siempre…'), "
                                            "la regla en una frase; si no, vacío"},
    },
    "required": ["entendi", "consultas_google", "consultas_noticias", "consultas_youtube", "semillas",
                 "una_app_por_video", "criterio", "consultas_nombres", "consultas_play", "quiere_apps",
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
        + "\nArma tu plan de investigación como la mejor investigadora (mejor que el jefe buscando solo):\n"
          "- Busca como habla la gente cuando tiene el problema, no como experto: sinónimos y modismos de México "
          "(ej. montadeudas, 'me están exponiendo', 'le escribieron a mis contactos', 'cobranza ilegal', "
          "'préstamo exprés', 'me depositaron menos').\n"
          "- Usa operadores de Google cuando ayuden: site:reddit.com, site:condusef.gob.mx, site:gob.mx, comillas "
          "para frases exactas, intitle:, OR, y el año actual para traer lo reciente.\n"
          "- Combina fuentes: oficiales (Condusef, Policía Cibernética, SSPC), foros y quejas (Reddit, Facebook, "
          "Quora, Profeco), noticias y reseñas.\n"
          "- En español de México; alguna en inglés solo si ayuda.",
        SCHEMA_PLAN, tarea="ideas", que="plan de investigación")
    senales = _juntar_senales(plan)
    print(f"  · Paola estudió: {len(senales['videos'])} videos que pegan, "
          f"{sum(len(x) for x in senales['sugerencias'].get('youtube', {}).values())} búsquedas de YouTube, "
          f"{sum(len(x) for x in senales['sugerencias'].get('google', {}).values())} de Google, "
          f"{len(senales['noticias'])} noticias, {len(senales['google'])} resultados de Google", flush=True)
    if plan.get("una_app_por_video"):
        try:
            return _cazar_apps(instruccion, guia, cuantas, hechas or set(), plan, senales, sistema)
        except claude.ErrorIA:
            raise
        except Exception as exc:  # noqa: BLE001 — si el cazador falla, salen ideas normales
            print(f"  · el cazador de apps falló ({exc}); sigo con ideas normales", flush=True)
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


# ---------- 🎯 cazador de apps: un video por app, con su evidencia ----------
PALABRAS_QUEJA = ("amenaz", "extors", "contactos", "acos", "insult", "exhib", "expon", "fotos", "montadeuda",
                  "monta deuda", "fraude", "estafa", "robo", "robaron", "cobran de m", "intereses", "me depositaron",
                  "depositan menos", "7 días", "6 días", "difam", "groser", "hostig", "denunci", "ilegal")

SCHEMA_NOMBRES = {
    "type": "object",
    "properties": {"apps": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "nombre": {"type": "string", "description": "Nombre de la app TAL CUAL aparece en los datos"},
            "play_id": {"type": "string", "description": "Su id de Play Store si aparece en los datos (com.algo.app); "
                                                         "si no, vacío"},
            "donde": {"type": "array", "items": {"type": "string"}, "description": "Etiquetas donde aparece: [G3], [P2]…"},
        },
        "required": ["nombre", "play_id", "donde"], "additionalProperties": False}}},
    "required": ["apps"], "additionalProperties": False,
}

SCHEMA_APPS = {
    "type": "object",
    "properties": {
        "analisis": SCHEMA_IDEAS["properties"]["analisis"],
        "apps": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "nombre": {"type": "string", "description": "Igual que en [APP k]"},
                "titulo_video": {"type": "string", "description": "Título del video (máx. 70 caracteres). Tan fuerte "
                                                                  "como la evidencia lo permita"},
                "por_que": {"type": "string", "description": "Por qué esta app merece video ahora, en 1-2 frases"},
                "evidencia": {"type": "array", "items": {"type": "string"},
                              "description": "Datos reales citando etiquetas: '[APP 2] 48 de 160 reseñas hablan de "
                                             "amenazas', '[G5] Condusef la lista', '[A] la gente busca «… montadeudas»'"},
                "nivel_evidencia": {"type": "string", "enum": ["fuerte", "media", "debil"]},
                "gravedad": {"type": "integer", "description": "1-10: qué tan mala es (abusos, amenazas, fraude)"},
                "popularidad": {"type": "integer", "description": "1-10: cuánta gente la usa o la busca"},
                "puntaje": {"type": "integer", "description": "1-10: qué tan buen video sería según el criterio"},
                "inspiracion": {"type": "string", "description": "URL de un video que pega relacionado, o vacío"},
                "fuentes": {"type": "array", "items": {"type": "string"}, "description": "URLs de los datos"},
            },
            "required": ["nombre", "titulo_video", "por_que", "evidencia", "nivel_evidencia", "gravedad",
                         "popularidad", "puntaje", "inspiracion", "fuentes"],
            "additionalProperties": False}},
    },
    "required": ["analisis", "apps"], "additionalProperties": False,
}


def _norm(t: str) -> str:
    import re
    import unicodedata
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def _buscar_play(consultas: list[str]) -> list[dict]:
    from . import playstore
    salida, vistos = [], set()
    for q in consultas[:3]:
        try:
            for a in playstore.buscar(q, 20):
                if a.get("appId") and a["appId"] not in vistos:
                    vistos.add(a["appId"])
                    salida.append({"id": a["appId"], "titulo": a.get("title", ""), "score": a.get("score"),
                                   "instalaciones": a.get("installs", ""), "dev": a.get("developer", "")})
        except Exception as exc:  # noqa: BLE001 — Play Store falla seguido
            print(f"  · aviso Play Store ({q}): {exc}", flush=True)
    return salida


def _verificar(app: dict, play: list[dict]) -> dict:
    """Revisa UNA app: Play Store (¿sigue? descargas, estrellas, reseñas con quejas), Google y autocompletado."""
    import difflib
    import re

    from . import playstore

    nombre = app["nombre"].strip()
    d = {"nombre": nombre, "play_id": "", "ficha": None, "en_play": None, "revisadas": 0, "quejas": 0, "citas": [],
         "google": [], "sugerencias": [], "conteo": {}}
    pid = app.get("play_id") if re.fullmatch(r"[a-zA-Z][\w]*(\.[\w]+)+", app.get("play_id") or "") else ""
    if not pid:  # emparejar por nombre con lo que salió en Play Store ("Wudh" = "Wudh - Préstamo rápido")
        n = _norm(nombre)

        def parecido(titulo: str) -> float:
            t = _norm(titulo)
            if t == n or t.startswith(n + " "):
                return 1.0
            corte = " ".join(t.split()[:len(n.split())])  # mismas palabras iniciales
            return difflib.SequenceMatcher(None, n, corte).ratio()

        mejor = max(play, key=lambda a: parecido(a["titulo"]), default=None)
        if mejor is None or parecido(mejor["titulo"]) < 0.85:
            try:
                encontradas = _buscar_play([nombre])
                mejor = max(encontradas, key=lambda a: parecido(a["titulo"]), default=None)
            except Exception:  # noqa: BLE001
                mejor = None
        if mejor and parecido(mejor["titulo"]) >= 0.85:
            pid = mejor["id"]
    if pid:
        d["play_id"] = pid
        try:
            f = playstore.ficha(pid)
            d["ficha"] = {"titulo": f.get("title"), "instalaciones": f.get("installs"), "estrellas": f.get("score"),
                          "calificaciones": f.get("ratings"), "dev": f.get("developer"),
                          "actualizada": str(f.get("updated") or f.get("lastUpdatedOn") or "")[:16]}
            d["en_play"] = True
            res = playstore.resenas(pid, 100)
            d["revisadas"] = len(res)
            malas = [r for r in res if any(k in r["texto"].lower() for k in PALABRAS_QUEJA)]
            d["quejas"] = len(malas)
            d["citas"] = [f"«{r['texto'][:220]}{'…' if len(r['texto']) > 220 else ''}» ({r['estrellas']}⭐, {r['fecha']})"
                          for r in sorted(malas, key=lambda r: r["likes"], reverse=True)[:3]]
        except Exception:  # noqa: BLE001 — ya la quitaron de Play Store (o no se ve en México)
            d["en_play"] = False
    if buscar_web.disponible():
        try:
            res, conteo = buscar_web.buscar([f'"{nombre}" app préstamo amenazas OR extorsión OR montadeudas OR fraude'],
                                            por_consulta=6, max_texto=220, reciente="y")
            d["google"], d["conteo"] = res, conteo
        except Exception:  # noqa: BLE001
            pass
    sug = buscar_web.sugerencias([_norm(nombre), f"{_norm(nombre)} app"])
    d["sugerencias"] = sorted({x for donde in sug.values() for lista in donde.values() for x in lista})[:12]
    return d


def _texto_app(k: int, d: dict) -> str:
    l = [f"[APP {k}] {d['nombre']}"]
    if d["ficha"]:
        f = d["ficha"]
        l.append(f"   Play Store ({d['play_id']}): SIGUE PUBLICADA · {f['instalaciones']} descargas · "
                 f"⭐{f['estrellas'] or '?'} ({f['calificaciones'] or 0} calificaciones) · dev {f['dev']} · "
                 f"actualizada {f['actualizada']}")
        l.append(f"   Reseñas: revisé {d['revisadas']}; {d['quejas']} hablan de amenazas, cobros abusivos o fraude.")
        l += [f"      cita: {c}" for c in d["citas"]]
    elif d["en_play"] is False:
        l.append(f"   Play Store ({d['play_id']}): YA NO ESTÁ (la quitaron o no se ve en México)")
    else:
        l.append("   Play Store: no la encontré (puede ser APK o página web)")
    if d["google"]:
        l.append(f"   Google (último año, '{d['nombre']}' + amenazas/extorsión/montadeudas/fraude): {len(d['google'])} resultados")
        l += [f"      [G{k}.{i}] {g['titulo']} — {g['url']} — {g['texto'][:160]}" for i, g in enumerate(d["google"][:5], 1)]
    if d["sugerencias"]:
        l.append("   [A] La gente teclea: " + " | ".join(d["sugerencias"]))
    return "\n".join(l)


def _cazar_apps(instruccion: str, guia: str, cuantas: int, hechas: set, plan: dict, senales: dict,
                sistema: str) -> dict:
    from . import temas

    # 1) nombres: Google (listas, quejas, foros del último año) + Play Store
    if buscar_web.disponible() and plan["consultas_nombres"]:
        extra, conteo = buscar_web.buscar(plan["consultas_nombres"][:6], por_consulta=8, max_texto=300, reciente="y")
        _gastar(conteo, f"Google ({sum(conteo.values())} búsquedas para encontrar apps)")
        urls = {g["url"] for g in senales["google"]}
        senales["google"] = senales["google"] + [g for g in extra if g["url"] not in urls]
    play = _buscar_play(plan["consultas_play"] or plan["semillas"][:2])
    datos = _texto_senales(senales)
    if play:
        datos += "\n\n📱 PLAY STORE (búsqueda):\n" + "\n".join(
            f"[P{i}] {a['titulo']} ({a['id']}) — ⭐{a['score'] or '?'} · {a['instalaciones']} · {a['dev']}"
            for i, a in enumerate(play, 1))
    r = claude.json_estructurado(
        sistema, f"INSTRUCCIÓN DEL JEFE: {instruccion}\nLO QUE ENTENDISTE: {plan['entendi']}\n\n{datos}\n\n"
        "Saca las apps CONCRETAS (con nombre propio) que tienen que ver con lo que pide el jefe, hasta 12, las que más "
        "aparecen primero. Solo nombres que aparecen tal cual en los datos; nada de categorías ('apps de préstamo') "
        "ni de apps que no tienen que ver.",
        SCHEMA_NOMBRES, tarea="ideas", que="sacar nombres de apps")
    todo = _norm(datos)
    apps, vistos = [], set()
    for a in r["apps"]:
        n = _norm(a["nombre"])
        if n and n in todo and n not in vistos and a.get("play_id") not in hechas:
            vistos.add(n)
            apps.append(a)
    if not apps:
        raise RuntimeError("no salieron nombres de apps en las búsquedas")
    print(f"  · Paola encontró {len(apps)} apps: " + ", ".join(a["nombre"] for a in apps[:10]), flush=True)
    # 2) verificar cada una (en paralelo)
    with ThreadPoolExecutor(max_workers=4) as pool:
        fichas = list(pool.map(lambda a: _verificar(a, play), apps[:10]))
    conteo = {}
    for f in fichas:
        for k, v in f["conteo"].items():
            conteo[k] = conteo.get(k, 0) + v
    _gastar(conteo, f"Google ({sum(conteo.values())} búsquedas para verificar apps)")
    # 3) calificar y armar un video por app
    criterio = {"peores": "las PEORES primero (más abusos y quejas reales), y entre parecidas, la más usada o buscada",
                "mejores": "las MEJORES primero (pagan o cumplen, con evidencia)",
                "populares": "las más usadas o buscadas primero", "nuevas": "las más nuevas o que acaban de aparecer"}
    r = claude.json_estructurado(
        sistema, f"INSTRUCCIÓN DEL JEFE: {instruccion}\nCRITERIO: {criterio[plan['criterio']]}\n"
        + (f"\nGUSTOS Y REGLAS DEL JEFE:\n{guia}\n" if guia else "")
        + "\nAPPS VERIFICADAS:\n" + "\n\n".join(_texto_app(k, d) for k, d in enumerate(fichas, 1))
        + "\n\nCONTEXTO (lo que está pegando):\n" + _texto_senales({**senales, "google": []})[:9000]
        + "\n\nUn video por app. Para cada una: título, evidencia con números y etiquetas, gravedad, popularidad y "
          "puntaje según el criterio. Reglas del título según la evidencia (cuida al canal de una demanda):\n"
          "- fuerte (muchas reseñas con amenazas/abusos, o Condusef/autoridad/noticias la señalan): título directo, "
          "ej. «Nombre: así te extorsiona» o «Nombre es montadeudas: lo que nadie te dice».\n"
          "- media (algunas quejas reales): ej. «¿Nombre es montadeudas? Esto cuentan N usuarios».\n"
          "- débil (casi nada): márcala débil, no la recomiendes.\n"
          "Nunca afirmes algo que no esté en los datos. Ordena de mejor a peor video.",
        SCHEMA_APPS, tarea="ideas", que="calificar apps")
    por_nombre = {_norm(d["nombre"]): d for d in fichas}
    videos = {v["url"]: v for v in senales["videos"]}
    urls = {g["url"] for g in senales["google"]} | {n["url"] for n in senales["noticias"]} | set(videos) \
        | {g["url"] for d in fichas for g in d["google"]}
    elegidas = [a for a in r["apps"] if a["nivel_evidencia"] != "debil" and _norm(a["nombre"]) in por_nombre]
    elegidas.sort(key=lambda a: (a["puntaje"], a["gravedad"] if plan["criterio"] == "peores" else a["popularidad"]),
                  reverse=True)
    propuestas = []
    for k, a in enumerate(elegidas[:max(cuantas, 6)], 1):
        d = por_nombre[_norm(a["nombre"])]
        evidencia = "\n".join(f"• {e}" for e in a["evidencia"][:4])
        datos_play = (f"📱 {d['ficha']['instalaciones']} descargas · ⭐{d['ficha']['estrellas'] or '?'} · "
                      f"{d['quejas']} de {d['revisadas']} reseñas con quejas" if d["ficha"]
                      else "📱 Ya no está en Play Store" if d["en_play"] is False else "📱 Fuera de Play Store")
        base = {"angulo": a["titulo_video"][:90], "potencial_vistas": _potencial(a["puntaje"]), "personalizada": True,
                "idea_jefe": instruccion, "puntaje": a["puntaje"], "fuentes": [u for u in a["fuentes"] if u in urls][:4],
                "por_que": f"🎯 #{k} · {a['por_que']} (⭐ {a['puntaje']}/10 · gravedad {a['gravedad']}/10 · "
                           f"evidencia {a['nivel_evidencia']})\n{datos_play}" + (f"\n📊 {evidencia}" if evidencia else "")
                           + ("\n🗣️ " + "\n🗣️ ".join(d["citas"][:2]) if d["citas"] else "")}
        if a["inspiracion"] in videos:
            v = videos[a["inspiracion"]]
            base["inspiracion"] = {"url": v["url"], "titulo": v["titulo"], "multiplicador": v["multiplicador"]}
        if d["ficha"]:
            propuestas.append({**base, "app_id": d["play_id"], "titulo": d["ficha"]["titulo"] or d["nombre"]})
        else:
            propuestas.append({**base, "app_id": f"web:{temas._slug(d['nombre'], 50)}", "titulo": d["nombre"],
                               "fuera_de_play": True})
    an = r["analisis"]
    debiles = len(r["apps"]) - len(elegidas)
    analisis = (f"🎯 Revisé {len(fichas)} apps una por una (Play Store, reseñas, Google y lo que la gente teclea).\n"
                f"📈 Lo que pega: {an['que_pega']}\n🗣️ Lo que pide la gente: {an['que_pide_la_gente']}\n"
                f"🕳️ Huecos: {an['huecos']}" + (f"\n🗑️ Descarté {debiles} con poca evidencia." if debiles > 0 else ""))
    return {"entendi": plan["entendi"], "regla_permanente": plan["regla_permanente"].strip(), "analisis": analisis,
            "ideas": propuestas}
