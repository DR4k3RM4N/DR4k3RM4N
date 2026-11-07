"""El trabajo del equipo de TikTok Shop: Toño (ficha del producto), Sofi (guion) y Diego (lista de tomas).

Las reglas del guion son las de la skill "guion-tiktok-shop" de Miguel. Todo con Claude Haiku (centavos)
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

REGLAS = """Escribes guiones de video para vender productos de TikTok Shop (México) como creador afiliado.
Un video de Shop no busca solo vistas: busca que la persona piense "ah, qué chido, eso me sirve" y pique el carrito
naranja. Todo el guion está al servicio de esa reacción.

FORMATO (elige el que mejor deje VER el beneficio): problema_solucion (el caballo de batalla), antes_despues
(limpieza, belleza, organización, carro, casa), resena ("lo uso diario", recomendación a un compa), unboxing
(productos que la gente no conoce o que lucen al abrirse), tutorial (cuando surge "¿y eso cómo funciona?"),
objecion (responde la duda que frena la compra), asmr (productos con sonido o textura). Mostrar > decir: si el
beneficio no se puede mostrar, búscale la forma (comparación lado a lado, prueba, reacción real). Pocas
características habladas; resultados visibles.

ESTRUCTURA normal 35–50 s (corta 15–25 s si el producto es barato o de impulso):
- 0–3 s GANCHO: para el scroll, siempre ligado al producto. Tres capas a la vez: visual (movimiento, acción, algo
  raro), texto en pantalla (específico) y voz (empieza a media acción, nada de "hola chicos").
- 3–8 s PUENTE: por qué vale la pena ver lo que sigue ("pensé que era puro choro hasta que…", "llevo 2 semanas
  usándolo"). El producto ya en mano.
- 8–18 s PROBLEMA: la molestia exacta que el público reconoce. Que se vea.
- 18–30 s SOLUCIÓN / DEMO: el momento "ah, qué chido". Producto trabajando, resultado en close-up. Se debe entender
  qué hace antes del segundo 30.
- 30–42 s BENEFICIOS: "como hace X, te queda Y, entonces Z". Solo 2–3 ligados al problema. Prueba social aquí solo
  si existe de verdad (en la ficha).
- 42–50 s LLAMADO A LA ACCIÓN: directo, señalando abajo a la izquierda: "pícale al carrito naranja". Razón para
  hacerlo ya (oferta, envío, stock) solo si es real.
En la versión corta junta bloques, pero conserva gancho, demo y llamado a la acción.
Cambio de toma cada 1.5–2.5 s. Texto en pantalla corto y en zona segura (no arriba 15 %, no abajo 20 %, no a la
derecha 15 %). El video se debe entender sin sonido.

GANCHOS: siempre 3 variantes que se pegan al MISMO cuerpo (puente → llamado a la acción):
- A. Advertencia / dolor: "Deja de gastar en ___ que se rompen", "Si te pasa ___, no scrollees".
- B. Curiosidad / incredulidad: "Pensé que esto era fake…", "¿Por qué todo mundo está comprando esto?".
- C. Visual / demo muda: el resultado o la acción más impactante en los primeros 2 s con texto grande, casi sin voz.
Otros moldes: "No compres ___, compra esto", "Lo que pedí vs lo que me llegó", "Cosas que ojalá hubiera comprado
antes", "La forma floja de ___", "Probé ___ para que tú no tengas que".

VOZ Y TONO: recomendación a un compa, no comercial. Español mexicano natural ("está bien práctico", "neta", "te
ahorras un buen"), sin albur ni groserías. Frases cortas, nada de "este increíble producto revolucionario".
Honesto: menciona una pega pequeña o el momento en que dudaste. Precio en pesos y comparado con algo cotidiano si
ayuda ("menos que una pizza"). NUNCA prometas resultados médicos, de salud o de peso, ni cifras que no se puedan
comprobar. NUNCA inventes reseñas, ventas ni "se agotó": usa solo lo que trae la ficha. Si un dato no está en la
ficha, no lo afirmes.

Miguel graba él mismo con su celular (manos, producto, a veces su cara y su voz). Las tomas deben poder grabarse
en casa con el producto real.
CAPTION corto + 3–5 hashtags (mezcla de nicho y #TikTokShop / #TikTokMeHizoComprarlo). COMENTARIO FIJADO que
responda la objeción principal."""


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
                           "para": {"type": "string", "description": "a qué parte del guion va (Gancho A, Problema…)"},
                           "tip": {"type": "string"}}}},
        "consejos": {"type": "array", "items": {"type": "string"}},
    },
}


def tomas(p: dict, g: dict) -> dict:
    pedido = (f"Producto: {p['nombre']}\nGuion de Sofi:\n" + json.dumps(
        {"ganchos": g["ganchos"], "cuerpo": g["cuerpo"]}, ensure_ascii=False)
        + "\n\nArma la lista de tomas para que Miguel grabe TODO en una sola sesión con su celular en vertical. "
          "Ordénalas por lugar para no mover las cosas dos veces (no en el orden del video). Incluye las tomas de "
          "los 3 ganchos. Cada toma de 2 a 6 s, con 1–2 s de colchón. Consejos cortos de luz, sonido y zona segura.")
    r = ia.json_estructurado("Eres Diego, director de grabación. Práctico: tomas que se hacen en casa con el producto "
                             "real y un celular.", pedido, TOMAS, tarea="tomas_shop", que="lista de tomas")
    for i, t in enumerate(r["tomas"], 1):
        t["n"] = i
    return r
