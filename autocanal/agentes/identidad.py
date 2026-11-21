"""🪪 Identidad del canal: portada (banner), foto de perfil y descripción.

- Portada y descripción: se ponen solas en YouTube con la API (channelBanners.insert + channels.update).
- Foto de perfil: YouTube NO deja cambiarla por la API; se genera lista (800×800) para subirla en 3 clics.
Lo hecho se guarda en estilo/identidad_<canal>/ (portada.jpg, perfil.png, descripcion.txt).
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import config

FUENTE = config.ASSETS / "fuentes" / "LuckiestGuy-Regular.ttf"

# Lo que se dice del canal según su tema (sin inventar datos: qué hace el canal y a dónde acudir)
DESCRIPCIONES = {
    "fraudes": """🐑 Cuida Tu Lana: alertas de fraudes y estafas en México, para que no te quiten tu dinero.

Aquí te cuento, con pruebas y fuentes, qué estafas están pegando AHORA:
🚨 Apps de préstamo montadeudas: cómo operan, cómo reconocerlas y qué hacer si ya te están amenazando o exhibiendo con tus contactos.
📱 Fraudes por WhatsApp, llamadas, SMS, redes sociales y compras en línea.
🏦 Alertas de la Condusef y la Policía Cibernética explicadas fácil.
🛡️ Qué hacer si ya caíste y dónde denunciar.

Con Lanudo, el borrego que no se deja trasquilar 🐑

Suscríbete y activa la campanita 🔔 para enterarte antes de que le pase a alguien de tu familia. Comparte los videos: una alerta a tiempo vale más que mil denuncias.

ℹ️ Contenido informativo y educativo; no es asesoría legal ni financiera. Si eres víctima, acude a la Condusef y a la Policía Cibernética de tu estado (o llama al 088).

#CuidaTuLana #Fraudes #Montadeudas #Estafas #México""",
}
PALABRAS = {"fraudes": 'fraudes estafas montadeudas "apps de préstamo" condusef "policía cibernética" México '
                       '"cuida tu dinero" extorsión'}
LEMAS = {"fraudes": "ALERTAS DE FRAUDES Y MONTADEUDAS EN MÉXICO", "apps": "APPS QUE PROMETEN PAGAR: ¿PAGAN O SON ESTAFA?"}
COLORES = {"fraudes": ((10, 62, 52), (6, 30, 40), (255, 214, 10))}  # verde lana, fondo oscuro, amarillo alerta


def carpeta(cid: str) -> Path:
    c = config.ESTILO_DIR / f"identidad_{cid}"
    c.mkdir(parents=True, exist_ok=True)
    return c


def _fuente(t: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(FUENTE), t)
    except OSError:
        return ImageFont.load_default()


def _degradado(w: int, h: int, c1, c2) -> Image.Image:
    fondo = Image.new("RGB", (w, h), c2)
    d = ImageDraw.Draw(fondo)
    cx, cy, r = w / 2, h / 2, max(w, h) * 0.6
    for k in range(60, 0, -1):  # luz radial al centro
        f = k / 60
        col = tuple(int(c2[i] + (c1[i] - c2[i]) * (1 - f)) for i in range(3))
        d.ellipse((cx - r * f, cy - r * f * 0.7, cx + r * f, cy + r * f * 0.7), fill=col)
    return fondo.filter(ImageFilter.GaussianBlur(40))


