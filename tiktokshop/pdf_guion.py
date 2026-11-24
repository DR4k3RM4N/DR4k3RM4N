"""📄 El guion en PDF para tenerlo en el cel mientras grabas: página angosta (se lee grande en el teléfono), una
tarjeta por momento del video (toma, texto en pantalla y lo que dices) y al final la lista de tomas para palomear.
Sin costo: se arma en el servidor con reportlab, sin Claude."""
from __future__ import annotations

import io
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from xml.sax.saxutils import escape

ANCHO, ALTO = 110 * mm, 200 * mm  # como pantalla de cel: al abrirlo se ve grande
BLOQUES = {"puente": "Puente", "problema": "Problema", "solucion": "Solución / demo", "beneficios": "Beneficios",
           "cta": "Carrito naranja"}
ROSA, GRIS, FONDO = colors.HexColor("#e11d48"), colors.HexColor("#555555"), colors.HexColor("#f6f6f6")


def _fuentes() -> tuple[str, str, bool]:
    """DejaVu si el servidor la tiene (acentos y signos completos); si no, Helvetica (sin emojis)."""
    for carpeta in ("/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/dejavu", str(Path(__file__).parent)):
        normal, negrita = Path(carpeta) / "DejaVuSans.ttf", Path(carpeta) / "DejaVuSans-Bold.ttf"
        if normal.exists() and negrita.exists():
            try:
                if "Guion" not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont("Guion", str(normal)))
                    pdfmetrics.registerFont(TTFont("Guion-B", str(negrita)))
                    pdfmetrics.registerFontFamily("Guion", normal="Guion", bold="Guion-B", italic="Guion",
                                                  boldItalic="Guion-B")
                return "Guion", "Guion-B", True
            except Exception:  # noqa: BLE001
                break
    return "Helvetica", "Helvetica-Bold", False


def _limpio(texto, unicode_ok: bool) -> str:
    t = str(texto or "")
    t = re.sub(r"[\U0001F000-\U0001FFFF☀-➿️‍]", "", t)  # emojis: ninguna fuente de PDF los trae
    if not unicode_ok:
        t = t.encode("cp1252", "ignore").decode("cp1252")
    return escape(t.strip())


