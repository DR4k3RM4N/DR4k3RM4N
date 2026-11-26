"""Genera las miniaturas A y B del Expediente #002 (1280×720 JPG).

Uso: python miniatura.py
"""
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent / "motor"))
import motor as m  # noqa: E402
from PIL import ImageDraw  # noqa: E402

OUT = AQUI / "render"
OUT.mkdir(exist_ok=True)


def guardar(img, nombre):
    img = img.convert("RGB").resize((1280, 720), m.Image.LANCZOS)
    ruta = OUT / nombre
    img.save(ruta, quality=90, optimize=True)
    print(ruta, ruta.stat().st_size // 1024, "KB")


def texto(d, xy, s, size, color, anchor="la"):
    f = m.font("display", size)
    # contorno negro para que se lea sobre cualquier fondo
    d.text(xy, s, font=f, fill=m.C[color], anchor=anchor, stroke_width=max(4, size // 28), stroke_fill=(0, 0, 0))
    return f


# --- A: el tóper con cinta + "QUEBRÓ… Y LO COMPRÓ MÉXICO"
img, d = m.canvas()
d.ellipse([40, 200, 840, 1000], fill=(36, 36, 40))
m.icon(d, "bowl", 430, 610, 1.85)
band = m.tape_band("ESCENA DEL CRIMEN · NO PASAR", 1500, 24)
band = band.crop((0, 0, 980, band.height))  # que la cinta no se meta al texto
img.paste(band, (-120, 330), band)
d = ImageDraw.Draw(img)
texto(d, (930, 150), "QUEBRÓ…", 250, "ink")
texto(d, (930, 420), "Y LO COMPRÓ", 200, "tape")
texto(d, (930, 640), "MÉXICO", 300, "green")
# bandera mínima
x, y = 1700, 70
for i, c in enumerate([(0, 104, 71), (245, 245, 245), (206, 17, 38)]):
    d.rectangle([x + i * 50, y, x + i * 50 + 50, y + 100], fill=c)
img.paste(m.hazard(m.W, 18), (0, m.H - 18))
guardar(img, "miniatura-A.jpg")

# --- B: $23 M vs $250 M
img, d = m.canvas()
d.rectangle([0, 0, m.W // 2, m.H], fill=(30, 14, 16))
d.rectangle([m.W // 2, 0, m.W, m.H], fill=(12, 30, 18))
m.icon(d, "bowl", 480, 330, 1.5)
m.icon(d, "bowl", 1440, 330, 1.5)
texto(d, (480, 720), "$23 M", 300, "red", anchor="mm")
texto(d, (1440, 720), "$250 M", 300, "green", anchor="mm")
texto(d, (480, 930), "ESTADOS UNIDOS", 90, "ink", anchor="mm")
texto(d, (1440, 930), "MÉXICO", 90, "ink", anchor="mm")
d.rectangle([m.W // 2 - 6, 0, m.W // 2 + 6, m.H], fill=m.C["tape"])
img.paste(m.hazard(m.W, 18), (0, m.H - 18))
guardar(img, "miniatura-B.jpg")
