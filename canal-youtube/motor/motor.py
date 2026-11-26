"""Motor de video de la serie ¿Quién MATÓ a…?

Lee el guion técnico (líneas "> " = narración) y el storyboard del episodio,
genera la voz, las tarjetas animadas, la música, los subtítulos y el video final.

Uso:
  python motor.py <carpeta_episodio> --hojas            # hojas de contacto para revisar tarjetas
  python motor.py <carpeta_episodio> --voz              # solo genera la voz
  python motor.py <carpeta_episodio> --render           # video completo
  python motor.py <carpeta_episodio> --render --escenas 1-2   # solo algunas escenas (prueba)

Voz propia: pon archivos voz/escena-01.wav … voz/escena-14.wav en la carpeta del episodio
y vuelve a correr --render. Esas escenas usarán tu voz en lugar de la de computadora.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import re
import shutil
import subprocess
import sys
import wave
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1920, 1080, 30
SR = 48000
INTRO = 0.7          # segundos de animación de entrada
XFADE = 8            # cuadros de fundido entre tarjetas
KB = 0.035           # zoom lento (Ken Burns)
LEAD = 0.6           # silencio al inicio
PARA_GAP = 0.35      # pausa entre frases
SCENE_GAP = 0.9      # pausa entre escenas
END_HOLD = 20.0      # pantalla final
TOP, BOT = 140, 110  # bandas fijas (encabezado y pie)
MOTOR = Path(__file__).resolve().parent
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"

C = {
    "bg": (17, 17, 18), "panel": (30, 30, 32), "panel2": (44, 44, 48), "ink": (243, 243, 240),
    "muted": (150, 150, 146), "tape": (255, 214, 10), "red": (230, 57, 70), "green": (45, 198, 83),
    "line": (66, 66, 70), "paper": (234, 228, 212), "paperink": (34, 32, 30), "papermuted": (120, 114, 104),
    "cork": (38, 33, 29), "black": (10, 10, 10),
}
TAGC = {"y": "tape", "r": "red", "g": "green", "m": "muted", "k": "paperink"}

# ---------------------------------------------------------------- utilidades

_fc = {}


def font(kind, size):
    size = int(size)
    key = (kind, size)
    if key in _fc:
        return _fc[key]
    F = "C:/Windows/Fonts/"
    var = {"display": "Bold Condensed", "display_sb": "SemiBold Condensed", "cond": "Condensed"}
    if kind in var:
        f = ImageFont.truetype(F + "bahnschrift.ttf", size)
        try:
            f.set_variation_by_name(var[kind])
        except Exception:
            f.set_variation_by_name(var[kind].encode())
    else:
        files = {"body": "segoeui.ttf", "bodyb": "seguisb.ttf", "mono": "consola.ttf", "monob": "consolab.ttf",
                 "serif": "georgia.ttf", "serifb": "georgiab.ttf", "serifi": "georgiai.ttf"}
        f = ImageFont.truetype(F + files[kind], size)
    _fc[key] = f
    return f


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease(p):
    p = clamp(p)
    return 1 - (1 - p) ** 3


def atoms_of(s, base):
    atoms, stack, pending = [], [base], False
    for tok in re.split(r"(</?[yrgmk]>)", s):
        if not tok:
            continue
        m = re.fullmatch(r"<(/?)([yrgmk])>", tok)
        if m:
            if m.group(1):
                if len(stack) > 1:
                    stack.pop()
            else:
                stack.append(TAGC[m.group(2)])
            continue
        for part in re.split(r"(\n|[ \t]+)", tok):
            if part == "":
                continue
            if part == "\n":
                atoms.append(("\n", None, False))
                pending = False
                continue
            if part.isspace():
                pending = True
                continue
            atoms.append((part, stack[-1], pending))
            pending = False
    return atoms


def units_of(atoms):
    units = []
    for a in atoms:
        if a[0] == "\n":
            units.append("\n")
        elif a[2] or not units or units[-1] == "\n":
            units.append([a])
        else:
            units[-1].append(a)
    return units


def layout(units, f, maxw):
    sw = f.getlength(" ")
    lines, widths = [[]], [0.0]
    for u in units:
        if u == "\n":
            lines.append([])
            widths.append(0.0)
            continue
        uw = sum(f.getlength(a[0]) for a in u)
        if lines[-1] and widths[-1] + sw + uw > maxw:
            lines.append([])
            widths.append(0.0)
        if lines[-1]:
            widths[-1] += sw
        lines[-1].append((u, uw))
        widths[-1] += uw
    return lines, widths


class Rich:
    def __init__(self, s, kind, maxw, maxh, smax, smin=24, lh=1.08, base="ink", maxlines=None):
        units = units_of(atoms_of(s, base))
        size = smax
        while True:
            f = font(kind, size)
            lines, widths = layout(units, f, maxw)
            h = len(lines) * size * lh
            ok = h <= maxh and max(widths) <= maxw and (maxlines is None or len(lines) <= maxlines)
            if ok or size <= smin:
                break
            size -= 3
        self.f, self.size, self.lines, self.widths, self.lh = f, size, lines, widths, lh
        self.h = len(lines) * size * lh
        self.w = max(widths) if widths else 0

    def draw(self, d, x, y, w, align="center", stroke=0):
        f, sw = self.f, self.f.getlength(" ")
        extra = dict(stroke_width=stroke, stroke_fill=(0, 0, 0)) if stroke else {}
        for i, (line, lw) in enumerate(zip(self.lines, self.widths)):
            cx = x + (w - lw) / 2 if align == "center" else (x + w - lw if align == "right" else x)
            yy = y + i * self.size * self.lh
            first = True
            for (u, _uw) in line:
                if not first:
                    cx += sw
                first = False
                for a in u:
                    d.text((cx, yy), a[0], font=f, fill=C[a[1]], **extra)
                    cx += f.getlength(a[0])
        return self.h


def make_bg():
    rng = np.random.default_rng(7)
    base = np.zeros((H, W, 3), np.float32)
    base[:] = C["bg"]
    base[::96, :, :] += 6
    base[:, ::96, :] += 6
    yy, xx = np.mgrid[0:H, 0:W]
    dist = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    base *= (1 - 0.45 * np.clip(dist - 0.35, 0, 1))[..., None]
    base += rng.normal(0, 3.2, (H, W, 1))
    return Image.fromarray(np.clip(base, 0, 255).astype(np.uint8))


BG = None
STYLE = "expediente"     # "expediente" (fondo oscuro con barras) o "cine" (material a pantalla completa)
_BG_OVERRIDE = None
_bg_cache = {}


def canvas():
    global BG
    if _BG_OVERRIDE is not None:
        img = _BG_OVERRIDE.copy()
        return img, ImageDraw.Draw(img)
    if BG is None:
        BG = make_bg()
    img = BG.copy()
    return img, ImageDraw.Draw(img)


def bg_image(f):
    """Fondo para gráficas en estilo cine: la foto o video desenfocado y oscurecido."""
    if f in _bg_cache:
        return _bg_cache[f]
    from PIL import ImageFilter
    p = media_path(f)
    if p.suffix.lower() in (".mp4", ".webm", ".mov"):
        cap = cv2.VideoCapture(str(p))
        cap.set(cv2.CAP_PROP_POS_MSEC, 1500)
        ok, fr = cap.read()
        cap.release()
        im = Image.fromarray(cv2.cvtColor(fr, cv2.COLOR_BGR2RGB))
    else:
        im = load_photo(f)
    im = cover(im, W, H).filter(ImageFilter.GaussianBlur(16))
    a = np.asarray(im).astype(np.float32) * 0.30
    yy, xx = np.mgrid[0:H, 0:W]
    dist = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    a *= (1 - 0.5 * np.clip(dist - 0.4, 0, 1))[..., None]
    out = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    _bg_cache[f] = out
    return out


def hazard(w, h, off=0):
    img = Image.new("RGB", (w, h), C["black"])
    d = ImageDraw.Draw(img)
    step = 44
    for x in range(-h * 2 + off, w + h * 2, step):
        d.polygon([(x, h), (x + h, 0), (x + h + step / 2, 0), (x + step / 2, h)], fill=C["tape"])
    return img


def tape_band(text, length, angle):
    band = Image.new("RGBA", (length, 78), C["tape"] + (255,))
    d = ImageDraw.Draw(band)
    f = font("display", 44)
    unit = f"  {text}  ·"
    x = 0
    while x < length:
        d.text((x, 39), unit, font=f, fill=C["black"], anchor="lm")
        x += f.getlength(unit)
    d.rectangle([0, 0, length, 5], fill=C["black"])
    d.rectangle([0, 73, length, 78], fill=C["black"])
    return band.rotate(angle, expand=True, resample=Image.BICUBIC)


def chrome(label, tag, src):
    img, d = canvas()
    d.text((80, 58), label, font=font("mono", 26), fill=C["muted"])
    if tag:
        f = font("monob", 26)
        tw = f.getlength(tag)
        x1 = W - 80
        d.rectangle([x1 - tw - 32, 48, x1, 92], fill=C["tape"])
        d.text((x1 - tw - 16, 70), tag, font=f, fill=C["black"], anchor="lm")
    if src:
        d.text((80, H - 64), "FUENTE: " + src.upper(), font=font("mono", 22), fill=C["muted"], anchor="lm")
    img.paste(hazard(W, 10), (0, H - 10))
    a = np.asarray(img)
    return a[:TOP].copy(), a[H - BOT:].copy()


# ---------------------------------------------------------------- íconos

def icon(d, kind, cx, cy, s=1.0):
    def P(x, y):
        return (cx + x * s, cy + y * s)
    ink, tape, red, panel2 = C["ink"], C["tape"], C["red"], C["panel2"]
    if kind in ("bowl", "bowl_flip"):
        flip = -1 if kind == "bowl_flip" else 1
        body = [P(-170, -40 * flip), P(170, -40 * flip), P(135, 120 * flip), P(-135, 120 * flip)]
        d.polygon(body, fill=panel2, outline=ink, width=int(7 * s))
        lid = [P(-195, -95 * flip), P(195, -50 * flip)] if flip == 1 else [P(-195, 50), P(195, 95)]
        d.rounded_rectangle([min(lid[0][0], lid[1][0]), min(lid[0][1], lid[1][1]),
                             max(lid[0][0], lid[1][0]), max(lid[0][1], lid[1][1])], radius=int(16 * s), fill=tape)
        tab = P(195, -72 * flip)
        d.rectangle([tab[0], tab[1] - 12 * s, tab[0] + 34 * s, tab[1] + 12 * s], fill=tape)
        if flip == -1:
            for i, (x, y) in enumerate([(-60, 150), (10, 175), (75, 145)]):
                pass  # sin gotas: no se cae nada
    elif kind == "vhs":
        d.rounded_rectangle([P(-260, -150), P(260, 150)], radius=int(14 * s), fill=panel2, outline=ink, width=int(6 * s))
        d.rectangle([P(-200, -110), P(200, -40)], fill=tape)
        for x in (-110, 110):
            d.ellipse([P(x - 62, -10), P(x + 62, 114)], outline=ink, width=int(6 * s))
            d.ellipse([P(x - 18, 34), P(x + 18, 70)], fill=ink)
    elif kind == "down":
        d.polygon([P(-70, -170), P(70, -170), P(70, 30), P(150, 30), P(0, 190), P(-150, 30), P(-70, 30)], fill=red)
    elif kind == "phone":
        d.rounded_rectangle([P(-120, -220), P(120, 220)], radius=int(30 * s), fill=panel2, outline=ink, width=int(6 * s))
        d.rectangle([P(-95, -170), P(95, 160)], fill=C["bg"])
        for i, wdt in enumerate((150, 110, 160, 90, 140)):
            y = -140 + i * 58
            d.rounded_rectangle([P(-80, y), P(-80 + wdt, y + 30)], radius=int(8 * s), fill=C["green"] if i % 2 else C["line"])
    elif kind == "pin":
        d.ellipse([P(-60, -150), P(60, -30)], fill=red)
        d.polygon([P(-50, -70), P(50, -70), P(0, 30)], fill=red)
        d.ellipse([P(-24, -114), P(24, -66)], fill=C["bg"])


# ---------------------------------------------------------------- tarjetas
X0, X1, Y0, Y1 = 140, W - 140, 170, H - 150
CW, CH = X1 - X0, Y1 - Y0


def c_quote(s, p):
    img, d = canvas()
    label, sub, ic = s.get("label"), s.get("sub"), s.get("icon")
    lab_h = 74 if label else 0
    ic_h = 420 if ic else 0
    sub_r = Rich(sub, "body", 1580, 200, s.get("subsize", 50), base="muted") if sub else None
    sub_h = (sub_r.h + 40) if sub_r else 0
    main = Rich(s["text"], s.get("font", "display"), s.get("maxw", 1520), CH - lab_h - sub_h - ic_h,
                s.get("size", 128), base=s.get("color", "ink"), lh=s.get("lh", 1.06))
    total = lab_h + ic_h + main.h + sub_h
    y = Y0 + (CH - total) / 2
    align = s.get("align", "center")
    if label:
        d.text((W / 2 if align == "center" else X0, y + 20), label, font=font("monob", 34), fill=C["tape"],
               anchor="mm" if align == "center" else "lm")
        y += lab_h
    if ic:
        icon(d, ic, W / 2, y + ic_h / 2 - 10, 1.0)
        y += ic_h
    main.draw(d, X0, y, CW, align)
    y += main.h + 40
    if sub_r:
        sub_r.draw(d, X0, y, CW, align)
    return img


def c_title(s, p):
    s2 = dict(s)
    s2.setdefault("size", 230)
    s2.setdefault("color", "ink")
    img = c_quote(s2, p)
    if s.get("tape"):
        b1 = tape_band("ESCENA DEL CRIMEN · NO PASAR", 2400, 2.2)
        b2 = tape_band("ESCENA DEL CRIMEN · NO PASAR", 2400, -1.8)
        img.paste(b1, (-240, int(192 - b1.height / 2)), b1)
        img.paste(b2, (-240, int(902 - b2.height / 2)), b2)
    return img


def fmt_num(v, dec):
    return f"{v:,.{dec}f}"


def c_bignum(s, p):
    img, d = canvas()
    txt = s.get("pre", "") + fmt_num(s["num"] * ease(p), s.get("dec", 0)) + s.get("suf", "")
    final_txt = s.get("pre", "") + fmt_num(s["num"], s.get("dec", 0)) + s.get("suf", "")
    label, cap = s.get("label"), s.get("cap")
    size = s.get("size", 300)
    f = font("display", size)
    while f.getlength(final_txt) > 1600 and size > 80:
        size -= 6
        f = font("display", size)
    cap_r = Rich(cap, "bodyb", 1620, 200, s.get("capsize", 54), base="ink") if cap else None
    total = (70 if label else 0) + size * 0.95 + ((cap_r.h + 50) if cap_r else 0)
    y = Y0 + (CH - total) / 2
    if label:
        d.text((W / 2, y + 18), label, font=font("monob", 34), fill=C["muted"], anchor="mm")
        y += 70
    d.text((W / 2, y + size * 0.47), txt, font=f, fill=C[s.get("color", "tape")], anchor="mm")
    y += size * 0.95 + 50
    if cap_r:
        cap_r.draw(d, X0, y, CW)
    return img


def c_bars(s, p):
    img, d = canvas()
    items = s["items"]
    n = len(items)
    rowh, gap = 118, 44
    label, cap = s.get("label"), s.get("cap")
    total = n * rowh + (n - 1) * gap + (80 if label else 0) + (110 if cap else 0)
    y = Y0 + (CH - total) / 2
    if label:
        d.text((X0, y + 20), label, font=font("monob", 34), fill=C["tape"], anchor="lm")
        y += 80
    labw = s.get("labw", 430)
    maxv = max(it[1] for it in items)
    bx = X0 + labw
    maxbw = CW - labw - 330
    for it in items:
        lab, val, col, vl = it
        lf = font("display_sb", 62)
        d.text((X0, y + rowh / 2), lab, font=lf, fill=C["ink"], anchor="lm")
        bw = maxbw * val / maxv * ease(p)
        d.rectangle([bx, y + 14, bx + max(bw, 4), y + rowh - 14], fill=C[col])
        d.text((bx + bw + 26, y + rowh / 2), vl, font=font("display", 80), fill=C[col], anchor="lm")
        y += rowh + gap
    if cap:
        r = Rich(cap, "body", CW, 110, 44, base="muted")
        r.draw(d, X0, y + 10, CW, "left")
    return img


_stamp_cache = {}


def stamp_layer(text, sub, color, rot, scale=1.0):
    key = (text, sub, color, rot, scale)
    if key in _stamp_cache:
        return _stamp_cache[key]
    f = font("display", int(170 * scale))
    fs = font("monob", int(46 * scale))
    tw = f.getlength(text)
    sw = fs.getlength(sub) if sub else 0
    w = int(max(tw, sw) + 130 * scale)
    h = int((205 + (75 if sub else 0)) * scale)
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    col = C[color] + (255,)
    ld.rounded_rectangle([6, 6, w - 6, h - 6], radius=int(18 * scale), outline=col, width=int(13 * scale))
    ld.rounded_rectangle([int(26 * scale), int(26 * scale), w - int(26 * scale), h - int(26 * scale)],
                         radius=int(10 * scale), outline=col, width=max(2, int(4 * scale)))
    ld.text((w / 2, int(112 * scale)), text, font=f, fill=col, anchor="mm")
    if sub:
        ld.text((w / 2, h - int(62 * scale)), sub, font=fs, fill=col, anchor="mm")
    a = np.array(layer)
    rng = np.random.default_rng(abs(hash(text)) % 1000)
    m = rng.random(a.shape[:2]) < 0.12
    a[..., 3][m] = (a[..., 3][m] * 0.25).astype(np.uint8)
    layer = Image.fromarray(a).rotate(rot, expand=True, resample=Image.BICUBIC)
    _stamp_cache[key] = layer
    return layer


def paste_scaled(img, layer, cx, cy, sc, alpha=1.0):
    if sc != 1.0:
        layer = layer.resize((max(1, int(layer.width * sc)), max(1, int(layer.height * sc))), Image.BICUBIC)
    if alpha < 1.0:
        a = np.array(layer)
        a[..., 3] = (a[..., 3] * alpha).astype(np.uint8)
        layer = Image.fromarray(a)
    img.paste(layer, (int(cx - layer.width / 2), int(cy - layer.height / 2)), layer)


def c_stamp(s, p):
    img, d = canvas()
    layer = stamp_layer(s["text"], s.get("sub"), s.get("color", "red"), s.get("rot", -7))
    cap = s.get("cap")
    cy = 520 if cap else 545
    q = clamp(p / 0.45)
    paste_scaled(img, layer, W / 2, cy, 1.45 - 0.45 * ease(q), clamp(q * 2.5))
    if cap:
        r = Rich(cap, "bodyb", 1400, 120, 50)
        r.draw(d, X0, cy + layer.height / 2 + 40, CW)
    return img


def c_list(s, p):
    img, d = canvas()
    items = s["items"]
    n = len(items)
    label = s.get("label")
    lab_h = 80 if label else 0
    size = s.get("size", 78)
    while True:
        rs = [Rich(it, "display_sb", 1340, 999, size, smin=size, lh=1.05) for it in items]
        total = sum(r.h for r in rs) + (n - 1) * 34
        if total <= CH - lab_h or size <= 40:
            break
        size -= 4
    y = Y0 + (CH - total - lab_h) / 2
    if label:
        d.text((X0 + 60, y + 20), label, font=font("monob", 34), fill=C["tape"], anchor="lm")
        y += lab_h
    shown = n if p >= 1 else int(p * n) + 1
    for i, r in enumerate(rs):
        if i < shown:
            d.rectangle([X0 + 60, y + size * 0.32, X0 + 60 + size * 0.36, y + size * 0.68], fill=C["tape"])
            r.draw(d, X0 + 60 + size * 0.7, y, 1340, "left")
        y += r.h + 34
    return img


def silhouette(d, box):
    x0, y0, x1, y1 = box
    d.rounded_rectangle(box, radius=16, fill=C["panel"], outline=C["line"], width=3)
    cx = (x0 + x1) / 2
    hr = (x1 - x0) * 0.22
    d.ellipse([cx - hr, y0 + (y1 - y0) * 0.18, cx + hr, y0 + (y1 - y0) * 0.18 + 2 * hr], fill=C["panel2"])
    d.pieslice([x0 + (x1 - x0) * 0.12, y0 + (y1 - y0) * 0.62, x1 - (x1 - x0) * 0.12, y1 + (y1 - y0) * 0.45],
               180, 360, fill=C["panel2"])
    d.rounded_rectangle(box, radius=16, outline=C["line"], width=3)


def c_profile(s, p):
    img, d = canvas()
    silhouette(d, (X0 + 20, 200, X0 + 480, 880))
    x = X0 + 560
    y = 250
    if s.get("label"):
        d.text((x, y), s["label"], font=font("monob", 34), fill=C["tape"])
        y += 70
    name = Rich(s["name"], "display", 1080, 340, 170, lh=1.0)
    name.draw(d, x, y, 1080, "left")
    y += name.h + 30
    for ln in s["lines"]:
        r = Rich(ln, "body", 1060, 200, 50, base="muted", lh=1.2)
        r.draw(d, x, y, 1060, "left")
        y += r.h + 16
    return img


def c_place(s, p):
    img, d = canvas()
    icon(d, "pin", X0 + 130, 560, 1.4)
    x = X0 + 300
    rn = Rich(s["name"], "display", 1300, 360, s.get("size", 140), lh=1.0)
    note = Rich(s["note"], "body", 1260, 200, 46, base="muted", lh=1.2) if s.get("note") else None
    total = (70 if s.get("date") else 0) + rn.h + ((note.h + 34) if note else 0)
    y = 540 - total / 2
    if s.get("date"):
        d.text((x, y), s["date"], font=font("monob", 42), fill=C["tape"])
        y += 70
    rn.draw(d, x, y, 1300, "left")
    y += rn.h + 34
    if note:
        note.draw(d, x, y, 1260, "left")
    return img


def c_route(s, p):
    img, d = canvas()
    bw, bh, cy = 600, 300, 500
    boxes = [(X0, s["a"]), (X1 - bw, s["b"])]
    for i, (bx, (place, country)) in enumerate(boxes):
        col = C["red"] if i == 0 else C["green"]
        d.rounded_rectangle([bx, cy - bh / 2, bx + bw, cy + bh / 2], radius=14, fill=C["panel"], outline=col, width=5)
        r = Rich(place, "display_sb", bw - 60, 170, 64, lh=1.02)
        r.draw(d, bx + 30, cy - r.h / 2 - 26, bw - 60)
        d.text((bx + bw / 2, cy + bh / 2 - 42), country, font=font("monob", 30), fill=col, anchor="mm")
    ax0, ax1 = X0 + bw + 30, X1 - bw - 30
    e = ease(p)
    xe = ax0 + (ax1 - 40 - ax0) * e
    d.rectangle([ax0, cy - 9, xe, cy + 9], fill=C["tape"])
    if e > 0.85:
        d.polygon([(xe - 4, cy - 34), (xe + 50, cy), (xe - 4, cy + 34)], fill=C["tape"])
    if s.get("over"):
        d.text(((ax0 + ax1) / 2, cy - 70), s["over"], font=font("display", 64), fill=C["red"], anchor="mm")
    if s.get("cap"):
        r = Rich(s["cap"], "bodyb", CW, 140, 50)
        r.draw(d, X0, cy + bh / 2 + 70, CW)
    return img


def c_file(s, p):
    img, d = canvas()
    x0, y0, x1, y1 = 430, 215, 1490, 890
    d.polygon([(x0 + 10, y0 + 14), (x0 + 330, y0 + 14), (x0 + 370, y0 + 54), (x1 + 10, y0 + 54), (x1 + 10, y1 + 14), (x0 + 10, y1 + 14)],
              fill=(8, 8, 8))
    d.polygon([(x0, y0), (x0 + 320, y0), (x0 + 360, y0 + 40), (x1, y0 + 40), (x1, y1), (x0, y1)], fill=C["paper"])
    d.line([(x0 + 40, y0 + 120), (x1 - 40, y0 + 120)], fill=C["papermuted"], width=2)
    d.text((x0 + 60, y0 + 85), s.get("num", "EXPEDIENTE N.º 002"), font=font("monob", 40), fill=C["paperink"], anchor="lm")
    r = Rich(s["title"], "display", 900, 230, 200, lh=1.0, base="paperink")
    r.draw(d, x0 + 60, y0 + 160, 900, "left")
    y = y0 + 160 + r.h + 30
    for ln in s.get("lines", []):
        d.text((x0 + 64, y), ln, font=font("mono", 38), fill=C["paperink"])
        y += 58
    q = clamp((p - 0.2) / 0.5)
    if q > 0:
        layer = stamp_layer(s.get("stamp", "CASO ABIERTO"), None, "red", -12, 0.62)
        paste_scaled(img, layer, x1 - 235, y1 - 100, 1.4 - 0.4 * ease(q), clamp(q * 2.5))
    return img


def board_card(i, revealed, label):
    cw, ch = 400, 520
    cimg = Image.new("RGBA", (cw, ch), C["paper"] + (255,))
    cd = ImageDraw.Draw(cimg)
    cd.rectangle([22, 22, cw - 22, 360], fill=(24, 24, 25))
    if revealed:
        cd.text((cw / 2, 190), str(i + 1), font=font("display", 250), fill=C["tape"], anchor="mm")
    else:
        cd.text((cw / 2, 190), "?", font=font("display", 250), fill=C["muted"], anchor="mm")
    cd.text((cw / 2, 395), f"SOSPECHOSO #{i + 1}", font=font("monob", 30), fill=C["papermuted"], anchor="mm")
    r = Rich(label if revealed else "???", "display_sb", cw - 40, 110, 52, lh=1.0, base="paperink")
    r.draw(cd, 20, 425 + (95 - r.h) / 2, cw - 40)
    return cimg


def c_board(s, p):
    img, d = canvas()
    d.rounded_rectangle([X0, 175, X1, 905], radius=10, fill=C["cork"], outline=C["line"], width=3)
    d.text((X0 + 40, 215), s.get("label", "SOSPECHOSOS"), font=font("monob", 34), fill=C["tape"], anchor="lm")
    labels = s.get("labels", ["SU PROPIO NOMBRE", "LA FIESTA", "LA DEUDA"])
    nb = len(labels)
    step = 520 if nb <= 3 else 400
    xs = [W / 2 + (i - (nb - 1) / 2) * step for i in range(nb)]
    top = 265
    pins = [(x, top + 8) for x in xs]
    for a, b in zip(pins, pins[1:]):
        mid = ((a[0] + b[0]) / 2, a[1] + 60)
        d.line([a, mid, b], fill=C["red"], width=5, joint="curve")
    for i, x in enumerate(xs):
        rev = s["reveal"][i]
        card = board_card(i, rev, labels[i])
        if nb > 3:
            card = card.resize((int(card.width * 0.86), int(card.height * 0.86)), Image.BICUBIC)
        if s.get("new") == i and p < 1:
            e = ease(p)
            if e < 0.5:
                card = board_card(i, False, labels[i])
                if nb > 3:
                    card = card.resize((int(card.width * 0.86), int(card.height * 0.86)), Image.BICUBIC)
                wsc = 1 - 2 * e
            else:
                wsc = 2 * e - 1
            wsc = max(0.04, wsc)
            card = card.resize((max(1, int(card.width * wsc)), card.height), Image.BICUBIC)
        img.paste(card, (int(x - card.width / 2), top), card)
        d.ellipse([x - 16, top - 8, x + 16, top + 24], fill=C["red"])
        if s.get("hi") == i:
            hw, hh = (card.width / 2 + 22), card.height + 22
            d.rounded_rectangle([x - hw, top - 22, x + hw, top + hh], radius=16, outline=C["red"], width=9)
            if s.get("hi_label"):
                tw = font("display", 54).getlength(s["hi_label"])
                d.rectangle([x - tw / 2 - 20, top + hh - 22, x + tw / 2 + 20, top + hh + 48], fill=C["red"])
                d.text((x, top + hh + 13), s["hi_label"], font=font("display", 54), fill=C["ink"], anchor="mm")
    return img


def c_def(s, p):
    img, d = canvas()
    x0, y0, x1, y1 = 300, 215, 1620, 880
    d.rectangle([x0 + 12, y0 + 12, x1 + 12, y1 + 12], fill=(8, 8, 8))
    d.rectangle([x0, y0, x1, y1], fill=C["paper"])
    x = x0 + 80
    d.text((x, y0 + 70), s["word"], font=font("serifb", 120), fill=C["paperink"])
    d.text((x + font("serifb", 120).getlength(s["word"]) + 30, y0 + 125), s.get("gram", "m."), font=font("serifi", 48), fill=C["papermuted"])
    y = y0 + 240
    r = Rich(s["definition"], "serif", x1 - x0 - 160, 220, 54, lh=1.3, base="paperink")
    r.draw(d, x, y, x1 - x0 - 160, "left")
    y += r.h + 30
    if s.get("origin"):
        r2 = Rich(s["origin"], "serifi", x1 - x0 - 160, 120, 44, lh=1.3, base="paperink")
        r2.draw(d, x, y, x1 - x0 - 160, "left")
        y += r2.h + 40
    if s.get("mark"):
        f = font("bodyb", 50)
        tw = f.getlength(s["mark"])
        e = ease(p)
        d.rectangle([x - 12, y - 6, x - 12 + (tw + 24) * e, y + 70], fill=C["tape"])
        d.text((x, y), s["mark"], font=f, fill=C["paperink"])
    return img


def c_doc(s, p):
    img, d = canvas()
    x0, y0, x1, y1 = 470, 175, 1450, 870
    d.rectangle([x0 + 12, y0 + 12, x1 + 12, y1 + 12], fill=(8, 8, 8))
    d.rectangle([x0, y0, x1, y1], fill=C["paper"])
    d.text((x0 + 60, y0 + 60), s.get("head", "DOCUMENTO DE LA EMPRESA"), font=font("monob", 32), fill=C["paperink"])
    d.text((x1 - 60, y0 + 60), "RECREACIÓN", font=font("monob", 26), fill=C["red"], anchor="ra")
    rng = np.random.default_rng(11)
    y = y0 + 150
    name_y = y0 + 330
    while y < y1 - 70:
        if abs(y - name_y) < 30:
            f = font("mono", 42)
            lab = s.get("role", "Vicepresidenta: ")
            d.text((x0 + 60, name_y), lab, font=f, fill=C["paperink"])
            nx = x0 + 60 + f.getlength(lab)
            nf = font("monob", 46)
            d.text((nx, name_y - 2), s["name"], font=nf, fill=C["paperink"])
            nw = nf.getlength(s["name"])
            e = ease(clamp((p - 0.15) / 0.85))
            d.rectangle([nx - 8, name_y - 6, nx - 8 + (nw + 16) * e, name_y + 52], fill=C["black"])
            y = name_y + 90
            continue
        wdt = rng.integers(380, 820)
        d.rounded_rectangle([x0 + 60, y, x0 + 60 + wdt, y + 18], radius=8, fill=(198, 191, 175))
        y += 46
    if s.get("cap"):
        r = Rich(s["cap"], "bodyb", CW, 70, 44)
        r.draw(d, X0, y1 + 22, CW)
    return img


def c_donut(s, p):
    img, d = canvas()
    cx, cy, ro, ri = 620, 555, 270, 175
    e = ease(p)
    ang = 360 * s["pct"] / 100 * e
    d.ellipse([cx - ro, cy - ro, cx + ro, cy + ro], fill=C["red"])
    d.pieslice([cx - ro, cy - ro, cx + ro, cy + ro], -90, -90 + ang, fill=C["green"])
    d.ellipse([cx - ri, cy - ri, cx + ri, cy + ri], fill=C["bg"])
    d.text((cx, cy), f"~{int(round(s['pct'] * e))}%", font=font("display", 120), fill=C["green"], anchor="mm")
    x = 1030
    y = 330
    if s.get("label"):
        d.text((x, y), s["label"], font=font("monob", 34), fill=C["tape"])
        y += 80
    for col, txt in (("green", s["a"]), ("red", s["b"])):
        d.rectangle([x, y + 14, x + 40, y + 54], fill=C[col])
        r = Rich(txt, "display_sb", 680, 200, 64, lh=1.02)
        r.draw(d, x + 70, y, 680, "left")
        y += r.h + 50
    if s.get("note"):
        r = Rich(s["note"], "body", 720, 200, 42, base="muted", lh=1.2)
        r.draw(d, x, y + 10, 720, "left")
    return img


def c_timeline(s, p):
    img, d = canvas()
    ev = s["events"]
    hi = s.get("hi")
    his = set(hi if isinstance(hi, (list, tuple)) else ([hi] if hi is not None else []))
    n = len(ev)
    lx0, lx1, ly = X0 + 60, X1 - 60, 560
    e = ease(p)
    d.rectangle([lx0, ly - 4, lx0 + (lx1 - lx0) * e, ly + 4], fill=C["line"])
    xs = [lx0 + (lx1 - lx0) * ((i + 0.5) / n) for i in range(n)]
    slot = (lx1 - lx0) / n
    if s.get("label"):
        d.text((X0, Y0 + 20), s["label"], font=font("monob", 34), fill=C["tape"], anchor="lm")
    for i, (yr, txt) in enumerate(ev):
        if xs[i] > lx0 + (lx1 - lx0) * e + 1:
            continue
        on = i in his
        r = 26 if on else 13
        col = C["tape"] if on else C["muted"]
        d.ellipse([xs[i] - r, ly - r, xs[i] + r, ly + r], fill=col)
        fy = font("display", 84 if on else 58)
        tw = min(slot * (1.0 if n <= 4 else 1.9), 560)
        rt = Rich(txt, "bodyb" if on else "body", tw, 220, 42 if on else 34, base="ink" if on else "muted", lh=1.15)
        if n <= 4:
            # año arriba de la línea, texto abajo
            d.text((xs[i], ly - 44), str(yr), font=fy, fill=col, anchor="ms")
            rt.draw(d, xs[i] - tw / 2, ly + 44, tw)
        elif i % 2 == 0:
            # arriba: año pegado a la línea y el texto encima
            d.text((xs[i], ly - 40), str(yr), font=fy, fill=col, anchor="ms")
            rt.draw(d, xs[i] - tw / 2, ly - 40 - fy.size - 14 - rt.h, tw)
        else:
            # abajo: año pegado a la línea y el texto debajo
            d.text((xs[i], ly + 40), str(yr), font=fy, fill=col, anchor="mt")
            rt.draw(d, xs[i] - tw / 2, ly + 40 + fy.size + 14, tw)
    return img


def c_stats(s, p):
    img, d = canvas()
    items = s["items"]
    n = len(items)
    colw = CW / n
    y = Y0 + 160
    if s.get("label"):
        d.text((W / 2, Y0 + 50), s["label"], font=font("monob", 34), fill=C["tape"], anchor="mm")
    shown = n if p >= 1 else int(p * n) + 1
    for i, (val, txt) in enumerate(items):
        if i >= shown:
            continue
        cx = X0 + colw * i + colw / 2
        size = 150
        f = font("display", size)
        while f.getlength(val) > colw - 60:
            size -= 6
            f = font("display", size)
        d.text((cx, y + 80), val, font=f, fill=C[s.get("color", "tape")], anchor="mm")
        r = Rich(txt, "body", colw - 80, 300, 44, base="ink", lh=1.2)
        r.draw(d, cx - (colw - 80) / 2, y + 200, colw - 80)
        if i:
            d.line([(X0 + colw * i, y), (X0 + colw * i, y + 420)], fill=C["line"], width=2)
    if s.get("cap"):
        r = Rich(s["cap"], "body", CW, 100, 40, base="muted")
        r.draw(d, X0, Y1 - 80, CW)
    return img


def c_end(s, p):
    img, d = canvas()
    r = Rich(s.get("title", "¿QUIÉN <y>MATÓ</y> A…?"), "display", 1500, 220, 190)
    r.draw(d, X0, 205, CW)
    d.text((W / 2, 470), s.get("sub", "SUSCRÍBETE PARA EL PRÓXIMO EXPEDIENTE"), font=font("monob", 40), fill=C["tape"], anchor="mm")
    d.rounded_rectangle([300, 560, 1000, 900], radius=12, fill=C["panel"], outline=C["line"], width=3)
    d.ellipse([1240, 600, 1560, 920], fill=C["panel"], outline=C["line"], width=3)
    return img


# ---------------------------------------------------------------- fotos y videos reales
EP_DIR = Path(".")
RY0, RY1 = TOP, H - BOT          # zona visible para material a pantalla completa
_media = {}


def media_path(f):
    p = Path(f)
    return p if p.is_absolute() else EP_DIR / p


def load_photo(f):
    if f not in _media:
        from PIL import ImageOps
        im = Image.open(media_path(f))
        im = ImageOps.exif_transpose(im).convert("RGB")
        _media[f] = im
    return _media[f]


def cover(im, w, h, pos=(0.5, 0.5)):
    iw, ih = im.size
    s = max(w / iw, h / ih)
    nw, nh = max(w, int(iw * s + 0.5)), max(h, int(ih * s + 0.5))
    im = im.resize((nw, nh), Image.LANCZOS)
    x, y = int((nw - w) * pos[0]), int((nh - h) * pos[1])
    return im.crop((x, y, x + w, y + h))


_grad = {}


def gradient_layer(strength=0.85, start=0.45):
    key = (strength, start)
    if key not in _grad:
        a = np.zeros((H, W), np.float32)
        y0 = int(RY0 + (RY1 - RY0) * start)
        ramp = np.linspace(0, 1, RY1 - y0) ** 1.4 * strength
        a[y0:RY1, :] = ramp[:, None]
        a[RY0:RY0 + 120, :] = np.maximum(a[RY0:RY0 + 120, :], np.linspace(0.45, 0, 120)[:, None])
        layer = np.zeros((H, W, 4), np.uint8)
        layer[..., 3] = (a * 255).astype(np.uint8)
        _grad[key] = Image.fromarray(layer, "RGBA")
    return _grad[key]


def caption_on(img, s):
    """Pone la capa de texto (degradado + etiqueta + texto) sobre una foto."""
    base = img.convert("RGBA")
    base.alpha_composite(caption_layer(s))
    return base.convert("RGB")


def caption_layer(s):
    """Capa transparente con el texto que va encima de una foto o video.
    - head="…": titular enorme al centro (estilo "10 AÑOS DESPUÉS"), sobre imagen oscurecida.
    - caja=("17", "AÑOS ANTES\nPOR ESCRITO"): caja semitransparente al centro con número grande + texto.
    - si no: etiqueta + texto + subtítulo abajo a la izquierda, sobre degradado oscuro."""
    if s.get("head"):
        base = Image.new("RGBA", (W, H), (0, 0, 0, int(255 * s.get("shade", 0.45))))
        d = ImageDraw.Draw(base)
        r = Rich(s["head"], "display", 1720, 620, s.get("size", 230), lh=0.98)
        sub = Rich(s["sub"], "bodyb", 1500, 140, 50, lh=1.2) if s.get("sub") else None
        total = r.h + ((sub.h + 30) if sub else 0)
        y = (H - total) / 2
        r.draw(d, 100, y, W - 200, "center", stroke=6)
        if sub:
            sub.draw(d, 210, y + r.h + 30, W - 420, "center", stroke=3)
        return base
    if s.get("caja"):
        base = Image.new("RGBA", (W, H), (0, 0, 0, 40))
        d = ImageDraw.Draw(base)
        big, txt = s["caja"]
        fb = font("display", s.get("size", 190))
        bw = fb.getlength(big)
        rt = Rich(txt, "display_sb", 900, 260, 84, lh=1.0)
        pad, gap = 56, 34
        box_w = pad * 2 + bw + gap + rt.w
        box_h = max(fb.size * 0.95, rt.h) + pad * 1.4
        cx, cy = W / 2, s.get("caja_y", H / 2)
        x0, y0 = cx - box_w / 2, cy - box_h / 2
        d.rounded_rectangle([x0, y0, x0 + box_w, y0 + box_h], radius=14, fill=(24, 24, 26, 200))
        d.text((x0 + pad, cy), big, font=fb, fill=C[s.get("color", "tape")] + (255,), anchor="lm")
        rt.draw(d, x0 + pad + bw + gap, cy - rt.h / 2 + 4, rt.w + 2, "left")
        if s.get("sub"):
            sr = Rich(s["sub"], "bodyb", 1400, 120, 46, lh=1.2)
            sr.draw(d, 260, y0 + box_h + 30, W - 520, "center", stroke=3)
        return base
    if not (s.get("text") or s.get("label") or s.get("sub")):
        return gradient_layer(0.35, 0.7).copy()
    base = gradient_layer(s.get("shade", 0.88), 0.35).copy()
    d = ImageDraw.Draw(base)
    y = RY1 - (100 if STYLE == "cine" else 54)
    sub = Rich(s["sub"], "bodyb", 1500, 120, 44, base="ink", lh=1.2) if s.get("sub") else None
    main = Rich(s["text"], "display", 1560, 270, s.get("size", 104), lh=1.02, base="ink") if s.get("text") else None
    if sub:
        y -= sub.h
        sub.draw(d, X0, y, 1500, "left", stroke=2)
        y -= 18
    if main:
        y -= main.h
        main.draw(d, X0, y, 1560, "left", stroke=4)
        y -= 14
    if s.get("label"):
        f = font("monob", 34)
        tw = f.getlength(s["label"])
        d.rectangle([X0 - 12, y - 52, X0 + tw + 12, y - 4], fill=C["tape"] + (255,))
        d.text((X0, y - 28), s["label"], font=f, fill=C["black"] + (255,), anchor="lm")
    return base


def c_photo(s, p):
    img, d = canvas()
    ph = load_photo(s["file"])
    if s.get("mode", "full") == "full":
        im = cover(ph, W, RY1 - RY0, s.get("pos", (0.5, 0.5)))
        if s.get("bw") or s.get("head"):
            im = im.convert("L").convert("RGB")
        img.paste(im, (0, RY0))
        return caption_on(img, s)
    # modo "frame": foto impresa sobre el fondo, con cinta en las esquinas
    side = s.get("side", "left")
    has_txt = bool(s.get("text") or s.get("sub"))
    maxw, maxh = (980, 680) if has_txt else (1400, 720)
    sc = min(maxw / ph.width, maxh / ph.height)
    pw, phh = int(ph.width * sc), int(ph.height * sc)
    framed = Image.new("RGBA", (pw + 36, phh + 36), (240, 236, 226, 255))
    framed.paste(ph.resize((pw, phh), Image.LANCZOS), (18, 18))
    rot = s.get("rot", -2.0 if side == "left" else 2.0)
    framed = framed.rotate(rot, expand=True, resample=Image.BICUBIC)
    shadow = Image.new("RGBA", framed.size, (0, 0, 0, 0))
    shadow.paste((0, 0, 0, 150), mask=framed.split()[3])
    cx = (X0 + 40 + framed.width / 2) if (has_txt and side == "left") else ((X1 - 40 - framed.width / 2) if has_txt else W / 2)
    cy = (RY0 + RY1) / 2
    img.paste(shadow, (int(cx - framed.width / 2 + 16), int(cy - framed.height / 2 + 18)), shadow)
    img.paste(framed, (int(cx - framed.width / 2), int(cy - framed.height / 2)), framed)
    d = ImageDraw.Draw(img)
    for (tx, ty, ang) in ((cx - framed.width / 2 + 40, cy - framed.height / 2 + 10, 35), (cx + framed.width / 2 - 40, cy - framed.height / 2 + 10, -35)):
        t = Image.new("RGBA", (140, 42), C["tape"] + (215,)).rotate(ang, expand=True)
        img.paste(t, (int(tx - t.width / 2), int(ty - t.height / 2)), t)
    if has_txt:
        tx0 = (cx + framed.width / 2 + 60) if side == "left" else X0
        tw = (X1 - tx0) if side == "left" else (cx - framed.width / 2 - 60 - X0)
        blocks = []
        if s.get("label"):
            blocks.append(("label", None, 60))
        main = Rich(s["text"], "display", tw, 420, s.get("size", 92), lh=1.04) if s.get("text") else None
        sub = Rich(s["sub"], "body", tw, 300, 42, base="muted", lh=1.22) if s.get("sub") else None
        total = (60 if s.get("label") else 0) + (main.h + 24 if main else 0) + (sub.h if sub else 0)
        y = cy - total / 2
        if s.get("label"):
            d.text((tx0, y + 18), s["label"], font=font("monob", 32), fill=C["tape"], anchor="lm")
            y += 60
        if main:
            main.draw(d, tx0, y, tw, "left")
            y += main.h + 24
        if sub:
            sub.draw(d, tx0, y, tw, "left")
    return img


class VideoSrc:
    def __init__(self, s):
        self.path = str(media_path(s["file"]))
        self.ss, self.speed = s.get("ss", 0.0), s.get("speed", 1.0)
        self.loop_len = s.get("len")  # segundos del tramo que se repite (desde ss)
        self.pos, self.bw = s.get("pos", (0.5, 0.5)), s.get("bw", bool(s.get("head")))
        self._open()
        fw = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        fh = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        rh = RY1 - RY0
        sc = max(W / fw, rh / fh)
        self.nw, self.nh = max(W, int(fw * sc + 0.5)), max(rh, int(fh * sc + 0.5))
        self.cx, self.cy = int((self.nw - W) * self.pos[0]), int((self.nh - rh) * self.pos[1])
        lay = np.asarray(caption_layer(s)).astype(np.float32)
        self.ov_rgb = lay[..., :3]
        self.ov_a = lay[..., 3:4] / 255.0

    def _open(self):
        self.cap = cv2.VideoCapture(self.path)
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30
        self.n = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
        self.idx, self.cur = -1, None

    def frame(self, t, base):
        tt = t * self.speed
        if self.loop_len:
            tt = tt % self.loop_len
        want = int((self.ss + tt) * self.fps) % max(1, self.n - 2)
        if want < self.idx:
            self.cap.release()
            self._open()
        while self.idx < want:
            ok, fr = self.cap.read()
            if not ok:
                self.cap.release()
                self._open()
                want = 0
                ok, fr = self.cap.read()
                if not ok:
                    break
            self.idx += 1
            self.cur = fr
        fr = cv2.resize(self.cur, (self.nw, self.nh), interpolation=cv2.INTER_AREA)
        fr = fr[self.cy:self.cy + RY1 - RY0, self.cx:self.cx + W]
        fr = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY if self.bw else cv2.COLOR_BGR2RGB)
        if self.bw:
            fr = cv2.cvtColor(fr, cv2.COLOR_GRAY2RGB)
        out = base.copy()
        out[RY0:RY1] = fr
        y0 = RY0
        seg = out[y0:RY1].astype(np.float32)
        a = self.ov_a[y0:RY1]
        out[y0:RY1] = (seg * (1 - a) + self.ov_rgb[y0:RY1] * a).astype(np.uint8)
        return out


def c_split(s, p):
    """Dos fotos en pantalla dividida en diagonal, con su etiqueta abajo (estilo "Chili's vs Vips")."""
    img, d = canvas()
    a = cover(load_photo(s["a"]), W, RY1 - RY0, s.get("pos_a", (0.5, 0.5)))
    b = cover(load_photo(s["b"]), W, RY1 - RY0, s.get("pos_b", (0.5, 0.5)))
    if s.get("bw_a"):
        a = a.convert("L").convert("RGB")
    if s.get("bw_b"):
        b = b.convert("L").convert("RGB")
    hh = RY1 - RY0
    e = ease(p)
    off = int((1 - e) * 220)
    top_x, bot_x = W * 0.56, W * 0.44
    mask = Image.new("L", (W, hh), 0)
    ImageDraw.Draw(mask).polygon([(0, 0), (top_x, 0), (bot_x, hh), (0, hh)], fill=255)
    canvas_ab = b.copy()
    canvas_ab.paste(a, (-off, 0), mask)
    img.paste(canvas_ab, (0, RY0))
    d = ImageDraw.Draw(img)
    d.line([(top_x, RY0), (bot_x, RY1)], fill=C["ink"], width=10)
    base = img.convert("RGBA")
    base.alpha_composite(gradient_layer(0.8, 0.55))
    d = ImageDraw.Draw(base)
    for txt, x0, col in ((s.get("la"), X0, s.get("col_a", "red")), (s.get("lb"), W / 2 + 120, s.get("col_b", "green"))):
        if txt:
            r = Rich(txt, "display", 700, 200, s.get("size", 96), lh=1.0, base=col)
            r.draw(d, x0, RY1 - 70 - r.h, 700, "left", stroke=5)
    if s.get("head"):
        r = Rich(s["head"], "display", 1500, 220, 120, lh=1.0)
        r.draw(d, 210, RY0 + 60, W - 420, "center", stroke=6)
    return base.convert("RGB")


def c_video(s, p):
    v = VideoSrc(s)
    img, _ = canvas()
    return Image.fromarray(v.frame(0.0, np.asarray(img)))


CARDS = {
    "quote": c_quote, "title": c_title, "bignum": c_bignum, "bars": c_bars, "stamp": c_stamp, "list": c_list,
    "profile": c_profile, "place": c_place, "route": c_route, "file": c_file, "board": c_board, "def": c_def,
    "doc": c_doc, "donut": c_donut, "timeline": c_timeline, "stats": c_stats, "end": c_end,
    "photo": c_photo, "video": c_video, "split": c_split,
}


def intro_of(spec):
    if "intro" in spec:
        return spec["intro"]
    t = spec["t"]
    if t == "list":
        return 0.45 * len(spec["items"])
    if t == "stats":
        return 0.5 * len(spec["items"])
    if t in ("bignum", "bars", "donut", "timeline", "route"):
        return 1.0
    if t in ("doc",):
        return 1.4
    if t in ("stamp", "file", "board", "def"):
        return 0.8
    if t == "split":
        return 0.5
    return 0.0


# ---------------------------------------------------------------- episodio

def load_episode(ep_dir):
    global EP_DIR, STYLE, RY0, RY1
    EP_DIR = ep_dir
    sys.path.insert(0, str(MOTOR))
    spec = importlib.util.spec_from_file_location("storyboard", ep_dir / "storyboard.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ep = mod.EP
    STYLE = ep.get("estilo", "expediente")
    if STYLE == "cine":
        RY0, RY1 = 0, H
    guion = (ep_dir / ep["guion"]).read_text(encoding="utf-8")
    scenes, cur = [], None
    for line in guion.splitlines():
        m = re.match(r"^## ESCENA\s+(\d+)\s*·\s*(.*)$", line)
        if m:
            cur = dict(num=int(m.group(1)), title=m.group(2).strip(), paras=[])
            scenes.append(cur)
            continue
        if cur is not None and line.startswith("> "):
            cur["paras"].append(dict(text=line[2:].strip()))
    if len(scenes) != len(ep["escenas"]):
        raise SystemExit(f"El guion tiene {len(scenes)} escenas y el storyboard {len(ep['escenas'])}.")
    for sc, sb in zip(scenes, ep["escenas"]):
        if len(sc["paras"]) != len(sb["cards"]):
            raise SystemExit(f"Escena {sc['num']}: {len(sc['paras'])} frases en el guion, {len(sb['cards'])} en el storyboard.")
        sc["tag"] = sb.get("tag", "")
        sc["capitulo"] = sb.get("capitulo", sc["title"])
        for para, cards in zip(sc["paras"], sb["cards"]):
            para["cards"] = cards if isinstance(cards, list) else [cards]
            fondo = sb.get("fondo")
            if STYLE == "cine" and fondo:
                for c in para["cards"]:
                    full_media = c["t"] in ("video", "split") or (c["t"] == "photo" and c.get("mode", "full") == "full")
                    if not full_media and "bg" not in c:
                        c["bg"] = fondo
    return ep, scenes


def prep_text(text, fon):
    """Texto listo para SSML: quita comas de miles, aplica la fonética, escapa y convierte … en pausa."""
    s = text
    s = re.sub(r"(?<=\d),(?=\d{3}\b)", "", s)
    for k in sorted(fon, key=len, reverse=True):
        s = re.sub(r"(?<![\wÁÉÍÓÚáéíóúÑñ])" + re.escape(k) + r"(?![\wÁÉÍÓÚáéíóúÑñ])", fon[k], s)
    s = s.replace('"', "").replace("“", "").replace("”", "").replace("«", "").replace("»", "")
    s = xml_escape(s)
    return s.replace("…", '<break time="450ms"/>')


def to_ssml(text, fon):
    return ('<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="es-MX">'
            + prep_text(text, fon) + "</speak>")


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        print(r.stdout[-2000:], r.stderr[-3000:])
        raise SystemExit(f"Falló: {' '.join(map(str, cmd[:4]))} …")
    return r


def read_wav48(path):
    with wave.open(str(path), "rb") as w:
        sr, n, ch = w.getframerate(), w.getnframes(), w.getnchannels()
        a = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        a = a.reshape(-1, ch).mean(axis=1)
    if sr != SR:
        raise SystemExit(f"{path} no está a {SR} Hz")
    return a


def to48(src, dst):
    run([FFMPEG, "-y", "-v", "error", "-i", str(src), "-ac", "1", "-ar", str(SR), "-sample_fmt", "s16", str(dst)])


def make_voice(ep, scenes, out):
    vdir = out / "voz_tts"
    vdir.mkdir(parents=True, exist_ok=True)
    motor_voz = ep.get("voz_motor", "windows")
    fon = ep.get("fonetica_azure", ep.get("fonetica", {})) if motor_voz == "azure" else ep.get("fonetica", {})
    todo = []
    for sc in scenes:
        for para in sc["paras"]:
            if motor_voz == "azure":
                import voz_azure
                ssml = voz_azure.ssml(prep_text(para["text"], fon), ep["voz"], ep.get("voz_velocidad", "0%"))
            else:
                ssml = to_ssml(para["text"], fon)
            h = hashlib.sha1((motor_voz + ep.get("voz", "Raul") + ssml).encode()).hexdigest()[:12]
            para["wav"] = vdir / f"{h}.wav"
            if not para["wav"].exists():
                todo.append(dict(id=h, ssml=ssml, out=str(vdir / f"{h}_16k.wav"), final=str(para["wav"])))
    if todo and motor_voz == "azure":
        import voz_azure
        print(f"Generando voz con Azure ({ep['voz']}) para {len(todo)} frases…", flush=True)
        for k, it in enumerate(todo, 1):
            tmp = Path(it["final"]).with_suffix(".tmp.wav")
            voz_azure.sintetizar(it["ssml"], tmp)
            to48(tmp, it["final"])
            tmp.unlink()
            if k % 10 == 0:
                print(f"  {k}/{len(todo)}", flush=True)
        todo = []
    if todo:
        lst = out / "tts_lista.json"
        lst.write_text(json.dumps(todo, ensure_ascii=True), encoding="utf-8")
        print(f"Generando voz para {len(todo)} frases…", flush=True)
        run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(MOTOR / "tts.ps1"),
             "-Lista", str(lst), "-Voz", ep.get("voz", "Raul")])
        for it in todo:
            to48(it["out"], it["final"])
            Path(it["out"]).unlink()
    # duraciones
    for sc in scenes:
        mine = out.parent / "voz" / f"escena-{sc['num']:02d}.wav"
        if mine.exists():
            conv = out / f"voz_escena-{sc['num']:02d}_48k.wav"
            to48(mine, conv)
            dur = len(read_wav48(conv)) / SR
            chars = [len(pp["text"]) for pp in sc["paras"]]
            sc["own"] = conv
            for pp, c in zip(sc["paras"], chars):
                pp["dur"] = dur * c / sum(chars)
                pp["own"] = True
        else:
            for pp in sc["paras"]:
                with wave.open(str(pp["wav"]), "rb") as w:
                    pp["dur"] = w.getnframes() / w.getframerate()


def build_timeline(ep, scenes):
    segs = []
    t = LEAD
    for sc in scenes:
        sc["start"] = t
        for j, pp in enumerate(sc["paras"]):
            last = j == len(sc["paras"]) - 1
            gap = SCENE_GAP if last else (0.0 if pp.get("own") else PARA_GAP)
            span = pp["dur"] + gap
            pp["start"] = t
            ws = [c.get("w", 1.0) for c in pp["cards"]]
            tt = t
            for c, wt in zip(pp["cards"], ws):
                dd = span * wt / sum(ws)
                segs.append(dict(start=tt, dur=dd, spec=c, tag=sc["tag"], scene=sc["num"]))
                tt += dd
            t += span
    segs.append(dict(start=t, dur=END_HOLD, spec=ep.get("end", {"t": "end"}), tag="", scene=99))
    return segs, t + END_HOLD


# ---------------------------------------------------------------- render

def render_card(spec, p):
    global _BG_OVERRIDE
    full_media = spec["t"] in ("video", "split") or (spec["t"] == "photo" and spec.get("mode", "full") == "full")
    if spec.get("bg") and not full_media:
        _BG_OVERRIDE = bg_image(spec["bg"])
    try:
        return CARDS[spec["t"]](spec, p)
    finally:
        _BG_OVERRIDE = None


def make_chrome(label, tag, src):
    """Expediente: barras arriba y abajo. Cine: solo el crédito chiquito abajo a la izquierda."""
    if STYLE != "cine":
        return ("exp", chrome(label, tag, src))
    if not src:
        return ("cine", None)
    f = font("monob", 22)
    txt = src.upper()
    w = min(int(f.getlength(txt)) + 24, W - 80)
    h = 40
    lay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(lay).text((10, h / 2), txt, font=f, fill=(235, 235, 235, 235), anchor="lm",
                             stroke_width=2, stroke_fill=(0, 0, 0, 210))
    a = np.asarray(lay).astype(np.float32)
    return ("cine", (H - 28 - h, 28, a[..., :3], a[..., 3:4] / 255.0))


def apply_chrome(fr, ch):
    kind, data = ch
    if kind == "exp":
        top, bot = data
        fr[:TOP] = top
        fr[H - BOT:] = bot
    elif data is not None:
        y, x, rgb, a = data
        h, w = a.shape[:2]
        reg = fr[y:y + h, x:x + w].astype(np.float32)
        fr[y:y + h, x:x + w] = (reg * (1 - a) + rgb * a).astype(np.uint8)
    return fr


def contact_sheets(ep, scenes, out):
    segs = []
    for sc in scenes:
        for pp in sc["paras"]:
            for c in pp["cards"]:
                segs.append((sc, c))
    segs.append((dict(num=99, tag=""), ep.get("end", {"t": "end"})))
    per = 12
    tw, th = 640, 360
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for k in range(0, len(segs), per):
        sheet = Image.new("RGB", (tw * 3, th * 4), (60, 60, 60))
        for i, (sc, c) in enumerate(segs[k:k + per]):
            img = render_card(c, 1.0)
            a = apply_chrome(np.asarray(img).copy(), make_chrome(ep["label"], sc.get("tag", ""), c.get("src")))
            im = Image.fromarray(a).resize((tw - 6, th - 6), Image.LANCZOS)
            sheet.paste(im, ((i % 3) * tw + 3, (i // 3) * th + 3))
            ImageDraw.Draw(sheet).text(((i % 3) * tw + 12, (i // 3) * th + 8), f"{k + i + 1} · E{sc['num']}",
                                       font=font("monob", 22), fill=(255, 80, 80))
        pth = out / f"hoja-{k // per + 1:02d}.jpg"
        sheet.save(pth, quality=85)
        paths.append(pth)
    print("\n".join(map(str, paths)))


def render_video(ep, segs, total, out, path):
    cmd = [FFMPEG, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-c:v", "libx264", "-preset", "faster", "-crf", "19", "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", str(path)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    prev = None
    total_frames = round(total * FPS)
    done = 0
    for k, seg in enumerate(segs):
        f0 = round(seg["start"] * FPS)
        f1 = round((seg["start"] + seg["dur"]) * FPS)
        n = max(1, f1 - f0)
        spec = seg["spec"]
        intro = intro_of(spec)
        ch = make_chrome(ep["label"], seg["tag"], spec.get("src"))
        cache = {}
        drift = 1 if k % 2 == 0 else -1
        last = None
        vsrc = VideoSrc(spec) if spec["t"] == "video" else None
        bg_arr = np.asarray(canvas()[0]) if vsrc else None
        for i in range(n):
            t = i / FPS
            if vsrc is not None:
                fr = vsrc.frame(t, bg_arr)
            else:
                p = 1.0 if intro <= 0 else min(1.0, t / intro)
                key = round(p * 48) / 48
                if key not in cache:
                    cache = {kk: vv for kk, vv in cache.items() if kk == 1.0}
                    cache[key] = np.asarray(render_card(spec, key))
                base = cache[key]
                z = 1.0 + (KB * 1.6 if spec["t"] == "photo" else KB) * (i / max(1, n - 1))
                M = np.float32([[z, 0, (1 - z) * W / 2 + drift * 10 * (i / n)], [0, z, (1 - z) * H / 2]])
                fr = cv2.warpAffine(base, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
            fr = apply_chrome(fr, ch)
            if prev is not None and i < XFADE:
                a = (i + 1) / (XFADE + 1)
                fr = cv2.addWeighted(fr, a, prev, 1 - a, 0)
            proc.stdin.write(fr.tobytes())
            last = fr
        prev = last
        done += n
        if k % 10 == 0:
            print(f"  video {done / total_frames * 100:5.1f}%", flush=True)
    # relleno por redondeo
    while done < total_frames:
        proc.stdin.write(prev.tobytes())
        done += 1
    proc.stdin.close()
    proc.wait()


def boom():
    t = np.arange(int(1.0 * SR)) / SR
    f = 62 * np.exp(-t * 1.2)
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = np.sin(ph) * np.exp(-4.0 * t) * 0.55
    nz = np.random.default_rng(1).normal(0, 1, len(t)) * np.exp(-28 * t) * 0.12
    return (s + nz).astype(np.float32)


def whoosh():
    """Barrido de aire corto para transiciones (ruido filtrado con envolvente)."""
    n = int(0.55 * SR)
    t = np.arange(n) / SR
    nz = np.random.default_rng(5).normal(0, 1, n)
    k = 60
    nz = np.convolve(nz, np.ones(k) / k, mode="same")      # suaviza: suena a "aire"
    env = np.minimum(1, t / 0.22) * np.exp(-np.maximum(0, t - 0.22) * 9)
    s = nz * env
    return (s / (np.abs(s).max() + 1e-9) * 0.22).astype(np.float32)


def build_audio(ep, scenes, segs, total, out):
    narr = np.zeros(int((total + 1) * SR), np.float32)
    for sc in scenes:
        if sc.get("own"):
            a = read_wav48(sc["own"])
            i0 = int(sc["paras"][0]["start"] * SR)
            narr[i0:i0 + len(a)] += a[: len(narr) - i0]
            continue
        for pp in sc["paras"]:
            a = read_wav48(pp["wav"])
            i0 = int(pp["start"] * SR)
            narr[i0:i0 + len(a)] += a
    b = boom()
    wh = whoosh()
    for seg in segs:
        sp = seg["spec"]
        i0 = int(seg["start"] * SR)
        if sp.get("sfx") == "boom" or sp["t"] == "stamp" or (sp["t"] == "board" and sp.get("new") is not None):
            narr[i0:i0 + len(b)] += b[: len(narr) - i0]
        elif sp.get("sfx") == "whoosh" or sp.get("head") or sp["t"] == "split":
            j0 = max(0, i0 - int(0.18 * SR))
            narr[j0:j0 + len(wh)] += wh[: len(narr) - j0]
    narr = np.clip(narr, -1, 1)
    npath = out / "narracion.wav"
    with wave.open(str(npath), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((narr * 32767).astype(np.int16).tobytes())
    mpath = out / "musica.wav"
    expr = ("0.10*sin(2*PI*55*t)*(0.55+0.45*sin(2*PI*0.031*t))"
            "+0.08*sin(2*PI*82.41*t)*(0.55+0.45*sin(2*PI*0.047*t+1.3))"
            "+0.05*sin(2*PI*110*t+0.8*sin(2*PI*0.2*t))*(0.5+0.5*sin(2*PI*0.021*t+2.1))"
            "+0.035*sin(2*PI*164.81*t)*(0.5+0.5*sin(2*PI*0.013*t+0.4))"
            "+0.02*sin(2*PI*220*t)*(0.5+0.5*sin(2*PI*0.5*t))*(0.5+0.5*sin(2*PI*0.017*t+1))")
    run([FFMPEG, "-y", "-v", "error", "-f", "lavfi", "-i", f"aevalsrc='{expr}':s={SR}:d={total + 1:.2f}",
         "-af", "lowpass=f=1200,afade=t=in:d=3,afade=t=out:st=" + f"{total - 4:.2f}" + ":d=4", "-ac", "1", str(mpath)])
    return npath, mpath


def fmt_ts(t, sep=","):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def chunks_of(text, maxc=84):
    words = text.split()
    out, cur = [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > maxc:
            out.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
        if re.search(r"[.?!…:]$", w) and len(cur) > maxc * 0.55:
            out.append(cur)
            cur = ""
    if cur:
        out.append(cur)
    return out


def two_lines(s, maxl=42):
    if len(s) <= maxl:
        return s
    words = s.split()
    best, bi = 10 ** 9, 1
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        sc = abs(len(a) - len(b)) + (0 if max(len(a), len(b)) <= maxl else 100)
        if sc < best:
            best, bi = sc, i
    return " ".join(words[:bi]) + "\n" + " ".join(words[bi:])


def write_srt(scenes, path):
    n = 1
    lines = []
    for sc in scenes:
        for pp in sc["paras"]:
            cs = chunks_of(pp["text"])
            tot = sum(len(c) for c in cs)
            t = pp["start"]
            for c in cs:
                d = pp["dur"] * len(c) / tot
                lines += [str(n), f"{fmt_ts(t)} --> {fmt_ts(t + d - 0.02)}", two_lines(c), ""]
                n += 1
                t += d
    path.write_text("\n".join(lines), encoding="utf-8")


def write_chapters(scenes, path):
    out = []
    for i, sc in enumerate(scenes):
        t = 0 if i == 0 else sc["start"]
        m, s = divmod(int(t), 60)
        out.append(f"{m}:{s:02d} {sc['capitulo']}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def write_media_credits(segs, path):
    """Lista de créditos (autor, licencia, enlace) de las fotos y videos usados, para la descripción de YouTube."""
    cred = {}
    for sub in ("fotos", "videos"):
        f = EP_DIR / "material" / sub / "creditos.json"
        if f.exists():
            cred.update(json.loads(f.read_text(encoding="utf-8")))
    used, seen = [], set()
    for sg in segs:
        f = sg["spec"].get("file")
        if not f:
            continue
        c = cred.get(Path(f).name) or cred.get(Path(f).stem + ".webm")
        if c and c.get("pagina") not in seen:
            seen.add(c.get("pagina"))
            used.append(c)
    lines = ["📷 CRÉDITOS DE IMÁGENES Y VIDEOS"]
    for c in used:
        aut = (c.get("autor") or "autor desconocido").split(",")[0]
        lines.append(f"• {c.get('titulo')} — {aut} — {c.get('licencia')} — {c.get('pagina')}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def mux(video, narr, music, srt, path, music_vol, total):
    # 1) mezcla voz + música (la música baja sola cuando hay voz)
    mix = path.parent / "mezcla.wav"
    fc = (f"[0:a]asplit=2[n1][n2];[1:a]volume={music_vol}[m];"
          "[m][n1]sidechaincompress=threshold=0.02:ratio=9:attack=20:release=500[md];"
          "[n2][md]amix=inputs=2:normalize=0[a]")
    run([FFMPEG, "-y", "-v", "error", "-i", str(narr), "-i", str(music), "-filter_complex", fc, "-map", "[a]",
         "-t", f"{total:.3f}", str(mix)])
    # 2) medir volumen y llevarlo a -14 LUFS (estándar de YouTube): ganancia fija + limitador para los picos
    r = subprocess.run([FFMPEG, "-hide_banner", "-i", str(mix), "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json",
                        "-f", "null", "-"], capture_output=True, text=True)
    m = json.loads(r.stderr[r.stderr.rfind("{"): r.stderr.rfind("}") + 1])
    gain = -14.0 - float(m["input_i"]) + 0.6   # +0.6 dB compensa lo que quita el limitador
    ln = (f"volume={gain:.2f}dB,alimiter=limit={10 ** (-1.5 / 20):.3f}:attack=4:release=60:level=disabled,"
          "aresample=48000")
    run([FFMPEG, "-y", "-v", "error", "-i", str(video), "-i", str(mix), "-i", str(srt),
         "-map", "0:v", "-map", "1:a", "-map", "2:s", "-af", ln, "-ac", "2", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
         "-c:s", "mov_text", "-metadata:s:s:0", "language=spa", "-t", f"{total:.3f}", "-movflags", "+faststart", str(path)])
    mix.unlink()
    ajustar_volumen(path)


def medir_lufs(path):
    r = subprocess.run([FFMPEG, "-hide_banner", "-i", str(path), "-map", "0:a", "-af", "ebur128=peak=true:framelog=quiet",
                        "-f", "null", "-"], capture_output=True, text=True)
    i = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)[-1])
    pk = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", r.stderr)[-1])
    return i, pk


def ajustar_volumen(path, objetivo=-14.0):
    """Mide el video final y corrige la ganancia si quedó lejos de -14 LUFS (sin pasar de -1 dBFS de pico)."""
    i, pk = medir_lufs(path)
    gain = objetivo - i
    if abs(gain) < 0.4 and pk <= -1.0:
        print(f"Volumen: {i:.1f} LUFS, pico {pk:.1f} dBFS", flush=True)
        return
    tmp = path.with_name(path.stem + "-vol.mp4")
    # ganancia + limitador a -2 dBFS para que el AAC no se pase de -1 dBFS
    af = f"volume={gain + 0.2:.2f}dB,alimiter=limit={10 ** (-2.0 / 20):.3f}:attack=3:release=50:level=disabled"
    run([FFMPEG, "-y", "-v", "error", "-i", str(path), "-map", "0", "-c:v", "copy", "-c:s", "copy", "-af", af,
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(tmp)])
    path.unlink()
    tmp.rename(path)
    i2, pk2 = medir_lufs(path)
    print(f"Volumen: {i:.1f} -> {i2:.1f} LUFS, pico {pk2:.1f} dBFS", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episodio")
    ap.add_argument("--hojas", action="store_true")
    ap.add_argument("--voz", action="store_true")
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--escenas", default=None, help="ej. 1-2")
    args = ap.parse_args()
    ep_dir = Path(args.episodio).resolve()
    ep, scenes = load_episode(ep_dir)
    out = ep_dir / ep.get("salida", "render")
    out.mkdir(parents=True, exist_ok=True)
    if args.escenas:
        a, b = (int(x) for x in args.escenas.split("-"))
        scenes = [s for s in scenes if a <= s["num"] <= b]
    if args.hojas:
        contact_sheets(ep, scenes, out / "hojas")
        return
    make_voice(ep, scenes, out)
    if args.voz and not args.render:
        print("Voz lista.")
        return
    segs, total = build_timeline(ep, scenes)
    name = ep["nombre"] + ("" if not args.escenas else f"-escenas-{args.escenas}")
    print(f"Duración: {int(total // 60)}:{int(total % 60):02d}  ·  {len(segs)} tarjetas", flush=True)
    srt = out / f"{name}.srt"
    write_srt(scenes, srt)
    write_chapters(scenes, out / f"{name}-capitulos.txt")
    write_media_credits(segs, out / f"{name}-creditos.txt")
    narr, music = build_audio(ep, scenes, segs, total, out)
    video = out / f"{name}-solo-video.mp4"
    render_video(ep, segs, total, out, video)
    final = out / f"{name}.mp4"
    mux(video, narr, music, srt, final, ep.get("musica_vol", 0.55), total)
    video.unlink()
    print("LISTO:", final)


if __name__ == "__main__":
    main()
