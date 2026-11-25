"""🕵️ Leer el paquete de producción de un expediente de «¿Quién MATÓ a…?».

El paquete lo arma Miguel con Claude en el chat: una página HTML (Artifact de claude.ai) o un ZIP con los .md.
Aquí se separa en sus partes y se convierte en datos que usa el equipo:
- 00-BRIEF-agentes: entregables, tareas en orden, guía de estilo, gráficas G1…Gn con datos exactos, tomas T1…Tn,
  reglas y la lista final antes de subir.
- 01-guion-tecnico: escenas con Visual (PROPIA / STOCK "términos" / ARCHIVO / GRÁFICA G#), texto en pantalla, audio
  y narración (los párrafos de voz).
- 03-publicacion: título, miniaturas A/B/C, descripción con capítulos, etiquetas, comentario fijado, pantalla final
  y los Shorts.
- 04-fuentes: enlaces por escena y la lista de datos por verificar.

Todo pasa primero a Markdown (el HTML se convierte; el ZIP ya lo trae) y un solo lector entiende los dos. Sin Claude:
no cuesta nada y no inventa nada.
"""
from __future__ import annotations

import io
import re
import unicodedata
import zipfile
from html.parser import HTMLParser

PARTES = {"brief": "00-BRIEF-agentes.md", "guion": "01-guion-tecnico.md", "narracion": "02-narracion.md",
          "publicacion": "03-publicacion.md", "fuentes": "04-fuentes.md"}
MAX_HTML = 6 * 1024 * 1024
MAX_ZIP = 25 * 1024 * 1024
MAX_MD = 3 * 1024 * 1024


class ErrorPaquete(ValueError):
    pass


# ---------------------------------------------------------------- HTML → árbol → Markdown
VACIOS = {"br", "hr", "img", "meta", "link", "input", "source", "wbr", "col", "area", "base", "embed", "track"}
FUERA = {"script", "style", "head", "title", "nav", "noscript", "template", "svg", "button", "form"}
CIERRA_P = {"p", "div", "ul", "ol", "table", "section", "h1", "h2", "h3", "h4", "h5", "h6", "pre", "blockquote"}


class _Nodo:
    __slots__ = ("tag", "attrs", "hijos", "padre")

    def __init__(self, tag: str, attrs: dict, padre=None):
        self.tag, self.attrs, self.hijos, self.padre = tag, attrs, [], padre

    def clases(self) -> set[str]:
        return set((self.attrs.get("class") or "").split())

    def nodos(self):
        for h in self.hijos:
            if isinstance(h, _Nodo):
                yield h
                yield from h.nodos()

    def texto(self) -> str:
        return "".join(h if isinstance(h, str) else h.texto() for h in self.hijos)


