"""Miniaturas del Expediente #001 (Sears), 1280×720 JPG.  Uso: python -E -P miniatura.py"""
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent / "motor"))
import motor as m  # noqa: E402
from PIL import Image, ImageDraw, ImageEnhance  # noqa: E402

m.EP_DIR = AQUI
OUT = AQUI / "render"
OUT.mkdir(exist_ok=True)


def foto(nombre):
    return m.load_photo(f"material/fotos/{nombre}")


def texto(d, xy, s, size, color, anchor="la"):
    f = m.font("display", size)
    d.text(xy, s, font=f, fill=m.C[color], anchor=anchor, stroke_width=max(5, size // 22), stroke_fill=(0, 0, 0))


def guardar(img, nombre):
    img = img.convert("RGB").resize((1280, 720), Image.LANCZOS)
    p = OUT / nombre
    img.save(p, quality=90, optimize=True)
    print(p, p.stat().st_size // 1024, "KB")


# A: pantalla dividida — Sears cerrado (EE.UU.) vs Sears abierto (México)
W, H = m.W, m.H
a = m.cover(foto("sears-cerrado-cicatriz.jpg"), W, H, (0.5, 0.35))
a = ImageEnhance.Color(a).enhance(0.15)
a = ImageEnhance.Brightness(a).enhance(0.7)
b = m.cover(foto("sears-perisur.jpg"), W, H, (0.5, 0.4))
b = ImageEnhance.Color(b).enhance(1.25)
mask = Image.new("L", (W, H), 0)
ImageDraw.Draw(mask).polygon([(0, 0), (W * 0.55, 0), (W * 0.45, H), (0, H)], fill=255)
img = b.copy()
img.paste(a, (0, 0), mask)
d = ImageDraw.Draw(img)
d.line([(W * 0.55, 0), (W * 0.45, H)], fill=(255, 255, 255), width=14)
texto(d, (60, 40), "MURIÓ", 210, "red")
texto(d, (W - 60, 40), "VIVE", 210, "green", anchor="ra")
texto(d, (60, H - 60), "EE.UU.", 150, "ink", anchor="ls")
texto(d, (W - 60, H - 60), "MÉXICO", 150, "ink", anchor="rs")
guardar(img, "miniatura-A.jpg")

# B: número contra número
img = Image.new("RGB", (W, H), (0, 0, 0))
img.paste(ImageEnhance.Brightness(ImageEnhance.Color(m.cover(foto("sears-cerrado-minnesota.jpg"), W // 2, H)).enhance(0.1)).enhance(0.55), (0, 0))
img.paste(ImageEnhance.Brightness(m.cover(foto("sears-perisur.jpg"), W // 2, H)).enhance(0.75), (W // 2, 0))
d = ImageDraw.Draw(img)
d.rectangle([W // 2 - 7, 0, W // 2 + 7, H], fill=m.C["tape"])
texto(d, (W // 4, H * 0.45), "5", 520, "red", anchor="mm")
texto(d, (W * 3 // 4, H * 0.45), "90+", 400, "green", anchor="mm")
texto(d, (W // 4, H * 0.86), "TIENDAS EN EE.UU.", 86, "ink", anchor="mm")
texto(d, (W * 3 // 4, H * 0.86), "TIENDAS EN MÉXICO", 86, "ink", anchor="mm")
guardar(img, "miniatura-B.jpg")
