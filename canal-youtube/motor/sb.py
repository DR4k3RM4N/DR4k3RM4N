"""Atajos para escribir storyboards. Cada función regresa una tarjeta (dict).

Texto enriquecido: <y>amarillo</y>, <r>rojo</r>, <g>verde</g>, <m>gris</m>. Salto de línea: \n
Opciones comunes de todas las tarjetas: src="fuente", label="etiqueta chica", w=peso (si una frase lleva varias tarjetas).
"""


def Q(text, **k):
    """Frase grande al centro."""
    return dict(t="quote", text=text, **k)


def TITLE(text, **k):
    """Título enorme. icon='bowl'|'bowl_flip'|'vhs'|'down'|'phone', tape=True agrega cinta de escena del crimen."""
    return dict(t="title", text=text, **k)


def NUM(pre, num, suf="", **k):
    """Número grande que cuenta desde cero. dec=decimales, color='tape'|'red'|'green', cap=texto abajo."""
    return dict(t="bignum", pre=pre, num=num, suf=suf, **k)


def BARS(items, **k):
    """Barras horizontales. items=[(etiqueta, valor, color, texto_valor), ...]"""
    return dict(t="bars", items=items, **k)


def STAMP(text, **k):
    """Sello que cae de golpe. sub=texto chico, color='red', cap=texto abajo."""
    return dict(t="stamp", text=text, **k)


def LIST(items, **k):
    """Lista que aparece renglón por renglón."""
    return dict(t="list", items=items, **k)


def PROFILE(name, lines, **k):
    """Ficha de persona con silueta."""
    return dict(t="profile", name=name, lines=lines, **k)


def PLACE(name, **k):
    """Lugar con pin. date=fecha, note=nota."""
    return dict(t="place", name=name, **k)


def ROUTE(a, b, **k):
    """De un lugar a otro con flecha. a=(lugar, país), b=(lugar, país), over=texto sobre la flecha."""
    return dict(t="route", a=a, b=b, **k)


def FILE(title, **k):
    """Carátula del expediente."""
    return dict(t="file", title=title, **k)


def BOARD(reveal, new=None, hi=None, **k):
    """Tablero de sospechosos. reveal=[bool,bool,bool], new=índice que se voltea, hi=índice resaltado."""
    return dict(t="board", reveal=reveal, new=new, hi=hi, **k)


def DEF(word, definition, **k):
    """Tarjeta de diccionario."""
    return dict(t="def", word=word, definition=definition, **k)


def DOC(name, **k):
    """Documento con un nombre que se tacha."""
    return dict(t="doc", name=name, **k)


def DONUT(pct, a, b, **k):
    """Dona de porcentaje. a=texto de la parte verde, b=texto del resto."""
    return dict(t="donut", pct=pct, a=a, b=b, **k)


def TIMELINE(events, hi=None, **k):
    """Línea de tiempo. events=[(año, texto), ...], hi=índice o lista de índices resaltados."""
    return dict(t="timeline", events=events, hi=hi, **k)


def STATS(items, **k):
    """Hasta 3 cifras lado a lado. items=[(valor, texto), ...]"""
    return dict(t="stats", items=items, **k)


def PHOTO(file, **k):
    """Foto real. mode='full' (pantalla completa) o 'frame' (impresa). text/label/sub encima, pos=(x,y) encuadre, bw=True."""
    return dict(t="photo", file=file, **k)


def VIDEO(file, **k):
    """Video real (clip en movimiento). ss=segundo de inicio, speed=velocidad, text/label/sub encima, bw=True."""
    return dict(t="video", file=file, **k)


def SPLIT(a, b, la="", lb="", **k):
    """Pantalla dividida en diagonal con dos fotos. la/lb = etiquetas; head = titular arriba."""
    return dict(t="split", a=a, b=b, la=la, lb=lb, **k)


def END(**k):
    """Pantalla final (20 s)."""
    return dict(t="end", **k)