class _Arbol(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.raiz = _Nodo("raiz", {})
        self.actual = self.raiz

    def handle_starttag(self, tag, attrs):
        if tag == "p" or tag == "li":  # un <p> o <li> sin cerrar se cierra solo al abrir otro
            n = self.actual
            while n is not self.raiz and n.tag not in ("ul", "ol", "section", "div", "td", "th", "body", "main"):
                if n.tag == tag:
                    self.actual = n.padre
                    break
                n = n.padre
        if tag in CIERRA_P and self.actual.tag == "p":
            self.actual = self.actual.padre
        nodo = _Nodo(tag, {k: (v or "") for k, v in attrs}, self.actual)
        self.actual.hijos.append(nodo)
        if tag not in VACIOS:
            self.actual = nodo

    def handle_startendtag(self, tag, attrs):
        self.actual.hijos.append(_Nodo(tag, {k: (v or "") for k, v in attrs}, self.actual))

    def handle_endtag(self, tag):
        n = self.actual
        while n is not None and n is not self.raiz:
            if n.tag == tag:
                self.actual = n.padre
                return
            n = n.padre

    def handle_data(self, data):
        self.actual.hijos.append(data)


def _arbol(html: str) -> _Nodo:
    p = _Arbol()
    p.feed(html)
    p.close()
    return p.raiz


def _espacios(t: str) -> str:
    return re.sub(r"[ \t\r\n ]+", " ", t)


def _en_linea(n) -> str:
    """Texto de un nodo con formato Markdown sencillo (negritas, código, enlaces, etiquetas)."""
    if isinstance(n, str):
        return _espacios(n)
    if n.tag in FUERA:
        return ""
    if n.tag == "br":
        return "\n"
    dentro = "".join(_en_linea(h) for h in n.hijos)
    if n.tag in ("strong", "b"):
        return f"**{dentro.strip()}**" if dentro.strip() else ""
    if n.tag in ("em", "i"):
        return f"*{dentro.strip()}*" if dentro.strip() else ""
    if n.tag == "code":
        return f"`{dentro.strip()}`"
    if n.tag == "a":
        href = n.attrs.get("href", "")
        if href.startswith(("http://", "https://")):
            return f"[{dentro.strip()}]({href})"
        return dentro
    if n.tag == "span" and "chip" in n.clases():
        return f"[{dentro.strip()}]"
    if n.tag == "img":
        return ""
    return dentro


def _md_bloques(n: _Nodo, salida: list[str], nivel_lista: int = 0) -> None:
    for h in n.hijos:
        if isinstance(h, str):
            if h.strip():
                salida.append(_espacios(h).strip())
            continue
        t = h.tag
        if t in FUERA:
            continue
        if re.fullmatch(r"h[1-6]", t):
            nivel = max(1, int(t[1]) - 1)
            if "escena-t" in h.clases():
                num = next((x.texto() for x in h.nodos() if "escena-n" in x.clases()), "")
                resto = "".join(_en_linea(x) for x in h.hijos
                                if not (isinstance(x, _Nodo) and "escena-n" in x.clases()))
                salida.append(f"{'#' * nivel} {num.strip().upper()} · {_limpiar_md(resto).strip()}")
            else:
                partes = [x for x in h.hijos if not (isinstance(x, _Nodo) and x.tag == "small")]
                titulo = _limpiar_md("".join(_en_linea(x) for x in partes)).strip()
                if titulo:
                    salida.append(f"{'#' * nivel} {titulo}")
            salida.append("")
        elif t == "p":
            texto = "".join(_en_linea(x) for x in h.hijos).strip()
            if not texto:
                continue
            if "voz" in h.clases():
                salida.append("> " + texto.replace("\n", " "))
            else:
                salida.append(texto)
            salida.append("")
        elif t in ("ul", "ol"):
            k = 0
            for li in h.hijos:
                if not (isinstance(li, _Nodo) and li.tag == "li"):
                    continue
                k += 1
                sangria = "  " * (nivel_lista + (1 if "sub" in li.clases() else 0))
                marca = "- [ ]" if "check" in li.clases() else (f"{k}." if t == "ol" else "-")
                propio = "".join(_en_linea(x) for x in li.hijos
                                 if not (isinstance(x, _Nodo) and x.tag in ("ul", "ol"))).strip()
                salida.append(f"{sangria}{marca} {propio}")
                for sub in li.hijos:
                    if isinstance(sub, _Nodo) and sub.tag in ("ul", "ol"):
                        _md_bloques(_envolver(sub), salida, nivel_lista + 1)
            salida.append("")
        elif t == "table":
            filas = [x for x in h.nodos() if x.tag == "tr"]
            tabla = []
            for tr in filas:
                celdas = [x for x in tr.hijos if isinstance(x, _Nodo) and x.tag in ("td", "th")]
                tabla.append([_en_linea(c).strip().replace("|", "/").replace("\n", " ") for c in celdas])
            if tabla:
                ancho = max(len(f) for f in tabla)
                for i, f in enumerate(tabla):
                    f = f + [""] * (ancho - len(f))
                    salida.append("| " + " | ".join(f) + " |")
                    if i == 0:
                        salida.append("|" + "---|" * ancho)
                salida.append("")
        elif t == "pre":
            salida.append("```")
            salida.append(h.texto().strip("\n"))
            salida.append("```")
            salida.append("")
        elif t == "hr":
            salida.append("---")
            salida.append("")
        elif t == "blockquote":
            texto = _espacios(h.texto()).strip()
            if texto:
                salida.append("> " + texto)
                salida.append("")
        else:
            _md_bloques(h, salida, nivel_lista)


def _envolver(lista: _Nodo) -> _Nodo:
    caja = _Nodo("div", {})
    caja.hijos = [lista]
    return caja


def _limpiar_md(t: str) -> str:
    return re.sub(r"\*\*|__", "", t)


def html_a_markdown(nodo: _Nodo) -> str:
    salida: list[str] = []
    _md_bloques(nodo, salida)
    texto = "\n".join(salida)
    return re.sub(r"\n{3,}", "\n\n", texto).strip() + "\n"


def partes_de_html(html: str) -> dict[str, str]:
    """Las 4 partes del paquete en Markdown, a partir de la página HTML."""
    raiz = _arbol(html)
    partes: dict[str, str] = {}
    for clave in ("brief", "guion", "publicacion", "fuentes"):
        nodo = next((x for x in raiz.nodos() if x.attrs.get("id") == clave), None)
        if nodo is not None:
            partes[clave] = html_a_markdown(nodo)
    encabezado = next((x for x in raiz.nodos() if x.tag == "header"), None)
    if encabezado is not None:
        partes["_portada"] = html_a_markdown(encabezado)
    if len([k for k in partes if not k.startswith("_")]) < 2:  # otra forma de HTML: se parte por títulos
        cuerpo = next((x for x in raiz.nodos() if x.tag == "body"), raiz)
        partes.update(partir_markdown(html_a_markdown(cuerpo)))
    return partes


# ---------------------------------------------------------------- ZIP
def _cual_parte(nombre: str) -> str | None:
    n = _clave(nombre.rsplit("/", 1)[-1])
    if "version" in n and "corta" in n:
        return None
    for clave, pistas in (("brief", ("00", "brief")), ("guion", ("01", "guion")), ("narracion", ("02", "narracion")),
                          ("publicacion", ("03", "publicacion")), ("fuentes", ("04", "fuentes"))):
        if n.startswith(pistas[0]) or pistas[1] in n:
            return clave
    return None


def partes_de_zip(datos: bytes) -> dict[str, str]:
    try:
        z = zipfile.ZipFile(io.BytesIO(datos))
    except zipfile.BadZipFile as exc:
        raise ErrorPaquete("Ese ZIP está dañado o no es un ZIP.") from exc
    partes: dict[str, str] = {}
    html = None
    for info in z.infolist():
        if info.is_dir() or info.file_size > MAX_MD * 2:
            continue
        nombre = info.filename
        if "__MACOSX" in nombre or nombre.rsplit("/", 1)[-1].startswith("."):
            continue
        if nombre.lower().endswith((".md", ".markdown", ".txt")):
            clave = _cual_parte(nombre)
            if clave and clave not in partes:
                partes[clave] = z.read(info).decode("utf-8", "replace")
        elif nombre.lower().endswith((".html", ".htm")) and html is None:
            html = z.read(info).decode("utf-8", "replace")
    if len([k for k in partes if k != "narracion"]) < 2 and html:
        return partes_de_html(html) | {k: v for k, v in partes.items()}
    return partes


def partir_markdown(md: str) -> dict[str, str]:
    """Un solo Markdown con todo: se parte por los títulos de cada sección."""
    partes: dict[str, list[str]] = {}
    actual = None
    for linea in md.splitlines():
        m = re.match(r"^(#{1,2})\s+(.+)", linea)
        if m:
            t = _clave(m.group(2))
            nueva = ("brief" if "brief" in t else "guion" if "guion" in t and "tecnico" in t else
                     "publicacion" if t.startswith("publicacion") else "fuentes" if t.startswith("fuentes") else None)
            if nueva:
                actual = nueva
                partes.setdefault(actual, [])
                continue
        if actual:
            partes[actual].append(linea)
    return {k: "\n".join(v) for k, v in partes.items()}


# ---------------------------------------------------------------- lector de Markdown
def _clave(t: str) -> str:
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", t)


def slug(t: str) -> str:
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:40] or "marca"


