"""Lanudo, el borrego de «Cuida Tu Lana». Dibujado con código (SVG) para poder animarlo.

    python generar.py      → crea los PNG transparentes (expresiones y bocas) y hoja.jpg en esta carpeta.

Expresiones: normal, feliz, preocupado, sorprendido, asustado, enojado, pensando, guinando.
Bocas (para que hable con la voz): cerrada, a, e, o, u, m.
"""
from __future__ import annotations

import io
from pathlib import Path

AQUI = Path(__file__).parent
TINTA = "#2b2140"
LANA, LANA_SOMBRA = "#fbf8f1", "#e6dfd2"
CARA, CARA_LUZ = "#4f3f63", "#65537a"
ROSA = "#ff9fb7"


def _lana(puntos, sombra=True) -> str:
    capas = []
    if sombra:
        capas += [f'<circle cx="{x+6}" cy="{y+10}" r="{r}" fill="{LANA_SOMBRA}"/>' for x, y, r in puntos]
    capas += [f'<circle cx="{x}" cy="{y}" r="{r}" fill="{LANA}" stroke="{TINTA}" stroke-width="7"/>' for x, y, r in puntos]
    capas += [f'<circle cx="{x}" cy="{y}" r="{r-7}" fill="{LANA}"/>' for x, y, r in puntos]  # tapa los bordes internos
    capas += [f'<path d="M{x-r*0.45},{y-r*0.35} q{r*0.25},-{r*0.25} {r*0.55},-{r*0.1}" stroke="#ffffff" stroke-width="8" '
              f'stroke-linecap="round" fill="none" opacity=".9"/>' for x, y, r in puntos[::2]]
    return "".join(capas)


CUERPO = [(185, 470, 92), (300, 440, 108), (415, 470, 92), (200, 560, 80), (300, 575, 100), (400, 560, 80), (300, 505, 95)]
COPETE = [(240, 200, 42), (300, 178, 50), (360, 200, 42), (270, 222, 40), (330, 222, 40), (205, 228, 30), (395, 228, 30)]


def ojos(tipo: str, cy: float = 315) -> str:
    g = []
    for lado in (-1, 1):
        x = 300 + lado * 52
        if tipo == "feliz":
            g.append(f'<path d="M{x-24},{cy+6} Q{x},{cy-22} {x+24},{cy+6}" stroke="{TINTA}" stroke-width="9" fill="none" stroke-linecap="round"/>')
        elif tipo == "guinando" and lado == 1:
            g.append(f'<path d="M{x-24},{cy} Q{x},{cy+10} {x+24},{cy}" stroke="{TINTA}" stroke-width="9" fill="none" stroke-linecap="round"/>')
        else:
            grande = tipo in ("sorprendido", "asustado")
            rx, ry = (30, 38) if grande else (26, 32)
            g.append(f'<ellipse cx="{x}" cy="{cy}" rx="{rx}" ry="{ry}" fill="#ffffff" stroke="{TINTA}" stroke-width="6"/>')
            pr = 9 if tipo == "asustado" else 15 if not grande else 13
            px = x + (lado * -4 if tipo != "pensando" else 8)
            py = cy + (8 if tipo in ("preocupado", "asustado") else -8 if tipo == "pensando" else 2)
            g.append(f'<circle cx="{px}" cy="{py}" r="{pr}" fill="{TINTA}"/>')
            g.append(f'<circle cx="{px+5}" cy="{py-6}" r="{pr*0.38}" fill="#ffffff"/>')
            if tipo == "enojado":  # párpado de enojo
                g.append(f'<path d="M{x-rx-2},{cy-ry*0.55 + (8 if lado==-1 else -8)} L{x+rx+2},{cy-ry*0.55 + (-8 if lado==-1 else 8)} L{x+rx+2},{cy-ry-6} L{x-rx-2},{cy-ry-6} Z" fill="{CARA}"/>')
    return "".join(g)


def cejas(tipo: str, cy: float = 315) -> str:
    g = []
    for lado in (-1, 1):
        x = 300 + lado * 52
        adentro, afuera = x - lado * 22, x + lado * 22
        if tipo in ("preocupado", "asustado"):
            ya, yf = cy - 62, cy - 46
        elif tipo == "enojado":
            ya, yf = cy - 36, cy - 58
        elif tipo == "sorprendido":
            ya, yf = cy - 70, cy - 70
        elif tipo == "pensando":
            ya, yf = (cy - 52, cy - 66) if lado == 1 else (cy - 50, cy - 48)
        else:
            ya, yf = cy - 52, cy - 50
        curva = "Q" if tipo in ("normal", "feliz", "sorprendido", "guinando") else "L"
        if curva == "Q":
            g.append(f'<path d="M{adentro},{ya} Q{x},{min(ya, yf)-10} {afuera},{yf}" stroke="{TINTA}" stroke-width="9" fill="none" stroke-linecap="round"/>')
        else:
            g.append(f'<path d="M{adentro},{ya} L{afuera},{yf}" stroke="{TINTA}" stroke-width="9" stroke-linecap="round"/>')
    return "".join(g)


