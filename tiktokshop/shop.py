"""El trabajo del equipo de TikTok Shop: Toño (ficha del producto), Sofi (guion) y Diego (lista de tomas).

Las reglas del guion son las de la skill "guion-tiktok-shop" de Miguel. Sofi escribe con Claude Opus; lo demás con Haiku
y búsquedas en Google con Serper/Tavily (las mismas claves de la oficina de YouTube).
Nada inventado: Toño solo guarda datos y opiniones que salieron en la búsqueda, con su enlace.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import unicodedata

from agentes import buscar_web
from agentes import claude as ia

FORMATOS = {
    "problema_solucion": "Problema → solución (demo)", "antes_despues": "Antes y después",
    "resena": "Reseña personal / lo uso diario", "unboxing": "Unboxing + primer uso",
    "tutorial": "Tutorial / cómo se usa", "objecion": "Objeción / FAQ", "asmr": "ASMR / satisfactorio",
}

REGLAS = """Eres Sofi, guionista de videos de TikTok Shop (México) para Miguel, creador afiliado. Escribes como alguien
que lleva miles de videos vendidos: sabes que un video de Shop gana cuando alguien deja de scrollear, se queda hasta
el final y piensa "ah, cabrón, eso me sirve" antes de picarle al carrito naranja. Nada de comercial de tele.

LO QUE HACE QUE UN GUION NO SEA PLANO (esto es lo más importante):
1. UNA ESCENA, NO UNA LISTA. Cuenta un momento concreto con una persona real: "son las 7:40, voy tarde y no
   encuentro el cargador", "mi jefa me vio usándolo y me lo quiso quitar". Lugar, hora, quién, qué pasó. Lo genérico
   ("¿te ha pasado que…?") aburre; lo específico engancha.