def plano(t: str) -> str:
    """Texto sin formato Markdown (para mostrar o comparar)."""
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1", t or "")
    t = re.sub(r"\*\*|__|`", "", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)([^*]+)(?<!\s)\*(?![\w*])", r"\1", t)
    return _espacios(t).strip()


def _secciones(md: str) -> list[dict]:
    """[{nivel, titulo, lineas}] cada título abre una sección; antes del primero va el nivel 0."""
    secs = [{"nivel": 0, "titulo": "", "lineas": []}]
    en_codigo = False
    for linea in (md or "").splitlines():
        if linea.strip().startswith("```"):
            en_codigo = not en_codigo
        m = None if en_codigo else re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", linea)
        if m:
            secs.append({"nivel": len(m.group(1)), "titulo": plano(m.group(2)), "lineas": []})
        else:
            secs[-1]["lineas"].append(linea)
    return secs


def _arbol_de(secs: list[dict], i: int) -> list[str]:
    """Las líneas de la sección i y de todas sus subsecciones."""
    nivel = secs[i]["nivel"]
    lineas = list(secs[i]["lineas"])
    for s in secs[i + 1:]:
        if s["nivel"] <= nivel:
            break
        lineas.append("#" * s["nivel"] + " " + s["titulo"])
        lineas.extend(s["lineas"])
    return lineas