def boca(tipo: str, cy: float = 392) -> str:
    rojo, lengua = "#5a1630", "#ff7d96"
    formas = {
        "cerrada": f'<path d="M270,{cy} Q300,{cy+16} 330,{cy}" stroke="{TINTA}" stroke-width="8" fill="none" stroke-linecap="round"/>',
        "m": f'<path d="M276,{cy+4} L324,{cy+4}" stroke="{TINTA}" stroke-width="9" stroke-linecap="round"/>',
        "a": f'<path d="M262,{cy-8} Q300,{cy-4} 338,{cy-8} Q334,{cy+44} 300,{cy+46} Q266,{cy+44} 262,{cy-8} Z" fill="{rojo}" stroke="{TINTA}" stroke-width="6"/>'
             f'<path d="M278,{cy+30} Q300,{cy+18} 322,{cy+30} Q300,{cy+44} 278,{cy+30} Z" fill="{lengua}"/>',
        "e": f'<path d="M258,{cy-2} Q300,{cy+6} 342,{cy-2} Q330,{cy+28} 300,{cy+30} Q270,{cy+28} 258,{cy-2} Z" fill="{rojo}" stroke="{TINTA}" stroke-width="6"/>'
             f'<path d="M266,{cy+2} Q300,{cy+8} 334,{cy+2} L332,{cy+10} Q300,{cy+16} 268,{cy+10} Z" fill="#ffffff"/>',
        "o": f'<ellipse cx="300" cy="{cy+14}" rx="20" ry="26" fill="{rojo}" stroke="{TINTA}" stroke-width="6"/>',
        "u": f'<ellipse cx="300" cy="{cy+10}" rx="13" ry="15" fill="{rojo}" stroke="{TINTA}" stroke-width="6"/>',
        "sonrisa": f'<path d="M258,{cy-6} Q300,{cy+46} 342,{cy-6} Z" fill="{rojo}" stroke="{TINTA}" stroke-width="6" stroke-linejoin="round"/>'
                   f'<path d="M280,{cy+18} Q300,{cy+32} 320,{cy+18} Q300,{cy+12} 280,{cy+18} Z" fill="{lengua}"/>',
        "preocupado": f'<path d="M266,{cy+16} Q283,{cy} 300,{cy+12} Q317,{cy} 334,{cy+16}" stroke="{TINTA}" stroke-width="8" fill="none" stroke-linecap="round"/>',
        "asustado": f'<path d="M264,{cy} L336,{cy} L330,{cy+30} L270,{cy+30} Z" fill="#ffffff" stroke="{TINTA}" stroke-width="6" stroke-linejoin="round"/>'
                    + "".join(f'<path d="M{x},{cy} v30" stroke="{TINTA}" stroke-width="4"/>' for x in (282, 300, 318)),
        "enojado": f'<path d="M266,{cy+18} Q300,{cy-6} 334,{cy+18}" stroke="{TINTA}" stroke-width="9" fill="none" stroke-linecap="round"/>',
        "pensando": f'<path d="M278,{cy+10} Q300,{cy+4} 326,{cy+2}" stroke="{TINTA}" stroke-width="8" fill="none" stroke-linecap="round"/>',
    }
    return formas[tipo]


def extras(expresion: str) -> str:
    if expresion in ("preocupado", "asustado"):
        return (f'<path d="M398,250 q14,24 0,36 q-14,-12 0,-36 Z" fill="#8fd8ff" stroke="{TINTA}" stroke-width="4"/>'
                + (f'<path d="M190,250 q-10,18 0,28 q10,-10 0,-28 Z" fill="#8fd8ff" stroke="{TINTA}" stroke-width="4"/>' if expresion == "asustado" else ""))
    if expresion == "enojado":
        return f'<path d="M420,215 l18,-18 m-6,24 l24,-6 m-34,-4 l6,-24" stroke="#ff4d4d" stroke-width="8" stroke-linecap="round"/>'
    if expresion == "pensando":
        return (f'<circle cx="455" cy="200" r="10" fill="#ffffff" stroke="{TINTA}" stroke-width="4"/>'
                f'<circle cx="480" cy="165" r="15" fill="#ffffff" stroke="{TINTA}" stroke-width="4"/>'
                f'<ellipse cx="520" cy="115" rx="40" ry="30" fill="#ffffff" stroke="{TINTA}" stroke-width="4"/>'
                f'<text x="520" y="128" font-size="38" text-anchor="middle" font-family="DejaVu Sans" font-weight="bold" fill="{TINTA}">?</text>')
    if expresion == "sorprendido":
        return f'<path d="M150,180 l-22,-18 M160,150 l-10,-26 M450,180 l22,-18 M440,150 l10,-26" stroke="#ffd23f" stroke-width="8" stroke-linecap="round"/>'
    return ""