def _texto(d: ImageDraw.ImageDraw, xy, texto: str, t: int, color, borde=(0, 0, 0), ancla="lm") -> None:
    d.text(xy, texto, font=_fuente(t), fill=color, anchor=ancla, stroke_width=max(4, t // 12), stroke_fill=borde)


def _ajustar(texto: str, ancho: int, t: int) -> int:
    while t > 20 and _fuente(t).getlength(texto) > ancho:
        t -= 4
    return t


def portada(cid: str, nombre: str, lema: str, mascota: Path | None, destino: Path) -> Path:
    """2560×1440 (lo que pide YouTube). Todo lo importante va en la zona segura del centro (1546×423), que es lo
    que se ve en celular."""
    w, h = 2560, 1440
    c1, c2, acento = COLORES.get(cid, ((30, 41, 82), (12, 16, 36), (255, 214, 10)))
    im = _degradado(w, h, c1, c2)
    d = ImageDraw.Draw(im)
    for x in range(-h, w, 90):  # rayas diagonales suaves de "alerta"
        d.line((x, h, x + h, 0), fill=tuple(min(255, v + 8) for v in c2), width=18)
    im = Image.blend(_degradado(w, h, c1, c2), im, 0.35)
    d = ImageDraw.Draw(im)
    sx, sy, sw, sh = (w - 1546) // 2, (h - 423) // 2, 1546, 423
    texto_ancho = sw - 420
    if mascota and mascota.exists():
        m = Image.open(mascota).convert("RGBA")
        m = m.crop(m.getbbox())
        alto = int(sh * 0.96)  # cabe completo en la zona que se ve en el celular
        m = m.resize((int(m.width * alto / m.height), alto), Image.LANCZOS)
        sombra = Image.new("RGBA", m.size, (0, 0, 0, 0))
        sombra.putalpha(m.getchannel("A").point(lambda a: int(a * 0.45)))
        sombra = sombra.filter(ImageFilter.GaussianBlur(18))
        x, y = sx + sw - m.width - 20, sy + (sh - alto) // 2
        im.paste(sombra, (x + 14, y + 18), sombra)
        im.paste(m, (x, y), m)
    else:
        texto_ancho = sw
    t = _ajustar(nombre.upper(), texto_ancho, 190)
    _texto(d, (sx, sy + sh * 0.40), nombre.upper(), t, (255, 255, 255), (0, 0, 0))
    t2 = _ajustar(lema, texto_ancho, 64)
    caja_y = sy + sh * 0.78
    ancho_lema = _fuente(t2).getlength(lema)
    d.rounded_rectangle((sx - 10, caja_y - t2 * 0.75, sx + ancho_lema + 30, caja_y + t2 * 0.75), radius=18, fill=acento)
    d.text((sx + 10, caja_y), lema, font=_fuente(t2), fill=(20, 20, 20), anchor="lm")
    im.convert("RGB").save(destino, "JPEG", quality=90, optimize=True)
    return destino


def perfil(cid: str, mascota: Path | None, destino: Path, nombre: str = "") -> Path:
    """800×800, la cara de la mascota grande sobre un círculo de color (YouTube la recorta en círculo)."""
    w = 800
    c1, c2, acento = COLORES.get(cid, ((30, 41, 82), (12, 16, 36), (255, 214, 10)))
    im = _degradado(w, w, c1, c2).convert("RGBA")
    d = ImageDraw.Draw(im)
    d.ellipse((24, 24, w - 24, w - 24), outline=acento, width=26)
    if mascota and mascota.exists():
        m = Image.open(mascota).convert("RGBA")
        m = m.crop(m.getbbox())
        cabeza = m.crop((0, 0, m.width, int(m.height * 0.80)))  # cabeza, copete y algo de lana (el círculo corta)
        esc = (w * 0.86) / cabeza.width
        cabeza = cabeza.resize((int(cabeza.width * esc), int(cabeza.height * esc)), Image.LANCZOS)
        mascara = Image.new("L", (w, w), 0)
        ImageDraw.Draw(mascara).ellipse((50, 50, w - 50, w - 50), fill=255)
        capa = Image.new("RGBA", (w, w), (0, 0, 0, 0))
        capa.paste(cabeza, ((w - cabeza.width) // 2, int(w * 0.10)), cabeza)
        capa.putalpha(Image.composite(capa.getchannel("A"), Image.new("L", (w, w), 0), mascara))
        im.alpha_composite(capa)
    else:
        iniciales = "".join(p[0] for p in nombre.split()[:3]).upper() or "TV"
        _texto(d, (w / 2, w / 2), iniciales, 300, (255, 255, 255), ancla="mm")
    im.convert("RGB").save(destino, "PNG", optimize=True)
    return destino


def descripcion(cid: str, info: dict) -> str:
    if info.get("nicho") in DESCRIPCIONES:
        return DESCRIPCIONES[info["nicho"]]
    from . import canales, claude, manual
    r = claude.json_estructurado(
        "Escribes la descripción de un canal de YouTube en español de México: clara, cálida, con lo que la gente "
        "encuentra en el canal, palabras que se buscan, una invitación a suscribirse y 3-5 hashtags. Máx. 900 "
        "caracteres. Nada inventado (ni datos de contacto, ni cifras, ni frecuencia de publicación).",
        f"CANAL: {info.get('nombre')}\nTEMA: {canales.NICHOS.get(info.get('nicho'), '')}\n\n{manual.leer(cid)[:3000]}",
        {"type": "object", "properties": {"descripcion": {"type": "string"}}, "required": ["descripcion"],
         "additionalProperties": False}, tarea="ideas", que="descripción del canal")
    return r["descripcion"].strip()[:4900]


def generar(cid: str) -> dict:
    """Hace portada, perfil y descripción (no toca YouTube)."""
    from . import canales
    info = canales.get(cid)
    nombre = info.get("nombre") or config.CANAL_NOMBRE
    c = carpeta(cid)
    portada(cid, nombre, LEMAS.get(info.get("nicho"), canales.NICHOS.get(info.get("nicho"), "")[:60].upper()),
            canales.mascota(cid, "feliz"), c / "portada.jpg")
    perfil(cid, canales.mascota(cid, "normal"), c / "perfil.png", nombre)
    texto = descripcion(cid, info)
    (c / "descripcion.txt").write_text(texto, encoding="utf-8")
    return estado(cid)


def estado(cid: str) -> dict:
    c = carpeta(cid)
    try:
        hecho = json.loads((c / "aplicado.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        hecho = {}
    return {"canal": cid, "portada": (c / "portada.jpg").exists(), "perfil": (c / "perfil.png").exists(),
            "descripcion": (c / "descripcion.txt").read_text(encoding="utf-8") if (c / "descripcion.txt").exists() else "",
            "aplicado": hecho}


def aplicar(cid: str, texto: str | None = None) -> dict:
    """Sube la portada y pone la descripción en YouTube (la foto de perfil, a mano: la API no lo permite)."""
    import time

    from googleapiclient.http import MediaFileUpload

    from . import youtube

    c = carpeta(cid)
    if texto is not None:
        (c / "descripcion.txt").write_text(texto.strip()[:4900], encoding="utf-8")
    if not (c / "portada.jpg").exists():
        generar(cid)
    yt = youtube._servicio(abrir_navegador=False, canal=cid)
    subida = yt.channelBanners().insert(media_body=MediaFileUpload(str(c / "portada.jpg"), mimetype="image/jpeg")).execute()
    canal = yt.channels().list(part="brandingSettings", mine=True).execute()["items"][0]
    antes = (canal.get("brandingSettings") or {}).get("channel") or {}
    # solo los campos que se pueden escribir (lo que no se manda se borra): se conservan los que ya tenía
    ch = {k: antes[k] for k in ("keywords", "defaultLanguage", "country", "unsubscribedTrailer") if antes.get(k)}
    ch["description"] = (c / "descripcion.txt").read_text(encoding="utf-8")
    ch.setdefault("country", config.CANAL_PAIS.upper())
    from . import canales
    if not ch.get("keywords") and canales.get(cid).get("nicho") in PALABRAS:
        ch["keywords"] = PALABRAS[canales.get(cid)["nicho"]]
    marca = {"channel": ch, "image": {"bannerExternalUrl": subida["url"]}}
    yt.channels().update(part="brandingSettings", body={"id": canal["id"], "brandingSettings": marca}).execute()
    hecho = {"t": time.time(), "canal_id": canal["id"]}
    (c / "aplicado.json").write_text(json.dumps(hecho), encoding="utf-8")
    return {**estado(cid), "url_canal": f"https://www.youtube.com/channel/{canal['id']}"}