def _buscar(secs: list[dict], patron: str) -> int | None:
    for i, s in enumerate(secs):
        if re.search(patron, _clave(s["titulo"])):
            return i
    return None


def _texto_de(secs, patron) -> str:
    i = _buscar(secs, patron)
    return "\n".join(_arbol_de(secs, i)) if i is not None else ""


def _tablas(texto: str) -> list[dict]:
    tablas, actual = [], None
    for linea in texto.splitlines():
        s = linea.strip()
        if s.startswith("|") and s.endswith("|") and len(s) > 2:
            celdas = [c.strip() for c in s.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in celdas if c):
                continue
            if actual is None:
                actual = {"cab": [plano(c) for c in celdas], "filas": []}
                tablas.append(actual)
            else:
                actual["filas"].append(celdas)
        else:
            actual = None
    return tablas


def _tabla_con(texto: str, *palabras: str) -> dict | None:
    for t in _tablas(texto):
        cab = _clave(" ".join(t["cab"]))
        if all(_clave(p) in cab for p in palabras):
            return t
    return None


def _items(texto: str) -> list[dict]:
    """Elementos de lista: [{texto, nivel, check}]"""
    salida = []
    for linea in texto.splitlines():
        m = re.match(r"^(\s*)(?:[-*+]|\d+[.)])\s+(\[[ xX]\]\s*)?(.*)$", linea)
        if m and m.group(3).strip():
            salida.append({"texto": m.group(3).strip(), "nivel": len(m.group(1).replace("\t", "  ")) // 2,
                           "check": bool(m.group(2))})
    return salida


def _codigos(texto: str) -> list[str]:
    return [b.strip("\n") for b in re.findall(r"```[^\n]*\n(.*?)```", texto, flags=re.S)]


def _parrafos(texto: str) -> list[str]:
    bloques, actual = [], []
    for linea in texto.splitlines():
        if not linea.strip() or linea.lstrip().startswith(("#", "|", "```", "- ", "* ", ">")):
            if actual:
                bloques.append(" ".join(actual))
                actual = []
            continue
        actual.append(linea.strip())
    if actual:
        bloques.append(" ".join(actual))
    return [plano(b) for b in bloques if plano(b)]


def numeros_escena(texto: str) -> list[int]:
    """«Escenas 3 a 5: …» → [3, 4, 5]; «Escenas 11 y 12» → [11, 12]; «1, 13» → [1, 13]."""
    t = texto.split(":")[0]
    salida: list[int] = []
    for a, b in re.findall(r"(\d{1,2})\s*(?:a|al|-|–|—)\s*(\d{1,2})\b", t):
        if int(a) <= int(b) <= 99:
            salida.extend(range(int(a), int(b) + 1))
    t = re.sub(r"(\d{1,2})\s*(?:a|al|-|–|—)\s*(\d{1,2})\b", " ", t)
    salida.extend(int(x) for x in re.findall(r"\b(\d{1,2})\b", t))
    return sorted(set(x for x in salida if 0 < x < 100))


