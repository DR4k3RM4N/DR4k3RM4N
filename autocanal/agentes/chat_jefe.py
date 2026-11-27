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
    "• *publica el 3* / *publica todos* → Carla los sube (y los programa en la agenda)\n"
    "• *reintenta los que fallaron* · *descarta el 4* · *prende el piloto* / *apaga el piloto*\n"
    "• pega el *enlace de un video* (YouTube, TikTok, Instagram…) → te digo de qué trata y por qué funciona; "
    "puedes agregar una pregunta, ej. *¿qué gancho usa?* (de YouTube veo miniatura, título, descripción y comentarios)\n"
    "• en la oficina, súbeme el *archivo del video* con el 📎 → lo veo completo: transcripción e imágenes\n"
    "• *graba la app Cash Gato* (o *ya la tengo instalada, grábala*) → el robot la abre en tu cel, la usa, la graba, "
    "le pica a los anuncios de apps de dinero (van a tu lista de deseos) y el equipo arma el video"
)

SYSTEM = """Eres Paola, la productora de la oficina que hace los videos de YouTube de Miguel (tu jefe): el canal de
apps que prometen pagar y sus otros canales (p. ej. «Cuida Tu Lana», de fraudes). Te escribe por chat. Conviertes su
mensaje en acciones para el equipo y le contestas. Eres lista: usa la PLÁTICA RECIENTE para entender mensajes cortos
o correcciones («no, pero cuida tu lana», «esos», «el de ayer») y la lista de VIDEOS (con canal, estado y fecha) para
saber a cuáles se refiere («los últimos 3 de Cuida Tu Lana» = los 3 primeros de ese canal en la lista, que ya viene
de más nuevo a más viejo). No le preguntes lo que puedes deducir; pregunta solo si de verdad es ambiguo.

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
- "miniaturas" = quiere que Carla vuelva a poner en YouTube las miniaturas de los videos ya subidos que no la
  tienen (todos los canales). Si nombra un solo video, pon su número en "numero"; si no, 0.
- "publicar" = subir a YouTube un video que espera revisión (número del video en "numero"; 0 = TODOS los que
  esperan revisión). En "texto" pon "public", "unlisted" o "private" si lo dijo; si no, vacío (público con agenda).
- "reintentar" = volver a intentar un video con problema (número; 0 = todos los que tienen problema).
- "descartar" = tirar un video en revisión o con problema (número obligatorio).
- "piloto" = prender o apagar el piloto automático: "texto" = "on" u "off".
- "grabar_app" = el jefe quiere que el robot use y GRABE una app en su celular conectado ("graba esta app",
  "prueba X en el cel", "ya la tengo instalada, grábala"). En "texto" el nombre de la app tal cual lo dijo; en
  "numero" pon 1 si dijo que YA la tiene instalada o abierta en el cel, 0 si no. En "canal" el id si lo pidió para
  un canal (ej. una app de préstamos para el canal de fraudes); vacío si no.
- "reeditar" = volver a EDITAR video(s) (aunque ya estén publicados) con lo que ya tienen (guion y voz iguales),
  p. ej. para el estilo nuevo de edición. "rehacer" = rehacerlo desde el guion (guion, voz y edición nuevos).
  Pon los números en "numeros" y lo que quiere cambiar (si dijo) en "texto". Si ya estaba publicado, el video nuevo
  se sube solo con la misma fecha programada. "reemplazar" = true si pidió borrar o reemplazar el anterior en
  YouTube (se borra hasta que el nuevo ya subió); false si dijo que él los borra o no dijo nada.
- "borrar_youtube" = BORRAR de YouTube video(s) ya subidos (números en "numeros"). Solo si lo pidió claramente
  («borra», «elimina», «bájalo de YouTube»); nunca lo deduzcas. Es para siempre.
- "quitar_deseos" = quitar apps de la ⭐ lista de deseos: pon en "numeros" los números de la LISTA DE DESEOS que
  cumplen lo que pidió (p. ej. todas las de apuestas o casino). Si además dice «no vuelvas a…», agrega un "corregir".
- Para acciones sobre varios videos usa "numeros" (lista); "numero" queda para una sola idea o video.
- MUY IMPORTANTE: solo puedes hacer las acciones de esta lista. Si pide algo que no está aquí (hacer shorts,
  cambiar descripciones en YouTube, etc.), NO digas que lo vas a hacer: dile con honestidad que eso todavía no lo
  hace el equipo. Nunca inventes resultados ni cifras. Nunca digas «pídeselo a quien programa la oficina».
- Si solo saluda o platica, contesta breve y amable, sin acciones.
- "respuesta": 1 o 2 frases en español de México, cálida y directa, como compañera de trabajo. Di qué vas a
  hacer con nombres concretos (qué videos), no generalidades."""

