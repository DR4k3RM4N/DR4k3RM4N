"""Tarjetas para el video y la miniatura, dibujadas con Pillow."""
from __future__ import annotations

import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from . import config

W, H = 1920, 1080
FONDO = (14, 16, 22)
BLANCO = (245, 245, 247)
GRIS = (160, 165, 175)
ROJO = (255, 59, 48)
AMARILLO = (255, 214, 10)
VERDE = (52, 199, 89)
NARANJA = (255, 149, 0)

COLOR_VEREDICTO = {
    "estafa_comprobada": (ROJO, "NO PAGA"),
    "senales_de_alerta": (NARANJA, "CUIDADO"),
    "paga_pero_no_vale_la_pena": (AMARILLO, "NO VALE LA PENA"),
    "legitima": (VERDE, "SÍ PAGA"),
    "no_concluyente": (GRIS, "SIN PRUEBAS"),
}
COLOR_SELLO = {"NO PAGA": ROJO, "CUIDADO": NARANJA, "SÍ PAGA": VERDE, "¿PAGA?": AMARILLO}


def fuente(tam: int, negrita: bool = True) -> ImageFont.FreeTypeFont:
    propia = config.ASSETS / ("fuente_negrita.ttf" if negrita else "fuente.ttf")
    candidatas = [propia,
                  Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if negrita
                       else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
                  Path("C:/Windows/Fonts/arialbd.ttf" if negrita else "C:/Windows/Fonts/arial.ttf"),
                  Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf")]
    for c in candidatas:
        if c.exists():
            return ImageFont.truetype(str(c), tam)
    return ImageFont.load_default(tam)


def abrir(ruta: str | None) -> Image.Image | None:
    if not ruta or not Path(ruta).exists():
        return None
    return Image.open(ruta).convert("RGBA")


def redondear(img: Image.Image, radio: int) -> Image.Image:
    mascara = Image.new("L", img.size, 0)
    ImageDraw.Draw(mascara).rounded_rectangle([0, 0, *img.size], radio, fill=255)
    img = img.convert("RGBA")
    img.putalpha(mascara)
    return img


def fondo_desenfocado(img: Image.Image | None, size=(W, H), oscuro: float = 0.55) -> Image.Image:
    if img is None:
        base = Image.new("RGB", size, FONDO)
        d = ImageDraw.Draw(base)
        for y in range(size[1]):  # degradado sutil
            t = y / size[1]
            d.line([(0, y), (size[0], y)], fill=(int(14 + 20 * t), int(16 + 8 * t), int(22 + 30 * t)))
        return base
    base = ImageOps.fit(img.convert("RGB"), size).filter(ImageFilter.GaussianBlur(40))
    return Image.blend(base, Image.new("RGB", size, (0, 0, 0)), oscuro)


def texto_centrado(d: ImageDraw.ImageDraw, texto: str, y: int, tam: int, color=BLANCO,
                   ancho_max: int = 1600, borde: int = 0, x_centro: int = W // 2) -> int:
    f = fuente(tam)
    chars = max(8, int(ancho_max / (tam * 0.58)))
    for linea in textwrap.wrap(texto, chars):
        bw = d.textlength(linea, font=f)
        d.text((x_centro - bw / 2, y), linea, font=f, fill=color,
               stroke_width=borde, stroke_fill=(0, 0, 0))
        y += int(tam * 1.18)
    return y


def pegar_icono(lienzo: Image.Image, icono: Image.Image | None, x: int, y: int, tam: int) -> None:
    if icono is None:
        return
    lienzo.paste(redondear(icono.resize((tam, tam)), tam // 5), (x, y), redondear(icono.resize((tam, tam)), tam // 5))


def tarjeta_titulo(texto: str, icono_ruta: str | None, destino: Path, color=AMARILLO) -> Path:
    icono = abrir(icono_ruta)
    img = fondo_desenfocado(icono)
    pegar_icono(img, icono, W // 2 - 140, 170, 280)
    d = ImageDraw.Draw(img)
    texto_centrado(d, texto.upper(), 520, 110, color, borde=6)
    img.save(destino)
    return destino


def tarjeta_dato(texto: str, icono_ruta: str | None, destino: Path) -> Path:
    icono = abrir(icono_ruta)
    img = fondo_desenfocado(icono, oscuro=0.7)
    pegar_icono(img, icono, 80, 70, 140)
    d = ImageDraw.Draw(img)
    d.rectangle([W // 2 - 120, 330, W // 2 + 120, 342], fill=ROJO)
    texto_centrado(d, texto, 400, 96, BLANCO, borde=4)
    img.save(destino)
    return destino


def tarjeta_captura(captura_ruta: str | None, icono_ruta: str | None, destino: Path, etiqueta: str = "") -> Path:
    cap = abrir(captura_ruta)
    if cap is None:
        return tarjeta_dato(etiqueta or "", icono_ruta, destino)
    img = fondo_desenfocado(cap, oscuro=0.6)
    alto = 960
    ancho = int(cap.width * alto / cap.height)
    if ancho > 1700:  # captura horizontal
        ancho = 1700
        alto = int(cap.height * ancho / cap.width)
    pieza = redondear(cap.resize((ancho, alto)), 36)
    sombra = Image.new("RGBA", (ancho + 80, alto + 80), (0, 0, 0, 0))
    ImageDraw.Draw(sombra).rounded_rectangle([40, 40, ancho + 40, alto + 40], 40, fill=(0, 0, 0, 170))
    sombra = sombra.filter(ImageFilter.GaussianBlur(25))
    x, y = (W - ancho) // 2, (H - alto) // 2
    img.paste(sombra, (x - 40, y - 20), sombra)
    img.paste(pieza, (x, y), pieza)
    img.save(destino)
    return destino


def tarjeta_resena(resena: dict, icono_ruta: str | None, destino: Path) -> Path:
    icono = abrir(icono_ruta)
    img = fondo_desenfocado(icono, oscuro=0.75)
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = 260, 170, W - 260, H - 230
    d.rounded_rectangle([x0, y0, x1, y1], 40, fill=(255, 255, 255))
    d.ellipse([x0 + 60, y0 + 55, x0 + 160, y0 + 155], fill=(66, 133, 244))
    inicial = (resena.get("usuario") or "U")[0].upper()
    fi = fuente(56)
    d.text((x0 + 110 - d.textlength(inicial, font=fi) / 2, y0 + 70), inicial, font=fi, fill=BLANCO)
    d.text((x0 + 190, y0 + 60), (resena.get("usuario") or "Usuario")[:40], font=fuente(44), fill=(30, 30, 30))
    estrellas = int(resena.get("estrellas") or 1)
    d.text((x0 + 190, y0 + 115), "★" * estrellas + "☆" * (5 - estrellas), font=fuente(40), fill=(251, 188, 4))
    d.text((x0 + 420, y0 + 122), resena.get("fecha", ""), font=fuente(30, False), fill=(120, 120, 120))
    texto = resena.get("texto", "")
    if len(texto) > 330:
        texto = texto[:327].rsplit(" ", 1)[0] + "…"
    ft = fuente(46, False)
    y = y0 + 210
    for linea in textwrap.wrap(texto, 52):
        d.text((x0 + 70, y), linea, font=ft, fill=(40, 40, 40))
        y += 62
    if resena.get("likes"):
        d.text((x0 + 70, y1 - 80), f"{resena['likes']} personas encontraron útil esta reseña",
               font=fuente(32, False), fill=(110, 110, 110))
    img.save(destino)
    return destino


def tarjeta_veredicto(veredicto: str, icono_ruta: str | None, destino: Path, frase: str = "") -> Path:
    color, palabra = COLOR_VEREDICTO.get(veredicto, (GRIS, "VEREDICTO"))
    icono = abrir(icono_ruta)
    img = fondo_desenfocado(icono, oscuro=0.7)
    pegar_icono(img, icono, W // 2 - 130, 120, 260)
    d = ImageDraw.Draw(img)
    f = fuente(150)
    bw = d.textlength(palabra, font=f)
    d.rounded_rectangle([W // 2 - bw / 2 - 50, 440, W // 2 + bw / 2 + 50, 640], 30, outline=color, width=14)
    d.text((W // 2 - bw / 2, 455), palabra, font=f, fill=color)
    if frase:
        texto_centrado(d, frase, 720, 54, BLANCO)
    img.save(destino)
    return destino


def miniatura(texto: str, sello: str, icono_ruta: str | None, captura_ruta: str | None, destino: Path) -> Path:
    """Miniatura 1280x720. Si existe assets/cara.png (tu cara recortada, PNG transparente) se usa."""
    MW, MH = 1280, 720
    img = fondo_desenfocado(abrir(captura_ruta) or abrir(icono_ruta), (MW, MH), oscuro=0.45)
    d = ImageDraw.Draw(img)
    icono = abrir(icono_ruta)
    cara = abrir(str(config.ASSETS / "cara.png"))
    if icono is not None:
        pieza = redondear(icono.resize((380, 380)), 80).rotate(-6, expand=True, resample=Image.BICUBIC)
        img.paste(pieza, (60, 150), pieza)
        color = COLOR_SELLO.get(sello, ROJO)
        if sello == "NO PAGA":  # gran X sobre el icono
            d.line([(90, 190), (440, 540)], fill=color, width=34)
            d.line([(440, 190), (90, 540)], fill=color, width=34)
    if cara is not None:
        h = 700
        cara = cara.resize((int(cara.width * h / cara.height), h))
        img.paste(cara, (MW - cara.width + 40, MH - h), cara)
    zona_x = 760 if cara is None else 640
    texto_centrado(d, texto.upper(), 150, 112, AMARILLO, ancho_max=480 if cara is None else 420,
                   borde=8, x_centro=(470 + MW) // 2 if cara is None else zona_x - 80)
    color = COLOR_SELLO.get(sello, ROJO)
    fs = fuente(64)
    bw = d.textlength(sello, font=fs)
    sx = 900 - bw / 2 if cara is None else 470
    d.rounded_rectangle([sx - 24, 560, sx + bw + 24, 660], 18, fill=color)
    d.text((sx, 572), sello, font=fs, fill=BLANCO if color != AMARILLO else (0, 0, 0))
    img.convert("RGB").save(destino, quality=92)
    return destino