def escenas_en(texto: str) -> list[int]:
    """«Gancho (escena 1) + escena 11» → [1, 11]; «Escenas 4 y 5 resumidas» → [4, 5]."""
    salida: set[int] = set()
    for m in re.finditer(r"escenas?\s+(\d{1,2}(?:\s*(?:,|y|a|al|-|–)\s*\d{1,2})*)", texto or "", flags=re.I):
        salida.update(numeros_escena(m.group(1)))
    return sorted(salida)


def _comillas(t: str) -> list[str]:
    return [x.strip() for x in re.findall(r'["“«]([^"”»]{1,160})["”»]', t)]


# ---------------------------------------------------------------- cada parte
def leer_brief(md: str) -> dict:
    secs = _secciones(md)
    texto = md or ""
    graficas = []
    t = _tabla_con(texto, "datos") or _tabla_con(texto, "grafica")
    if t:
        for f in t["filas"]:
            if f and re.fullmatch(r"G\d{1,2}", plano(f[0]).upper()):
                graficas.append({"id": plano(f[0]).upper(), "nombre": plano(f[1]) if len(f) > 1 else "",
                                 "datos": plano(f[2]) if len(f) > 2 else "",
                                 "escenas": numeros_escena(plano(f[3])) if len(f) > 3 else []})
    tomas = []
    t = _tabla_con(texto, "toma", "escena")
    if t:
        for f in t["filas"]:
            if f and re.fullmatch(r"T\d{1,2}", plano(f[0]).upper()):
                tomas.append({"id": plano(f[0]).upper(), "toma": plano(f[1]) if len(f) > 1 else "",
                              "escenas": numeros_escena(plano(f[2])) if len(f) > 2 else [],
                              "notas": plano(f[3]) if len(f) > 3 else ""})
    entregables = []
    t = _tabla_con(texto, "entregable")
    if t:
        entregables = [{"entregable": plano(f[0]), "especificacion": plano(f[1]) if len(f) > 1 else ""}
                       for f in t["filas"] if f]
    checklist = [plano(x["texto"]) for x in _items(_texto_de(secs, r"listafinal|antesdesubir|checklist"))]
    reglas = [plano(x["texto"]) for x in _items(_texto_de(secs, r"^\d*reglas"))]
    tareas = []
    for i, s in enumerate(secs):
        m = re.match(r"^tarea(\d+)", _clave(s["titulo"]))
        if m:
            tareas.append({"n": int(m.group(1)), "titulo": s["titulo"], "md": "\n".join(_arbol_de(secs, i)).strip()})
    guia = next((x["md"] for x in tareas if "grafica" in _clave(x["titulo"])), "")
    guia = re.split(r"\*\*Lista de gr[áa]ficas\*\*", guia)[0].strip()
    palabras = []
    m = re.search(r"palabras:\s*(.+?)(?:\.\s|\.$|\n)", texto)
    if m:
        palabras = [plano(x).strip(" .") for x in re.split(r",\s*|\s+y\s+", m.group(1)) if plano(x).strip(" .")]
    duracion = None
    m = re.search(r"[Dd]uraci[óo]n aproximada:?\**\s*~?(\d{1,3})\s*min", texto)
    if m:
        duracion = int(m.group(1))
    return {"entregables": entregables, "tareas": tareas, "guia_graficas": guia,
            "colores": sorted(set(c.upper() for c in re.findall(r"#[0-9A-Fa-f]{6}\b", guia))),
            "graficas": graficas, "tomas": tomas, "reglas": reglas, "checklist": checklist,
            "palabras_dificiles": palabras, "duracion_min": duracion, "md": md}


TIPOS_VISUAL = ("PROPIA", "STOCK", "ARCHIVO", "GRAFICA")


