"""🕵️ Estilo noir de «¿Quién MATÓ a…?» para el kit de animación (sin Claude: lo arma el código).

Fondo: las fotos de la marca, oscurecidas y con movimiento lento; cada frase trae su texto en pantalla (amarillo, letra
de impacto), las cifras como contador, una cortinilla por capítulo, zoom en las palabras fuertes, sacudida al cambiar de
frase y el sello «CASO CERRADO» al final. Subtítulos con la palabra que se dice en amarillo.
"""
from __future__ import annotations

import re
from pathlib import Path

from estilo_lana import CIFRA_RE, _sonido
from estilo_pro import _numero

AMARILLO, ROJO = "#FFD60A", "#E63946"
FUERTE = re.compile(r"quiebra|muri|mat[oó]|cerr|deuda|millones|perdi|fracas|culpa|sospech|\d", re.I)


def armar(mesa: Path, m: dict, borrador: dict) -> dict:
    whoosh, golpe = _sonido(mesa, "whoosh"), _sonido(mesa, "golpe", "impact", "boom")
    escenas_m = m.get("escenas") or []
    n = len(borrador["escenas"])
    for k, esc in enumerate(borrador["escenas"]):
        e = escenas_m[k] if k < len(escenas_m) else {}
        dur = float(esc["duracion"])
        palabras = esc.get("palabras") or []
        fotos = [f for f in e.get("fotos") or [] if (mesa / f).exists()]
        capas, sfx = [], []
        # fondo: la primera foto oscurecida; si no hay, un degradado oscuro del canal
        esc["fondo"] = ({"tipo": "imagen", "archivo": fotos[0], "movimiento": ("acercar", "izquierda", "alejar", "derecha")[k % 4],
                         "oscurecer": 0.55} if fotos else {"tipo": "degradado", "color": "#121212", "color2": "#2a1f00"})
        # cortinilla del capítulo al empezar la escena (la primera escena entra directo con el gancho)
        cortinilla = 0.0
        if k and e.get("texto"):
            titulo = e["texto"].strip()
            while len(titulo) > 22 and " " in titulo:  # corto por palabra para que quepa en la franja
                titulo = titulo.rsplit(" ", 1)[0]
            cortinilla = round(min(dur * 0.4, 1.8), 2)
            capas.append({"tipo": "titulo_seccion", "desde": 0.0, "hasta": cortinilla, "texto": f"#{k + 1:02d}", "titulo": titulo[:24]})
        # cada frase: su texto en pantalla cuando empieza y, cada tanto, otra foto que entra de lado
        inicio, cuenta = 0, 0
        for j, nw in enumerate(e.get("frases") or []):
            t = palabras[inicio]["t"] if inicio < len(palabras) else None
            inicio += nw
            if t is None or t > dur - 0.8:
                continue
            t = max(t, cortinilla + 0.2 if cortinilla else t)  # nada encima de la cortinilla del capítulo
            fin = palabras[min(inicio, len(palabras)) - 1]["t"] + 0.4 if palabras else dur
            textos = e.get("texto_pantalla") or []
            if j < len(textos) and textos[j] and (k or j):
                capas.append({"tipo": "texto", "estilo": "impacto", "texto": textos[j].upper()[:42], "x": 0.27 if j % 2 else 0.73,
                              "y": 0.32, "tamano": 0.62, "desde": round(t + 0.1, 2), "hasta": round(min(dur, max(t + 2.4, fin)), 2),
                              "color": AMARILLO})
            if j and len(fotos) > 1 and j % 2 == 0:
                capas.append({"tipo": "imagen", "archivo": fotos[1 + cuenta % (len(fotos) - 1)], "lado": "izquierda" if j % 4 else "derecha",
                              "desde": round(t, 2), "hasta": round(min(dur, t + 3.2), 2), "tamano": 0.8})
                cuenta += 1
            if j:
                capas.append({"tipo": "sacudida", "desde": round(t, 2), "hasta": round(t + 0.25, 2), "tamano": 0.3})
        # gancho: el título del caso de golpe
        if k == 0:
            capas.append({"tipo": "texto", "estilo": "golpe", "texto": f"¿QUIÉN MATÓ A {str(m.get('marca', '')).upper()}?",
                          "y": 0.42, "desde": 0.2, "hasta": round(min(dur, 4.0), 2), "color": AMARILLO})
            if golpe:
                sfx.append({"archivo": golpe, "desde": 0.2, "volumen": 0.5})
        # cifras dichas → contador grande, justo cuando se dicen (máx. 2 por escena)
        for cifra in [x.group(1).strip().rstrip(".,") for x in CIFRA_RE.finditer(e.get("narracion") or "")][:2]:
            num = _numero(cifra)
            t = next((p["t"] for p in palabras if cifra.split()[0].strip("$").rstrip(".,%") in p["w"]), None)
            if num and t is not None and t < dur - 1:
                capas.append({"tipo": "dato", **num, "x": 0.5, "y": 0.62, "tamano": 0.5, "color": AMARILLO,
                              "desde": round(t, 2), "hasta": round(min(dur, t + 2.8), 2)})
        # zoom en la primera palabra fuerte
        fuerte = next((p for p in palabras if p["t"] > 0.5 and FUERTE.search(p["w"])), None)
        if fuerte and fuerte["t"] < dur - 0.6:
            capas.append({"tipo": "zoom_golpe", "desde": round(fuerte["t"], 2), "hasta": round(fuerte["t"] + 0.6, 2), "tamano": 0.1})
        # cierre: caso cerrado
        if k == n - 1:
            capas.append({"tipo": "sello", "texto": "CASO CERRADO", "color": ROJO, "x": 0.5, "y": 0.4, "angulo": -8,
                          "tamano": 0.75, "desde": round(max(0.5, dur - 4.5), 2), "hasta": dur})
            if golpe:
                sfx.append({"archivo": golpe, "desde": round(max(0.5, dur - 4.5), 2), "volumen": 0.6})
        transicion = "destello" if k == 0 else ("deslizar", "zoom", "corte")[k % 3]
        if whoosh and transicion != "corte" and k:
            sfx.append({"archivo": whoosh, "desde": 0, "volumen": 0.35})
        esc.update(capas=capas, sfx=sfx, transicion=transicion)
    borrador.update(acento=AMARILLO, peligro=ROJO, barra=True,
                    subtitulos={"activar": True, "estilo": "karaoke", "y": 0.88, "porGrupo": 3, "resaltado": AMARILLO})
    if borrador.get("musica"):
        borrador["musica"]["volumen"] = 0.06
    return borrador
