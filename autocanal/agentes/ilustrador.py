"""🎨 Miniaturas ilustradas (estilo "Apps que sí pagan"): caricatura 2D vibrante hecha con IA + tu plantilla.

1. Claude (diseñador experto en miniaturas y CTR) lee la app y su mecánica y escribe 3 conceptos MUY distintos:
   la escena (prompt visual en inglés para el generador), el titular en español y por qué jala clics.
2. Gemini dibuja cada escena en 16:9, SIN texto: personaje expresivo con el celular mostrando la mecánica,
   billetes, monedas, diamantes… (le pasamos el icono y capturas de la app como referencia).
3. El código pone encima tu plantilla: titular enorme con borde (letra Luckiest Guy), el icono de la app en su
   cuadro blanco arriba a la derecha y el botón de SUSCRÍBETE abajo a la izquierda. Así el texto nunca sale chueco.

Necesita GEMINI_API_KEY (Google AI Studio). Costo aprox.: PRECIO_IMAGEN USD por imagen (0.04 por defecto).
Sin clave, Dani hace las miniaturas de siempre (gratis).
"""
from __future__ import annotations

import base64
import io
import json
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from . import claude, config, estilo

W, H = 1920, 1080
FUENTE = config.BASE / "assets" / "fuentes" / "LuckiestGuy-Regular.ttf"
COLORES = {"blanco": ((255, 255, 255), (0, 0, 0)), "rojo": ((230, 30, 35), (255, 255, 255)),
           "amarillo": ((255, 214, 10), (0, 0, 0)), "naranja": ((255, 150, 20), (255, 255, 255))}


def disponible() -> bool:
    return bool(config.env("GEMINI_API_KEY"))


SCHEMA = {
    "type": "object",
    "properties": {
        "conceptos": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "escena": {"type": "string", "description": "Prompt visual detallado EN INGLÉS para el generador de imágenes"},
                "titular": {"type": "string", "description": "Titular en ESPAÑOL, 2 a 5 palabras, en pregunta o exclamación"},
                "color_titular": {"type": "string", "enum": list(COLORES)},
                "por_que": {"type": "string", "description": "Por qué este diseño y estas palabras suben el CTR, en una frase"},
            },
            "required": ["escena", "titular", "color_titular", "por_que"],
            "additionalProperties": False,
        }},
    },
    "required": ["conceptos"],
    "additionalProperties": False,
}

SISTEMA = """Eres un diseñador experto de miniaturas de YouTube y redactor especializado en análisis de apps móviles,
juegos y plataformas que prometen dinero. Tu trabajo: miniaturas optimizadas para clics (CTR) con un estilo coherente.

Reglas de la ESCENA (el prompt visual, en inglés, para el generador de imágenes):
- Estilo: caricatura 2D moderna, vibrante y muy colorida, como los anuncios de juegos móviles populares.
- Un personaje muy expresivo (asombro, felicidad extrema o concentración analítica), mediano-grande, en el CENTRO o
  el TERCIO DERECHO. El tercio IZQUIERDO queda libre (fondo sencillo) porque ahí va el titular, y la esquina superior
  derecha también (ahí va el icono de la app).
- El personaje sostiene o usa un smartphone cuya pantalla muestra la mecánica de la app (ruleta, tragamonedas,
  caminar, ver dramas, minar cripto, rompecabezas…). Elementos flotantes dinámicos: billetes, monedas de oro,
  diamantes o piezas según la app.
- El escenario va con el tema de la app (casino, parque, cuarto, ciudad cripto…).
- MUY IMPORTANTE: la imagen NO lleva ningún texto, letras, números ni logotipos (el texto lo ponemos nosotros).
- Formato 16:9.

Reglas del TITULAR (lo ponemos nosotros, enorme, a la izquierda):
- En español, 2 a 5 palabras, pregunta o exclamación con gancho: "¿PAGA O ESTAFA?", "¿DINERO FÁCIL O FRAUDE?",
  "¿DEMASIADO BUENO?", "¿LEGIT O FAKE?", "NUEVA APP ESTAFA??". Usa palabras clave que la gente busca: estafa, paga,
  legit, fake, review, real.
- Honesto con el veredicto: no digas "ESTAFA" afirmando si la evidencia no lo dice; en pregunta sí se vale.

Haz 3 conceptos MUY distintos entre sí (personaje, escenario, emoción y color del titular)."""