def _visual(item: str) -> dict:
    sin_tildes = item.replace("GRÁFICA", "GRAFICA").replace("Gráfica", "GRAFICA")
    chips = re.findall(r"\[([^\]\[]{2,300})\](?!\()", sin_tildes)
    tipos, terminos, graficas = [], [], []
    fuentes_chip = chips or [sin_tildes]
    for c in fuentes_chip:
        for tipo in TIPOS_VISUAL:
            if re.search(rf"\b{tipo}\b", c) and tipo not in tipos:
                tipos.append(tipo)
        if "STOCK" in c:
            despues = c.split("STOCK", 1)[1]
            terminos.extend(_comillas(despues))
        graficas.extend(f"G{n}" for n in re.findall(r"\bGRAFICA\s+G(\d{1,2})\b", c))
    if not chips and "STOCK" in sin_tildes and not terminos:
        terminos = _comillas(sin_tildes.split("STOCK", 1)[1])
    descripcion = re.sub(r"\[[^\]\[]{2,300}\](?!\()", "", item)
    return {"tipos": tipos, "terminos": terminos, "graficas": sorted(set(graficas), key=lambda g: int(g[1:])),
            "descripcion": plano(descripcion).strip(" .:"), "md": item}


def _campo(lineas: list[str], nombre: str) -> tuple[str, int]:
    """«**Texto en pantalla:** …» → (lo de después, índice de la línea)."""
    patron = re.compile(rf"^\s*\**\s*{nombre}\s*:?\s*\**\s*:?\s*(.*)$", re.I)
    for i, linea in enumerate(lineas):
        m = patron.match(linea)
        if m:
            return m.group(1).strip(), i
    return "", -1


def leer_guion(md: str) -> dict:
    secs = _secciones(md)
    escenas = []
    for i, s in enumerate(secs):
        m = re.match(r"^\s*escena\s+(\d{1,2})\s*[·:.\-–—|]*\s*(.*)$", s["titulo"], flags=re.I)
        if not m:
            continue
        lineas = _arbol_de(secs, i)
        visual = []
        _, iv = _campo(lineas, "Visual")
        if iv >= 0:
            resto, _ = _campo(lineas[iv:iv + 1], "Visual")
            if resto:
                visual.append(_visual(resto))
            for linea in lineas[iv + 1:]:
                if not linea.strip():
                    if visual:
                        continue
                    continue
                mi = re.match(r"^\s*(?:[-*+]|\d+[.)])\s+(.*)$", linea)
                if not mi:
                    break
                visual.append(_visual(mi.group(1)))
        pantalla, _ = _campo(lineas, "Texto en pantalla")
        textos = [x.strip(' "“”«»') for x in re.split(r"\s+·\s+|\s+\|\s+", plano(pantalla)) if x.strip(' "“”«»')]
        audio, _ = _campo(lineas, "Audio")
        narracion, actual = [], []
        for linea in lineas:
            if linea.lstrip().startswith(">"):
                contenido = linea.lstrip()[1:].strip()
                if contenido:
                    actual.append(contenido)
                elif actual:
                    narracion.append(plano(" ".join(actual)))
                    actual = []
            elif actual:
                narracion.append(plano(" ".join(actual)))
                actual = []
        if actual:
            narracion.append(plano(" ".join(actual)))
        escenas.append({"n": int(m.group(1)), "titulo": plano(m.group(2)).strip(" ·"), "visual": visual,
                        "texto_pantalla": textos, "audio": plano(audio), "narracion": narracion,
                        "palabras": sum(len(p.split()) for p in narracion)})
    escenas.sort(key=lambda e: e["n"])
    tiempos = {}
    t = _tabla_con(md or "", "escena", "empieza")
    if t:
        for f in t["filas"]:
            n = re.match(r"\s*(\d{1,2})", plano(f[0]))
            if n and len(f) > 1:
                tiempos[int(n.group(1))] = plano(f[1])
    for e in escenas:
        e["empieza_estimado"] = tiempos.get(e["n"], "")
    return {"escenas": escenas, "md": md}


