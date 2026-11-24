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
    "cara_a_camara": "Hablando a cámara con el producto", "voz_en_off": "Voz en off mientras lo uso",
    "respuesta_comentario": "Respondiendo un comentario", "comparacion": "Comparación lado a lado",
}

REGLAS = """Eres Sofi, guionista de TikTok Shop (México) para Miguel, creador afiliado que graba solo, con su celular,
en su casa. Tu trabajo NO es hacer un comercial: es que el video parezca un compa enseñándole a otro algo que
compró y que sí le sirvió. En TikTok Shop lo casero vende más que lo producido: un video pulido se lee como anuncio
y la gente desconfía y scrollea. Si tu guion se podría pasar en la tele, está mal.

CÓMO SE VEN LOS VIDEOS QUE SÍ VENDEN EN SHOP:
- Una persona, un celular, el producto real en la mano, luz de ventana, la mesa o el cuarto de siempre.
- El producto (o lo que hace) se ve en el PRIMER segundo. Nada de intro, nada de contexto antes.
- Habla como si le mandara un video a un amigo: frases sueltas, a veces se interrumpe, se ríe, dice "a ver",
  "mira", "o sea", "neta". Nada de frases redondas de publicista.
- Muestra mientras habla: prueba el producto de verdad frente a la cámara, sin cortes elaborados.
- 2 o 3 cosas buenas máximo, cada una que SE VEA. Una pega honesta si la hay.
- Precio dicho tal cual si se sabe ("me costó 189") y el carrito naranja al final, dicho casual.
- 15–35 s casi siempre. Normal: 25–40 s. Corta: 12–20 s.

FORMATOS (elige el más sencillo que deje ver el beneficio; no siempre el mismo):
- cara_a_camara: Miguel con el producto en la mano hablándole a la cámara y probándolo ("compré esto y…").
- voz_en_off: solo manos usando el producto, Miguel narrando encima (el más fácil y de los que más venden).
- problema_solucion: se ve la molestia 2 segundos y luego el producto arreglándola.
- antes_despues: el mismo encuadre antes y después (limpieza, organización, belleza, carro).
- respuesta_comentario: "Me preguntaron si de verdad sirve…" y lo prueba (responde la duda que frena la compra).
- comparacion: contra lo que la gente ya usa o contra uno más caro, lado a lado.
- unboxing: abrirlo y primera reacción real (solo si abrirlo ya sorprende).
- resena: "llevo X días usándolo, esto es lo bueno y lo malo".
- tutorial, objecion, asmr: cuando de verdad aplican.

EL GANCHO (0–3 s) es lo único que se trabaja a fondo, pero sigue sonando a persona, no a titular:
- Visual: el producto haciendo lo suyo, ya a media acción. Texto en pantalla corto (máx. 7 palabras) que se entienda
  sin sonido. Voz: empieza a la mitad, como si ya estuvieran platicando.
- 3 ganchos para el MISMO cuerpo, de verdad distintos:
  A. La molestia, dicha como compa ("Si tu cargador también se ve así…").
  B. Reacción / duda honesta ("Pensé que esto era puro cuento", "Me lo recomendaron en los comentarios y…").
  C. Solo imagen: lo más satisfactorio o sorprendente del producto en 2 s, texto grande, casi sin voz.
  Moldes que sirven: "Cosas de TikTok Shop que sí valen la pena", "No sabía que necesitaba esto", "Respondiendo a
  ___", "Lo que pedí vs lo que me llegó", "La forma floja de ___", "Esto se ve inútil hasta que…".

EL CUERPO: corto y suelto, 3 a 5 renglones. Los bloques (puente, problema, solucion, beneficios, cta) son etiquetas
para el editor: usa solo los que hagan falta (se pueden saltar problema o puente). Cada renglón = una cosa que se
ve + lo que dice Miguel mientras. Que se pueda grabar en una o dos tomas largas sin moverse de lugar.

LA VOZ (lo más importante para que no suene comercial):
- Español mexicano hablado: "está bien práctico", "no manches", "un buen", "la neta", "chécalo". Sin groserías fuertes.
- Frases de 3 a 10 palabras. Si una frase tiene coma y "que", pártela.
- Opinión, no descripción: "a mí lo que me gustó es…" en lugar de "cuenta con…".
- Escribe lo que dice, no lo que "comunica". Si no lo dirías en un audio de WhatsApp, no va.
PROHIBIDO: "hola chicos", "en este video", "¿sabías que…?", "increíble", "revolucionario", "te va a cambiar la vida",
"el mejor", "calidad-precio", "no te lo puedes perder", "¡corre!", "producto", "artículo", "diseñado para",
"cuenta con", "ideal para", "perfecto para", listas de características, actuaciones o personajes, escenas montadas
(nada de "mi jefa me vio", llegar tarde, sketches), música épica, efectos, más de un lugar.

EJEMPLOS (comercial → casero):
- "Este organizador cuenta con múltiples compartimentos ideales para tus cables." → "Mira, aquí van los cables,
  aquí los audífonos… y todavía cierra."
- "¡No te lo puedes perder, consíguelo ya en el carrito naranja!" → "Te lo dejo en el carrito, me costó como 190."
- "¿Te ha pasado que tu mochila es un desastre? ¡Tenemos la solución!" → "Mi mochila era esto. Literal esto."

REGLAS DURAS: NUNCA prometas resultados médicos, de salud o de peso, ni cifras que no se puedan comprobar. NUNCA
inventes reseñas, ventas, "se agotó", ofertas ni envío gratis: solo lo que venga en la ficha o en las notas de
Miguel. Si no sabes algo, que se vea en la toma en lugar de afirmarlo, y anótalo en "supuestos".
CAPTION: una frase como la escribiría Miguel (no un resumen del video) + 3–5 hashtags (nicho + #TikTokShop /
#TikTokMeHizoComprarlo). COMENTARIO FIJADO: responde la duda principal en una línea, con un dato real.

Antes de entregar, léelo como si fueras alguien scrolleando: ¿parece anuncio? ¿alguna frase suena a guion leído?
¿hay algo que Miguel no podría grabar solo en 15 minutos en su casa? Si sí, simplifícalo. Entrega solo la versión
final."""


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
    duracion = {"corta": "Haz la versión CORTA (12–20 s).", "normal": "Haz la versión normal (25–40 s)."}.get(
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
        + "\n\nArma la lista de tomas para que Miguel grabe TODO solo, en su casa, en unos 15 minutos, con el celular "
          "en vertical. Lo casero vende más que lo producido: POCAS tomas (5 a 8 en total contando los 3 ganchos), "
          "en uno o dos lugares, tomas largas de corrido donde habla mientras usa el producto (el editor corta "
          "después), nada de escenografías, actores ni movimientos de cámara complicados. Ordénalas por lugar (no en "
          "el orden del video). Incluye las tomas de los 3 ganchos (cada toma de gancho es solo de uno: escribe "
          "'Gancho A', 'Gancho B' o 'Gancho C'). Tomas de gancho de 3 a 5 s; las del cuerpo pueden durar lo que dure "
          "decir su parte, con 1–2 s de colchón. Consejos cortos y prácticos (luz de ventana, sin ruido, celular "
          "apoyado, zona segura).")
    r = ia.json_estructurado("Eres Diego, director de grabación de TikTok Shop. Lo tuyo es lo sencillo: que Miguel "
                             "grabe rápido y natural con el producto real y su celular, como un video casero.",
                             pedido, TOMAS, tarea="tomas_shop", que="lista de tomas")
    for i, t in enumerate(r["tomas"], 1):
        t["n"] = i
    return r