def conceptos(ficha: dict, expediente: dict, guion: dict) -> list[dict]:
    pedido = (f"APP: {ficha.get('title')}\nQUÉ PROMETE: {expediente.get('que_promete') or ficha.get('summary') or ''}\n"
              f"CÓMO DICE QUE PAGA: {expediente.get('como_dice_que_paga', '')}\n"
              f"VEREDICTO DE LA INVESTIGACIÓN: {expediente.get('veredicto')} — {expediente.get('resumen', '')}\n"
              f"MECÁNICA VISTA EN LA PRUEBA: {(expediente.get('prueba_propia') or {}).get('como_funciona', '')}\n"
              f"IDEAS DE TEXTO DEL GUIONISTA: {', '.join(guion.get('textos_miniatura') or [])}\n"
              f"TÍTULOS DEL VIDEO: {' | '.join((guion.get('titulos') or [])[:3])}\n\nHaz los 3 conceptos.")
    r = claude.json_estructurado(SISTEMA, pedido, SCHEMA, tarea="miniatura_ia", que="conceptos de miniatura")
    return r["conceptos"][:3]


def _parte_imagen(ruta: str | None, lado: int = 768) -> dict | None:
    if not ruta or not Path(ruta).exists():
        return None
    img = Image.open(ruta).convert("RGB")
    img.thumbnail((lado, lado))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return {"inlineData": {"mimeType": "image/jpeg", "data": base64.b64encode(buf.getvalue()).decode()}}


def _pedir(modelo: str, partes: list, con_formato: bool) -> requests.Response:
    config_gen = {"responseModalities": ["TEXT", "IMAGE"]}
    if con_formato:
        config_gen["imageConfig"] = {"aspectRatio": "16:9"}
    return requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent",
                         headers={"x-goog-api-key": config.env("GEMINI_API_KEY"), "Content-Type": "application/json"},
                         json={"contents": [{"role": "user", "parts": partes}], "generationConfig": config_gen},
                         timeout=180)


def dibujar(escena: str, referencias: list[str], destino: Path) -> Path:
    """Gemini dibuja la escena (16:9, sin texto). `referencias`: icono y capturas de la app."""
    refs = [p for p in (_parte_imagen(r) for r in referencias[:3]) if p]
    texto = (escena + "\n\nAspect ratio 16:9 (wide, 1920x1080). Vibrant modern 2D cartoon, mobile game ad style. "
             "Keep the left third with a simple background for a headline and the top-right corner clear. "
             "ABSOLUTELY NO text, letters, numbers, words, logos or watermarks anywhere in the image."
             + (" Use the attached images only as reference for the app's look and mechanics (colors, character, "
                "what the phone screen shows); do not copy their text." if refs else ""))
    partes = [*refs, {"text": texto}]
    modelos = list(dict.fromkeys([config.env("GEMINI_MODELO_IMAGEN", "gemini-2.5-flash-image"),
                                  "gemini-2.5-flash-image", "gemini-2.5-flash-image-preview"]))
    r, ultimo = None, ""
    for modelo in modelos:  # si un nombre de modelo o un campo no lo acepta Google, se prueba lo siguiente
        for con_formato in (True, False):
            r = _pedir(modelo, partes, con_formato)
            if r.status_code == 200:
                break
            ultimo = f"{modelo} ({r.status_code}): {r.text[:200]}"
            if r.status_code in (401, 403, 429):  # clave mala, sin permiso o sin saldo: no tiene caso seguir
                raise RuntimeError(f"Gemini no dibujó la miniatura: {ultimo}")
            if r.status_code == 404:
                break
        if r is not None and r.status_code == 200:
            break
    if r is None or r.status_code != 200:
        raise RuntimeError(f"Gemini no dibujó la miniatura: {ultimo}")
    for cand in r.json().get("candidates", []):
        for parte in (cand.get("content") or {}).get("parts", []):
            datos = (parte.get("inlineData") or parte.get("inline_data") or {}).get("data")
            if datos:
                img = Image.open(io.BytesIO(base64.b64decode(datos))).convert("RGB")
                ImageOps.fit(img, (W, H)).save(destino, quality=95)
                gasto = float(config.env("PRECIO_IMAGEN", "0.04") or 0)
                if claude.al_gastar and gasto:
                    claude.al_gastar(getattr(claude.contexto, "proyecto", None), "miniatura", "gemini (imagen)", gasto,
                                     0, 0, "dibujo de miniatura")
                return destino
    raise RuntimeError("Gemini no regresó imagen (puede que la haya bloqueado por sus reglas): "
                       + json.dumps(r.json())[:200])


