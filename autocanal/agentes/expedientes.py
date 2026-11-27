"""🕵️ Expedientes: la oficina de la serie «¿Quién MATÓ a [Marca]?» (documentales de 15–20 min).

Cada video es un expediente (#001, #002…). Miguel arma el paquete de producción con Claude en el chat (HTML o ZIP) y
aquí se importa: se guarda en `autocanal/expedientes/<numero>-<marca>/` (paquete.json + las partes en .md + lo que
va saliendo) y el equipo trabaja por pasos:

Verificación → Voz → Gráficas → Stock → Edición → Subtítulos → Shorts → Subida (privado) → Miniaturas

- 🔎 Detective Ramos (verificación): revisa la lista de datos por verificar y CADA cifra del guion (narración, texto
  en pantalla y gráficas) contra las fuentes del paquete. Lee la página original; si no puede, busca con Serper. Por
  cada dato: ✅ confirmado (con enlace y cita), ⚠️ corregir (con la frase nueva) o ❌ no confirmado (quitarlo o
  suavizarlo). Nunca agrega cifras que no estén en las fuentes (se revisa en código, no solo en el prompt). Nada
  avanza sin el OK de Miguel: «Aprobar cambios» arma la narración corregida y su PDF para leerla en el cel.
- 💬 Chat con el equipo por expediente (cambiar frases, dejar notas para los demás agentes).

Reglas: ningún dato sin fuente; nada público sin OK (siempre privado); la voz final es la de Miguel; solo material con
licencia libre; análisis y opinión (no se acusa a nadie de delitos); la plantilla del título no cambia.
Costo: todo con el plan de Claude de Miguel (`claude.SOLO_PLAN`); la API solo si prende la casilla 💳.
Búsquedas con Serper (centavos).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import threading
import time
import unicodedata
import uuid
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path

import requests

from . import buscar_web, claude, config
from . import paquete_expediente as pq
from .expedientes_previos import ORIGEN as ORIGEN_PREVIO, PREVIOS

CARPETA = Path(os.environ.get("AUTOCANAL_EXPEDIENTES") or config.BASE / "expedientes")
AJUSTES = CARPETA / "ajustes.json"
TAREAS_IA = ("verificar_exp", "chat_exp", "fabrica_exp")

EQUIPO = [  # id, nombre, rol, color, peinado, qué hace (los retratos de la pestaña Equipo)
    ("ex_guion", "Vera", "Investigación y guion", "#38bdf8", "largo",
     "Investiga la marca en Google con fuentes reales (cita literal de cada dato) y escribe el guion técnico del caso."),
    ("ex_ramos", "Detective Ramos", "Verificación", "#facc15", "gorra",
     "Revisa cada dato y cada cifra del guion contra sus fuentes: ✅ confirmado, ⚠️ corregir o ❌ no confirmado."),
    ("ex_graficas", "Nico", "Gráficas", "#e63946", "copete",
     "Anima las gráficas G1…Gn con los datos exactos y la guía de estilo de la serie."),
    ("ex_archivista", "Inés", "Archivista (stock y archivo)", "#2dc653", "chongo",
     "Busca video y fotos con licencia libre (Pexels, Pixabay, Mixkit, Wikimedia) y lleva licencias.csv."),
    ("ex_miniaturas", "Mina", "Miniaturas", "#d946ef", "bob",
     "Hace las miniaturas A y B del paquete con foto real (tuya o de stock libre)."),
    ("ex_editor", "Beto", "Editor", "#3b82f6", "corto",
     "Arma el video escena por escena con tu voz, las gráficas y el stock."),
    ("ex_subtitulos", "Sol", "Subtítulos y Shorts", "#f97316", "largo",
     "Saca el .srt de tu voz para que lo revises y recorta los 5 Shorts en vertical."),
    ("ex_publicacion", "Pepe", "Publicación", "#94a3b8", "rizos",
     "Sube el video a YouTube en PRIVADO con todo listo y te manda el enlace. Solo tú lo haces público."),
]
NOMBRES = {i: n for i, n, *_ in EQUIPO}
PASOS = [  # (clave, etiqueta, quién, en qué parte de la obra llega)
    ("verificacion", "Verificación", "ex_ramos", 1), ("voz", "Voz", "jefe", 3), ("graficas", "Gráficas", "ex_graficas", 2),
    ("stock", "Stock", "ex_archivista", 2), ("edicion", "Edición", "ex_editor", 3),
    ("subtitulos", "Subtítulos", "ex_subtitulos", 3), ("shorts", "Shorts", "ex_subtitulos", 3),
    ("subida", "Subida (privado)", "ex_publicacion", 4), ("miniaturas", "Miniaturas", "ex_miniaturas", 2),
]
ESTADOS_DATO = ("pendiente", "confirmado", "corregir", "no_confirmado", "no_es_dato")
MAX_BUSQUEDAS = 30  # Serper por verificación (≈ 3 centavos)

_candado = threading.RLock()
_corriendo: set[str] = set()
_agentes: dict[str, dict] = {}
_tareas: list[dict] = []
al_cambiar = None  # la oficina pone aquí su _tocar (para que la pantalla se actualice sola)
al_avisar = None   # función(nombre, texto): aviso por Telegram/WhatsApp


def _demo() -> bool:
    return bool(os.environ.get("AUTOCANAL_DEMO"))


def _avisa_pantalla() -> None:
    if al_cambiar:
        try:
            al_cambiar()
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------- el equipo en pantalla
FABRICA_AGENTES = {"ex_guion", "ex_ramos", "ex_archivista", "ex_graficas", "ex_editor", "ex_miniaturas", "ex_subtitulos",
                   "ex_publicacion"}  # 🏭 los que ya trabajan en la fábrica (no están «en obra»)


def agentes() -> list[dict]:
    salida = []
    for i, nombre, rol, color, pelo, desc in EQUIPO:
        a = _agentes.get(i, {})
        parte = 1 if i in FABRICA_AGENTES else min((pa for _, _, q, pa in PASOS if q == i), default=1)
        salida.append({"id": i, "nombre": nombre, "rol": rol, "color": color, "pelo": pelo, "desc": desc,
                       "estado": a.get("estado", "libre"), "dice": a.get("dice", ""), "dice_t": a.get("dice_t", 0),
                       "ubicacion": "casa", "obra": f"Llega en la parte {parte} de la obra" if parte > 1 else ""})
    return salida


def tareas() -> list[dict]:
    with _candado:
        activas = [t for t in _tareas if t["estado"] in ("trabajando", "en_cola", "esperando")]
        return activas + [t for t in _tareas if t not in activas][-40:]


def _decir(agente: str, estado: str, dice: str = "") -> None:
    with _candado:
        a = _agentes.setdefault(agente, {})
        a["estado"] = estado
        if dice:
            a["dice"], a["dice_t"] = dice[:140], time.time()
    _avisa_pantalla()


def _tarea(agente: str, accion: str, titulo: str) -> dict:
    t = {"id": uuid.uuid4().hex[:8], "agente": agente, "etapa": "expediente", "accion": accion, "titulo": titulo,
         "estado": "trabajando", "inicio": time.time(), "fin": None, "error": None, "paso": "", "avance": None,
         "resultado": "", "costo": 0.0, "proyecto": None}
    with _candado:
        _tareas.append(t)
        del _tareas[:-60]
    _avisa_pantalla()
    return t


def _fin_tarea(t: dict, error: str | None = None, resultado: str = "") -> None:
    with _candado:
        t.update(estado="fallo" if error else "hecha", fin=time.time(), error=error, resultado=resultado, paso="")
    _avisa_pantalla()


# ---------------------------------------------------------------- ajustes (💳 la API solo si la prendes)
def ajustes() -> dict:
    try:
        d = json.loads(AJUSTES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    return {"api": bool(d.get("api", False))}


def _aplicar_ajustes() -> None:
    a = ajustes()
    for tarea in TAREAS_IA:
        claude.permitir_api(tarea, a["api"])


def cambiar_ajustes(d: dict) -> dict:
    a = ajustes()
    if "api" in d:
        a["api"] = bool(d["api"])
    CARPETA.mkdir(parents=True, exist_ok=True)
    AJUSTES.write_text(json.dumps(a), encoding="utf-8")
    _aplicar_ajustes()
    return a


_aplicar_ajustes()


# ---------------------------------------------------------------- guardar / leer
def _valido(eid: str) -> bool:
    return bool(re.fullmatch(r"\d{3,4}-[a-z0-9-]{1,40}", eid or ""))


def carpeta(eid: str) -> Path:
    if not _valido(eid):
        raise ValueError("Ese expediente no existe.")
    return CARPETA / eid


def _leer_json(ruta: Path, defecto):
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defecto


def _escribir_json(ruta: Path, datos) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix(".tmp")
    tmp.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(ruta)


def paquete(eid: str) -> dict:
    p = _leer_json(carpeta(eid) / "paquete.json", None)
    if not p:
        raise ValueError("Ese expediente no existe.")
    return p


def trabajo(eid: str) -> dict:
    t = _leer_json(carpeta(eid) / "trabajo.json", {})
    t.setdefault("datos", [])
    t.setdefault("chat", [])
    t.setdefault("notas", [])
    t.setdefault("checklist", {})
    t.setdefault("verificacion", {"estado": "sin_empezar"})
    t.setdefault("costo", 0.0)
    v = t["verificacion"]
    if v.get("estado") == "trabajando" and eid not in _corriendo:  # se cortó (la oficina se reinició)
        v["estado"], v["error"] = "interrumpida", "Se interrumpió (se reinició la oficina). Dale «Seguir verificando»."
    return t


def _guardar_trabajo(eid: str, t: dict) -> None:
    with _candado:
        _escribir_json(carpeta(eid) / "trabajo.json", t)


def lista() -> list[dict]:
    salida = []
    if CARPETA.exists():
        for c in sorted(CARPETA.iterdir()):
            if not (c.is_dir() and _valido(c.name) and (c / "paquete.json").exists()):
                continue
            try:
                p, t = paquete(c.name), trabajo(c.name)
            except ValueError:
                continue
            salida.append({"id": c.name, "numero": p["numero"], "marca": p["marca"], "titulo": p["titulo"],
                           "importado": p.get("importado"), "pasos": pasos(p, t), "cuenta": _cuenta(t["datos"]),
                           "verificacion": t["verificacion"].get("estado")})
    return sorted(salida, key=lambda x: x["numero"], reverse=True)


def _cuenta(datos: list[dict]) -> dict:
    c = {k: 0 for k in ESTADOS_DATO}
    for d in datos:
        c[d.get("estado", "pendiente")] = c.get(d.get("estado", "pendiente"), 0) + 1
    return c


def pasos(p: dict, t: dict) -> list[dict]:
    if t.get("fabrica"):  # 🏭 los casos de la fábrica tienen sus propios pasos
        from . import expedientes_fabrica
        return expedientes_fabrica.pasos(t)
    v = t["verificacion"].get("estado")
    estado_v = {"sin_empezar": "pendiente", "trabajando": "trabajando", "interrumpida": "pendiente",
                "lista": "espera_ok", "aprobada": "listo", "error": "error"}.get(v, "pendiente")
    salida = []
    for clave, etiqueta, quien, parte in PASOS:
        if clave == "verificacion":
            e = estado_v
        elif clave == "voz":
            e = "pendiente" if v == "aprobada" else "bloqueado"
        else:
            e = "en_obra"
        salida.append({"clave": clave, "etiqueta": etiqueta, "quien": quien, "estado": e, "parte": parte})
    return salida


# ---------------------------------------------------------------- números y frases
UNIDADES = {
    "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
    "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15, "dieciseis": 16, "diecisiete": 17,
    "dieciocho": 18, "diecinueve": 19, "veinte": 20, "veintiun": 21, "veintiuno": 21, "veintiuna": 21,
    "veintidos": 22, "veintitres": 23, "veinticuatro": 24, "veinticinco": 25, "veintiseis": 26, "veintisiete": 27,
    "veintiocho": 28, "veintinueve": 29, "treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60,
    "setenta": 70, "ochenta": 80, "noventa": 90, "cien": 100, "ciento": 100, "doscientos": 200, "doscientas": 200,
    "trescientos": 300, "trescientas": 300, "cuatrocientos": 400, "cuatrocientas": 400, "quinientos": 500,
    "quinientas": 500, "seiscientos": 600, "seiscientas": 600, "setecientos": 700, "setecientas": 700,
    "ochocientos": 800, "ochocientas": 800, "novecientos": 900, "novecientas": 900,
}
UNO = {"un", "uno", "una"}
MESES = r"(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)"


def _sin_tildes(t: str) -> str:
    return unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()


def numeros(texto: str) -> set[str]:
    """Las cifras de un texto, normalizadas: «2,670» → 2670, «23.5» → 23.5, «dieciocho» → 18, «setenta y un» → 71."""
    t = texto or ""
    salida: set[str] = set()
    for m in re.finditer(r"(?<![\w.])\d+(?:[.,]\d+)*", t):
        n = m.group(0)
        if re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", n):
            n = n.replace(",", "")
        elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+", n):
            n = n.replace(".", "")
        else:
            n = n.replace(",", ".")
        n = n.lstrip("0") or "0"
        if n.startswith("."):
            n = "0" + n
        if "." in n:
            n = n.rstrip("0").rstrip(".")
        salida.add(n)
    for m in re.finditer(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(mil|millones|millon|M)\b", _sin_tildes(t).replace(",", "")):
        base = float(m.group(1))
        salida.add(f"{base * (1000 if m.group(2) == 'mil' else 1_000_000):.0f}")
    palabras = re.findall(r"[a-zñ]+", _sin_tildes(t))
    total, actual, viendo = 0, 0, False
    for i, w in enumerate(palabras + ["_"]):
        if w in UNIDADES and not (w == "ciento" and i and palabras[i - 1] == "por"):
            actual += UNIDADES[w]
            viendo = True
        elif w in UNO and i + 1 < len(palabras) and palabras[i + 1] in ("mil", "millon", "millones"):
            actual += 1
            viendo = True
        elif w == "y" and viendo and i + 1 < len(palabras) and (palabras[i + 1] in UNIDADES or palabras[i + 1] in UNO):
            continue
        elif w in UNO and viendo:  # «setenta y un»
            actual += 1
        elif w == "mil" and viendo:
            total += actual * 1000
            actual = 0
        else:
            if viendo and (total or actual):
                if not (total + actual == 1 and w in ("millon", "millones")):
                    salida.add(str(total + actual))
                if w in ("millon", "millones"):
                    salida.add(str((total + actual) * 1_000_000))
            total, actual, viendo = 0, 0, False
    return salida


def tiene_cifra(texto: str) -> bool:
    return bool(numeros(texto)) or bool(re.search(rf"\b{MESES}\b|por ciento|%|\bla mitad\b|\bel doble\b",
                                                  _sin_tildes(texto)))


def oraciones(parrafo: str) -> list[str]:
    partes = re.split(r"(?<=[.!?…])\s+(?=[¿¡\"“«A-ZÁÉÍÓÚÑ0-9])", (parrafo or "").strip())
    return [p.strip() for p in partes if p.strip()]


def _norm(t: str) -> str:
    t = _sin_tildes(t).replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", re.sub(r"[^\w%$.,'\" ]+", " ", t)).strip()


STOP = set("""de la el los las un una unos unas y o en por para con sin que se su sus del al lo le les mas pero como
este esta estos estas ese esa eso aqui alli hay fue era son ser es ya muy tan todo toda todos todas cada cuando donde
quien hoy ese porque desde hasta entre sobre tambien solo""".split())
SINONIMOS = {"bancarrota": "bankruptcy chapter", "quiebra": "bankruptcy", "deuda": "debt", "ventas": "sales revenue",
             "vendedoras": "sales force dealers consultants", "vendedores": "sales force", "planta": "plant factory facility",
             "fabrica": "factory plant", "acciones": "shares stock", "accion": "stock shares", "despidos": "layoffs jobs",
             "isla": "island", "nacionalidad": "citizenship", "millones": "million", "mil": "thousand",
             "acreedores": "lenders creditors", "inversionistas": "investors", "contabilidad": "accounting",
             "renegociar": "amend amendments", "prestamos": "loans credit", "asociados": "associates",
             "portada": "cover", "revista": "magazine", "inventor": "inventor", "diccionario": "dictionary",
             "compro": "acquired acquisition bought", "compra": "acquisition", "licencia": "license",
             "perpetua": "perpetual", "regalias": "royalty", "efectivo": "cash", "hectareas": "hectares",
             "productos": "products", "semana": "week", "distribuidores": "distributors", "representantes": "representatives",
             "director": "ceo chief executive", "presidente": "president", "trimestre": "quarter", "cayeron": "declined decreased",
             "impuestos": "taxes tax", "divorcio": "divorced divorce", "murio": "died death", "vendio": "sold sale",
             "empresa": "company", "nacio": "born", "renuncio": "renounced gave", "corrieron": "fired ousted",
             "demando": "sued lawsuit", "sueldo": "salary", "tiendas": "stores retail", "fiestas": "parties party",
             "reuniones": "parties", "convencion": "jubilee", "cerro": "closed completed", "anuncio": "announced"}


def _tokens(texto: str) -> dict[str, float]:
    pesos: dict[str, float] = {}
    for n in numeros(texto):
        pesos[n] = 4.0
    for w in re.findall(r"[a-zñ]{4,}", _sin_tildes(texto)):
        if w in STOP:
            continue
        pesos.setdefault(w, 1.0)
        for s in SINONIMOS.get(w, "").split():
            pesos.setdefault(s, 0.8)
    for nombre in re.findall(r"\b[A-ZÁÉÍÓÚ][a-záéíóúñ]{3,}", texto or ""):
        if _sin_tildes(nombre) not in STOP:
            pesos[_sin_tildes(nombre)] = 2.0
    return pesos


# ---------------------------------------------------------------- armar la lista de datos al importar
def _parrafos(p: dict) -> list[tuple[int, str]]:
    return [(e["n"], x) for e in p["escenas"] for x in e.get("narracion", [])]


def _ubicar(p: dict, pedazo: str) -> tuple[int | None, str]:
    """La escena y el pedazo tal cual aparece en la narración (sin importar espacios)."""
    if not pedazo:
        return None, ""
    for n, parrafo in _parrafos(p):
        if pedazo in parrafo:
            return n, pedazo
    objetivo = _norm(pedazo)
    for n, parrafo in _parrafos(p):
        for o in oraciones(parrafo):
            if objetivo and (objetivo in _norm(o) or _norm(o) in objetivo and len(_norm(o)) > 20):
                return n, o
    return None, ""


def _mejor_oracion(p: dict, dato: str) -> tuple[int | None, str]:
    pesos = _tokens(dato)
    mejor, puntos = (None, ""), 0.0
    for n, parrafo in _parrafos(p):
        for o in oraciones(parrafo):
            otros = _tokens(o)
            s = sum(w for k, w in pesos.items() if k in otros)
            if s > puntos:
                mejor, puntos = (n, o), s
    return mejor if puntos >= 4 else (None, "")


def _nuevo_dato(**campos) -> dict:
    base = {"id": "", "escena": None, "frase": "", "dato": "", "origen": "guion", "lista": None, "tipo": "dato",
            "estado": "pendiente", "explicacion": "", "cita": "", "url": "", "fuente": "", "frase_nueva": "",
            "nota_editor": "", "pendiente_original": False, "usar": True, "revisado": None}
    base.update({k: v for k, v in campos.items() if v is not None})
    return base


def armar_datos(p: dict, anteriores: list[dict] | None = None) -> list[dict]:
    datos: list[dict] = []
    cubiertas: list[str] = []
    listas_previas = set()
    urls = {e["url"] for e in p["fuentes"]["enlaces"]}
    for x in PREVIOS.get(p["id"], []):
        escena, frase = _ubicar(p, x.get("contiene", ""))
        if x.get("contiene") and not frase:
            continue  # el paquete cambió: esa frase ya no está, Ramos la revisa de nuevo
        d = _nuevo_dato(escena=escena, frase=frase, dato=x["dato"], origen="previo", lista=x.get("lista"),
                        tipo=x.get("tipo", "dato"), estado=x.get("estado", "pendiente"),
                        explicacion=x.get("explicacion", ""), fuente=x.get("fuente", ""),
                        url=x.get("url", "") if x.get("url") in urls else "",
                        frase_nueva=x.get("frase_nueva", "") if x.get("estado") in ("corregir", "no_confirmado") else "",
                        nota_editor=x.get("nota_editor", ""), pendiente_original=bool(x.get("pendiente_original")))
        d["explicacion"] = (d["explicacion"] + f" ({ORIGEN_PREVIO}.)").strip()
        datos.append(d)
        if frase:
            cubiertas.append(_norm(frase))
        if x.get("lista"):
            listas_previas.add(x["lista"])
    for v in p["fuentes"]["por_verificar"]:
        if v["n"] in listas_previas:
            continue
        escena, frase = _mejor_oracion(p, v["dato"])
        datos.append(_nuevo_dato(escena=escena, frase=frase, dato=v["dato"], origen="lista", lista=v["n"],
                                 explicacion=f"Por qué falta: {v['por_que']}" if v.get("por_que") else ""))
        if frase:
            cubiertas.append(_norm(frase))

    def cubierta(o: str) -> bool:
        n = _norm(o)
        return any(c and (c in n or n in c) for c in cubiertas)

    for e in p["escenas"]:
        cifras_voz: set[str] = set()
        for parrafo in e.get("narracion", []):
            for o in oraciones(parrafo):
                if not tiene_cifra(o):
                    continue
                cifras_voz |= numeros(o)
                if cubierta(o):
                    continue
                datos.append(_nuevo_dato(escena=e["n"], frase=o, dato=o, origen="guion"))
                cubiertas.append(_norm(o))
        for texto in e.get("texto_pantalla", []):
            n = numeros(re.sub(r"#\s*\d+", "", texto))
            if n and not n <= cifras_voz:
                datos.append(_nuevo_dato(escena=e["n"], frase=texto, dato=texto, origen="pantalla"))
    for g in p["brief"]["graficas"]:
        if g.get("datos") and tiene_cifra(g["datos"]):
            datos.append(_nuevo_dato(escena=(g.get("escenas") or [None])[0], frase=g["datos"],
                                     dato=f"{g['id']} · {g['nombre']}", origen="grafica"))
    # si se reimporta el paquete, se conserva lo que Ramos ya revisó de las frases que siguen igual
    previas = {(_norm(a.get("frase")), a.get("origen")): a for a in (anteriores or []) if a.get("estado") != "pendiente"}
    for i, d in enumerate(datos, 1):
        d["id"] = f"d{i}"
        viejo = previas.get((_norm(d["frase"]), d["origen"]))
        if viejo and d["origen"] != "previo":
            for k in ("estado", "explicacion", "cita", "url", "fuente", "frase_nueva", "usar", "revisado", "nota_editor"):
                d[k] = viejo.get(k, d[k])
    return datos


# ---------------------------------------------------------------- importar el paquete
def importar(nombre: str, contenido: bytes) -> dict:
    p, md = pq.leer(nombre, contenido)
    eid = p["id"]
    c = carpeta(eid)
    with _candado:
        if eid in _corriendo:
            raise pq.ErrorPaquete("Ramos está verificando este expediente; espera a que termine para reimportarlo.")
        existia = (c / "paquete.json").exists()
        anterior = trabajo(eid) if existia else None
        c.mkdir(parents=True, exist_ok=True)
        ext = ".zip" if p["origen"] == "zip" else ".html" if p["origen"] == "html" else ".md"
        (c / f"original{ext}").write_bytes(contenido)
        for clave, texto in md.items():
            (c / pq.PARTES.get(clave, f"{clave}.md")).write_text(texto, encoding="utf-8")
        p["importado"] = time.time()
        p["archivo_original"] = f"original{ext}"
        _escribir_json(c / "paquete.json", p)
        t = anterior or trabajo(eid)
        t["datos"] = armar_datos(p, anterior["datos"] if anterior else None)
        if anterior and t["verificacion"].get("estado") == "aprobada":
            t["verificacion"]["estado"] = "lista"
            t["verificacion"]["nota"] = "Reimportaste el paquete: revisa y vuelve a aprobar."
        t.setdefault("chat", []).append({"quien": "ex_ramos", "t": time.time(), "texto": (
            f"📥 {'Actualicé' if existia else 'Abrí'} el expediente #{p['numero']}: {len(p['escenas'])} escenas, "
            f"{len(p['brief']['graficas'])} gráficas, {len(p['fuentes']['enlaces'])} fuentes y {len(t['datos'])} datos "
            f"por revisar." + (f" Ya traigo {sum(1 for d in t['datos'] if d['origen'] == 'previo')} de la verificación "
                               "que hicieron en el chat." if any(d["origen"] == "previo" for d in t["datos"]) else "")
            + " Cuando quieras, dale «🔎 Verificar».")})
        _guardar_trabajo(eid, t)
    _decir("ex_ramos", "libre", f"Expediente #{p['numero']} · {p['marca']} abierto 🗂️")
    return {"ok": True, "id": eid, "avisos": p["avisos"], "datos": len(t["datos"]), "actualizado": existia}


# ---------------------------------------------------------------- leer las fuentes
class _Texto(HTMLParser):
    BLOQUE = {"p", "div", "li", "br", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section", "article", "td", "th",
              "blockquote", "pre", "table", "ul", "ol", "dd", "dt"}
    FUERA = {"script", "style", "noscript", "svg", "nav", "footer", "form", "button", "iframe", "template", "select"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.partes: list[str] = []
        self.fuera = 0
        self.titulo = ""
        self.en_titulo = False
        self.fecha = ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in self.FUERA:
            self.fuera += 1
        elif tag == "title":
            self.en_titulo = True
        elif tag == "meta" and not self.fecha:
            clave = (a.get("property") or a.get("name") or a.get("itemprop") or "").lower()
            if clave in ("article:published_time", "datepublished", "date", "pubdate", "publishdate", "dc.date"):
                self.fecha = (a.get("content") or "")[:25]
        elif tag == "time" and not self.fecha and a.get("datetime"):
            self.fecha = a["datetime"][:25]
        if tag in self.BLOQUE:
            self.partes.append("\n")

    def handle_endtag(self, tag):
        if tag in self.FUERA and self.fuera:
            self.fuera -= 1
        elif tag == "title":
            self.en_titulo = False
        if tag in self.BLOQUE:
            self.partes.append("\n")

    def handle_data(self, data):
        if self.en_titulo:
            self.titulo += data
        elif not self.fuera:
            self.partes.append(data)


def _texto_html(html: str) -> tuple[str, str, str]:
    p = _Texto()
    try:
        p.feed(html)
    except Exception:  # noqa: BLE001
        pass
    texto = re.sub(r"[ \t ]+", " ", "".join(p.partes))
    texto = re.sub(r"\n\s*\n+", "\n", texto).strip()
    fecha = p.fecha
    if not fecha:
        m = re.search(r'"datePublished"\s*:\s*"([^"]{8,25})"', html)
        fecha = m.group(1) if m else ""
    return texto, re.sub(r"\s+", " ", p.titulo).strip()[:200], fecha


def leer_fuente(eid: str, url: str) -> dict:
    """El texto de la página original (guardado 7 días en el expediente para no volver a bajarla)."""
    archivo = carpeta(eid) / "fuentes" / f"{hashlib.sha1(url.encode()).hexdigest()[:14]}.json"
    guardada = _leer_json(archivo, None)
    if guardada and time.time() - guardada.get("t", 0) < 7 * 86400:
        return guardada
    r_ok = {"url": url, "ok": False, "texto": "", "titulo": "", "fecha": "", "error": "", "t": time.time()}
    if _demo():
        r_ok.update(error="modo demo: no se bajan páginas")
        return r_ok
    agente = config.env("SEC_USER_AGENT") if "sec.gov" in url and config.env("SEC_USER_AGENT") else "Mozilla/5.0"
    try:
        r = requests.get(url, timeout=25, stream=True, headers={"User-Agent": agente,
                                                                "Accept-Language": "es-MX,es;q=0.9,en;q=0.8"})
        tipo = r.headers.get("Content-Type", "")
        crudo = r.raw.read(4_000_000, decode_content=True)
        if r.status_code >= 400:
            r_ok["error"] = f"la página respondió {r.status_code}"
        elif "pdf" in tipo:
            r_ok["error"] = "es un PDF (no lo leo todavía)"
        else:
            html = crudo.decode(r.encoding or "utf-8", "replace")
            texto, titulo, fecha = _texto_html(html) if "<" in html[:3000] else (html, "", "")
            r_ok.update(texto=texto[:400_000], titulo=titulo, fecha=fecha, url_final=r.url)
            r_ok["ok"] = len(texto) >= 400
            if not r_ok["ok"]:
                r_ok["error"] = "la página casi no trae texto (pide JavaScript o bloquea robots)"
    except requests.RequestException as exc:
        r_ok["error"] = f"no abrió: {str(exc)[:120]}"
    _escribir_json(archivo, r_ok)
    return r_ok


def _pedazos(texto: str, largo: int = 520) -> list[str]:
    frases = re.split(r"(?<=[.!?])\s+|\n+", texto)
    salida, actual = [], ""
    for f in frases:
        f = f.strip()
        if not f:
            continue
        if len(actual) + len(f) > largo and actual:
            salida.append(actual.strip())
            actual = actual[-160:] if len(actual) > 160 else ""  # se enciman un poco para no cortar un dato
        actual += " " + f
    if actual.strip():
        salida.append(actual.strip())
    return salida


def _buscar_pasajes(claim: str, fuentes: list[dict], escena: int | None, preferida: str = "",
                    k: int = 3) -> list[tuple[float, dict, str]]:
    pesos = _tokens(claim)
    candidatos = []
    for f in fuentes:
        if not f.get("ok"):
            continue
        bono = 1.5 if (escena and escena in f.get("escenas", [])) else 1.0
        if preferida and f["url"] == preferida:
            bono = 3.0
        for trozo in f["_pedazos"]:
            otros = _tokens(trozo)
            s = sum(w for t, w in pesos.items() if t in otros) * bono
            if s > 0:
                candidatos.append((s, f, trozo))
    candidatos.sort(key=lambda x: -x[0])
    salida, vistos = [], set()
    for s, f, trozo in candidatos:
        clave = (f["url"], trozo[:60])
        if clave in vistos:
            continue
        vistos.add(clave)
        salida.append((s, f, trozo))
        if len(salida) >= k:
            break
    return salida


# ---------------------------------------------------------------- Ramos verifica
SISTEMA_RAMOS = """Eres el Detective Ramos, verificador de datos de «¿Quién MATÓ a…?», una serie documental de YouTube \
en español de México sobre marcas que murieron (o están por morir) y qué pasó con ellas en México. Revisas cada dato \
del guion contra los TEXTOS DE LAS FUENTES que te paso (copiados de las páginas originales o resúmenes de Google).

