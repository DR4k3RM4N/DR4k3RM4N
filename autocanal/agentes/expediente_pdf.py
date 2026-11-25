"""📄 La narración corregida de un expediente en PDF, para leerla en el cel mientras grabas.

Página angosta (se lee grande en el teléfono), una tarjeta por escena con el nombre del archivo que toca grabar
(escena-01.wav…) y los párrafos de voz; lo que cambió Ramos va resaltado. Al final, la lista de cambios y las
palabras difíciles. Sin costo: se arma en el servidor con reportlab, sin Claude.
"""
from __future__ import annotations

import io
import re
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ANCHO, ALTO = 110 * mm, 200 * mm
AMARILLO, ROJO, GRIS = colors.HexColor("#FFD60A"), colors.HexColor("#B3121D"), colors.HexColor("#555555")
FONDO, MARCA = colors.HexColor("#F6F6F3"), "#FFF0A8"


def _fuentes() -> tuple[str, str, bool]:
    """DejaVu si el servidor la tiene (acentos y signos completos); si no, Helvetica."""
    for carpeta in ("/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/dejavu"):
        normal, negrita = Path(carpeta) / "DejaVuSans.ttf", Path(carpeta) / "DejaVuSans-Bold.ttf"
        if normal.exists() and negrita.exists():
            try:
                if "Expediente" not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont("Expediente", str(normal)))
                    pdfmetrics.registerFont(TTFont("Expediente-B", str(negrita)))
                    pdfmetrics.registerFontFamily("Expediente", normal="Expediente", bold="Expediente-B",
                                                  italic="Expediente", boldItalic="Expediente-B")
                return "Expediente", "Expediente-B", True
            except Exception:  # noqa: BLE001
                break
    return "Helvetica", "Helvetica-Bold", False


def _limpio(texto, unicode_ok: bool) -> str:
    t = re.sub(r"[\U0001F000-\U0001FFFF☀-➿️‍]", "", str(texto or ""))
    if not unicode_ok:
        t = t.encode("cp1252", "ignore").decode("cp1252")
    return escape(t.strip())


def armar(paquete: dict, escenas: list[dict], cambios: list[dict], demo: bool = False) -> bytes:
    """`escenas`: [{n, titulo, narracion: [párrafos]}] ya corregidas. `cambios`: [{escena, antes, despues}]."""
    normal, negrita, uni = _fuentes()
    L = lambda x: _limpio(x, uni)  # noqa: E731
    est = {
        "titulo": ParagraphStyle("t", fontName=negrita, fontSize=16, leading=19, spaceAfter=2),
        "sub": ParagraphStyle("s", fontName=normal, fontSize=8.5, leading=11, textColor=GRIS),
        "h": ParagraphStyle("h", fontName=negrita, fontSize=11.5, leading=14, textColor=ROJO, spaceBefore=8, spaceAfter=4),
        "cab": ParagraphStyle("c", fontName=negrita, fontSize=10, leading=12.5),
        "archivo": ParagraphStyle("a", fontName=normal, fontSize=8, leading=10, textColor=GRIS),
        "voz": ParagraphStyle("v", fontName=normal, fontSize=12.5, leading=17.5, spaceAfter=5),
        "txt": ParagraphStyle("x", fontName=normal, fontSize=9.5, leading=12.5),
    }
    nuevas = [c["despues"] for c in cambios if c.get("despues")]

    def resaltar(parrafo: str) -> str:
        texto = L(parrafo)
        for frase in sorted(nuevas, key=len, reverse=True):
            f = L(frase)
            if f and f in texto:
                texto = texto.replace(f, f"<font backColor='{MARCA}'><b>{f}</b></font>", 1)
        return texto

    total = sum(len(" ".join(e.get("narracion", [])).split()) for e in escenas)
    hist = [Paragraph(L(paquete.get("titulo")), est["titulo"]),
            Paragraph(f"Expediente #{L(paquete.get('numero'))} · narración corregida · {total:,} palabras "
                      f"(≈{max(1, round(total / 150))} min a 150 palabras por minuto)", est["sub"])]
    if demo:
        hist.append(Paragraph("<b>MODO DEMO: los cambios de este PDF son de ejemplo. No lo grabes.</b>", est["sub"]))
    if nuevas:
        hist.append(Paragraph(f"<font backColor='{MARCA}'><b>Lo resaltado</b></font> es lo que cambió tras la "
                              "verificación.", est["sub"]))
    hist.append(Spacer(1, 4))
    for e in escenas:
        filas = [[Paragraph(f"ESCENA {e['n']} · {L(e.get('titulo'))}", est["cab"])],
                 [Paragraph(f"Graba: escena-{e['n']:02d}.wav", est["archivo"])]]
        for p in e.get("narracion", []):
            filas.append([Paragraph(resaltar(p), est["voz"])])
        tabla = Table(filas, colWidths=[ANCHO - 16 * mm])
        tabla.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), FONDO), ("LINEBEFORE", (0, 0), (0, -1), 3, AMARILLO),
                                   ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                                   ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
        hist.append(KeepTogether([tabla, Spacer(1, 6)]) if len(filas) < 6 else tabla)
        hist.append(Spacer(1, 6))
    if cambios:
        hist.append(Paragraph("Lo que cambió", est["h"]))
        for c in cambios:
            hist.append(Paragraph(f"<b>Escena {c.get('escena') or '—'}</b> · antes: «{L(c.get('antes'))}»<br/>"
                                  f"ahora: «{L(c.get('despues')) or '(se quitó)'}»", est["txt"]))
            hist.append(Spacer(1, 4))
    palabras = (paquete.get("brief") or {}).get("palabras_dificiles") or []
    if palabras:
        hist.append(Paragraph("Ojo con estas palabras", est["h"]))
        hist.append(Paragraph(L(", ".join(palabras)), est["txt"]))

    salida = io.BytesIO()
    doc = SimpleDocTemplate(salida, pagesize=(ANCHO, ALTO), leftMargin=8 * mm, rightMargin=8 * mm,
                            topMargin=8 * mm, bottomMargin=8 * mm,
                            title=f"Narración · {paquete.get('titulo', '')}", author="Oficina Expedientes")

    def pie(canvas, d):
        canvas.saveState()
        canvas.setFont(normal, 7)
        canvas.setFillColor(GRIS)
        canvas.drawRightString(ANCHO - 8 * mm, 4 * mm, f"{d.page}")
        canvas.restoreState()

    doc.build(hist, onFirstPage=pie, onLaterPages=pie)
    return salida.getvalue()