BOCA_DE = {"normal": "sonrisa", "feliz": "a", "preocupado": "preocupado", "sorprendido": "o", "asustado": "asustado",
           "enojado": "enojado", "pensando": "pensando", "guinando": "sonrisa"}
OJOS_DE = {"normal": "normal", "feliz": "feliz", "preocupado": "preocupado", "sorprendido": "sorprendido",
           "asustado": "asustado", "enojado": "enojado", "pensando": "pensando", "guinando": "guinando"}


def lanudo(expresion: str = "normal", la_boca: str | None = None) -> str:
    patas = "".join(f'<rect x="{x}" y="620" width="40" height="80" rx="16" fill="{CARA}" stroke="{TINTA}" stroke-width="6"/>'
                    f'<rect x="{x}" y="682" width="40" height="22" rx="9" fill="{TINTA}"/>' for x in (205, 262, 298, 355))
    orejas = (f'<g transform="rotate(-28 180 300)"><ellipse cx="180" cy="300" rx="58" ry="27" fill="{CARA}" stroke="{TINTA}" stroke-width="6"/>'
              f'<ellipse cx="174" cy="300" rx="36" ry="13" fill="{ROSA}"/></g>'
              f'<g transform="rotate(28 420 300)"><ellipse cx="420" cy="300" rx="58" ry="27" fill="{CARA}" stroke="{TINTA}" stroke-width="6"/>'
              f'<ellipse cx="426" cy="300" rx="36" ry="13" fill="{ROSA}"/></g>')
    cabeza = (f'<ellipse cx="300" cy="335" rx="118" ry="132" fill="{CARA}" stroke="{TINTA}" stroke-width="7"/>'
              f'<ellipse cx="270" cy="290" rx="60" ry="55" fill="{CARA_LUZ}" opacity=".55"/>'
              f'<ellipse cx="300" cy="400" rx="70" ry="48" fill="{CARA_LUZ}" opacity=".5"/>'
              f'<ellipse cx="232" cy="372" rx="24" ry="13" fill="{ROSA}" opacity=".55"/>'
              f'<ellipse cx="368" cy="372" rx="24" ry="13" fill="{ROSA}" opacity=".55"/>')
    cara = (cejas(expresion) + ojos(OJOS_DE[expresion]) + boca(la_boca or BOCA_DE[expresion]) + extras(expresion))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="600" height="730" viewBox="0 0 600 730">'
            f'<ellipse cx="300" cy="708" rx="175" ry="16" fill="#000000" opacity=".18"/>'
            + patas + _lana(CUERPO) + orejas + cabeza + _lana(COPETE, sombra=False) + cara + "</svg>")


EXPRESIONES = list(BOCA_DE)
BOCAS = ["cerrada", "m", "a", "e", "o", "u"]

if __name__ == "__main__":
    import cairosvg
    from PIL import Image, ImageDraw, ImageFont

    def png(svg: str, ancho: int = 600) -> Image.Image:
        return Image.open(io.BytesIO(cairosvg.svg2png(bytestring=svg.encode(), output_width=ancho))).convert("RGBA")

    for e in EXPRESIONES:
        png(lanudo(e), 900).save(AQUI / f"{e}.png")
        (AQUI / f"{e}.svg").write_text(lanudo(e), encoding="utf-8")
    for b in BOCAS:
        png(lanudo("normal", b), 900).save(AQUI / f"boca_{b}.png")
    # hoja para verlo todo
    fuente = ImageFont.truetype(str(AQUI.parents[1] / "fuentes" / "LuckiestGuy-Regular.ttf"), 34)
    celda = 300
    filas = [(e, lanudo(e)) for e in EXPRESIONES] + [(f"boca {b}", lanudo("normal", b)) for b in BOCAS]
    cols = 7
    hoja = Image.new("RGB", (cols * celda, ((len(filas) + cols - 1) // cols) * (celda + 60) + 20), (24, 28, 48))
    d = ImageDraw.Draw(hoja)
    for i, (nombre, svg) in enumerate(filas):
        x, y = (i % cols) * celda, (i // cols) * (celda + 60) + 10
        im = png(svg, 260)
        hoja.paste(im, (x + 20, y), im)
        d.text((x + 20, y + celda + 4), nombre.upper(), font=fuente, fill=(255, 214, 10))
    hoja.save(AQUI / "hoja.jpg", quality=92)
    print("listo")
