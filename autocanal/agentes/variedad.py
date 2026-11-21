"""🎲 Variedad: muchos videos sin que parezcan hechos en serie.

YouTube le quita la monetización a los canales con contenido «genérico o repetitivo» (julio 2026): videos casi
iguales, misma plantilla, mismas frases. La IA está permitida si cada video aporta algo único. Como este canal saca
mucho volumen, cada guion recibe:
- cómo empezaron los últimos videos del canal (para no arrancar igual) y el tipo de gancho que toca (el menos usado),
- las frases que ya se repitieron en varios guiones (prohibidas),
- el orden de bloques reciente (para cambiar la estructura),
- el recordatorio de aportar algo propio (opinión con datos, un caso concreto, la prueba del jefe).
Todo sale de los guiones ya hechos (salida/*/guion.json); no cuesta nada.
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter

from . import config

GANCHOS = ["historia", "dato_impactante", "pregunta_al_espectador", "promesa_vs_realidad", "prueba_en_vivo",
           "caso_de_usuario", "advertencia_directa", "contraintuitivo"]
DESCRIPCION_GANCHO = {
    "historia": "arranca contando lo que le pasó a alguien (o al canal) a media acción",
    "dato_impactante": "arranca con la cifra más fuerte del video",
    "pregunta_al_espectador": "arranca con una pregunta directa al que ve, que le pique",
    "promesa_vs_realidad": "arranca con lo que promete contra lo que de verdad pasa",
    "prueba_en_vivo": "arranca en medio de la prueba (lo que se ve en pantalla en ese momento)",
    "caso_de_usuario": "arranca citando un comentario o reseña real de un usuario",
    "advertencia_directa": "arranca advirtiendo qué te puede pasar si no ves esto",
    "contraintuitivo": "arranca con algo que contradice lo que todos creen",
}
_VACIAS = {"de", "la", "que", "el", "en", "y", "a", "los", "se", "del", "las", "un", "por", "con", "no", "una", "su",
           "para", "es", "al", "lo", "como", "mas", "o", "pero", "sus", "le", "ya", "te", "si", "me", "tu", "esta",
           "este", "eso", "esto", "muy", "hay"}


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9 ]+", " ", t)


def _guiones(canal: str, n: int = 15) -> list[dict]:
    """Los últimos guiones del canal (el más nuevo primero)."""
    salida = []
    for g in config.SALIDA.glob("*/guion.json"):
        if g.parent.name.startswith("_"):
            continue
        try:
            origen = json.loads((g.parent / "origen.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            origen = {}
        if (origen.get("canal") or "principal") != canal:
            continue
        try:
            datos = json.loads(g.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        salida.append((g.stat().st_mtime, g.parent.name, datos))
    salida.sort(key=lambda x: x[0], reverse=True)
    return [{"app_id": a, **d} for _, a, d in salida[:n]]


def titulos_recientes(canal: str, n: int = 12) -> list[str]:
    return [f"- {(g.get('titulos') or ['?'])[0]}" for g in _guiones(canal, n)]


def muletillas(guiones: list[dict], minimo: int = 3) -> list[str]:
    """Frases de 4 palabras que aparecen en `minimo` o más guiones distintos."""
    cuenta = Counter()
    for g in guiones:
        texto = _norm(" ".join(e.get("narracion") or "" for e in g.get("escenas") or []))
        palabras = texto.split()
        vistos = set()
        for i in range(len(palabras) - 3):
            trozo = palabras[i:i + 4]
            if sum(p not in _VACIAS for p in trozo) < 2:
                continue
            vistos.add(" ".join(trozo))
        cuenta.update(vistos)
    nombres = {_norm(g["app_id"]) for g in guiones}
    return [f for f, c in cuenta.most_common(40) if c >= minimo and not any(f in n for n in nombres)][:15]


def gancho_que_toca(guiones: list[dict]) -> str:
    usados = Counter(g.get("tipo_gancho") for g in guiones[:10] if g.get("tipo_gancho"))
    ultimo = guiones[0].get("tipo_gancho") if guiones else None
    return min((g for g in GANCHOS if g != ultimo), key=lambda g: (usados[g], GANCHOS.index(g)))


def para_guionista(canal: str | None = None) -> str:
    from . import canales
    canal = canal or canales.actual()
    guiones = _guiones(canal)
    toca = gancho_que_toca(guiones)
    partes = ["VARIEDAD (este canal publica mucho; YouTube castiga lo repetitivo y hecho en serie: este video debe "
              "sentirse distinto y hecho a mano):",
              f"- Tipo de gancho de esta vez: «{toca}» — {DESCRIPCION_GANCHO[toca]}. Ponlo en tipo_gancho."]
    if guiones:
        arranques = [((g.get("escenas") or [{}])[0].get("narracion") or "")[:110] for g in guiones[:8]]
        partes.append("- Así empezaron los últimos videos (no empieces igual ni con la misma fórmula):\n"
                      + "\n".join(f"    «{a}»" for a in arranques if a))
        estructuras = []
        for g in guiones[:5]:
            visuales = [e.get("visual") for e in g.get("escenas") or []]
            estructuras.append(" → ".join(v for i, v in enumerate(visuales) if i == 0 or v != visuales[i - 1])[:160])
        partes.append("- Orden de bloques de los últimos (cambia el orden y el ritmo esta vez):\n"
                      + "\n".join(f"    {e}" for e in estructuras))
        repetidas = muletillas(guiones)
        if repetidas:
            partes.append("- Frases que ya repetiste en varios guiones (NO las uses): " + "; ".join(f"«{f}»" for f in repetidas))
    partes.append("- Aporta algo propio que no tenga otro video: una opinión clara en primera persona basada en los "
                  "datos, un caso concreto con nombre y cifra, una comparación que tú hiciste, o la prueba del jefe.")
    return "\n\n" + "\n".join(partes)