2. DETALLES QUE SE SIENTEN: números, texturas, sonidos, tiempos ("en 4 segundos", "hace clic", "pesa lo que un
   celular", "le cupieron 3 cargadores y los audífonos"). Solo datos de la ficha o de lo que se ve en la toma.
3. UNA PREGUNTA ABIERTA QUE SE CIERRA TARDE: el gancho promete algo (un resultado, una sorpresa, un "no me lo
   esperaba") y el cuerpo lo paga DESPUÉS de la mitad, no antes. Así se quedan.
4. REENGANCHE A MEDIO VIDEO (entre el segundo 10 y 18): un giro ("pero lo que me convenció fue esto…", "y aquí
   viene lo bueno", "esperen, falta lo mejor"), un cambio de lugar o un close-up sorpresa. Los videos de Shop se
   caen justo ahí.
5. SE ESCUCHA HABLADO, NO ESCRITO. Léelo en voz alta en tu cabeza: frases de 4 a 10 palabras, con muletillas
   naturales mexicanas ("neta", "o sea", "está bien práctico", "no manches", "un buen"), sin albur ni groserías
   fuertes. Si suena a anuncio, reescríbelo. Mejor que Miguel diga algo a medias y siga mostrando, que un párrafo.
6. MOSTRAR > DECIR. Cada línea de voz debe ir con algo que se ve pasando en ese momento. Si el beneficio no se ve,
   búscale la prueba: lado a lado, cronómetro, "lo dejé caer", "le eché agua", reacción de alguien de la casa.
7. HONESTIDAD QUE VENDE: una pega pequeña y real o el momento en que dudaste ("pensé que se iba a romper a la
   semana"). Da más confianza que diez halagos.
8. CADA SEGUNDO SE GANA SU LUGAR: si una línea se puede quitar y el video se entiende igual, quítala.

PROHIBIDO (suena plano o a anuncio): "hola chicos", "en este video", "¿sabías que…?", "increíble", "revolucionario",
"te va a cambiar la vida", "el mejor producto", "calidad-precio" a secas, "no te lo puedes perder", listas de
características, adjetivos sin prueba, empezar presentándose, explicar qué es el producto antes de enseñarlo.

EJEMPLOS (plano → con vida):
- "Este organizador es muy práctico y tiene muchos compartimentos." → "Mira, le cupieron tres cargadores, los
  audífonos y todavía cerró. Yo no le tenía fe."
- "Si tienes problemas de desorden, este producto es para ti." → "Así estaba mi mochila ayer. Saqué el cargador y
  salieron los audífonos colgando de él."
- "Cómpralo en el carrito naranja." → "Está en el carrito naranja aquí abajo; yo ya pedí otro para mi carro."

FORMATO (elige el que mejor deje VER el beneficio, y no siempre el mismo): problema_solucion, antes_despues
(limpieza, belleza, organización, carro, casa), resena ("llevo 2 semanas usándolo", recomendación a un compa),
unboxing (cuando abrirlo ya sorprende), tutorial (cuando la gente pregunta "¿y eso cómo funciona?"), objecion
(responde la duda que frena la compra), asmr (productos con sonido o textura). Puedes mezclar (reseña con antes y
después, POV, "probé X para que tú no", "cosas que mi mamá no sabía que necesitaba").

ESTRUCTURA (guía, no plantilla rígida). Normal 30–50 s; corta 15–25 s si es barato o de compra por impulso:
- 0–3 s GANCHO: el producto o el resultado ya se ve en el primer segundo. Tres capas a la vez: visual (acción a
  media marcha, algo raro o satisfactorio), texto en pantalla (específico, máx. 7 palabras, que funcione sin sonido)
  y voz (empieza a media acción). Debe sonar como persona, no como titular.
- PUENTE (corto): por qué quedarse. El producto ya en mano.
- PROBLEMA: la molestia exacta, que se vea. Puede ir muy corto o incluso dentro del gancho.
- SOLUCIÓN / DEMO: el momento "ah, qué chido", en close-up. Aquí va el reenganche. Se entiende qué hace antes del 25.
- BENEFICIOS: 2–3, cada uno con su prueba visible y "como hace X, te queda Y". Prueba social solo si está en la
  ficha (copiada tal cual).
- CTA: natural, señalando abajo a la izquierda, con una razón ("yo ya pedí otro", "para que no te pase lo de la
  mochila"). Urgencia (oferta, envío gratis, stock) SOLO si es real y viene en la ficha o en las notas.
Las etiquetas de bloque son para el editor: los tiempos se acomodan a la historia. Cambio de toma cada 1.5–3 s.
Texto en pantalla corto, en zona segura (no arriba 15 %, no abajo 20 %, no a la derecha 15 %).

GANCHOS: 3 variantes que se pegan al MISMO cuerpo, y que de verdad sean distintas (otra emoción, otra imagen,
otra promesa), no la misma frase con otras palabras:
- A. Dolor / advertencia, dicho como compa ("Si tu mochila se ve así, no la vuelvas a abrir en público").
- B. Curiosidad / incredulidad / historia ("Mi hermana se burló de esto y ahora me lo pidió prestado").
- C. Visual / demo muda: el resultado más impactante en los primeros 2 s, texto grande, casi sin voz.
En "tipo" pon el molde que usaste. Moldes que funcionan: "No compres ___, compra esto", "Lo que pedí vs lo que
llegó", "Cosas que ojalá hubiera comprado antes", "La forma floja de ___", "Probé ___ para que tú no", "POV: ___",
"Mi ___ me preguntó dónde lo compré", "Esto se ve inútil hasta que…".

REGLAS DURAS: NUNCA prometas resultados médicos, de salud o de peso, ni cifras que no se puedan comprobar. NUNCA
inventes reseñas, ventas, "se agotó" ni descuentos: usa solo lo que trae la ficha o las notas de Miguel. Si no
sabes algo del producto, que se vea en la toma en lugar de afirmarlo, y anótalo en "supuestos".
Miguel graba él mismo con su celular (manos, producto, a veces su cara y su voz), en su casa o en lugares normales,
con el producto real: nada de actores, efectos ni lugares imposibles.
CAPTION corto, con la misma voz del video (no un resumen) + 3–5 hashtags (nicho + #TikTokShop /
#TikTokMeHizoComprarlo). COMENTARIO FIJADO que responda la duda principal como lo haría Miguel, con un dato real.

Antes de entregar, revisa tu guion como editor exigente: ¿el gancho para el scroll sin sonido? ¿hay escena y
detalles concretos? ¿hay reenganche? ¿alguna línea suena a anuncio o se puede quitar? Corrige y entrega solo la
versión final."""


def slug(texto: str, largo: int = 40) -> str:
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:largo].strip("-") or "producto"


def _texto_producto(p: dict) -> str:
    partes = [f"Producto: {p['nombre']}"]
    if p.get("enlace"):
        partes.append(f"Enlace en TikTok Shop: {p['enlace']}")
    if p.get("precio"):
        partes.append(f"Precio que dio Miguel: ${p['precio']} MXN")
    if p.get("comision"):
        partes.append(f"Comisión: {p['comision']} %")
    if p.get("notas"):
        partes.append(f"Notas de Miguel: {p['notas']}")
    partes.append("Se lo mandó una marca (es contenido de marca)." if p.get("de_marca") else "Lo compró/eligió Miguel.")
    return "\n".join(partes)


# ---------- Toño: ficha del producto ----------
FICHA = {
    "type": "object", "additionalProperties": False,
    "required": ["resumen", "problema", "publico", "objecion", "precio", "datos", "opiniones", "cuidado"],
    "properties": {
        "resumen": {"type": "string", "description": "qué es, en una línea"},
        "problema": {"type": "string", "description": "el problema de todos los días que resuelve"},
        "publico": {"type": "string", "description": "quién lo compra"},
        "objecion": {"type": "string", "description": "la duda más probable que frena la compra"},
        "precio": {"type": "string", "description": "precio en pesos SOLO si sale en los resultados o lo dio Miguel; si no, vacío"},
        "datos": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["dato", "url"],
                  "properties": {"dato": {"type": "string"}, "url": {"type": "string"}}}},
        "opiniones": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["texto", "url"],
                      "properties": {"texto": {"type": "string", "description": "copiado TAL CUAL del resultado"},
                                     "url": {"type": "string"}}}},
        "cuidado": {"type": "string", "description": "algo que NO se debe prometer (salud, peso, cifras), o vacío"},
    },
}


def _limpio(t: str) -> str:
    return re.sub(r"\s+", " ", t or "").strip().lower()


def ficha(p: dict) -> dict:
    """Busca el producto en Google y arma la ficha. Solo se quedan datos con un enlace que sí salió."""
    resultados = []
    if buscar_web.disponible():
        n = p["nombre"]
        resultados, conteo = buscar_web.buscar([f"{n} opiniones", f"{n} precio México", f"{n} TikTok Shop reseña"],
                                               por_consulta=5, max_texto=500)
        gasto = buscar_web.costo(conteo)
        if ia.al_gastar and gasto:
            ia.al_gastar(getattr(ia.contexto, "proyecto", None), "ficha", "búsqueda", gasto, 0, 0, "búsquedas en Google")
    lista = "\n".join(f"[{i}] {r['titulo']} — {r['url']}\n{r['texto']}" for i, r in enumerate(resultados[:15], 1))
    pedido = (_texto_producto(p) + "\n\nResultados de Google:\n" + (lista or "(no hay búsqueda disponible: usa solo "
              "lo que dio Miguel y deja datos y opiniones vacíos)") +
              "\n\nArma la ficha. 'datos' y 'opiniones' SOLO con lo que diga un resultado, con su URL exacta. "
              "Las opiniones van copiadas tal cual (un pedazo del texto del resultado). Problema, público y objeción "
              "los puedes deducir.")
    r = ia.json_estructurado("Eres Toño, cazador de productos de TikTok Shop México. Preciso y sin inventar.",
                             pedido, FICHA, tarea="ficha_shop", que="ficha del producto")
    urls = {r_["url"] for r_ in resultados}
    textos = {r_["url"]: _limpio(r_["titulo"] + " " + r_["texto"]) for r_ in resultados}
    r["datos"] = [d for d in r["datos"] if d["url"] in urls][:6]
    r["opiniones"] = [o for o in r["opiniones"]
                      if o["url"] in urls and _limpio(o["texto"]).strip('"“”…. ') in textos[o["url"]]][:4]
    if not p.get("precio") and r["precio"] and not any(re.search(r"\$|mxn|pesos", textos[u]) for u in urls):
        r["precio"] = ""  # sin fuente, no hay precio
    r["fuentes"] = len(resultados)
    return r


# ---------- Sofi: guion ----------
_ESCENA = {"toma": {"type": "string", "description": "qué se ve (acción concreta con el producto)"},
           "texto_pantalla": {"type": "string", "description": "texto corto en pantalla"},
           "voz": {"type": "string", "description": "lo que dice Miguel (vacío si es demo muda)"}}
GUION = {
    "type": "object", "additionalProperties": False,
    "required": ["formato", "angulo", "duracion", "supuestos", "ganchos", "cuerpo", "caption", "hashtags",
                 "comentario_fijado", "mejoraria"],
    "properties": {
        "formato": {"type": "string", "enum": list(FORMATOS)},
        "angulo": {"type": "string", "description": "una línea: formato elegido y por qué"},
        "duracion": {"type": "string", "enum": ["normal", "corta"]},
        "supuestos": {"type": "string", "description": "lo que asumiste del producto, en una línea (o vacío)"},
        "ganchos": {"type": "array", "description": "exactamente 3: A advertencia, B curiosidad, C demo muda",
                    "items": {"type": "object", "additionalProperties": False, "required": ["letra", "tipo", *_ESCENA],
                              "properties": {"letra": {"type": "string", "enum": ["A", "B", "C"]},
                                             "tipo": {"type": "string"}, **_ESCENA}}},
        "cuerpo": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["tiempo", "bloque", *_ESCENA],
            "properties": {"tiempo": {"type": "string", "description": "ej. 3–8 s"},
                           "bloque": {"type": "string", "enum": ["puente", "problema", "solucion", "beneficios", "cta"]},
                           **_ESCENA}}},
        "caption": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
        "comentario_fijado": {"type": "string"},
        "mejoraria": {"type": "string", "description": "qué dato del producto mejoraría la siguiente versión"},
    },
}


def guion(p: dict, f: dict, aprendido: str = "") -> dict:
    duracion = {"corta": "Haz la versión CORTA (15–25 s).", "normal": "Haz la versión normal (35–50 s)."}.get(
        p.get("duracion"), "Elige tú la duración: corta si es barato o de impulso, normal si necesita demo.")
    pedido = (_texto_producto(p) + "\n\nFicha de Toño (lo único que puedes afirmar como hecho):\n"
              + json.dumps({k: f.get(k) for k in ("resumen", "problema", "publico", "objecion", "precio", "datos",
                                                   "opiniones", "cuidado")}, ensure_ascii=False)
              + (f"\n\nLo que ya aprendimos de videos anteriores de Miguel:\n{aprendido}" if aprendido else "")
              + f"\n\n{duracion}\nEscribe el guion: 3 ganchos A/B/C (en ese orden) que se pegan al mismo cuerpo.")
    r = ia.json_estructurado(REGLAS, pedido, GUION, tarea="guion_shop", que="guion con 3 ganchos")
    orden = {"A": 0, "B": 1, "C": 2}
    r["ganchos"] = sorted(r["ganchos"], key=lambda g: orden.get(g["letra"], 9))[:3]
    if len(r["ganchos"]) < 3 or not r["cuerpo"]:
        raise ia.ErrorIA("El guion salió incompleto (faltan ganchos o cuerpo). Dale Rehacer.")
    r["hashtags"] = [h if h.startswith("#") else f"#{h}" for h in r["hashtags"]][:5]
    hoy = dt.date.today().isoformat()
    r["id"] = f"{hoy}_{slug(p['nombre'], 30)}_{r['formato']}"
    return r


AJUSTE = {"type": "object", "additionalProperties": False, "required": ["respuesta", "guion"],
          "properties": {"respuesta": {"type": "string", "description": "a Miguel, 1-2 frases: qué cambiaste"},
                         "guion": GUION}}


def ajustar_guion(p: dict, g: dict, f: dict, pedido: str, cual: str, reglas: list[str] | None = None,
                  historial: list[dict] | None = None) -> dict:
    """💬 Miguel pide un cambio: Sofi toca SOLO lo que pidió. cual = "todo" o la letra del gancho (A/B/C)."""
    actual = {k: g.get(k) for k in GUION["properties"]}
    alcance = ("Cambia SOLO el gancho " + cual + ". Los otros ganchos, el cuerpo, caption, hashtags y comentario "
               "déjalos EXACTAMENTE iguales." if cual in ("A", "B", "C") else
               "Aplica el cambio en todo el guion donde haga falta (los 3 ganchos, el cuerpo, caption…), pero lo que "
               "no tenga que ver con el pedido déjalo igual.")
    texto = (_texto_producto(p) + "\n\nFicha de Toño (lo único que puedes afirmar como hecho):\n"
             + json.dumps({k: f.get(k) for k in ("resumen", "problema", "publico", "objecion", "precio", "datos",
                                                  "opiniones", "cuidado")}, ensure_ascii=False)
             + (("\n\nReglas que Miguel ya te pidió para todos sus guiones:\n- " + "\n- ".join(reglas)) if reglas else "")
             + (("\n\nLo que ya platicaron de este guion:\n" + "\n".join(
                 f"- {'Miguel' if h['quien'] == 'jefe' else 'Sofi'}: {h['texto']}" for h in historial[-8:])) if historial else "")
             + "\n\nGUION ACTUAL:\n" + json.dumps(actual, ensure_ascii=False)
             + f"\n\nMIGUEL PIDE: {pedido}\n\n{alcance} Si pide quitar algo que no quiere hacer (una toma, una "
               "acción, un lugar), reemplázalo por otra cosa que él sí pueda grabar y que siga vendiendo. Devuelve el "
               "guion COMPLETO ya corregido (3 ganchos A/B/C y todo el cuerpo).")
    r = ia.json_estructurado(REGLAS, texto, AJUSTE, tarea="guion_shop", que=f"ajustar guion ({cual})")
    nuevo = r["guion"]
    orden = {"A": 0, "B": 1, "C": 2}
    nuevo["ganchos"] = sorted(nuevo.get("ganchos") or [], key=lambda x: orden.get(x["letra"], 9))[:3]
    if cual in ("A", "B", "C"):  # aunque Claude se pase, solo cambia el gancho elegido
        nuevo_g = next((x for x in nuevo["ganchos"] if x["letra"] == cual), None)
        if not nuevo_g:
            raise ia.ErrorIA("Sofi no regresó el gancho. Vuelve a pedirlo.")
        final = dict(g)
        final["ganchos"] = [nuevo_g if x["letra"] == cual else x for x in g["ganchos"]]
    else:
        if len(nuevo["ganchos"]) < 3 or not nuevo.get("cuerpo"):
            raise ia.ErrorIA("El guion salió incompleto. Vuelve a pedirlo.")
        nuevo["hashtags"] = [h if h.startswith("#") else f"#{h}" for h in nuevo["hashtags"]][:5]
        final = {**g, **nuevo, "id": g.get("id") or nuevo.get("id")}
    return {"respuesta": r["respuesta"], "guion": final}


# ---------- Diego: lista de tomas ----------
TOMAS = {
    "type": "object", "additionalProperties": False, "required": ["material", "tomas", "consejos"],
    "properties": {
        "material": {"type": "array", "items": {"type": "string"}, "description": "qué tener a la mano antes de grabar"},
        "tomas": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["lugar", "que_grabar", "encuadre", "segundos", "para", "tip"],
            "properties": {"lugar": {"type": "string", "description": "dónde (mesa, cocina, coche…)"},
                           "que_grabar": {"type": "string"},
                           "encuadre": {"type": "string", "description": "close-up de manos, plano medio, desde arriba…"},
                           "segundos": {"type": "number", "description": "cuánto grabar (deja 1–2 s de colchón)"},
                           "para": {"type": "string", "description": "a qué parte va: exactamente 'Gancho A', 'Gancho B' o 'Gancho C' si es de un gancho; si no, Puente, Problema, Solución, Beneficios o Carrito naranja"},
                           "tip": {"type": "string"}}}},
        "consejos": {"type": "array", "items": {"type": "string"}},
    },
}


def tomas(p: dict, g: dict) -> dict:
    pedido = (f"Producto: {p['nombre']}\nGuion de Sofi:\n" + json.dumps(
        {"ganchos": g["ganchos"], "cuerpo": g["cuerpo"]}, ensure_ascii=False)
        + "\n\nArma la lista de tomas para que Miguel grabe TODO en una sola sesión con su celular en vertical. "
          "Ordénalas por lugar para no mover las cosas dos veces (no en el orden del video). Incluye las tomas de "
          "los 3 ganchos (cada toma de gancho es solo de uno: escribe 'Gancho A', 'Gancho B' o 'Gancho C'). Cada toma de 2 a 6 s, con 1–2 s de colchón. Consejos cortos de luz, sonido y zona segura.")
    r = ia.json_estructurado("Eres Diego, director de grabación. Práctico: tomas que se hacen en casa con el producto "
                             "real y un celular.", pedido, TOMAS, tarea="tomas_shop", que="lista de tomas")
    for i, t in enumerate(r["tomas"], 1):
        t["n"] = i
    return r
