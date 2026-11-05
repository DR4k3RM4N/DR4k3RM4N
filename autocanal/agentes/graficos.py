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
    nombre = "fuente_negrita.ttf" if negrita else "fuente.ttf"
    candidatas = [config.BASE / "estilo" / nombre, config.BASE / "estilo" / "fuente_negrita.ttf", config.ASSETS / nombre,
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


# Estilo de miniatura por defecto (se reemplaza con lo que Dani aprende de tus referencias).
ESTILO_DEFECTO = {
    "fondo": "captura_desenfocada", "color_fondo": "#1E1B2E", "color_fondo_2": "#E53935",
    "color_texto": "#FFD60A", "color_borde_texto": "#000000", "color_acento": "#FF3B30",
    "posicion_texto": "derecha", "mayusculas": True, "tamano_texto": "enorme", "lado_icono": "izquierda",
    "lado_cara": "derecha", "elementos": [], "palabras_max": 4, "inclinacion_icono": -6,
}


def _rgb(hex_: str, defecto=(255, 255, 255)) -> tuple:
    try:
        h = hex_.lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except (ValueError, AttributeError):
        return defecto


def _fondo(spec: dict, captura, icono, size) -> Image.Image:
    MW, MH = size
    if spec["fondo"] == "color_solido":
        return Image.new("RGB", size, _rgb(spec["color_fondo"]))
    if spec["fondo"] == "degradado":
        a, b = _rgb(spec["color_fondo"]), _rgb(spec["color_fondo_2"])
        base = Image.new("RGB", size)
        d = ImageDraw.Draw(base)
        for x in range(MW):
            t = x / MW
            d.line([(x, 0), (x, MH)], fill=tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)))
        return base
    return fondo_desenfocado(captura or icono, size, oscuro=0.45)