def leer_publicacion(md: str) -> dict:
    secs = _secciones(md)
    titulo = next((p for p in _parrafos(_texto_de(secs, r"^titulo")) if "?" in p), "")
    miniaturas = []
    t = _tabla_con(_texto_de(secs, r"^miniatura") or md, "concepto")
    if t:
        for f in t["filas"]:
            if not f:
                continue
            letra = re.match(r"\s*\**\s*([A-Z])\b", f[0])
            if letra:
                miniaturas.append({"letra": letra.group(1), "recomendada": "recomend" in _clave(f[0]),
                                   "concepto": plano(f[1]) if len(f) > 1 else "",
                                   "texto": plano(f[2]) if len(f) > 2 else ""})
    reglas_mini = " ".join(_parrafos(_texto_de(secs, r"^miniatura")))
    descripcion = next(iter(_codigos(_texto_de(secs, r"^descripcion"))), "") or "\n".join(
        _parrafos(_texto_de(secs, r"^descripcion")))
    capitulos = [{"tiempo": m.group(1), "titulo": m.group(2).strip()}
                 for m in re.finditer(r"^\s*(\d{1,2}:\d{2}(?::\d{2})?)\s+(.+)$", descripcion, flags=re.M)]
    etiquetas_txt = " ".join(_parrafos(_texto_de(secs, r"^etiquetas")))
    etiquetas = [x.strip(" .") for x in etiquetas_txt.split(",") if x.strip(" .")]
    comentario = next(iter(_codigos(_texto_de(secs, r"comentariofijado"))), "") or " ".join(
        _parrafos(_texto_de(secs, r"comentariofijado")))
    pantalla_final = [plano(x["texto"]) for x in _items(_texto_de(secs, r"pantallafinal"))]
    shorts = []
    t = _tabla_con(_texto_de(secs, r"^shorts") or md, "gancho")
    if t:
        for f in t["filas"]:
            if f and re.fullmatch(r"S\d{1,2}", plano(f[0]).upper()):
                de_donde = plano(f[2]) if len(f) > 2 else ""
                shorts.append({"id": plano(f[0]).upper(), "gancho": plano(f[1]).strip('"“”') if len(f) > 1 else "",
                               "de_donde": de_donde, "escenas": escenas_en(de_donde),
                               "texto": plano(f[3]).strip('"“”') if len(f) > 3 else ""})
    notas_shorts = " ".join(_parrafos(_texto_de(secs, r"^shorts")))
    cuando = [plano(x["texto"]) for x in _items(_texto_de(secs, r"^cuandopublicar"))]
    return {"titulo": titulo, "miniaturas": miniaturas, "reglas_miniatura": reglas_mini, "descripcion": descripcion,
            "capitulos": capitulos, "etiquetas": etiquetas, "comentario_fijado": comentario,
            "pantalla_final": pantalla_final, "shorts": shorts, "notas_shorts": notas_shorts, "cuando": cuando, "md": md}


def _enlaces(texto: str) -> list[dict]:
    salida = []
    for it in _items(texto):
        for m in re.finditer(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", it["texto"]):
            resto = it["texto"][m.end():]
            nota = plano(re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r"\1", resto)).lstrip(":·- ").strip()
            salida.append({"url": m.group(2), "texto": plano(m.group(1)), "nota": nota.replace("[VERIFICAR]", "").strip(),
                           "verificar": "VERIFICAR" in it["texto"]})
    return salida


def leer_fuentes(md: str) -> dict:
    secs = _secciones(md)
    por_escena = []
    i0 = _buscar(secs, r"^porescena")
    rango = range(i0 + 1, len(secs)) if i0 is not None else range(len(secs))
    for i in rango:
        s = secs[i]
        if i0 is not None and s["nivel"] <= secs[i0]["nivel"]:
            break
        if re.match(r"^escenas?\d", _clave(s["titulo"])) or (i0 is not None and s["titulo"]):
            enlaces = _enlaces("\n".join(s["lineas"]))
            if enlaces:
                por_escena.append({"titulo": s["titulo"], "escenas": numeros_escena(s["titulo"]), "enlaces": enlaces})
    por_verificar = []
    t = _tabla_con(_texto_de(secs, r"porverificar") or md, "dato")
    if t:
        for f in t["filas"]:
            if f and re.fullmatch(r"\d{1,2}", plano(f[0])):
                por_verificar.append({"n": int(plano(f[0])), "dato": plano(f[1]) if len(f) > 1 else "",
                                      "por_que": plano(f[2]) if len(f) > 2 else ""})
    vistos, todas = set(), []
    for g in por_escena:
        for e in g["enlaces"]:
            if e["url"] not in vistos:
                vistos.add(e["url"])
                todas.append({**e, "escenas": g["escenas"], "grupo": g["titulo"]})
    for e in _enlaces(md or ""):  # enlaces fuera de «Por escena»
        if e["url"] not in vistos:
            vistos.add(e["url"])
            todas.append({**e, "escenas": [], "grupo": ""})
    return {"por_escena": por_escena, "por_verificar": por_verificar, "enlaces": todas, "md": md}