Reglas que no se rompen:
1. Solo cuenta lo que está en esos textos. No uses lo que sabes de memoria: si no está en los textos, NO está confirmado.
2. Por cada dato decide:
   - "confirmado": un texto lo dice igual o con otras palabras (redondear está bien: «más de 700 millones» cuando el \
texto dice 812 millones; «la mitad» si las cifras lo muestran).
   - "corregir": un texto dice algo distinto (otra cifra, fecha, lugar o nombre). Propón la frase corregida.
   - "no_confirmado": ningún texto lo dice. Propón quitarlo (frase_nueva vacía) o suavizarlo sin la cifra.
   - "no_es_dato": la frase no afirma un hecho que se pueda verificar: es un ejemplo de la vida diaria («el tóper que \
tiene veinte años»), una imagen, una pregunta u opinión. No se cambia. Si es una cuenta que sale de otros datos \
(«setenta y un años después» de 1951 a 2022), no es «no_es_dato»: revisa la cuenta con las fechas de los textos.
3. "cita": copia LITERAL (en su idioma original, sin traducir ni resumir) del pedazo del texto que lo respalda o lo \
contradice, máximo 300 caracteres. "fuente": la etiqueta [F#] de ese texto. Si no hay cita, los dos vacíos.
4. "frase_nueva" (solo para corregir o no_confirmado; vacía si es confirmado): para leerse en voz alta, en español de \
México, con el mismo tono del guion, cambiando lo mínimo. NUNCA metas una cifra, fecha o nombre que no esté en la \
frase original o en tu cita. Si el dato es de una gráfica o de texto en pantalla, frase_nueva es el dato corregido tal \
como debe verse (corto).
5. Si una frase acusa a alguien de un delito o lo da por hecho sin fuente, márcala "corregir" y suavízala: es un video \
de análisis y opinión.
6. "explicacion": 1 o 2 frases cortas para Miguel, en español, de tú: qué dice la fuente y por qué.
7. Si te paso una «propuesta anterior», revísala con la fuente original: confírmala, ajústala o cámbiala.
Devuelve un resultado por cada id que te paso, sin saltarte ninguno."""

ESQUEMA_RAMOS = {
    "type": "object",
    "properties": {"datos": {"type": "array", "items": {
        "type": "object",
        "properties": {"id": {"type": "string"},
                       "estado": {"type": "string", "enum": ["confirmado", "corregir", "no_confirmado", "no_es_dato"]},
                       "explicacion": {"type": "string"}, "cita": {"type": "string"}, "fuente": {"type": "string"},
                       "frase_nueva": {"type": "string"}},
        "required": ["id", "estado", "explicacion", "cita", "fuente", "frase_nueva"], "additionalProperties": False}}},
    "required": ["datos"], "additionalProperties": False,
}


def _etiqueta(d: dict) -> str:
    if d["origen"] == "pantalla":
        return f"Texto en pantalla (escena {d['escena']}): «{d['frase']}»"
    if d["origen"] == "grafica":
        return f"Gráfica {d['dato']}: «{d['frase']}»"
    linea = f"Narración (escena {d['escena']}): «{d['frase']}»" if d["frase"] else f"Dato: «{d['dato']}»"
    if d["origen"] == "lista" or d.get("lista"):
        linea = f"Lista de datos por verificar #{d['lista']}: «{d['dato']}». " + (
            f"Frase del guion: «{d['frase']}»" if d["frase"] else "No encontré la frase exacta en la narración.")
        if d.get("explicacion") and d["origen"] == "lista":
            linea += f" ({d['explicacion']})"
    if d["origen"] == "previo":
        linea += (f"\n   Propuesta anterior: {d['estado']}" + (f"; frase nueva «{d['frase_nueva']}»" if d["frase_nueva"] else "")
                  + f". Nota: {d['explicacion']} Revísala leyendo la fuente original.")
    return linea


def _texto_fuentes(etiquetas: list[tuple[str, dict, list[str]]]) -> str:
    bloques = []
    for et, f, trozos in etiquetas:
        tipo = "resumen de Google" if f.get("google") else "página original"
        bloques.append(f"[{et}] {f.get('nombre') or f.get('titulo') or ''} — {f['url']} ({tipo})\n"
                       + "\n".join(f"«{t}»" for t in trozos))
    return "\n\n".join(bloques) or "(No hay textos de fuentes para estos datos.)"


def _validar(r: dict, d: dict, fuente: dict | None) -> dict:
    """Lo que dice Claude pasa por aquí: sin cita real o con cifras inventadas, no se acepta."""
    estado = r.get("estado") if r.get("estado") in ESTADOS_DATO[1:] else "no_confirmado"
    cita, frase_nueva, extra = (r.get("cita") or "").strip()[:400], (r.get("frase_nueva") or "").strip(), []
    dijo_confirmado, cita_ok = estado == "confirmado", False
    if cita and fuente:
        n_cita, n_texto = _norm(cita), _norm(fuente.get("texto", ""))
        cita_ok = n_cita in n_texto or (len(n_cita) > 60 and n_cita[:40] in n_texto and n_cita[-40:] in n_texto)
        if not cita_ok:
            extra.append("No encontré esa cita tal cual en la fuente; revísala tú.")
            if estado == "confirmado":
                estado = "no_confirmado"
    elif cita and not fuente:
        extra.append("Citó algo sin decir de qué fuente.")
        if estado == "confirmado":
            estado = "no_confirmado"
        cita = ""
    if estado == "confirmado" and not cita:
        estado = "no_confirmado"
        extra.append("Lo dio por bueno sin cita: queda sin confirmar.")
    if estado in ("confirmado", "no_es_dato"):
        frase_nueva = ""
    if estado == "no_es_dato" and d["origen"] in ("lista", "grafica", "pantalla"):
        estado = "no_confirmado"  # lo que el paquete pidió verificar o lo que sale en pantalla sí es dato
        extra.append("Esto sí es un dato del paquete: queda sin confirmar.")
    if frase_nueva:
        sobran = numeros(frase_nueva) - numeros(d["frase"]) - (numeros(cita) if cita_ok else set())
        if sobran:
            extra.append(f"Su frase nueva traía cifras que no están en la fuente ({', '.join(sorted(sobran))}): la quité.")
            frase_nueva = ""
            if estado == "corregir":
                dijo_confirmado = True  # se queda «revísalo tú»: hay algo que corregir pero sin frase válida
    return {"estado": estado, "explicacion": " ".join([(r.get("explicacion") or "").strip()] + extra).strip(),
            "a_mano": (dijo_confirmado and estado != "confirmado") or (estado == "corregir" and bool(cita) and not cita_ok)
                      or (estado == "corregir" and not frase_nueva and d["origen"] not in ("pantalla", "grafica")),
            "cita": cita, "url": fuente["url"] if fuente and cita else "",
            "fuente": (fuente.get("nombre") or fuente.get("titulo") or "") if fuente and cita else "",
            "frase_nueva": frase_nueva}


def _demo_resultado(d: dict, fuentes: list[dict]) -> dict:
    h = int(hashlib.md5(d["frase"].encode()).hexdigest(), 16) % 10
    f = fuentes[h % len(fuentes)] if fuentes else {"url": "", "nombre": ""}
    if h < 7:
        return {"estado": "confirmado", "explicacion": "(DEMO) Así lo diría la fuente; en el servidor real Ramos la lee de verdad.",
                "cita": "(DEMO) cita de ejemplo, no es de la página real", "url": f["url"], "fuente": f.get("nombre", ""),
                "frase_nueva": ""}
    if h < 9 and "unos " in d["frase"]:
        return {"estado": "corregir", "explicacion": "(DEMO) Ejemplo de corrección.", "cita": "(DEMO) cita de ejemplo",
                "url": f["url"], "fuente": f.get("nombre", ""), "frase_nueva": d["frase"].replace("unos ", "alrededor de ", 1)}
    return {"estado": "no_confirmado", "explicacion": "(DEMO) Ejemplo: ninguna fuente lo diría.", "cita": "", "url": "",
            "fuente": "", "frase_nueva": "" if d["origen"] != "guion" else ""}


def verificar(eid: str, rehacer: bool = False, solo: list[str] | None = None) -> dict:
    """Arranca a Ramos en otro hilo. `solo`: ids de datos (para revisar uno desde el chat)."""
    with _candado:
        if eid in _corriendo:
            return {"error": "Ramos ya está verificando este expediente."}
        p, t = paquete(eid), trabajo(eid)
        _corriendo.add(eid)
        t["verificacion"].update(estado="trabajando", inicio=time.time(), error=None,
                                 avance={"hechos": 0, "total": 0, "paso": "Empezando…"})
        _guardar_trabajo(eid, t)
    threading.Thread(target=_verificar, args=(eid, p, rehacer, solo), daemon=True).start()
    return {"ok": True}


def _verificar(eid: str, p: dict, rehacer: bool, solo: list[str] | None) -> None:
    tarea = _tarea("ex_ramos", "Verificar datos", f"Expediente #{p['numero']} · {p['marca']}")
    claude.contexto.proyecto, claude.contexto.etapa, claude.contexto.tarea = None, "expedientes", tarea
    _decir("ex_ramos", "trabajando", "Abriendo las fuentes del expediente… 🔎")
    busquedas = {"usadas": 0}
    gasto_busqueda = 0.0
    try:
        t = trabajo(eid)
        if solo:
            por_revisar = [d for d in t["datos"] if d["id"] in solo]
        else:
            por_revisar = [d for d in t["datos"] if rehacer or d["estado"] == "pendiente"
                           or (d["origen"] == "previo" and d["pendiente_original"] and not d.get("revisado"))]
            if rehacer:
                por_revisar = [d for d in por_revisar if not (d["origen"] == "previo" and not d["pendiente_original"])]

        def avance(paso: str, hechos: int | None = None) -> None:
            with _candado:
                tt = trabajo(eid)
                tt["verificacion"].setdefault("avance", {}).update(paso=paso, total=len(por_revisar))
                if hechos is not None:
                    tt["verificacion"]["avance"]["hechos"] = hechos
                _guardar_trabajo(eid, tt)
            tarea["paso"] = paso
            tarea["avance"] = (hechos or 0) / max(1, len(por_revisar)) if hechos is not None else tarea.get("avance")
            _decir("ex_ramos", "trabajando", paso)

        # 1) leer las páginas originales
        enlaces = p["fuentes"]["enlaces"]
        avance(f"Leyendo {len(enlaces)} fuentes originales…", 0)
        with ThreadPoolExecutor(max_workers=6) as pool:
            leidas = list(pool.map(lambda e: leer_fuente(eid, e["url"]), enlaces))
        fuentes = []
        for e, f in zip(enlaces, leidas):
            f = {**f, "nombre": e.get("texto", ""), "escenas": e.get("escenas", []), "nota": e.get("nota", "")}
            f["_pedazos"] = _pedazos(f["texto"]) if f.get("ok") else []
            fuentes.append(f)
        no_abrieron = [f for f in fuentes if not f.get("ok")]
        with _candado:
            tt = trabajo(eid)
            tt["verificacion"]["fuentes"] = [{"url": f["url"], "nombre": f["nombre"], "ok": f.get("ok", False),
                                              "error": f.get("error", ""), "titulo": f.get("titulo", ""),
                                              "fecha": f.get("fecha", "")} for f in fuentes]
            _guardar_trabajo(eid, tt)

        # 2) los datos que son enlaces de Fuentes (¿abre? ¿qué fecha trae?) se revisan sin Claude
        hechos = 0
        resultados: dict[str, dict] = {}
        for d in [x for x in por_revisar if x.get("tipo") == "fuente"]:
            f = leer_fuente(eid, d["url"]) if d.get("url") else {"ok": False, "error": "sin enlace"}
            resultados[d["id"]] = _revisar_enlace(d, f)
            hechos += 1
        por_revisar_ia = [x for x in por_revisar if x.get("tipo") != "fuente"]

        # 3) agrupar por escena (las gráficas juntas) y pedirle a Claude que verifique
        grupos: dict[str, list[dict]] = {}
        for d in por_revisar_ia:
            grupos.setdefault("graficas" if d["origen"] == "grafica" else f"e{d['escena'] or 0:02d}", []).append(d)
        resultados_lock = threading.Lock()

        def revisar_grupo(item):
            nonlocal hechos, gasto_busqueda
            clave, ds = item
            claude.contexto.proyecto, claude.contexto.etapa, claude.contexto.tarea = None, "expedientes", tarea
            etiquetas: list[tuple[str, dict, list[str]]] = []
            por_url: dict[str, tuple[str, dict, list[str]]] = {}
            for d in ds:
                pasajes = _buscar_pasajes(d["frase"] or d["dato"], fuentes, d["escena"], d.get("url", ""))
                sin_buenos = not pasajes or pasajes[0][0] < 5
                if sin_buenos and busquedas["usadas"] < MAX_BUSQUEDAS and not _demo() and buscar_web.disponible():
                    busquedas["usadas"] += 1
                    consulta = f"{p['marca']} " + re.sub(r"[«»“”\"¿?¡!…]", " ", d["frase"] or d["dato"])[:160]
                    try:
                        res, conteo = buscar_web.buscar([consulta], por_consulta=4, max_texto=600)
                        gasto_busqueda += buscar_web.costo(conteo)
                        for x in res:
                            g = {"url": x["url"], "nombre": x.get("titulo", ""), "texto": x.get("texto", ""),
                                 "ok": True, "google": True, "escenas": [d["escena"]] if d["escena"] else []}
                            g["_pedazos"] = [g["texto"]]
                            pasajes.append((1.0, g, g["texto"]))
                    except Exception as exc:  # noqa: BLE001
                        print(f"aviso: búsqueda de Ramos: {exc}", flush=True)
                for _, f, trozo in pasajes[:5]:
                    if f["url"] not in por_url:
                        por_url[f["url"]] = (f"F{len(por_url) + 1}", f, [])
                        etiquetas.append(por_url[f["url"]])
                    if trozo not in por_url[f["url"]][2]:
                        por_url[f["url"]][2].append(trozo)
            nombre = "las gráficas" if clave == "graficas" else f"la escena {int(clave[1:])}"
            _decir("ex_ramos", "trabajando", f"Revisando {nombre} ({len(ds)} datos)…")
            if _demo():
                time.sleep(1.2)
                salida = {d["id"]: _demo_resultado(d, [f for f in fuentes if f.get("url")]) for d in ds}
            else:
                contenido = (f"Expediente #{p['numero']} · {p['titulo']}\n"
                             + (f"ESCENA {int(clave[1:])}\n" if clave != "graficas" else "GRÁFICAS DEL VIDEO\n")
                             + "\nDATOS A REVISAR\n" + "\n".join(f"[{d['id']}] {_etiqueta(d)}" for d in ds)
                             + "\n\nTEXTOS DE LAS FUENTES\n" + _texto_fuentes(etiquetas))
                r = claude.json_estructurado(SISTEMA_RAMOS, contenido, ESQUEMA_RAMOS, tarea="verificar_exp",
                                             que=f"Ramos verifica {nombre}")
                por_etiqueta = {et: f for et, f, _ in etiquetas}
                salida = {}
                for x in r.get("datos", []):
                    d = next((y for y in ds if y["id"] == x.get("id")), None)
                    if d:
                        salida[d["id"]] = _validar(x, d, por_etiqueta.get((x.get("fuente") or "").strip("[] ")))
            with resultados_lock:
                resultados.update(salida)
                hechos += len(ds)
                _guardar_resultados(eid, salida)
            avance(f"Revisé {nombre}", hechos)

        with ThreadPoolExecutor(max_workers=3) as pool:
            for _ in pool.map(revisar_grupo, sorted(grupos.items())):
                pass
        _guardar_resultados(eid, {k: v for k, v in resultados.items()})
        with _candado:
            tt = trabajo(eid)
            faltan = [d for d in tt["datos"] if d["id"] in {x["id"] for x in por_revisar} and d["id"] not in resultados]
            c = _cuenta(tt["datos"])
            tt["costo"] = round(tt.get("costo", 0) + gasto_busqueda + tarea.get("costo", 0), 4)
            tt["verificacion"].update(estado="lista", fin=time.time(), busquedas=busquedas["usadas"],
                                      no_abrieron=len(no_abrieron))
            tt["verificacion"].pop("avance", None)
            resumen = (f"Terminé el expediente #{p['numero']}: ✅ {c['confirmado']} · ⚠️ {c['corregir']} · "
                       f"❌ {c['no_confirmado']}" + (f" · ⏳ {c['pendiente']} sin revisar" if c["pendiente"] else "")
                       + (" (modo demo: resultados de ejemplo)." if _demo() else
                          f". {len(no_abrieron)} fuentes no abrieron" + (f" (busqué en Google {busquedas['usadas']} veces)."
                                                                         if busquedas["usadas"] else ".") if no_abrieron else ".")
                       + " Revisa el reporte y dale «Aprobar cambios» para armar la narración corregida.")
            if faltan:
                resumen += f" Ojo: {len(faltan)} datos no me regresaron resultado; dale «Seguir verificando»."
            tt["chat"].append({"quien": "ex_ramos", "t": time.time(), "texto": "🔎 " + resumen})
            _guardar_trabajo(eid, tt)
        if gasto_busqueda and claude.al_gastar:
            claude.al_gastar(None, "expedientes", "búsqueda", gasto_busqueda, 0, 0, "Ramos: búsquedas en Google")
        _fin_tarea(tarea, resultado=f"✅ {c['confirmado']} · ⚠️ {c['corregir']} · ❌ {c['no_confirmado']}")
        _decir("ex_ramos", "libre", "Reporte listo: te toca revisarlo 🕵️")
        if al_avisar and not solo:
            al_avisar("Detective Ramos", f"{resumen} (🕵️ Expedientes)")
    except Exception as exc:  # noqa: BLE001
        with _candado:
            tt = trabajo(eid)
            tt["verificacion"].update(estado="error", error=str(exc)[:400], fin=time.time())
            tt["verificacion"].pop("avance", None)
            tt["chat"].append({"quien": "ex_ramos", "t": time.time(), "texto": f"😕 No pude terminar: {str(exc)[:300]}"})
            _guardar_trabajo(eid, tt)
        _fin_tarea(tarea, error=str(exc)[:300])
        _decir("ex_ramos", "libre", "Uy, algo falló 😕")
    finally:
        with _candado:
            _corriendo.discard(eid)
        _avisa_pantalla()


def _revisar_enlace(d: dict, f: dict) -> dict:
    if not f.get("ok"):
        return {"estado": "no_confirmado", "explicacion": f"No pude abrir el enlace ({f.get('error', '')}). Ábrelo tú.",
                "cita": "", "url": d.get("url", ""), "fuente": "", "frase_nueva": ""}
    m = re.search(r"/(20\d\d)/(\d\d)/(\d\d)/", d.get("url", ""))
    fecha = (f.get("fecha") or "")[:10]
    titulo = f.get("titulo", "")
    if m and fecha and fecha != f"{m.group(1)}-{m.group(2)}-{m.group(3)}":
        return {"estado": "corregir", "url": d["url"], "fuente": titulo, "cita": f"Publicado: {fecha}",
                "explicacion": f"La página dice que se publicó el {fecha} («{titulo}»); el enlace dice "
                               f"{m.group(3)}/{m.group(2)}/{m.group(1)}. Corrige la fecha en Fuentes.",
                "frase_nueva": ""}
    return {"estado": "confirmado", "url": d["url"], "fuente": titulo, "cita": f"Título: {titulo}" + (f" · {fecha}" if fecha else ""),
            "explicacion": "El enlace abre bien" + (f" y la fecha ({fecha}) coincide." if fecha else "."), "frase_nueva": ""}


def _guardar_resultados(eid: str, salida: dict[str, dict]) -> None:
    if not salida:
        return
    with _candado:
        t = trabajo(eid)
        for d in t["datos"]:
            r = salida.get(d["id"])
            if not r:
                continue
            if (d["origen"] == "previo" and d["pendiente_original"] and d["estado"] != "pendiente"
                    and r["estado"] == "no_confirmado" and not r["cita"]):
                d["explicacion"] = (d["explicacion"] + " · Ramos no pudo confirmarlo leyendo la fuente original: "
                                    + r["explicacion"]).strip()
                d["revisado"] = time.time()
                continue
            d.update({k: r[k] for k in ("estado", "explicacion", "cita", "url", "fuente", "frase_nueva")})
            d["revisado"] = time.time()
            d["a_mano"] = bool(r.get("a_mano"))
            d["usar"] = not d["a_mano"]  # si Ramos dijo «confirmado» sin cita real, no se toca la frase hasta que tú decidas
            if d["origen"] == "previo" and r.get("cita"):
                d["pendiente_original"] = False
                d["explicacion"] += " (Revisado con la fuente original.)"
        if t["verificacion"].get("estado") == "aprobada":
            t["verificacion"]["estado"] = "lista"
        _guardar_trabajo(eid, t)
    _avisa_pantalla()


# ---------------------------------------------------------------- tus decisiones
def _aplicables(t: dict) -> list[dict]:
    return [d for d in t["datos"] if d["estado"] in ("corregir", "no_confirmado") and d.get("usar", True)
            and d["frase"] and d["origen"] not in ("pantalla", "grafica") and d.get("tipo") != "fuente"
            and (d["frase_nueva"] or d["estado"] == "no_confirmado")]


def narracion_corregida(p: dict, t: dict) -> tuple[list[dict], list[dict], list[dict]]:
    """(escenas con la narración corregida, cambios hechos, los que no se pudieron aplicar)."""
    escenas = [{"n": e["n"], "titulo": e["titulo"], "narracion": list(e.get("narracion", []))} for e in p["escenas"]]
    cambios, fallidos = [], []
    for d in _aplicables(t):
        hecho = False
        for e in escenas:
            if d["escena"] and e["n"] != d["escena"]:
                continue
            for i, parrafo in enumerate(e["narracion"]):
                if d["frase"] in parrafo:
                    nuevo = parrafo.replace(d["frase"], d["frase_nueva"], 1)
                    e["narracion"][i] = re.sub(r"\s{2,}", " ", nuevo).strip()
                    cambios.append({"dato": d["id"], "escena": e["n"], "antes": d["frase"], "despues": d["frase_nueva"]})
                    hecho = True
                    break
            if hecho:
                break
        if not hecho:
            fallidos.append({"dato": d["id"], "escena": d["escena"], "antes": d["frase"], "despues": d["frase_nueva"]})
    for e in escenas:
        e["narracion"] = [x for x in e["narracion"] if x.strip()]
    return escenas, cambios, fallidos


def aprobar(eid: str, forzar: bool = False) -> dict:
    from . import expediente_pdf

    with _candado:
        if eid in _corriendo:
            return {"error": "Espera a que Ramos termine de verificar."}
        p, t = paquete(eid), trabajo(eid)
        pendientes = [d for d in t["datos"] if d["estado"] == "pendiente"]
        a_mano = [d for d in t["datos"] if d.get("a_mano") and not d.get("usar", True) and not d.get("decidido")]
        if (pendientes or a_mano) and not forzar:
            partes = ([f"Ramos no ha revisado {len(pendientes)} datos"] if pendientes else []) + (
                [f"{len(a_mano)} datos marcados «revísalo tú» se quedan con la frase original"] if a_mano else [])
            return {"error": " y ".join(partes) + ".", "confirmar": True, "pendientes": len(pendientes),
                    "a_mano": len(a_mano)}
        escenas, cambios, fallidos = narracion_corregida(p, t)
        c = carpeta(eid)
        (c / "02-narracion-corregida.md").write_text(pq.narracion_md(escenas, p["titulo"] + " (corregida)"),
                                                    encoding="utf-8")
        (c / "narracion-corregida.pdf").write_bytes(expediente_pdf.armar(p, escenas, cambios, demo=_demo()))
        _escribir_json(c / "narracion-corregida.json", {"escenas": escenas, "cambios": cambios, "t": time.time()})
        t["verificacion"].update(estado="aprobada", aprobada=time.time(), cambios=len(cambios), fallidos=fallidos,
                                 sin_revisar=len(pendientes), nota="")
        t["chat"].append({"quien": "ex_ramos", "t": time.time(), "texto": (
            f"✅ Aprobado. Apliqué {len(cambios)} cambios a la narración; ya está el PDF para leerla en el cel."
            + (f" {len(fallidos)} no los pude aplicar (la frase ya no está igual): revísalos." if fallidos else "")
            + (f" Quedaron {len(pendientes)} datos sin revisar." if pendientes else "")
            + " Ya puedes grabar tu voz escena por escena.")})
        _guardar_trabajo(eid, t)
    _decir("ex_ramos", "libre", "¡Caso verificado! A grabar 🎙️")
    return {"ok": True, "cambios": len(cambios), "fallidos": len(fallidos)}


def _revisa_cifras(nueva: str, d: dict) -> str | None:
    sobran = numeros(nueva) - numeros(d.get("frase", "")) - numeros(d.get("cita", "")) - numeros(d.get("frase_nueva", ""))
    if sobran:
        return (f"Esa frase trae cifras que no están ni en la original ni en su fuente ({', '.join(sorted(sobran))}). "
                "Ningún dato sin fuente: si tienes la fuente, agrégala al paquete y vuelve a importarlo.")
    return None


def _marca_sin_aprobar(t: dict) -> None:
    if t["verificacion"].get("estado") == "aprobada":
        t["verificacion"]["estado"] = "lista"
        t["verificacion"]["nota"] = "Hubo cambios después de aprobar: vuelve a aprobar para rehacer la narración y el PDF."


def accion(eid: str, d: dict) -> dict:
    a = str(d.get("accion") or "")
    if a == "verificar":
        return verificar(eid, rehacer=bool(d.get("rehacer")))
    if a == "aprobar":
        return aprobar(eid, forzar=bool(d.get("forzar")))
    if a == "chat":
        texto = str(d.get("texto") or "").strip()[:1500]
        if not texto:
            return {"error": "Escribe algo."}
        return chat(eid, texto)
    with _candado:
        t = trabajo(eid)
        dato = next((x for x in t["datos"] if x["id"] == str(d.get("dato") or "")), None)
        if a in ("usar", "editar", "reverificar") and not dato:
            return {"error": "No encontré ese dato."}
        if a == "usar":
            dato["usar"], dato["decidido"] = bool(d.get("usar")), True
            _marca_sin_aprobar(t)
        elif a == "editar":
            nueva = str(d.get("frase_nueva") or "").strip()[:800]
            problema = _revisa_cifras(nueva, dato)
            if problema:
                return {"error": problema}
            dato["frase_nueva"], dato["usar"] = nueva, True
            if dato["estado"] == "confirmado":
                dato["estado"] = "corregir"
            dato["editado"] = time.time()
            _marca_sin_aprobar(t)
        elif a == "check":
            t["checklist"][str(int(d.get("i", -1)))] = bool(d.get("hecho"))
        elif a == "reverificar":
            dato["estado"], dato["revisado"] = "pendiente", None
            _guardar_trabajo(eid, t)
            return verificar(eid, solo=[dato["id"]])
        else:
            return {"error": "¿Qué hago?"}
        _guardar_trabajo(eid, t)
    _avisa_pantalla()
    return {"ok": True}


# ---------------------------------------------------------------- 💬 chat con el equipo
ESQUEMA_CHAT = {
    "type": "object",
    "properties": {
        "quien": {"type": "string", "enum": [i for i, *_ in EQUIPO]},
        "respuesta": {"type": "string"},
        "acciones": {"type": "array", "items": {
            "type": "object",
            "properties": {"tipo": {"type": "string", "enum": ["cambiar_frase", "usar_original", "usar_propuesta",
                                                               "reverificar", "editar_narracion", "nota", "hacer_video",
                                                               "reintentar", "rehacer_video", "subir_programado",
                                                               "subir_privado", "continuar", "editar_video",
                                                               "miniatura_video"]},
                           "dato": {"type": "string"}, "escena": {"type": "integer"}, "frase": {"type": "string"},
                           "frase_nueva": {"type": "string"}, "para": {"type": "string"}, "nota": {"type": "string"}},
            "required": ["tipo", "dato", "escena", "frase", "frase_nueva", "para", "nota"], "additionalProperties": False}},
    },
    "required": ["quien", "respuesta", "acciones"], "additionalProperties": False,
}


def _sistema_chat(p: dict) -> str:
    from . import expedientes_fabrica as fb
    equipo = "\n".join(f"- {i} = {n} ({r}): {desc}" for i, n, r, _, _, desc in EQUIPO)
    return f"""Eres el equipo de la Agencia de Expedientes, que produce la serie de YouTube «¿Quién MATÓ a…?» con \
Miguel (el jefe). Contesta UNO del equipo (el que toque), en español de México, casual y corto (2–4 frases), de tú. \
Hablan del expediente #{p['numero']} «{p['titulo']}».

El equipo:
{equipo}

CÓMO TRABAJA LA AGENCIA HOY (todo esto YA funciona, no digas que «llega después»): la fábrica investiga, escribe el \
guion, busca material libre, arma el storyboard y las miniaturas; Ramos verifica; la compu de Miguel (sala de edición) \
hace el video con su motor y la voz de Azure (es-MX-JorgeNeural; Miguel puede regrabar con su voz las escenas que \
quiera, pero NO es obligatorio); Pepe lo sube a YouTube en PRIVADO (con fecha o sin fecha) y solo Miguel lo hace público.

EN QUÉ VA ESTE CASO (dato real, úsalo para contestar y no inventes otro estado):
{fb.situacion_caso(p['id'])}

Acciones (en "acciones"; si no aplica ninguna, lista vacía). Si Miguel pide que algo pase, HAZLO con una acción, no
lo dejes «anotado»:
- hacer_video: convertir este caso en video (si es un paquete importado) o reintentar lo que falte para el video.
- reintentar: volver a intentar el paso que falló. rehacer_video: que la compu haga el video otra vez.
- subir_programado / subir_privado: subir el video ya hecho, con la siguiente fecha de la agenda o sin fecha.
- continuar: destrabar la fábrica y seguir (si se quedó esperando).
- editar_video: cambiar un video que YA está en el canal (frase = cuál video, p. ej. «Sears»; frase_nueva = título \
nuevo o vacío; nota = descripción nueva completa o vacía). miniatura_video: Mina le hace miniatura nueva a un video \
del canal y la sube (frase = cuál video). Sí puedes: el canal está conectado.
- cambiar_frase: cambiar la frase nueva propuesta de un dato de la verificación (dato = su id, frase_nueva).
- usar_original / usar_propuesta: en ese dato se queda la frase original o la propuesta.
- reverificar: que Ramos vuelva a revisar ese dato con las fuentes.
- editar_narracion: cambiar una frase de la narración (escena, frase = copia exacta, frase_nueva).
- nota: solo para algo que de verdad ninguna acción hace.
Si algo está esperando a la compu, di EXACTAMENTE por qué (está en «en qué va») y qué tiene que hacer Miguel.
Reglas: ningún dato sin fuente (no metas cifras que no estén en el guion o en las citas de Ramos); nunca publiques en \
público; no se acusa a nadie de delitos; el título siempre es «¿Quién MATÓ a [Marca]?». Nunca digas que hiciste algo \
que no está en "acciones"."""


def _contexto_chat(p: dict, t: dict) -> str:
    datos = [d for d in t["datos"] if d["estado"] != "confirmado"]
    lineas = [f"[{d['id']}] esc. {d['escena'] or '—'} · {d['estado']}{'' if d.get('usar', True) else ' (usa la original)'}"
              f" · «{d['frase'][:160]}»" + (f" → «{d['frase_nueva'][:160]}»" if d["frase_nueva"] else "")
              for d in datos[:60]]
    escenas = "\n".join(f"Escena {e['n']} · {e['titulo']}" for e in p["escenas"])
    chat = "\n".join(f"{'Miguel' if m['quien'] == 'jefe' else NOMBRES.get(m['quien'], m['quien'])}: {m['texto'][:300]}"
                     for m in t["chat"][-12:])
    notas = "\n".join(f"- para {NOMBRES.get(n['para'], n['para'])}: {n['texto']}" for n in t["notas"][-20:])
    return (f"Verificación: {t['verificacion'].get('estado')} · {_cuenta(t['datos'])}\n"
            f"DATOS QUE NO ESTÁN CONFIRMADOS:\n" + ("\n".join(lineas) or "(ninguno)")
            + f"\n\nESCENAS:\n{escenas}\n\nNOTAS YA ANOTADAS:\n{notas or '(ninguna)'}\n\nPLÁTICA RECIENTE:\n{chat}")


def chat(eid: str, texto: str) -> dict:
    with _candado:
        p, t = paquete(eid), trabajo(eid)
        t["chat"].append({"quien": "jefe", "t": time.time(), "texto": texto})
        _guardar_trabajo(eid, t)
    threading.Thread(target=_responder, args=(eid, p, texto), daemon=True).start()
    _avisa_pantalla()
    return {"ok": True}


def _responder(eid: str, p: dict, texto: str) -> None:
    tarea = _tarea("ex_ramos", "Contestar el chat", texto[:80])
    claude.contexto.proyecto, claude.contexto.etapa, claude.contexto.tarea = None, "expedientes", tarea
    try:
        t = trabajo(eid)
        if _demo():
            time.sleep(1.5)
            tipo = "hacer_video" if any(k in texto.lower() for k in ("video", "súbelo", "subelo", "haz")) else "nota"
            r = {"quien": "ex_publicacion" if tipo == "hacer_video" else "ex_ramos",
                 "acciones": [{"tipo": tipo, "dato": "", "escena": 0, "frase": "", "frase_nueva": "",
                               "para": "ex_ramos", "nota": texto[:300]}],
                 "respuesta": "(DEMO) Va, jefe. En el servidor real te contesta Claude con tu plan."}
        else:
            r = claude.json_estructurado(_sistema_chat(p), _contexto_chat(p, t) + f"\n\nMIGUEL DICE AHORA: {texto}",
                                         ESQUEMA_CHAT, tarea="chat_exp", que="Chat de Expedientes")
        notas_resultado, reverificar = [], []
        with _candado:
            t = trabajo(eid)
            for ac in r.get("acciones", [])[:8]:
                tipo = ac.get("tipo")
                dato = next((x for x in t["datos"] if x["id"] == ac.get("dato")), None)
                if tipo in ("cambiar_frase", "usar_original", "usar_propuesta", "reverificar") and not dato:
                    notas_resultado.append(f"⚠️ No encontré el dato {ac.get('dato')}.")
                    continue
                if tipo == "cambiar_frase":
                    problema = _revisa_cifras(ac.get("frase_nueva", ""), dato)
                    if problema:
                        notas_resultado.append(f"⚠️ No cambié {dato['id']}: {problema}")
                        continue
                    dato["frase_nueva"], dato["usar"], dato["editado"] = ac["frase_nueva"].strip(), True, time.time()
                    if dato["estado"] == "confirmado":
                        dato["estado"] = "corregir"
                    _marca_sin_aprobar(t)
                    notas_resultado.append(f"✏️ Cambié la propuesta de {dato['id']}.")
                elif tipo in ("usar_original", "usar_propuesta"):
                    dato["usar"] = tipo == "usar_propuesta"
                    _marca_sin_aprobar(t)
                    notas_resultado.append(f"{'↩️ Se queda la frase original' if tipo == 'usar_original' else '✔ Se usa la propuesta'} en {dato['id']}.")
                elif tipo == "reverificar":
                    dato["estado"], dato["revisado"] = "pendiente", None
                    reverificar.append(dato["id"])
                elif tipo == "editar_narracion":
                    escena, frase = _ubicar(p, ac.get("frase", ""))
                    if not frase:
                        notas_resultado.append("⚠️ No encontré esa frase en la narración; cópiala tal cual.")
                        continue
                    nuevo = _nuevo_dato(escena=escena, frase=frase, dato=frase, origen="jefe", estado="corregir",
                                        frase_nueva=ac.get("frase_nueva", "").strip(),
                                        explicacion="Lo pediste en el chat.")
                    problema = _revisa_cifras(nuevo["frase_nueva"], nuevo)
                    if problema:
                        notas_resultado.append(f"⚠️ No lo cambié: {problema}")
                        continue
                    nuevo["id"] = f"d{len(t['datos']) + 1}"
                    while any(x["id"] == nuevo["id"] for x in t["datos"]):
                        nuevo["id"] = f"d{int(nuevo['id'][1:]) + 1}"
                    t["datos"].append(nuevo)
                    _marca_sin_aprobar(t)
                    notas_resultado.append(f"✏️ Agregué el cambio a la escena {escena} ({nuevo['id']}).")
                elif tipo == "nota" and ac.get("nota"):
                    para = ac.get("para") if ac.get("para") in NOMBRES else r.get("quien", "ex_ramos")
                    t["notas"].append({"para": para, "texto": ac["nota"][:500], "t": time.time()})
                    notas_resultado.append(f"📌 Anotado para {NOMBRES.get(para, para)}.")
            quien = r.get("quien") if r.get("quien") in NOMBRES else "ex_ramos"
            t["chat"].append({"quien": quien, "t": time.time(),
                              "texto": (r.get("respuesta") or "").strip() + ("\n" + "\n".join(notas_resultado) if notas_resultado else "")})
            _guardar_trabajo(eid, t)
        # 🏭 lo que hace la fábrica (fuera del candado: arrancan sus propios hilos)
        from . import expedientes_fabrica as fb
        hechos = []
        for ac in r.get("acciones", [])[:8]:
            tipo = ac.get("tipo")
            try:
                x = (fb.convertir(eid) if tipo == "hacer_video" else fb.reintentar(eid) if tipo == "reintentar"
                     else fb.revisar(eid, {"accion": "rehacer_video"}) if tipo == "rehacer_video"
                     else fb.subir_ya(eid, con_fecha=tipo == "subir_programado") if tipo in ("subir_programado", "subir_privado")
                     else fb.continuar() if tipo == "continuar"
                     else fb.editar_video_canal(ac.get("frase", ""), titulo=ac.get("frase_nueva", ""), descripcion=ac.get("nota", "")) if tipo == "editar_video"
                     else fb.miniatura_video(ac.get("frase", "")) if tipo == "miniatura_video" else None)
            except Exception as exc:  # noqa: BLE001
                x = {"error": str(exc)[:200]}
            if x is not None:
                hechos.append(f"✖ {x['error']}" if "error" in x else {
                    "hacer_video": "🎬 Arranqué la preparación del video.", "reintentar": "🔁 Lo estoy reintentando.",
                    "rehacer_video": "🎬 Mandé a hacer el video otra vez.", "subir_programado": "📤 Subiendo en privado con fecha.",
                    "subir_privado": "📤 Subiendo en privado.", "continuar": "▶ La fábrica sigue.",
                    "editar_video": "✏️ Cambié el video en YouTube.",
                    "miniatura_video": "🖼️ Mina ya está haciendo la miniatura (te aviso en el chat de la agencia)."}[tipo])
        if hechos:
            with _candado:
                t = trabajo(eid)
                t["chat"][-1]["texto"] += "\n" + "\n".join(hechos)
                _guardar_trabajo(eid, t)
        _fin_tarea(tarea, resultado=(r.get("respuesta") or "")[:120])
        _decir(quien, "libre", (r.get("respuesta") or "")[:90])
        if reverificar:
            verificar(eid, solo=reverificar)
    except Exception as exc:  # noqa: BLE001
        with _candado:
            t = trabajo(eid)
            t["chat"].append({"quien": "ex_ramos", "t": time.time(), "texto": f"😕 No pude contestar: {str(exc)[:300]}"})
            _guardar_trabajo(eid, t)
        _fin_tarea(tarea, error=str(exc)[:300])
    _avisa_pantalla()


# ---------------------------------------------------------------- para la pantalla
def resumen() -> dict:
    return {"expedientes": lista(), "ajustes": ajustes(), "equipo": agentes(), "tareas": tareas(),
            "plan": claude.suscripcion_lista(), "demo": _demo()}


def detalle(eid: str) -> dict:
    p, t = paquete(eid), trabajo(eid)
    c = carpeta(eid)
    checklist = []
    aprobada = t["verificacion"].get("estado") == "aprobada"
    for i, texto in enumerate(p["brief"].get("checklist", [])):
        auto = aprobada and "verific" in _sin_tildes(texto)
        checklist.append({"i": i, "texto": texto, "hecho": bool(t["checklist"].get(str(i))) or auto, "auto": auto})
    archivos = {n: (c / n).exists() for n in ("narracion-corregida.pdf", "02-narracion-corregida.md",
                                               *pq.PARTES.values())}
    ligero = {k: v for k, v in p.items() if k not in ("brief", "publicacion", "fuentes")}
    ligero["brief"] = {k: v for k, v in p["brief"].items() if k not in ("md", "tareas")}
    ligero["publicacion"] = {k: v for k, v in p["publicacion"].items() if k != "md"}
    ligero["fuentes"] = {k: v for k, v in p["fuentes"].items() if k != "md"}
    return {"paquete": ligero, "datos": t["datos"], "verificacion": t["verificacion"], "chat": t["chat"][-80:],
            "notas": t["notas"][-40:], "checklist": checklist, "pasos": pasos(p, t), "cuenta": _cuenta(t["datos"]),
            "archivos": archivos, "costo": t.get("costo", 0), "corriendo": eid in _corriendo}


def archivo(eid: str, nombre: str) -> Path | None:
    """Solo los archivos sueltos del expediente (PDF, .md, licencias…), nunca fuera de su carpeta."""
    c = carpeta(eid)
    ruta = (c / Path(nombre).name).resolve()
    if ruta.is_file() and ruta.is_relative_to(c.resolve()) and ruta.suffix.lower() in (".pdf", ".md", ".csv", ".json",
                                                                                      ".srt", ".txt", ".html", ".zip"):
        return ruta
    return None


def borrar(eid: str) -> dict:
    with _candado:
        if eid in _corriendo:
            return {"error": "Espera a que Ramos termine."}
        c = carpeta(eid)
        if c.exists():
            shutil.rmtree(c)
    _avisa_pantalla()
    return {"ok": True}