# ---------- tu plantilla encima ----------
def _fuente(tam: int) -> ImageFont.FreeTypeFont:
    propia = estilo.archivo("fuente")
    return ImageFont.truetype(str(FUENTE if FUENTE.exists() else propia), tam) if (FUENTE.exists() or propia) \
        else ImageFont.load_default(tam)


def _titular(lienzo: Image.Image, texto: str, color: str) -> None:
    """Titular enorme a la izquierda, hasta 3 renglones, con borde grueso y sombra."""
    relleno, borde = COLORES.get(color, COLORES["blanco"])
    palabras = texto.upper().split()
    caja_w, caja_h = int(W * 0.46), int(H * 0.72)
    d = ImageDraw.Draw(lienzo)
    for tam in range(260, 90, -8):
        f = _fuente(tam)
        renglones, actual = [], ""
        for p in palabras:  # acomodar en renglones que quepan
            prueba = f"{actual} {p}".strip()
            if d.textlength(prueba, font=f) <= caja_w or not actual:
                actual = prueba
            else:
                renglones.append(actual)
                actual = p
        renglones.append(actual)
        alto = int(tam * 0.98) * len(renglones)
        sueltas = len(renglones) > 1 and any(len(r.strip("¿?¡!")) <= 2 for r in renglones)  # que no quede una "O" sola
        if len(renglones) <= 4 and alto <= caja_h and all(d.textlength(r, font=f) <= caja_w for r in renglones) \
                and not sueltas:
            break
    grosor = max(8, tam // 11)
    y = int(H * 0.47) - alto // 2
    sombra = Image.new("RGBA", lienzo.size, (0, 0, 0, 0))
    ds = ImageDraw.Draw(sombra)
    for i, r in enumerate(renglones):
        ds.text((70 + 10, y + i * int(tam * 0.98) + 12), r, font=f, fill=(0, 0, 0, 160), stroke_width=grosor,
                stroke_fill=(0, 0, 0, 160))
    lienzo.alpha_composite(sombra.filter(ImageFilter.GaussianBlur(6)))
    d = ImageDraw.Draw(lienzo)
    for i, r in enumerate(renglones):
        d.text((70, y + i * int(tam * 0.98)), r, font=f, fill=relleno, stroke_width=grosor, stroke_fill=borde)


def _icono(lienzo: Image.Image, icono: str | None) -> None:
    if not icono or not Path(icono).exists():
        return
    lado, marco, x, y = 400, 22, W - 400 - 70, 50
    img = ImageOps.fit(Image.open(icono).convert("RGBA"), (lado, lado))
    mascara = Image.new("L", (lado, lado), 0)
    ImageDraw.Draw(mascara).rounded_rectangle((0, 0, lado, lado), radius=lado // 6, fill=255)
    sombra = Image.new("RGBA", lienzo.size, (0, 0, 0, 0))
    ImageDraw.Draw(sombra).rounded_rectangle((x - marco + 10, y - marco + 16, x + lado + marco + 10, y + lado + marco + 16),
                                             radius=lado // 5, fill=(0, 0, 0, 120))
    lienzo.alpha_composite(sombra.filter(ImageFilter.GaussianBlur(14)))
    ImageDraw.Draw(lienzo).rounded_rectangle((x - marco, y - marco, x + lado + marco, y + lado + marco),
                                             radius=lado // 5, fill=(255, 255, 255, 255))
    lienzo.paste(img, (x, y), mascara)


def _suscribete(lienzo: Image.Image) -> None:
    d = ImageDraw.Draw(lienzo)
    f = _fuente(46)
    texto = "SUSCRÍBETE"
    x, y, alto = 60, H - 130, 76
    ancho = int(d.textlength(texto, font=f)) + 56
    d.rounded_rectangle((x, y, x + ancho, y + alto), radius=16, fill=(230, 30, 35))
    d.text((x + 28, y + 14), texto, font=f, fill=(255, 255, 255))
    bx = x + ancho + 18  # la campanita
    d.rounded_rectangle((bx, y, bx + alto, y + alto), radius=14, fill=(230, 30, 35))
    d.pieslice((bx + 18, y + 14, bx + alto - 18, y + alto - 6), 180, 360, fill=(255, 255, 255))
    d.rectangle((bx + 18, y + 36, bx + alto - 18, y + 54), fill=(255, 255, 255))
    d.ellipse((bx + alto // 2 - 7, y + 54, bx + alto // 2 + 7, y + 66), fill=(255, 255, 255))


def componer(fondo: Path, icono: str | None, titular: str, color: str, destino: Path) -> Path:
    lienzo = ImageOps.fit(Image.open(fondo).convert("RGB"), (W, H)).convert("RGBA")
    # un velo suave a la izquierda para que el titular resalte sobre cualquier dibujo
    velo = Image.new("L", (W, H), 0)
    ImageDraw.Draw(velo).rectangle((0, 0, int(W * 0.5), H), fill=70)
    lienzo.alpha_composite(Image.composite(Image.new("RGBA", (W, H), (0, 0, 0, 255)), Image.new("RGBA", (W, H), (0, 0, 0, 0)),
                                           velo.filter(ImageFilter.GaussianBlur(120))))
    _titular(lienzo, titular, color)
    _icono(lienzo, icono)
    _suscribete(lienzo)
    final = lienzo.convert("RGB")
    for calidad in (92, 85, 78, 70):  # YouTube acepta miniaturas de máximo 2 MB
        final.save(destino, "JPEG", quality=calidad, optimize=True)
        if destino.stat().st_size < 1_900_000:
            break
    return destino


def miniaturas(ficha: dict, expediente: dict, guion: dict, imagenes: dict, carpeta: Path) -> list[dict]:
    """Las 3 opciones ilustradas. Regresa [{archivo, texto, por_que}] (las que sí salieron)."""
    refs = [r for r in [imagenes.get("icono"), *(imagenes.get("capturas") or [])[:2]] if r]
    salida = []
    for i, c in enumerate(conceptos(ficha, expediente, guion), 1):
        fondo = carpeta / f"miniatura_ia_fondo_{i}.jpg"
        try:
            dibujar(c["escena"], refs, fondo)
        except Exception as exc:  # noqa: BLE001 — si una falla, siguen las demás
            print(f"  · la miniatura ilustrada {i} no salió: {exc}", flush=True)
            continue
        destino = carpeta / f"miniatura_{i}.jpg"
        componer(fondo, imagenes.get("icono"), c["titular"], c["color_titular"], destino)
        salida.append({"archivo": destino.name, "texto": c["titular"], "por_que": c["por_que"], "ilustrada": True})
    (carpeta / "miniaturas_ia.json").write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    return salida
