"""🎁 Empaque: el título y la miniatura (lo que decide si alguien le da clic).

Lo que dice la investigación (YouTube 2026, estrategas como Paddy Galloway y el equipo de MrBeast, estudios de CTR):
- El empaque se piensa ANTES que el video: si una idea no se puede empaquetar en un título + miniatura que den ganas
  de clic, no es buena idea. El equipo de MrBeast hace ~50 conceptos por video y se queda con el mejor.
- Título y miniatura son UNA sola unidad: se complementan, no repiten lo mismo.
- YouTube elige al ganador de las pruebas A/B por TIEMPO VISTO, no por clics: el empaque debe prometer algo que el
  video cumple rápido (si engaña, la gente se va y el video se hunde).
- Caras con emoción clara y fuerte, texto corto y grande (3-5 palabras), alto contraste, un solo punto focal.
- Títulos en pregunta a secas tienden a rendir menos; mejor una postura o un resultado concreto.

Aquí: después del guion, un crítico arma ~10 conceptos, los califica con esa guía y con los números reales del
canal (los títulos que más jalaron y los que no) y deja 3 PAQUETES MUY DISTINTOS (para probarlos en YouTube Studio
con «Prueba A/B» o para el 🛟 rescate automático si el primero no jala).
"""
from __future__ import annotations

from . import claude, config

GUIA = """GUÍA DE EMPAQUE (títulos y miniaturas que funcionan; síguela siempre):
TÍTULO
1. Título y miniatura son UN paquete: la miniatura muestra la emoción o la escena, el título da el contexto o la
   promesa. Nunca repitas en el título las mismas palabras de la miniatura.
2. Máximo ~55 caracteres (en el celular se corta). Lo importante en las primeras 3-4 palabras: el nombre de la app o
   la palabra que la gente busca.
3. Específico gana a genérico: cifras ($, días, personas), nombres propios, resultados ("La usé 7 días", "me pagó
   $43", "le escribieron a 200 de mis contactos").
4. Curiosidad con promesa clara: abre una pregunta que solo el video contesta, y el video la contesta pronto
   (YouTube premia el tiempo visto, no el clic: si engaña, se hunde).
5. Emoción y algo en juego: perder dinero, sorpresa, enojo, alivio, protegerse.
6. Mejor una postura que una pregunta a secas ("X no paga: lo comprobé" > "¿X paga?"). Pregunta solo si trae gancho.
7. Usa las palabras con que la gente lo busca (para que también salga en búsquedas).
8. Nunca prometas algo que el video no cumple. Sin TODO EN MAYÚSCULAS; máximo 1 emoji.
MINIATURA
1. Una sola idea y un punto focal; máximo 3 elementos. Se entiende en 1 segundo en tamaño celular.
2. Cara o personaje con una emoción fuerte y clara (sorpresa, miedo, enojo) mirando al elemento clave.
3. Texto de 2-4 palabras GRANDES y de alto contraste que COMPLETA el título, no lo repite ("ME ROBÓ", "$0 PAGADO",
   "NO LA BAJES").
4. Prueba visual cuando se pueda: captura del pago, la cifra, el chat de amenaza, el celular con la app.
5. Fondo limpio y colores que contrasten; misma marca (colores, fuente, mascota) pero cada miniatura con su escena.
PRUEBA A/B: los paquetes deben ser MUY distintos entre sí (otro concepto, no la misma idea con otro color): por
ejemplo uno de emoción, uno de prueba/cifra y uno de contraste promesa vs. realidad."""

NICHO = {
    "apps": "Este canal: apps que prometen pagar. Lo que jala: la cifra real (cuánto pagó o no), 'lo probé X días', "
            "promesa contra realidad, advertir antes de que pierdas tiempo.",
    "fraudes": "Este canal: alertas de fraude y montadeudas en México. Lo que jala: la amenaza concreta y cercana "
               "('te exhiben con tus contactos'), el nombre de la app o la estafa, protegerse ('haz esto si ya "
               "caíste'), la urgencia de esta semana. Colores de alerta. Lanudo (el borrego) asustado o enojado.",
    "libre": "",
}

SCHEMA = {
    "type": "object",
    "properties": {
        "conceptos": {"type": "array", "items": {"type": "string"},
                      "description": "Lluvia de 10 conceptos de empaque (título + texto de miniatura + qué se ve), "
                                     "en una línea cada uno, lo más variados posible"},
        "paquetes": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "titulo": {"type": "string", "description": "Máx. 60 caracteres"},
                "texto_miniatura": {"type": "string", "description": "2-4 palabras, completa el título sin repetirlo"},
                "sello": {"type": "string", "description": "1-2 palabras para el sello de la miniatura"},
                "escena_miniatura": {"type": "string", "description": "Qué se ve: personaje y emoción, elemento clave"},
                "angulo": {"type": "string", "enum": ["emocion", "prueba_cifra", "contraste", "urgencia", "curiosidad"]},
                "por_que": {"type": "string", "description": "Por qué daría clic Y se quedaría viendo, en una frase"},
                "puntaje": {"type": "integer", "description": "1-10 según la guía y los números del canal"},
            },
            "required": ["titulo", "texto_miniatura", "sello", "escena_miniatura", "angulo", "por_que", "puntaje"],
            "additionalProperties": False,
        }, "description": "Los 3 mejores paquetes, MUY distintos entre sí, el mejor primero"},
    },
    "required": ["conceptos", "paquetes"],
    "additionalProperties": False,
}