def armar(p: dict, gancho: str = "") -> bytes:
    g, t = p.get("guion") or {}, p.get("tomas") or {}
    elegido = gancho if gancho in ("A", "B", "C", "todos") else (p.get("gancho") or "todos")
    letras = ["A", "B", "C"] if elegido == "todos" else [elegido]
    normal, negrita, uni = _fuentes()
    L = lambda x: _limpio(x, uni)  # noqa: E731
    est = {
        "titulo": ParagraphStyle("t", fontName=negrita, fontSize=15, leading=18, spaceAfter=2),
        "sub": ParagraphStyle("s", fontName=normal, fontSize=8.5, leading=11, textColor=GRIS),
        "h": ParagraphStyle("h", fontName=negrita, fontSize=11.5, leading=14, textColor=ROSA, spaceBefore=8, spaceAfter=4),
        "cab": ParagraphStyle("c", fontName=negrita, fontSize=9, leading=11, textColor=GRIS),
        "toma": ParagraphStyle("tm", fontName=normal, fontSize=9.5, leading=12.5),
        "pant": ParagraphStyle("p", fontName=negrita, fontSize=10, leading=13),
        "voz": ParagraphStyle("v", fontName=normal, fontSize=12, leading=16),
        "txt": ParagraphStyle("x", fontName=normal, fontSize=10, leading=13.5),
        "chk": ParagraphStyle("k", fontName=normal, fontSize=10, leading=13.5, leftIndent=12, firstLineIndent=-12),
    }

    def tarjeta(tiempo, etiqueta, c):
        filas = [[Paragraph(f"{L(tiempo)} · {L(etiqueta)}", est["cab"])],
                 [Paragraph(f"<b>Toma:</b> {L(c.get('toma'))}", est["toma"])]]
        if c.get("texto_pantalla"):
            filas.append([Paragraph(f"<font color='#e11d48'>EN PANTALLA:</font> {L(c.get('texto_pantalla'))}", est["pant"])])
        filas.append([Paragraph(f"<b>Dices:</b> {L(c.get('voz')) or '<i>(sin voz)</i>'}", est["voz"])])
        tabla = Table(filas, colWidths=[ANCHO - 16 * mm])
        tabla.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), FONDO), ("BOX", (0, 0), (-1, -1), 0.6, ROSA),
                                   ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                                   ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
        return KeepTogether([tabla, Spacer(1, 5)])

    hist = [Paragraph(L(p.get("nombre")), est["titulo"]),
            Paragraph(f"ID: {L(g.get('id'))}{'-' + elegido if len(letras) == 1 else ''} · "
                      f"{'12–20 s' if g.get('duracion') == 'corta' else '25–40 s'}", est["sub"])]
    if g.get("angulo"):
        hist.append(Paragraph(L(g["angulo"]), est["sub"]))
    if p.get("de_marca"):
        hist.append(Paragraph("<b>Al subirlo: activa «Contenido de marca» en TikTok.</b>", est["sub"]))
    ganchos = [x for x in g.get("ganchos", []) if x.get("letra") in letras]
    hist.append(Paragraph("Gancho" if len(ganchos) == 1 else "Los 3 ganchos (graba los 3)", est["h"]))
    for x in ganchos:
        hist.append(tarjeta("0–3 s", f"Gancho {x.get('letra')} · {x.get('tipo', '')}", x))
    hist.append(Paragraph("Cuerpo" + (" (el mismo para los 3)" if len(ganchos) > 1 else ""), est["h"]))
    for c in g.get("cuerpo", []):
        hist.append(tarjeta(c.get("tiempo", ""), BLOQUES.get(c.get("bloque"), c.get("bloque", "")), c))

    tomas = [x for x in t.get("tomas", [])
             if not (m := re.search(r"gancho\s*([abc])\b", x.get("para", ""), re.I)) or m.group(1).upper() in letras]
    if tomas:
        hist.append(Paragraph("Tomas para grabar (en este orden)", est["h"]))
        if t.get("material"):
            hist.append(Paragraph("<b>Ten a la mano:</b> " + L(", ".join(t["material"])), est["txt"]))
            hist.append(Spacer(1, 4))
        for k, x in enumerate(tomas, 1):
            hist.append(Paragraph(f"☐ <b>{k}. {L(x.get('que_grabar'))}</b> — {L(x.get('lugar'))}, {L(x.get('encuadre'))}, "
                                  f"{L(x.get('segundos'))} s · para {L(x.get('para'))}"
                                  + (f"<br/><font color='#555555'>Tip: {L(x.get('tip'))}</font>" if x.get("tip") else ""),
                                  est["chk"]))
            hist.append(Spacer(1, 3))
        for c in t.get("consejos", []):
            hist.append(Paragraph(f"• {L(c)}", est["txt"]))
    hist.append(Paragraph("Caption", est["h"]))
    hist.append(Paragraph(L(g.get("caption")) + "<br/>" + L(" ".join(g.get("hashtags") or [])), est["txt"]))
    if g.get("comentario_fijado"):
        hist.append(Paragraph("Comentario fijado", est["h"]))
        hist.append(Paragraph(L(g["comentario_fijado"]), est["txt"]))

    salida = io.BytesIO()
    doc = SimpleDocTemplate(salida, pagesize=(ANCHO, ALTO), leftMargin=8 * mm, rightMargin=8 * mm,
                            topMargin=8 * mm, bottomMargin=8 * mm, title=f"Guion · {p.get('nombre', '')}",
                            author="Oficina TikTok Shop")

    def pie(canvas, d):
        canvas.saveState()
        canvas.setFont(normal, 7)
        canvas.setFillColor(GRIS)
        canvas.drawRightString(ANCHO - 8 * mm, 4 * mm, f"{d.page}")
        canvas.restoreState()

    doc.build(hist, onFirstPage=pie, onLaterPages=pie)
    return salida.getvalue()