def narracion_md(escenas: list[dict], titulo: str = "") -> str:
    lineas = [f"# Narración · {titulo}".strip(" ·"), ""]
    for e in escenas:
        lineas += [f"## Escena {e['n']} · {e['titulo']}  (escena-{e['n']:02d}.wav)", ""]
        for p in e.get("narracion", []):
            lineas += [p, ""]
    return "\n".join(lineas)


# ---------------------------------------------------------------- todo junto
TITULO_RE = re.compile(r"¿\s*Qui[ée]n\s+MAT[ÓO]\s+a\s+([^?¿\n*]+?)\s*\?", re.I)


def leer(nombre: str, datos: bytes) -> tuple[dict, dict[str, str]]:
    """(paquete, partes en Markdown). `nombre` decide si es HTML o ZIP."""
    bajo = (nombre or "").lower()
    if bajo.endswith(".zip") or datos[:2] == b"PK":
        if len(datos) > MAX_ZIP:
            raise ErrorPaquete("El ZIP pesa demasiado (máx. 25 MB).")
        partes = partes_de_zip(datos)
        origen = "zip"
    else:
        if len(datos) > MAX_HTML:
            raise ErrorPaquete("El HTML pesa demasiado (máx. 6 MB).")
        texto = datos.decode("utf-8", "replace")
        if bajo.endswith((".md", ".markdown", ".txt")) or "<" not in texto[:2000]:
            partes = partir_markdown(texto)
            origen = "md"
        else:
            partes = partes_de_html(texto)
            origen = "html"
    faltan = [k for k in ("brief", "guion", "publicacion", "fuentes") if not partes.get(k)]
    if "guion" in faltan:
        raise ErrorPaquete("No encontré el guion técnico (01-guion-tecnico) en el paquete. ¿Es el paquete del expediente?")
    brief = leer_brief(partes.get("brief", ""))
    guion = leer_guion(partes["guion"])
    if not guion["escenas"]:
        raise ErrorPaquete("El guion no trae escenas («ESCENA 1 …»). Revisa el paquete.")
    publicacion = leer_publicacion(partes.get("publicacion", ""))
    fuentes = leer_fuentes(partes.get("fuentes", ""))
    todo = "\n".join(partes.values())
    num = re.search(r"Expediente\s*#\s*0*(\d{1,4})", todo, flags=re.I)
    titulo = TITULO_RE.search(publicacion["titulo"] or "") or TITULO_RE.search(partes.get("_portada", "")) or \
        TITULO_RE.search(todo)
    marca = plano(titulo.group(1)).strip(" *") if titulo else ""
    if not num or not marca:
        raise ErrorPaquete("No encontré el número del expediente («Expediente #002») o la marca («¿Quién MATÓ a …?»).")
    numero = f"{int(num.group(1)):03d}"
    titulo_fijo = f"¿Quién MATÓ a {marca}?"
    avisos = []
    if publicacion["titulo"] and _clave(publicacion["titulo"]) != _clave(titulo_fijo):
        avisos.append(f"El título del paquete («{publicacion['titulo']}») no sigue la plantilla; se usa «{titulo_fijo}».")
    for k in faltan:
        avisos.append(f"No encontré la parte {PARTES[k]}.")
    if not fuentes["enlaces"]:
        avisos.append("La parte de Fuentes no trae enlaces: Ramos no podrá verificar nada sin fuentes.")
    paquete = {
        "id": f"{numero}-{slug(marca)}", "numero": numero, "marca": marca, "titulo": titulo_fijo, "origen": origen,
        "brief": brief, "escenas": guion["escenas"], "publicacion": publicacion, "fuentes": fuentes, "avisos": avisos,
        "palabras": sum(e["palabras"] for e in guion["escenas"]),
    }
    md = {k: v for k, v in partes.items() if not k.startswith("_")}
    if "narracion" not in md:
        md["narracion"] = narracion_md(guion["escenas"], titulo_fijo)
    return paquete, md