SELLOS_APP = ("NO PAGA", "CUIDADO", "SÍ PAGA", "¿PAGA?")


def para_guionista(canal: str | None = None) -> str:
    """La guía para que Gabi ya escriba títulos y textos de miniatura con ella."""
    from . import canales
    nicho = canales.get(canal or canales.actual()).get("nicho") or "apps"
    return "\n\n" + GUIA + ("\n" + NICHO[nicho] if NICHO.get(nicho) else "")


def empacar(guion: dict, resumen_video: str, canal: str | None = None, notas: str = "") -> dict:
    """Arma 3 paquetes y reordena títulos y textos de miniatura del guion (el mejor primero). Regresa el guion."""
    from . import analitica, canales, lecciones, variedad

    canal = canal or canales.actual()
    info = canales.get(canal)
    buenos, malos = analitica.titulos_que_jalan(canal)
    recientes = variedad.titulos_recientes(canal, 12)
    gancho = ((guion.get("escenas") or [{}])[0].get("narracion") or "")
    r = claude.json_estructurado(
        f"Eres el estratega de empaque del canal de YouTube «{info.get('nombre') or config.CANAL_NOMBRE}» (México). "
        "Decides el título y la miniatura de cada video: lo que hace que alguien le dé clic y se quede viendo.\n\n"
        + GUIA + ("\n" + NICHO.get(info.get("nicho") or "apps", "") if NICHO.get(info.get("nicho") or "apps") else "")
        + lecciones.para("disenadora"),
        f"EL VIDEO: {resumen_video}\nGANCHO (lo primero que se dice): «{gancho}»\n"
        + (f"INDICACIONES DEL JEFE: {notas}\n" if notas else "")
        + f"\nPROPUESTAS DEL GUIONISTA:\nTítulos: {guion.get('titulos')}\nTextos de miniatura: "
          f"{guion.get('textos_miniatura') or [guion.get('texto_miniatura')]}\n"
        + (f"\nLOS TÍTULOS QUE MÁS JALARON EN ESTE CANAL:\n" + "\n".join(buenos) if buenos else "")
        + (f"\nLOS QUE MENOS JALARON:\n" + "\n".join(malos) if malos else "")
        + (f"\nTÍTULOS RECIENTES DEL CANAL (no repitas su fórmula ni sus palabras de arranque):\n" + "\n".join(recientes)
           if recientes else "")
        + "\n\nHaz la lluvia de 10 conceptos y quédate con los 3 mejores paquetes, muy distintos entre sí. Cada uno "
          "debe cumplirse en los primeros 30 segundos del video. Solo datos que estén en el video.",
        SCHEMA, tarea="guion", que="empaque (títulos y miniaturas)")
    paquetes = [p for p in r["paquetes"] if p["titulo"].strip()][:3]
    if not paquetes:
        return guion
    paquetes.sort(key=lambda p: p["puntaje"], reverse=True)
    for p in paquetes:
        p["titulo"] = p["titulo"].strip()[:100]
        p["texto_miniatura"] = p["texto_miniatura"].strip()
    guion["paquetes"] = paquetes
    guion["titulos"] = list(dict.fromkeys([p["titulo"] for p in paquetes] + (guion.get("titulos") or [])))[:8]
    guion["textos_miniatura"] = list(dict.fromkeys([p["texto_miniatura"] for p in paquetes]
                                                   + (guion.get("textos_miniatura") or [])))[:10]
    guion["texto_miniatura"] = paquetes[0]["texto_miniatura"]
    sello = paquetes[0]["sello"].strip().upper()
    if guion.get("sello_miniatura") in SELLOS_APP:  # videos de apps: el sello es uno de los de siempre
        if sello in SELLOS_APP:
            guion["sello_miniatura"] = sello
    elif sello:
        guion["sello_miniatura"] = sello[:14]
    return guion


def ligar_miniaturas(guion: dict, opciones: list[dict], elegida: int) -> dict:
    """Une cada paquete con su miniatura hecha y pone primero el paquete de la miniatura elegida (para que el
    título que se publica vaya con su miniatura)."""
    paquetes = guion.get("paquetes") or []
    if not paquetes:
        return guion
    for p in paquetes:
        o = next((o for o in opciones if (o.get("texto") or "").strip().lower() == p["texto_miniatura"].lower()), None)
        if o:
            p["archivo"] = o["archivo"]
    if 0 <= elegida < len(opciones):
        archivo = opciones[elegida]["archivo"]
        k = next((i for i, p in enumerate(paquetes) if p.get("archivo") == archivo), None)
        if k:
            paquetes.insert(0, paquetes.pop(k))
            guion["titulos"] = list(dict.fromkeys([paquetes[0]["titulo"]] + guion["titulos"]))
    return guion