SCHEMA = {
    "type": "object",
    "properties": {
        "respuesta": {"type": "string"},
        "acciones": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "tipo": {"type": "string", "enum": ["aprobar", "rechazar", "comentar", "pedir_ideas", "estado",
                                                     "pendientes", "corregir", "cambios", "miniaturas",
                                                     "publicar", "reintentar", "descartar", "piloto", "grabar_app",
                                                     "reeditar", "rehacer", "borrar_youtube", "quitar_deseos"]},
                "numero": {"type": "integer", "description": "Número de la idea o del video; 0 si no aplica"},
                "numeros": {"type": "array", "items": {"type": "integer"}, "description": "Varios videos (o deseos); [] si no aplica"},
                "reemplazar": {"type": "boolean", "description": "reeditar/rehacer: borrar el anterior de YouTube al subir el nuevo"},
                "texto": {"type": "string"},
                "agente": {"type": "string", "enum": ["", "productora", "investigador", "guionista", "locutor",
                                                      "disenadora", "editor", "redactora", "community", "todos"]},
                "canal": {"type": "string", "description": "id del canal si aplica solo a uno; vacío si no"},
            },
            "required": ["tipo", "numero", "numeros", "reemplazar", "texto", "agente", "canal"],
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


def interpretar(texto: str, ideas: list[dict], proyectos: list[dict], canales: list[dict] | None = None,
                platica: list[dict] | None = None, deseos: list[dict] | None = None) -> dict:
    r = rapido(texto)
    if r is not None:
        return r
    nombres = {c["id"]: c.get("nombre") for c in canales or []}
    import datetime as dt

    def fecha(p: dict) -> str:
        t = p.get("publicado_t") or p.get("creado") or 0
        return dt.datetime.fromtimestamp(t).strftime("%d/%m %H:%M") if t else ""

    contexto = {
        "ideas_pendientes": [{"numero": p.get("num", i), "titulo": p["titulo"], "video": p.get("angulo", "")} for i, p in enumerate(ideas, 1)],
        "videos (del más nuevo al más viejo)": [
            {"numero": i, "titulo": p["titulo"], "estado": p["estado"], "canal": nombres.get(p.get("canal") or "principal", p.get("canal") or "principal"),
             "fecha": fecha(p), "en_youtube": bool((p.get("publicado") or {}).get("youtube"))}
            for i, p in enumerate(proyectos[:40], 1)],
        "canales": [{"id": c["id"], "nombre": c.get("nombre")} for c in canales or []],
        "lista_de_deseos": [{"numero": i, "app": d.get("nombre")} for i, d in enumerate(deseos or [], 1)],
    }
    previa = "\n".join(f"{'Miguel' if m.get('quien') == 'jefe' else 'Paola'}: {m.get('texto', '')[:300]}" for m in (platica or [])[-10:])
    return claude.json_estructurado(
        SYSTEM, f"CONTEXTO:\n{json.dumps(contexto, ensure_ascii=False)}\n\nPLÁTICA RECIENTE:\n{previa or '(ninguna)'}"
        f"\n\nMENSAJE NUEVO DEL JEFE:\n{texto[:1500]}", SCHEMA, tarea="whatsapp")