def _texto_en_caja(d, texto: str, caja, tam_max: int, color, borde, sombra: bool) -> tuple[int, int]:
    """Escribe el texto lo más grande posible dentro de la caja. Devuelve (y_final, tamaño)."""
    x0, y0, x1, y1 = caja
    ancho, alto = x1 - x0, y1 - y0
    tam = tam_max
    while tam > 36:
        f = fuente(tam)
        palabras, lineas, actual = texto.split(), [], ""
        for p in palabras:
            prueba = (actual + " " + p).strip()
            if d.textlength(prueba, font=f) <= ancho or not actual:
                actual = prueba
            else:
                lineas.append(actual)
                actual = p
        lineas.append(actual)
        alto_total = int(len(lineas) * tam * 1.08)
        if alto_total <= alto and all(d.textlength(l, font=f) <= ancho for l in lineas):
            break
        tam -= 6
    y = y0 + (alto - alto_total) // 2
    grosor = max(4, tam // 11)
    for l in lineas:
        w = d.textlength(l, font=f)
        x = x0 + (ancho - w) / 2
        if sombra:
            d.text((x + grosor, y + grosor), l, font=f, fill=(0, 0, 0))
        d.text((x, y), l, font=f, fill=color, stroke_width=grosor, stroke_fill=borde)
        y += int(tam * 1.08)
    return y, tam


def _flecha(d, desde, hasta, color, grosor=22):
    import math
    (x0, y0), (x1, y1) = desde, hasta
    ang = math.atan2(y1 - y0, x1 - x0)
    punta = 60
    bx, by = x1 - punta * math.cos(ang), y1 - punta * math.sin(ang)
    d.line([(x0, y0), (bx, by)], fill=color, width=grosor)
    izq = (bx + punta * 0.6 * math.cos(ang + math.pi / 2), by + punta * 0.6 * math.sin(ang + math.pi / 2))
    der = (bx + punta * 0.6 * math.cos(ang - math.pi / 2), by + punta * 0.6 * math.sin(ang - math.pi / 2))
    d.polygon([(x1, y1), izq, der], fill=color)


def miniatura(texto: str, sello: str, icono_ruta: str | None, captura_ruta: str | None, destino: Path,
              spec: dict | None = None, cara_ruta: str | None = None, espejo: bool = False) -> Path:
    """Miniatura 1280x720 siguiendo el estilo `spec` (lo que Dani aprendió de tus referencias).
    `espejo` invierte los lados (para sacar otra opción)."""
    MW, MH = 1280, 720
    spec = {**ESTILO_DEFECTO, **(spec or {})}
    if cara_ruta is None:
        for c in (config.BASE / "estilo" / "cara.png", config.ASSETS / "cara.png"):
            if c.exists():
                cara_ruta = str(c)
                break
    icono, captura = abrir(icono_ruta), abrir(captura_ruta)
    cara = abrir(cara_ruta) if spec["lado_cara"] != "ninguno" else None
    img = _fondo(spec, captura, icono, (MW, MH))
    d = ImageDraw.Draw(img)
    acento = _rgb(spec["color_acento"], (255, 59, 48))

    lado_icono = spec["lado_icono"]
    if espejo:
        lado_icono = {"izquierda": "derecha", "derecha": "izquierda"}.get(lado_icono, lado_icono)
    lado_cara = spec["lado_cara"]
    if cara is not None:
        if espejo:
            lado_cara = {"izquierda": "derecha", "derecha": "izquierda"}.get(lado_cara, lado_cara)
        if lado_icono == lado_cara or lado_icono == "centro":
            lado_icono = "izquierda" if lado_cara == "derecha" else "derecha"

    # zonas: la cara ocupa su orilla; el icono y el texto se reparten el resto
    libre = [0, 0, MW, MH]
    if cara is not None:
        h = 690
        cara = cara.resize((int(cara.width * h / cara.height), h))
        cx = MW - cara.width + 30 if lado_cara == "derecha" else -30
        if lado_cara == "derecha":
            libre[2] = MW - int(cara.width * 0.78)
        else:
            libre[0] = int(cara.width * 0.78)

    vertical = spec["posicion_texto"] in ("arriba", "abajo") and cara is None
    tam_icono = 300 if cara is not None or vertical else 380
    if vertical:  # texto, sello e icono apilados
        ix = (MW - tam_icono) // 2
        if spec["posicion_texto"] == "arriba":
            iy = MH - tam_icono - 25
            caja_texto, y_sello = (60, 25, MW - 60, iy - 120), iy - 105
        else:
            iy = 25
            caja_texto, y_sello = (60, iy + tam_icono + 125, MW - 60, MH - 25), iy + tam_icono + 15
    else:
        mitad = (libre[0] + libre[2]) // 2
        if lado_icono == "izquierda":
            ix, caja_texto = libre[0] + 50, (mitad - 20, 60, libre[2] - 40, MH - 170)
        else:
            ix, caja_texto = libre[2] - tam_icono - 50, (libre[0] + 40, 60, mitad + 20, MH - 170)
        iy = (MH - tam_icono) // 2 - 20

    # icono de la app
    centro_icono = (ix + tam_icono // 2, iy + tam_icono // 2)
    if icono is not None:
        pieza = redondear(icono.resize((tam_icono, tam_icono)), tam_icono // 5)
        ang = spec["inclinacion_icono"] * (-1 if espejo else 1)
        pieza = pieza.rotate(ang, expand=True, resample=Image.BICUBIC)
        sombra = Image.new("RGBA", (pieza.width + 40, pieza.height + 40), (0, 0, 0, 0))
        ImageDraw.Draw(sombra).rounded_rectangle([20, 26, pieza.width + 20, pieza.height + 26], tam_icono // 5, fill=(0, 0, 0, 140))
        sombra = sombra.filter(ImageFilter.GaussianBlur(14))
        img.paste(sombra, (ix - 20 - (pieza.width - tam_icono) // 2, iy - 20 - (pieza.height - tam_icono) // 2), sombra)
        img.paste(pieza, (ix - (pieza.width - tam_icono) // 2, iy - (pieza.height - tam_icono) // 2), pieza)
        if "circulo" in spec["elementos"]:
            r = int(tam_icono * (0.66 if vertical else 0.72))
            d.ellipse([centro_icono[0] - r, centro_icono[1] - r, centro_icono[0] + r, centro_icono[1] + r], outline=acento, width=14)
        if sello == "NO PAGA":  # gran X sobre el icono
            m = int(tam_icono * 0.08)
            col = COLOR_SELLO["NO PAGA"]
            d.line([(ix + m, iy + m), (ix + tam_icono - m, iy + tam_icono - m)], fill=col, width=max(20, tam_icono // 11))
            d.line([(ix + tam_icono - m, iy + m), (ix + m, iy + tam_icono - m)], fill=col, width=max(20, tam_icono // 11))

    if cara is not None:
        img.paste(cara, (cx, MH - cara.height + 10), cara)

    # texto principal
    t = " ".join(texto.split()[:spec["palabras_max"] + 2])
    t = t.upper() if spec["mayusculas"] else t
    tam_max = 150 if spec["tamano_texto"] == "enorme" else 118
    y_fin, _ = _texto_en_caja(d, t, caja_texto, tam_max, _rgb(spec["color_texto"], AMARILLO),
                              _rgb(spec["color_borde_texto"], (0, 0, 0)), "sombra_texto" in spec["elementos"])

    # sello (NO PAGA, CUIDADO…) debajo del texto
    color_sello = COLOR_SELLO.get(sello, acento)
    fs = fuente(62)
    bw = d.textlength(sello, font=fs)
    sx = (caja_texto[0] + caja_texto[2]) / 2 - bw / 2
    sy = min(MH - 110, max(y_fin + 10, MH - 160)) if not vertical else y_sello
    sy = max(20, min(MH - 100, sy))
    d.rounded_rectangle([sx - 24, sy, sx + bw + 24, sy + 92], 18, fill=color_sello)
    d.text((sx, sy + 12), sello, font=fs, fill=BLANCO if color_sello != AMARILLO else (0, 0, 0))

    if "flecha" in spec["elementos"] and icono is not None and not vertical:
        hacia_izq = caja_texto[0] > ix
        inicio = (caja_texto[0] + 10, sy + 46) if hacia_izq else (caja_texto[2] - 10, sy + 46)
        fin = (ix + tam_icono + 10, iy + tam_icono - 40) if hacia_izq else (ix - 10, iy + tam_icono - 40)
        _flecha(d, inicio, fin, acento)
    if "marco" in spec["elementos"]:
        d.rectangle([0, 0, MW - 1, MH - 1], outline=acento, width=16)
    img.convert("RGB").save(destino, quality=92)
    return destino
