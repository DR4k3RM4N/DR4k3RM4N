"""🏭 Fábrica de la Agencia de Expedientes: hace los videos de «¿Quién MATÓ a…?» solita, uno tras otro, mientras tu
plan de Claude tenga uso disponible.

Por cada tema (de `canal-youtube/plan-del-canal.md` o propuestos por el equipo):
  1. 🔎 Vera investiga: busca en Google (Serper), lee las páginas y saca hechos con CITA LITERAL y su enlace. Una cita
     que no está tal cual en la página se tira (nada inventado).
  2. ✍️ Vera escribe el guion técnico con la estructura del canal (gancho → caso → víctima → sospechosos → giro de
     México → ¿final feliz? → veredicto → adelanto). Cada cifra de la narración tiene que venir de un hecho; si no,
     se marca [VERIFICAR] para Ramos.
  3. 🗄️ Inés busca material libre en Wikimedia Commons (y Pexels si hay clave) y escoge fotos y videos por escena.
  4. 📊 Nico escribe el storyboard.py (estilo «cine») con una tarjeta por frase; se revisa con el motor antes de
     seguir (que cuadren las frases y que el código no haga nada raro).
  5. 🔎 Ramos verifica todo como siempre (✅/⚠️/❌). Si todo sale bien, va directo a render; si no, te toca revisar.
  6. 🎬 Tu compu (sala de edición) baja el material, hace la voz con Azure y renderiza con el motor + miniaturas.
  7. 👀 Tú lo revisas en la Bandeja → «Aprobar y programar» → 📤 Pepe lo sube en PRIVADO con fecha de publicación
     (un video cada N días, del canal). Nada se publica sin tu OK.

Todo con tu plan de Claude (Opus, tarea `fabrica_exp` en `claude.SOLO_PLAN`): cero centavos de la API salvo que
prendas la casilla 💳. Si se acaba el límite del plan, la fábrica espera y sigue sola cuando vuelve.
"""
from __future__ import annotations

import ast
import datetime as dt
import io
import json
import math
import re
import shutil
import subprocess
import sys
import threading
import time
import unicodedata
import zipfile
from pathlib import Path

from . import buscar_web, claude, config
from . import expedientes as ex
from . import expedientes_agenda as agenda

CANAL_DIR = config.BASE.parent / "canal-youtube"
MOTOR = CANAL_DIR / "motor"
TEMAS = ex.CARPETA / "temas.json"
ESTADO = ex.CARPETA / "fabrica.json"
SALA_URL = config.env("SALA_URL", "http://127.0.0.1:8767").rstrip("/")
TAREA = "fabrica_exp"
_candado = threading.RLock()
_hilo: dict[str, threading.Thread] = {}

PASOS_FAB = [("investigacion", "Investigación", "ex_guion"), ("guion", "Guion", "ex_guion"),
             ("material", "Material libre", "ex_archivista"), ("storyboard", "Storyboard", "ex_graficas"),
             ("verificacion", "Verificación", "ex_ramos"), ("render", "Video (tu compu)", "ex_editor"),
             ("revision", "Tu revisión", "jefe"), ("programado", "Programado (privado)", "ex_publicacion")]


# ---------------------------------------------------------------- utilidades
def _slug(texto: str, largo: int = 40) -> str:
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:largo].strip("-") or "caso"


def _leer(ruta: Path, defecto):
    return ex._leer_json(ruta, defecto)


def _escribir(ruta: Path, datos) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ex._escribir_json(ruta, datos)


def estado() -> dict:
    with _candado:
        e = _leer(ESTADO, None) or {}
        e.setdefault("activa", False)
        e.setdefault("meta_dias", 90)  # juntar material para ~3 meses
        e.setdefault("en_curso", None)
        e.setdefault("espera_hasta", 0)
        e.setdefault("nota", "")
        return e


def _guardar_estado(e: dict) -> None:
    with _candado:
        _escribir(ESTADO, e)
    ex._avisa_pantalla()


def ajustar(d: dict) -> dict:
    e = estado()
    if "activa" in d:
        e["activa"] = bool(d["activa"])
        e["nota"] = "" if e["activa"] else "Pausada por ti."
    if "meta_dias" in d:
        try:
            e["meta_dias"] = max(6, min(365, int(d["meta_dias"])))
        except (TypeError, ValueError):
            return {"error": "Los días de material son un número."}
    _guardar_estado(e)
    return {"ok": True, "estado": e}


# ---------------------------------------------------------------- 🧾 temas
def _sembrar() -> list[dict]:
    """Los temas de plan-del-canal.md (una tabla «| # | Marca | El gancho |» por grupo)."""
    plan = CANAL_DIR / "plan-del-canal.md"
    temas, grupo = [], ""
    if plan.exists():
        for linea in plan.read_text(encoding="utf-8").splitlines():
            if linea.startswith("### "):
                grupo = linea[4:].strip()
            m = re.match(r"^\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*$", linea)
            if m and grupo:
                marca = m.group(2).strip()
                temas.append({"id": _slug(marca), "canal": "quien_mato", "marca": marca, "gancho": m.group(3).strip(),
                              "grupo": grupo, "estado": "pendiente", "eid": None, "orden": int(m.group(1))})
    hechos = {"sears", "tupperware"}  # Miguel ya los hizo (Expediente #001 y #002)
    for t in temas:
        if t["id"] in hechos:
            t["estado"] = "hecho"
    return temas


def temas() -> list[dict]:
    with _candado:
        lista = _leer(TEMAS, None)
        if lista is None:
            lista = _sembrar()
            _escribir(TEMAS, lista)
        return lista


def _guardar_temas(lista: list[dict]) -> None:
    with _candado:
        _escribir(TEMAS, lista)
    ex._avisa_pantalla()


def mover_tema(d: dict) -> dict:
    with _candado:
        lista = temas()
        t = next((x for x in lista if x["id"] == d.get("id")), None)
        a = d.get("op") or d.get("accion")
        if a == "nuevo":
            marca = str(d.get("marca") or "").strip()[:80]
            if len(marca) < 2:
                return {"error": "Escribe la marca."}
            tid = _slug(marca)
            if any(x["id"] == tid for x in lista):
                return {"error": "Ese tema ya está en la lista."}
            lista.insert(0, {"id": tid, "canal": d.get("canal") or "quien_mato", "marca": marca,
                             "gancho": str(d.get("gancho") or "").strip()[:300], "grupo": "Tus ideas",
                             "estado": "pendiente", "eid": None, "orden": 0})
        elif not t:
            return {"error": "No encontré ese tema."}
        elif a == "primero":
            lista.remove(t)
            lista.insert(0, t)
        elif a == "saltar":
            t["estado"] = "saltado"
        elif a in ("reactivar", "aprobar"):
            t["estado"] = "pendiente"
        elif a == "borrar" and t["estado"] in ("propuesto", "saltado", "pendiente"):
            lista.remove(t)
        else:
            return {"error": "¿Qué hago con el tema?"}
        _guardar_temas(lista)
    return {"ok": True}


ESQ_TEMAS = {"type": "object", "additionalProperties": False, "required": ["temas"], "properties": {"temas": {
    "type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["marca", "gancho", "grupo"],
                               "properties": {"marca": {"type": "string"}, "gancho": {"type": "string"},
                                              "grupo": {"type": "string"}}}}}}


def proponer_temas(canal: str = "quien_mato", n: int = 6) -> dict:
    """Más temas para cuando se acaba la lista (quedan como «propuestos»: tú los apruebas)."""
    c = next((x for x in agenda.lista() if x["id"] == canal), agenda.lista()[0])
    ya = ", ".join(x["marca"] for x in temas())
    if _demo():
        r = {"temas": [{"marca": "Comercial Mexicana", "gancho": "La «Mega» que terminó en manos de Soriana (demo)",
                        "grupo": "Marcas mexicanas"}]}
    else:
        r = claude.json_estructurado(
            "Propones temas para un canal de YouTube en español (México) que investiga como caso policiaco «quién "
            "mató» a una marca. Solo marcas reales y famosas en México/EE.UU./Latinoamérica que murieron, quebraron o "
            "están por morir, con un gancho concreto (de preferencia con el giro de qué pasó en México). Si no estás "
            "seguro de un dato del gancho, escríbelo como pregunta y agrega [investigar].",
            f"CANAL: {c['nombre']}\nDE QUÉ TRATA: {c.get('tema')}\nYA ESTÁN (no repitas): {ya}\n\nPropón {n} temas nuevos.",
            ESQ_TEMAS, tarea=TAREA, que="proponer temas")
    with _candado:
        lista = temas()
        nuevos = 0
        for x in r["temas"][:n]:
            tid = _slug(x["marca"])
            if any(y["id"] == tid for y in lista):
                continue
            lista.append({"id": tid, "canal": canal, "marca": x["marca"][:80], "gancho": x["gancho"][:300],
                          "grupo": x["grupo"][:60] or "Propuestos", "estado": "propuesto", "eid": None, "orden": 999})
            nuevos += 1
        _guardar_temas(lista)
    return {"ok": True, "nuevos": nuevos}


# ---------------------------------------------------------------- estado de cada caso hecho por la fábrica
def _demo() -> bool:
    return ex._demo()


def fab(eid: str) -> dict:
    return (ex.trabajo(eid).get("fabrica") or {})


def _poner(eid: str, **campos) -> None:
    with ex._candado:
        t = ex.trabajo(eid)
        t.setdefault("fabrica", {}).update(campos)
        ex._guardar_trabajo(eid, t)
    ex._avisa_pantalla()


def pasos(t: dict) -> list[dict]:
    """Los pasos de un caso de la fábrica (para la pestaña Casos y la Bandeja)."""
    f = t.get("fabrica") or {}
    hechos = set(f.get("hechos_pasos") or [])
    actual = f.get("paso")
    v = t["verificacion"].get("estado")
    salida = []
    for clave, etiqueta, quien in PASOS_FAB:
        if clave in hechos:
            e = "listo"
        elif clave == actual:
            e = "error" if f.get("error") else "espera_ok" if clave == "revision" else "trabajando"
        else:
            e = "pendiente"
        if clave == "verificacion":
            e = {"trabajando": "trabajando", "lista": "espera_ok", "aprobada": "listo", "error": "error"}.get(v, e)
            if v == "lista" and f.get("render_ok"):
                e = "listo"
        if clave == "render" and f.get("render_estado") == "en_fila":
            e = "trabajando"
        salida.append({"clave": clave, "etiqueta": etiqueta, "quien": quien, "estado": e, "parte": 1})
    return salida


# ---------------------------------------------------------------- 1. investigar
ESQ_HECHOS = {
    "type": "object", "additionalProperties": False,
    "required": ["hechos", "sospechosos", "giro_mexico", "final_feliz", "dudas"],
    "properties": {
        "hechos": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                               "required": ["dato", "cita", "fuente"],
                                               "properties": {"dato": {"type": "string", "description": "el hecho en español, corto"},
                                                              "cita": {"type": "string", "description": "frase copiada TAL CUAL de la fuente (mismo idioma), 8 a 40 palabras"},
                                                              "fuente": {"type": "string", "description": "F1, F2…"}}}},
        "sospechosos": {"type": "array", "items": {"type": "string"}, "description": "3 o 4 causas de la muerte de la marca, cada una apoyada en hechos"},
        "giro_mexico": {"type": "string", "description": "qué pasó en México (o vacío si no hay datos)"},
        "final_feliz": {"type": "string", "description": "riesgos actuales / si de verdad acabó"},
        "dudas": {"type": "array", "items": {"type": "string"}, "description": "lo que no se pudo confirmar"},
    },
}


def _bajar_pagina(url: str) -> tuple[str, str]:
    import requests
    r = requests.get(url, timeout=25, headers={"User-Agent": "Mozilla/5.0 (Agencia de Expedientes; investigación)",
                                               "Accept-Language": "es-MX,es;q=0.9,en;q=0.8"})
    if r.status_code >= 400 or "html" not in r.headers.get("Content-Type", "html"):
        return "", ""
    texto, titulo, _ = ex._texto_html(r.text[:2_000_000])
    return texto, titulo


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKC", t or "").lower()
    t = re.sub(r"[“”«»\"'’‘]", "", t)
    return re.sub(r"\s+", " ", t).strip()


def investigar(tema: dict) -> dict:
    marca, gancho = tema["marca"], tema.get("gancho", "")
    gancho_limpio = re.sub(r"[\[\]]|investigar|verificar", "", gancho)[:60]
    consultas = [f"{marca} quiebra historia", f"{marca} México qué pasó", f"{marca} bankruptcy history",
                 f"{marca} history founder", f"{marca} {gancho_limpio}",
                 f"{marca} cierre tiendas México", f"what happened to {marca}", f"{marca} wikipedia"]
    if _demo():
        fuentes = [{"url": "https://en.wikipedia.org/wiki/Blockbuster_LLC", "titulo": "Blockbuster (demo)",
                    "texto": "Blockbuster LLC was an American-based provider of home movie and video game rental services. "
                             "In 2014 Grupo Elektra acquired the Mexican operations of Blockbuster. Blockbuster filed for "
                             "bankruptcy in 2010. At its peak in 2004, Blockbuster had 9,094 stores."}]
    else:
        if not buscar_web.disponible():
            raise RuntimeError("Falta la clave de Serper (o Tavily) en el .env del servidor para investigar.")
        resultados, _ = buscar_web.buscar(consultas, por_consulta=5)
        vistos, fuentes = set(), []
        for x in resultados:
            url = x.get("url") or ""
            dominio = re.sub(r"^www\.", "", url.split("/")[2]) if url.count("/") >= 2 else url
            if not url or dominio in vistos and len(fuentes) > 6 or any(b in dominio for b in ("youtube.", "tiktok.", "facebook.", "instagram.", "x.com", "twitter.")):
                continue
            try:
                texto, titulo = _bajar_pagina(url)
            except Exception:  # noqa: BLE001 — una página que no abre no detiene la investigación
                continue
            if len(texto) < 800:
                continue
            vistos.add(dominio)
            fuentes.append({"url": url, "titulo": titulo or x.get("titulo") or x.get("title") or url, "texto": texto[:9000]})
            if len(fuentes) >= 12:
                break
        if len(fuentes) < 3:
            raise RuntimeError(f"No encontré suficientes fuentes buenas sobre {marca} ({len(fuentes)}).")
    bloque = "\n\n".join(f"[F{i}] {f['titulo']} — {f['url']}\n{f['texto']}" for i, f in enumerate(fuentes, 1))
    if _demo():
        r = {"hechos": [{"dato": "Grupo Elektra compró la operación de Blockbuster en México en 2014",
                         "cita": "In 2014 Grupo Elektra acquired the Mexican operations of Blockbuster.", "fuente": "F1"},
                        {"dato": "Blockbuster se declaró en bancarrota en 2010",
                         "cita": "Blockbuster filed for bankruptcy in 2010.", "fuente": "F1"},
                        {"dato": "En 2004 tenía 9,094 tiendas", "cita": "At its peak in 2004, Blockbuster had 9,094 stores.", "fuente": "F1"}],
             "sospechosos": ["El streaming", "Las multas por retraso", "La deuda"], "giro_mexico": "Elektra compró la operación en 2014.",
             "final_feliz": "Ya no hay tiendas en México.", "dudas": ["Cuándo cerró la última tienda en México"]}
    else:
        r = claude.json_estructurado(
            "Eres Vera, investigadora de un canal de YouTube que analiza como caso policiaco por qué murió una marca. "
            "Lee las fuentes y saca SOLO hechos que estén escritos en ellas, cada uno con su cita copiada TAL CUAL "
            "(mismo idioma, mismas palabras) y su fuente [F#]. Prioriza: fechas, cifras (ventas, tiendas, deuda, "
            "empleados), decisiones clave, personas, anécdotas reales y TODO lo de México. Nada de suposiciones.",
            f"MARCA: {marca}\nGANCHO PROPUESTO: {gancho}\n\nFUENTES:\n{bloque}\n\nSaca 30 a 60 hechos útiles para un "
            "video de 15-20 minutos.", ESQ_HECHOS, tarea=TAREA, que=f"investigar {marca}")
    # nada inventado: la cita tiene que estar en la página
    buenos, malos = [], []
    for h in r["hechos"]:
        m = re.match(r"F(\d+)", h.get("fuente", ""))
        f = fuentes[int(m.group(1)) - 1] if m and 0 < int(m.group(1)) <= len(fuentes) else None
        if f and len(h.get("cita", "")) > 15 and _norm(h["cita"]) in _norm(f["texto"]):
            buenos.append({**h, "url": f["url"], "titulo_fuente": f["titulo"]})
        else:
            malos.append(h["dato"])
    if len(buenos) < 3:
        raise RuntimeError(f"Casi ninguna cita se pudo comprobar en las fuentes ({len(buenos)} de {len(r['hechos'])}).")
    return {"hechos": [{"id": f"H{i}", **h} for i, h in enumerate(buenos, 1)], "descartados": malos,
            "sospechosos": r["sospechosos"], "giro_mexico": r["giro_mexico"], "final_feliz": r["final_feliz"],
            "dudas": r["dudas"] + [f"(sin cita comprobable) {x}" for x in malos[:10]],
            "fuentes": [{"url": f["url"], "titulo": f["titulo"]} for f in fuentes]}


# ---------------------------------------------------------------- 2. guion técnico
ESQ_GUION = {
    "type": "object", "additionalProperties": False,
    "required": ["escenas", "descripcion", "etiquetas", "comentario_fijado", "miniatura_a", "miniatura_b", "proximo"],
    "properties": {
        "escenas": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                    "required": ["titulo", "capitulo", "visual", "texto_pantalla", "audio", "frases"],
                    "properties": {
                        "titulo": {"type": "string"}, "capitulo": {"type": "string", "description": "título corto del capítulo de YouTube"},
                        "visual": {"type": "array", "items": {"type": "string"}, "description": "ideas de visual: [STOCK: \"términos\"], [ARCHIVO] foto…, [GRÁFICA] …"},
                        "texto_pantalla": {"type": "array", "items": {"type": "string"}, "description": "máx. 6 palabras cada uno"},
                        "audio": {"type": "string"},
                        "frases": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                   "required": ["texto", "hechos"],
                                   "properties": {"texto": {"type": "string", "description": "una frase/párrafo corto de narración (1-3 oraciones)"},
                                                  "hechos": {"type": "array", "items": {"type": "string"}, "description": "H# en los que se apoya (vacío si es opinión o transición)"}}}}}}},
        "descripcion": {"type": "string", "description": "descripción de YouTube SIN capítulos (se ponen solos), con «🔎 EN ESTE EXPEDIENTE» y la pregunta para comentarios"},
        "etiquetas": {"type": "array", "items": {"type": "string"}},
        "comentario_fijado": {"type": "string"},
        "miniatura_a": {"type": "array", "items": {"type": "string"}, "description": "2 o 3 renglones gigantes (máx. 3 palabras c/u), de preferencia con número"},
        "miniatura_b": {"type": "array", "items": {"type": "string"}, "description": "comparación: [izquierda, derecha, etiqueta izq, etiqueta der] p. ej. ['QUEDAN 5','96','EE.UU.','MÉXICO']"},
        "proximo": {"type": "string", "description": "el siguiente expediente que se anuncia al final"},
    },
}


def _ejemplo_guion() -> str:
    """Dos escenas del guion de Tupperware como ejemplo de tono y formato."""
    g = (CANAL_DIR / "02-tupperware" / "01-guion-tecnico.md")
    if not g.exists():
        return ""
    texto = g.read_text(encoding="utf-8")
    i = texto.find("## ESCENA 1")
    j = texto.find("## ESCENA 3")
    k = texto.find("## ESCENA 7")
    m = texto.find("## ESCENA 8")
    return texto[i:j] + "\n…\n" + (texto[k:m] if k > 0 and m > k else "")


def _sistema_canal() -> str:
    guia = (CANAL_DIR / "CLAUDE.md")
    return guia.read_text(encoding="utf-8")[:7000] if guia.exists() else ""


def escribir_guion(tema: dict, inv: dict, numero: str, siguiente: str) -> dict:
    hechos = "\n".join(f"{h['id']}: {h['dato']}  (cita: «{h['cita'][:200]}»)" for h in inv["hechos"])
    pedido = (f"EXPEDIENTE #{numero} · MARCA: {tema['marca']}\nGANCHO PROPUESTO: {tema.get('gancho', '')}\n"
              f"SOSPECHOSOS QUE SALEN DE LA INVESTIGACIÓN: {'; '.join(inv['sospechosos'])}\n"
              f"GIRO DE MÉXICO: {inv['giro_mexico'] or '(no hay datos: no lo inventes)'}\n¿FINAL FELIZ?: {inv['final_feliz']}\n"
              f"DUDAS (no las afirmes): {'; '.join(inv['dudas'][:12])}\nPRÓXIMO EXPEDIENTE SUGERIDO: {siguiente}\n\n"
              f"HECHOS COMPROBADOS (lo único que puedes afirmar; cita su H# en cada frase que los use):\n{hechos}\n\n"
              f"EJEMPLO DE TONO Y FORMATO (Tupperware):\n{_ejemplo_guion()[:9000]}")
    if _demo():
        def F(t, h=()):
            return {"texto": t, "hechos": list(h)}
        return {"escenas": [
            {"titulo": "Gancho", "capitulo": "Cada viernes, a rentar", "visual": ['[STOCK: "vhs tapes"]'], "texto_pantalla": ["CADA VIERNES"],
             "audio": "misterio", "frases": [F("Cada viernes media familia se tardaba una hora en escoger qué película rentar."),
                                             F("En 2004 tenía 9,094 tiendas.", ["H3"]), F("Hoy abrimos el expediente: ¿quién mató a Blockbuster?")]},
            {"titulo": "El giro: México", "capitulo": "Mientras tanto, en México", "visual": ['[STOCK: "video store"]'], "texto_pantalla": ["ELEKTRA · 2014"],
             "audio": "esperanza", "frases": [F("En 2014 Grupo Elektra compró la operación de México.", ["H1"]),
                                              F("Y en 2010 Blockbuster se declaró en bancarrota.", ["H2"]),
                                              F("Mientras tanto, aquí la gente seguía rentando.")]},
            {"titulo": "Cierre y el próximo caso", "capitulo": "El próximo caso", "visual": [], "texto_pantalla": ["PRÓXIMO EXPEDIENTE"],
             "audio": "cierre", "frases": [F("El próximo expediente: RadioShack. Suscríbete.")]}],
            "descripcion": "En 2014 Elektra compró Blockbuster México. ¿Qué pasó? (demo)\n\n💬 ¿Tú rentabas en Blockbuster?",
            "etiquetas": ["blockbuster", "quién mató a"], "comentario_fijado": "¿Rentabas en Blockbuster? 👇",
            "miniatura_a": ["LA MATÓ", "NETFLIX?"], "miniatura_b": ["9,094", "0", "2004", "HOY"], "proximo": "RadioShack"}
    return claude.json_estructurado(
        "Eres Vera, guionista del canal «¿Quién MATÓ a…?». Escribes guiones técnicos de 15 a 20 minutos (2,200 a "
        "2,800 palabras de narración, 12 a 15 escenas) para un video que se arma solo con un motor: cada «frase» se "
        "vuelve una o varias tarjetas en pantalla. Reglas del canal (síguelas al pie de la letra):\n\n"
        + _sistema_canal() + "\n\nREGLAS DURAS: toda cifra, fecha, nombre o hecho de la narración tiene que venir de "
        "los HECHOS COMPROBADOS (pon su H#). Si un dato no está, no lo digas. Opinión solo en el veredicto y dicha como "
        "opinión. No acuses a nadie de delitos. Frases cortas, tono de caso policiaco, palabras de México. La primera "
        "escena es el gancho (30-60 s) y la última el adelanto del próximo expediente. El título del video es fijo: "
        f"«¿Quién MATÓ a {tema['marca']}?».",
        pedido, ESQ_GUION, tarea=TAREA, que=f"guion {tema['marca']}")


def _revisar_cifras(g: dict, inv: dict) -> list[dict]:
    """Frases con cifras que no salen de sus hechos → [VERIFICAR] (Ramos las revisa)."""
    por_id = {h["id"]: h for h in inv["hechos"]}
    dudosas = []
    for n, e in enumerate(g["escenas"], 1):
        for f in e["frases"]:
            cifras = ex.numeros(f["texto"])
            if not cifras:
                continue
            permitidas = set()
            for hid in f.get("hechos") or []:
                h = por_id.get(hid)
                if h:
                    permitidas |= ex.numeros(h["dato"]) | ex.numeros(h["cita"])
            sobran = cifras - permitidas
            if sobran:
                dudosas.append({"escena": n, "frase": f["texto"], "cifras": sorted(sobran)})
    return dudosas


def _md_guion(tema: dict, numero: str, g: dict) -> str:
    total = sum(len(f["texto"].split()) for e in g["escenas"] for f in e["frases"])
    s = [f"# ¿Quién MATÓ a {tema['marca']}? · Guion técnico", "",
         f"**Expediente #{numero}** · Canal: serie \"¿Quién MATÓ a…?\" · hecho por la Agencia (Vera)", "",
         f"**Total:** unas {total:,} palabras de narración (~{round(total / 165)} min con la voz a +12 %).", "", "---", ""]
    for n, e in enumerate(g["escenas"], 1):
        s += [f"## ESCENA {n} · {e['titulo']}", "", "**Visual:**", *[f"- {v}" for v in e["visual"]], "",
              f"**Texto en pantalla:** " + " · ".join(f"\"{x}\"" for x in e["texto_pantalla"]), "",
              f"**Audio:** {e['audio']}", ""]
        for f in e["frases"]:
            s += [f"> {f['texto'].strip()}", ""]
        s += ["---", ""]
    return "\n".join(s)


def _md_fuentes(tema: dict, g: dict, inv: dict, dudosas: list[dict]) -> str:
    por_id = {h["id"]: h for h in inv["hechos"]}
    s = [f"# ¿Quién MATÓ a {tema['marca']}? · Fuentes", "",
         "Toda cifra que salga en pantalla tiene que venir de esta lista. Si un dato no se puede confirmar, se quita del guion.",
         "", "## Por escena", ""]
    for n, e in enumerate(g["escenas"], 1):
        usados = []
        for f in e["frases"]:
            for hid in f.get("hechos") or []:
                h = por_id.get(hid)
                if h and h["url"] not in [u for u, _ in usados]:
                    usados.append((h["url"], h))
        if usados:
            s += [f"### Escena {n}: {e['titulo']}"]
            for url, h in usados:
                s.append(f"- [{h['titulo_fuente'][:90]}]({url}): {h['dato']}")
            s.append("")
    s += ["## Lista de datos por verificar", "", "| # | Dato | Por qué falta confirmarlo |", "|---|---|---|"]
    k = 0
    for d in dudosas:
        k += 1
        s.append(f"| {k} | {d['frase'][:160]} | Trae cifras ({', '.join(d['cifras'])}) que no están en su fuente |")
    for x in inv["dudas"][:10]:
        k += 1
        s.append(f"| {k} | {x[:160]} | No se pudo confirmar en la investigación |")
    return "\n".join(s) + "\n"


def _md_publicacion(tema: dict, g: dict) -> str:
    return "\n".join([
        f"# ¿Quién MATÓ a {tema['marca']}? · Publicación", "", "## Título (plantilla fija de la serie, no se cambia)", "",
        f"**¿Quién MATÓ a {tema['marca']}?**", "", "## Miniatura", "",
        f"- A: {' / '.join(g['miniatura_a'])}", f"- B: {' vs '.join(g['miniatura_b'][:2])}", "", "## Descripción", "",
        "```", g["descripcion"], "```", "", "## Etiquetas", "", ", ".join(g["etiquetas"]), "", "## Comentario fijado", "",
        "```", g["comentario_fijado"], "```", ""])


# ---------------------------------------------------------------- 3. material libre
ESQ_BUSQUEDAS = {"type": "object", "additionalProperties": False, "required": ["escenas"], "properties": {"escenas": {
    "type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["commons", "videos"],
                               "properties": {"commons": {"type": "array", "items": {"type": "string"}, "description": "1-3 búsquedas en inglés para Wikimedia Commons (fotos reales de la marca, tiendas, personas, logos históricos)"},
                                              "videos": {"type": "array", "items": {"type": "string"}, "description": "1-2 búsquedas en inglés de video de stock genérico (ambiente)"}}}}}}
ESQ_ELEGIR = {"type": "object", "additionalProperties": False, "required": ["elegidos"], "properties": {"elegidos": {
    "type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["id", "nombre", "describe", "escenas"],
                               "properties": {"id": {"type": "string", "description": "C# o P# del candidato"},
                                              "nombre": {"type": "string", "description": "nombre corto de archivo, minúsculas-con-guiones, sin extensión"},
                                              "describe": {"type": "string", "description": "qué se ve, en 6-12 palabras"},
                                              "escenas": {"type": "array", "items": {"type": "integer"}}}}}}}
LIBRES = ("public domain", "cc0", "cc by", "cc-by", "no restrictions", "pd-", "pd ", "attribution")


def _licencia_libre(lic: str) -> bool:
    x = (lic or "").lower()
    return any(k in x for k in LIBRES) and not any(k in x for k in ("nc", "nd", "fair use", "non-free", "noderivs", "noncommercial"))


def _fuentes_libres():
    sys.path.insert(0, str(MOTOR))
    import fuentes_libres  # noqa: E402 — el mismo módulo del motor (solo biblioteca estándar)
    return fuentes_libres


def buscar_material(tema: dict, g: dict) -> dict:
    if _demo():
        return {"fotos": [], "videos": [], "lista": []}
    escenas = "\n".join(f"{n}. {e['titulo']} — visual: {'; '.join(e['visual'])[:300]}" for n, e in enumerate(g["escenas"], 1))
    b = claude.json_estructurado(
        "Eres Inés, archivista. Propones búsquedas para conseguir material con licencia libre por escena.",
        f"MARCA: {tema['marca']}\nESCENAS:\n{escenas}\n\nUna entrada por escena, en el mismo orden.", ESQ_BUSQUEDAS,
        tarea=TAREA, que=f"búsquedas de material {tema['marca']}")
    fl = _fuentes_libres()
    candidatos, vistos = [], set()
    hay_pexels = (CANAL_DIR / ".pexels_key").exists()
    for n, e in enumerate(b["escenas"][:len(g["escenas"])], 1):
        for q in e["commons"][:3]:
            try:
                res = fl.commons(q, 10)
            except Exception:  # noqa: BLE001
                continue
            for x in res:
                if x["titulo"] in vistos or not _licencia_libre(x.get("licencia")):
                    continue
                if not (x.get("mime") or "").startswith(("image/jpeg", "image/png", "video/webm")):
                    continue
                if (x.get("ancho") or 0) < 900:
                    continue
                vistos.add(x["titulo"])
                candidatos.append({**x, "id": f"C{len(candidatos) + 1}", "escena": n})
        if hay_pexels:
            for q in e["videos"][:2]:
                try:
                    res = fl.pexels_video(q, 4)
                except Exception:  # noqa: BLE001
                    continue
                for x in res:
                    if x["titulo"] in vistos:
                        continue
                    vistos.add(x["titulo"])
                    candidatos.append({**x, "id": f"P{len(candidatos) + 1}", "escena": n})
    if not candidatos:
        return {"fotos": [], "videos": [], "lista": []}
    lista = "\n".join(f"{c['id']} (escena {c['escena']}) {c['fuente']} · {c['titulo'][:90]} · {c.get('ancho')}x{c.get('alto')}"
                      for c in candidatos[:220])
    el = claude.json_estructurado(
        "Eres Inés, archivista. Escoge el mejor material para cada escena (fotos reales de la marca y su época, "
        "tiendas, logos, personas públicas relevantes; videos de ambiente). Nada de personas privadas. Entre 25 y 45 "
        "archivos en total, que cubran todas las escenas.",
        f"MARCA: {tema['marca']}\nCANDIDATOS:\n{lista}", ESQ_ELEGIR, tarea=TAREA, que=f"escoger material {tema['marca']}")
    por_id = {c["id"]: c for c in candidatos}
    fotos, videos, elegidos, usados = [], [], [], set()
    thumbs = {}
    titulos = [por_id[x["id"]]["titulo"] for x in el["elegidos"] if x["id"] in por_id and por_id[x["id"]]["fuente"] == "Wikimedia Commons"
               and not por_id[x["id"]]["mime"].startswith("video")]
    try:
        thumbs = fl.commons_thumbs(titulos) if titulos else {}
    except Exception:  # noqa: BLE001
        thumbs = {}
    for x in el["elegidos"]:
        c = por_id.get(x["id"])
        if not c:
            continue
        nombre = _slug(x["nombre"], 40)
        while nombre in usados:
            nombre += "-b"
        usados.add(nombre)
        es_video = c["fuente"] == "Pexels" or (c.get("mime") or "").startswith("video")
        url = c["url"]
        if c["fuente"] == "Wikimedia Commons":
            if es_video:
                try:
                    url = fl.commons_video_transcode(c["titulo"]) or ""
                except Exception:  # noqa: BLE001
                    url = ""
            else:
                url = thumbs.get(c["titulo"]) or c["url"]
        if not url:
            continue
        ext = ".mp4" if c["fuente"] == "Pexels" else Path(url.split("?")[0]).suffix.lower() or ".jpg"
        item = {"nombre": nombre + ext, "url": url, "fuente": c["fuente"], "licencia": c.get("licencia"),
                "autor": c.get("autor"), "pagina": c.get("pagina"), "titulo": c.get("titulo")}
        (videos if es_video else fotos).append(item)
        elegidos.append({"archivo": f"material/{'videos' if es_video else 'fotos'}/{nombre + ext}", "describe": x["describe"],
                         "escenas": x["escenas"], "video": es_video, "fuente": c["fuente"]})
    return {"fotos": fotos, "videos": videos, "lista": elegidos}


# ---------------------------------------------------------------- 4. storyboard
ESQ_SB = {"type": "object", "additionalProperties": False, "required": ["codigo"],
          "properties": {"codigo": {"type": "string", "description": "el archivo storyboard.py completo"}}}
NOMBRES_PROHIBIDOS = {"eval", "exec", "open", "compile", "__import__", "globals", "locals", "vars", "getattr", "setattr",
                      "delattr", "input", "breakpoint", "exit", "quit", "help", "memoryview", "os", "sys", "subprocess",
                      "shutil", "socket", "urllib", "requests", "importlib", "builtins"}
ATRIBUTOS_PROHIBIDOS = {"write_text", "write_bytes", "unlink", "rmdir", "mkdir", "rename", "touch", "chmod", "symlink_to",
                        "system", "popen", "remove", "rmtree", "open", "hardlink_to", "load_module", "exec_module"}


def codigo_seguro(src: str) -> str | None:
    """El storyboard lo escribe Claude con datos de internet: antes de correrlo (aquí y en tu compu) se revisa que
    solo arme tarjetas. Regresa el problema o None."""
    try:
        arbol = ast.parse(src)
    except SyntaxError as exc:
        return f"Error de sintaxis en la línea {exc.lineno}: {exc.msg}"
    for n in ast.walk(arbol):
        if isinstance(n, ast.Import):
            if any(a.name not in ("json", "pathlib") for a in n.names):
                return f"import no permitido: {', '.join(a.name for a in n.names)}"
        elif isinstance(n, ast.ImportFrom):
            if n.module not in ("sb", "pathlib", "json"):
                return f"import no permitido: {n.module}"
        elif isinstance(n, ast.Name) and n.id in NOMBRES_PROHIBIDOS:
            return f"no se permite usar «{n.id}»"
        elif isinstance(n, ast.Attribute) and (n.attr.startswith("__") or n.attr in ATRIBUTOS_PROHIBIDOS):
            return f"no se permite «.{n.attr}»"
        elif isinstance(n, (ast.Global, ast.Nonlocal, ast.AsyncFunctionDef, ast.Await, ast.ClassDef)):
            return "estructura no permitida"
    return None


PRUEBA_SB = r'''
import importlib.util, json, re, sys
from pathlib import Path
ep_dir = Path(sys.argv[1]); sys.path.insert(0, sys.argv[2])
spec = importlib.util.spec_from_file_location("storyboard", ep_dir / "storyboard.py")
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
EP = mod.EP
guion = (ep_dir / EP["guion"]).read_text(encoding="utf-8")
esc, cur = [], None
for line in guion.splitlines():
    m = re.match(r"^## ESCENA\s+(\d+)\s*·\s*(.*)$", line)
    if m: cur = []; esc.append(cur); continue
    if cur is not None and line.startswith("> "): cur.append(line)
errores, archivos = [], set()
def junta(x):
    if isinstance(x, dict):
        for v in x.values(): junta(v)
    elif isinstance(x, (list, tuple)):
        for v in x: junta(v)
    elif isinstance(x, str) and x.startswith("material/"): archivos.add(x)
if len(esc) != len(EP["escenas"]):
    errores.append(f"El guion tiene {len(esc)} escenas y el storyboard {len(EP['escenas'])}.")
for i, (g, s) in enumerate(zip(esc, EP["escenas"]), 1):
    if len(g) != len(s["cards"]):
        errores.append(f"Escena {i}: {len(g)} frases en el guion y {len(s['cards'])} entradas en cards.")
    for c in s["cards"]:
        for t in (c if isinstance(c, list) else [c]):
            if not isinstance(t, dict) or "t" not in t: errores.append(f"Escena {i}: una tarjeta no es válida ({str(t)[:60]}).")
junta(EP)
print(json.dumps({"errores": errores[:12], "archivos": sorted(archivos), "nombre": EP.get("nombre", "")}))
'''


def _probar_storyboard(carpeta: Path) -> dict:
    prueba = carpeta / "_prueba_sb.py"
    prueba.write_text(PRUEBA_SB, encoding="utf-8")
    try:
        r = subprocess.run([sys.executable, "-I", str(prueba), str(carpeta), str(MOTOR)], capture_output=True, text=True,
                           timeout=60, cwd=str(carpeta))
    finally:
        prueba.unlink(missing_ok=True)
    if r.returncode != 0:
        return {"errores": [(r.stderr or r.stdout or "falló")[-600:]], "archivos": []}
    return json.loads(r.stdout.strip().splitlines()[-1])


def _ejemplo_storyboard() -> str:
    sb_tup = CANAL_DIR / "02-tupperware" / "storyboard.py"
    if not sb_tup.exists():
        return ""
    texto = sb_tup.read_text(encoding="utf-8")
    corte = texto.find("# 4 ·")
    return texto[:corte if corte > 0 else 12000][:14000]


def _storyboard_demo(tema: dict, numero: str, g: dict) -> str:
    escenas = []
    for e in g["escenas"]:
        cards = ", ".join(f"Q({json.dumps(f['texto'][:60].upper(), ensure_ascii=False)})" for f in e["frases"])
        escenas.append(f"        dict(capitulo={json.dumps(e['capitulo'], ensure_ascii=False)}, cards=[{cards}]),")
    return ("from sb import *  # noqa: F401,F403\n\nEP = dict(\n"
            f"    label=\"EXPEDIENTE #{numero} · {tema['marca'].upper()}\",\n    nombre=\"Expediente-{numero}-{_slug(tema['marca']).title()}\",\n"
            "    guion=\"01-guion-tecnico.md\",\n    salida=\"render\",\n    estilo=\"cine\",\n    voz_motor=\"azure\",\n"
            "    voz=\"es-MX-JorgeNeural\",\n    voz_velocidad=\"+12%\",\n    musica_vol=0.35,\n    fonetica_azure={},\n"
            "    end=END(),\n    escenas=[\n" + "\n".join(escenas) + "\n    ],\n)\n")


def escribir_storyboard(tema: dict, numero: str, g: dict, material: dict, carpeta: Path) -> str:
    frases = []
    for n, e in enumerate(g["escenas"], 1):
        frases.append(f"ESCENA {n} · {e['titulo']} (capítulo «{e['capitulo']}») — {len(e['frases'])} frases → {len(e['frases'])} entradas en cards:")
        frases += [f"  {k}. {f['texto']}" for k, f in enumerate(e["frases"], 1)]
        if e["texto_pantalla"]:
            frases.append(f"  texto en pantalla sugerido: {' · '.join(e['texto_pantalla'])}")
    mat = "\n".join(f"- {m['archivo']} — {m['describe']} (escenas {m['escenas']}, {m['fuente']})" for m in material["lista"]) \
        or "(no hay material descargable: usa solo tarjetas gráficas Q/TITLE/NUM/BARS/STAMP/TIMELINE/STATS/BOARD/FILE…)"
    api_sb = (MOTOR / "sb.py").read_text(encoding="utf-8")
    pedido = (f"EXPEDIENTE #{numero} · {tema['marca']}\n\nGUION (una entrada de cards por frase, en el mismo orden):\n"
              + "\n".join(frases) + f"\n\nMATERIAL DISPONIBLE (usa solo estos archivos; F('nombre.jpg') para fotos y "
              f"V('nombre') para videos SIN extensión .mp4 — si un video es .webm usa la ruta completa con VIDEO):\n{mat}")
    if _demo():
        codigo = _storyboard_demo(tema, numero, g)
        (carpeta / "storyboard.py").write_text(codigo, encoding="utf-8")
        r = _probar_storyboard(carpeta)
        if r.get("errores"):
            raise RuntimeError("; ".join(r["errores"]))
        return codigo
    sistema = ("Eres Nico, el que arma los storyboards del motor de video (estilo «cine»: material real a pantalla "
               "completa casi siempre, gráficas sobre video desenfocado con fondo= por escena, cambio de imagen cada 3-5 s, "
               "créditos chicos). Escribe el archivo storyboard.py COMPLETO como el ejemplo: mismas funciones de ayuda "
               "(F, V, cr, P, M con créditos de material/fotos|videos/creditos.json), EP con label, nombre "
               f"(«Expediente-{numero}-Marca»), guion='01-guion-tecnico.md', salida='render', estilo='cine', "
               "voz_motor='azure', voz='es-MX-JorgeNeural', voz_velocidad='+12%', musica_vol=0.35, fonetica_azure "
               "(nombres en inglés como se pronuncian en español), end=END(bg=...), y escenas=[dict(capitulo=..., "
               "fondo=..., cards=[...]), ...]. REGLAS: exactamente UNA entrada en cards por frase (si una frase lleva "
               "varias tarjetas, va una lista [...] con w=); las cifras en pantalla solo si están en la frase; nada de "
               "archivos que no estén en la lista; solo Python simple (sin imports fuera de json/pathlib/sb, sin abrir "
               "ni escribir archivos, sin os/sys).\n\nAPI DE TARJETAS (sb.py):\n" + api_sb
               + "\n\nEJEMPLO (Tupperware, primeras escenas):\n" + _ejemplo_storyboard())
    error = ""
    for intento in range(3):
        texto = pedido + (f"\n\nTU VERSIÓN ANTERIOR TUVO ESTOS PROBLEMAS, corrígelos:\n{error}" if error else "")
        codigo = claude.json_estructurado(sistema, texto, ESQ_SB, tarea=TAREA, que=f"storyboard {tema['marca']} ({intento + 1})")["codigo"]
        codigo = re.sub(r"^```(?:python)?\s*|\s*```$", "", codigo.strip())
        problema = codigo_seguro(codigo)
        if problema:
            error = f"- Código no permitido: {problema}"
            continue
        (carpeta / "storyboard.py").write_text(codigo, encoding="utf-8")
        r = _probar_storyboard(carpeta)
        validos = {m["archivo"] for m in material["lista"]}
        faltan = [a for a in r.get("archivos", []) if a not in validos and not a.endswith("creditos.json")]
        errores = r.get("errores", []) + [f"Archivo que no está en la lista: {a}" for a in faltan[:8]]
        if not errores:
            return codigo
        error = "\n".join(f"- {e}" for e in errores)
    raise RuntimeError(f"El storyboard no quedó bien después de 3 intentos: {error[:400]}")


def miniatura_py(tema: dict, numero: str, g: dict) -> str:
    """El miniatura.py del episodio (como el de Tupperware): A = 2-3 renglones gigantes; B = comparación."""
    a = (g.get("miniatura_a") or [tema["marca"].upper(), "¿QUIÉN LA MATÓ?"])[:3]
    b = (g.get("miniatura_b") or ["ANTES", "HOY", "", ""]) + ["", "", "", ""]
    colores = ["ink", "tape", "red"]
    lineas = "\n".join(f"texto(d, (930, {150 + i * 250}), {json.dumps(t[:18], ensure_ascii=False)}, {240 if i == 0 else 210}, \"{colores[i]}\")"
                       for i, t in enumerate(a))
    return f'''"""Miniaturas A y B del Expediente #{numero} (1280×720 JPG). Hecho por la Agencia (Mina).

Uso: python miniatura.py
"""
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent / "motor"))
import motor as m  # noqa: E402
from PIL import ImageDraw  # noqa: E402

OUT = AQUI / "render"
OUT.mkdir(exist_ok=True)


def guardar(img, nombre):
    img = img.convert("RGB").resize((1280, 720), m.Image.LANCZOS)
    img.save(OUT / nombre, quality=90, optimize=True)


def texto(d, xy, s, size, color, anchor="la"):
    f = m.font("display", size)
    d.text(xy, s, font=f, fill=m.C[color], anchor=anchor, stroke_width=max(4, size // 28), stroke_fill=(0, 0, 0))


def foto():
    for sub in ("fotos",):
        fs = sorted((AQUI / "material" / sub).glob("*.jp*g"))
        if fs:
            return m.Image.open(fs[0]).convert("L").convert("RGB")
    return None


# --- A: foto deslavada + cinta + renglones gigantes
img, d = m.canvas()
f = foto()
if f:
    img.paste(m.cover(f, 900, m.H), (0, 0))
band = m.tape_band("ESCENA DEL CRIMEN · NO PASAR", 1500, 24)
band = band.crop((0, 0, 980, band.height))
img.paste(band, (-120, 330), band)
d = ImageDraw.Draw(img)
{lineas}
img.paste(m.hazard(m.W, 18), (0, m.H - 18))
guardar(img, "miniatura-A.jpg")

# --- B: comparación lado a lado
img, d = m.canvas()
d.rectangle([0, 0, m.W // 2, m.H], fill=(30, 14, 16))
d.rectangle([m.W // 2, 0, m.W, m.H], fill=(12, 30, 18))
texto(d, (480, 520), {json.dumps(b[0][:10], ensure_ascii=False)}, 300, "red", anchor="mm")
texto(d, (1440, 520), {json.dumps(b[1][:10], ensure_ascii=False)}, 300, "green", anchor="mm")
texto(d, (480, 820), {json.dumps(b[2][:18], ensure_ascii=False)}, 90, "ink", anchor="mm")
texto(d, (1440, 820), {json.dumps(b[3][:18], ensure_ascii=False)}, 90, "ink", anchor="mm")
d.rectangle([m.W // 2 - 6, 0, m.W // 2 + 6, m.H], fill=m.C["tape"])
img.paste(m.hazard(m.W, 18), (0, m.H - 18))
guardar(img, "miniatura-B.jpg")
'''


# ---------------------------------------------------------------- producir un caso completo
def _siguiente_numero() -> str:
    usados = [int(x["numero"]) for x in ex.lista()] + [1, 2]  # #001 Sears y #002 Tupperware ya existen
    for c in CANAL_DIR.glob("[0-9][0-9]-*"):
        usados.append(int(c.name[:2]))
    return f"{max(usados) + 1:03d}"


def _paso(eid: str | None, clave: str, agente: str, dice: str, tarea: dict | None = None) -> None:
    ex._decir(agente, "trabajando", dice)
    if tarea:
        tarea["paso"] = dice
    if eid:
        _poner(eid, paso=clave, error=None)


def _hecho(eid: str, clave: str, agente: str) -> None:
    f = fab(eid)
    _poner(eid, hechos_pasos=sorted(set(f.get("hechos_pasos") or []) | {clave}))
    ex._decir(agente, "libre")


def producir(tema_id: str) -> dict:
    """Arranca la producción de un tema en segundo plano."""
    with _candado:
        e = estado()
        if e.get("en_curso"):
            return {"error": "Ya hay un caso en producción; espera a que termine."}
        lista = temas()
        tema = next((x for x in lista if x["id"] == tema_id), None)
        if not tema or tema["estado"] not in ("pendiente", "propuesto"):
            return {"error": "Ese tema no está disponible."}
        tema["estado"] = "produciendo"
        _guardar_temas(lista)
        e["en_curso"] = tema_id
        _guardar_estado(e)
    threading.Thread(target=_producir, args=(tema_id,), daemon=True).start()
    return {"ok": True}


def _producir(tema_id: str) -> None:
    tema = next(x for x in temas() if x["id"] == tema_id)
    numero = _siguiente_numero()
    tarea = ex._tarea("ex_guion", "Producir el expediente", f"#{numero} · {tema['marca']}")
    claude.contexto.proyecto, claude.contexto.etapa, claude.contexto.tarea = None, "expedientes", tarea
    eid, mesa = None, None
    try:
        _paso(None, "investigacion", "ex_guion", f"Investigando {tema['marca']}… 🔎", tarea)
        inv = investigar(tema)
        siguiente = next((x["marca"] for x in temas() if x["estado"] == "pendiente" and x["id"] != tema_id), "otra marca")
        _paso(None, "guion", "ex_guion", f"Escribiendo el guion de {tema['marca']} ✍️", tarea)
        g = escribir_guion(tema, inv, numero, siguiente)
        if len(g["escenas"]) < 3 or sum(len(e["frases"]) for e in g["escenas"]) < 6:
            raise RuntimeError("El guion salió demasiado corto.")
        dudosas = _revisar_cifras(g, inv)
        ex._decir("ex_guion", "libre", f"Guion de {tema['marca']} listo ✔")
        mesa = ex.CARPETA / "_mesa" / f"{numero}-{_slug(tema['marca'])}"
        shutil.rmtree(mesa, ignore_errors=True)
        mesa.mkdir(parents=True)
        partes = {"01-guion-tecnico.md": _md_guion(tema, numero, g), "04-fuentes.md": _md_fuentes(tema, g, inv, dudosas),
                  "03-publicacion.md": _md_publicacion(tema, g)}
        for nombre, texto in partes.items():
            (mesa / nombre).write_text(texto, encoding="utf-8")
        _paso(None, "material", "ex_archivista", "Buscando fotos y videos libres 🗄️", tarea)
        material = buscar_material(tema, g)
        ex._decir("ex_archivista", "libre", f"{len(material['lista'])} archivos libres para {tema['marca']} ✔")
        _paso(None, "storyboard", "ex_graficas", "Armando el storyboard 📊", tarea)
        escribir_storyboard(tema, numero, g, material, mesa)
        ex._decir("ex_graficas", "libre", "Storyboard listo y revisado ✔")
        # al expediente (Casos): Ramos lo verifica como siempre
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for nombre, texto in partes.items():
                z.writestr(nombre, texto)
        r = ex.importar(f"expediente-{numero}.zip", buf.getvalue())
        eid = r["id"]
        destino = ex.carpeta(eid) / "fabrica"
        shutil.rmtree(destino, ignore_errors=True)
        destino.mkdir(parents=True)
        for nombre in ("storyboard.py", *partes):
            shutil.copyfile(mesa / nombre, destino / nombre)
        (destino / "miniatura.py").write_text(miniatura_py(tema, numero, g), encoding="utf-8")
        _escribir(destino / "manifiesto-fotos.json", material["fotos"])
        _escribir(destino / "manifiesto-videos.json", material["videos"])
        _escribir(destino / "investigacion.json", inv)
        _escribir(destino / "guion.json", g)
        _poner(eid, tema=tema_id, canal=tema.get("canal") or "quien_mato", numero=numero, marca=tema["marca"],
               carpeta=f"{numero[-2:]}-{_slug(tema['marca'], 30)}", hechos_pasos=["investigacion", "guion", "material", "storyboard"],
               paso="verificacion", dudosas=len(dudosas), material=len(material["lista"]), creado=time.time(),
               palabras=sum(len(f["texto"].split()) for e in g["escenas"] for f in e["frases"]))
        with _candado:
            lista = temas()
            for x in lista:
                if x["id"] == tema_id:
                    x["estado"], x["eid"] = "listo", eid
            _guardar_temas(lista)
        ex._fin_tarea(tarea, resultado=f"Expediente #{numero} listo para verificar")
        ex.verificar(eid)
    except Exception as exc:  # noqa: BLE001 — se ve en la Bandeja; el tema regresa a la lista
        limite = isinstance(exc, claude.ErrorIA) and "límite" in str(exc).lower()
        ex._fin_tarea(tarea, error=str(exc)[:300])
        ex._decir("ex_guion", "libre", "Se acabó el límite del plan; sigo al rato ⏳" if limite else "Uy, algo falló 😕")
        with _candado:
            lista = temas()
            for x in lista:
                if x["id"] == tema_id:
                    x["estado"] = "pendiente"
                    x["error"] = None if limite else str(exc)[:300]
                    x["intentos"] = x.get("intentos", 0) + (0 if limite else 1)
                    if x["intentos"] >= 2:
                        x["estado"] = "saltado"
            _guardar_temas(lista)
            e = estado()
            if limite:
                e["espera_hasta"] = time.time() + 3600
                e["nota"] = "Se acabó el límite de tu plan de Claude: sigo sola en cuanto vuelva."
            _guardar_estado(e)
    finally:
        claude.contexto.tarea = None
        if mesa:
            shutil.rmtree(mesa, ignore_errors=True)
        with _candado:
            e = estado()
            if e.get("en_curso") == tema_id:
                e["en_curso"] = None
                _guardar_estado(e)


# ---------------------------------------------------------------- 5-6. verificación → render en tu compu
def _listo_para_render(eid: str, t: dict) -> bool:
    f = t.get("fabrica") or {}
    if not f or f.get("render_estado") in ("en_fila", "listo") or f.get("render_ok") is False:
        return False
    v = t["verificacion"].get("estado")
    if v == "aprobada":
        return True
    if v == "lista":  # sin nada que corregir → directo a render (los ✅ no necesitan tu OK)
        c = ex._cuenta(t["datos"])
        return not c.get("corregir") and not c.get("no_confirmado") and not c.get("pendiente")
    return False


def _guion_final(eid: str) -> str:
    """El guion técnico con la narración corregida si aprobaste cambios de Ramos (misma cantidad de frases)."""
    c = ex.carpeta(eid)
    texto = (c / "fabrica" / "01-guion-tecnico.md").read_text(encoding="utf-8")
    corregida = ex._leer_json(c / "narracion-corregida.json", None)
    if not corregida:
        return texto
    escenas = corregida.get("escenas") if isinstance(corregida, dict) else corregida
    nuevas = [p for e in escenas or [] for p in e.get("narracion", [])]
    lineas, k = texto.splitlines(), 0
    viejas = [i for i, ln in enumerate(lineas) if ln.startswith("> ")]
    if len(nuevas) != len(viejas):
        return texto  # no cuadran las frases: mejor el original (el storyboard depende del orden)
    for i, nueva in zip(viejas, nuevas):
        lineas[i] = "> " + nueva.strip()
    return "\n".join(lineas) + "\n"


def _zip_render(eid: str) -> Path:
    c = ex.carpeta(eid)
    f = fab(eid)
    salida = c / "render-envio.zip"
    with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("01-guion-tecnico.md", _guion_final(eid))
        for nombre in ("storyboard.py", "miniatura.py", "manifiesto-fotos.json", "manifiesto-videos.json",
                       "04-fuentes.md", "03-publicacion.md"):
            p = c / "fabrica" / nombre
            if p.exists():
                z.write(p, nombre)
    if codigo_seguro((c / "fabrica" / "storyboard.py").read_text(encoding="utf-8")):
        raise RuntimeError("El storyboard no pasó la revisión de seguridad.")
    return salida


def enviar_render(eid: str) -> dict:
    import requests
    f = fab(eid)
    if _demo():
        _poner(eid, render_estado="listo", paso="revision", hechos_pasos=sorted(set(f.get("hechos_pasos") or []) | {"verificacion", "render"}),
               render_ok=True, video=None, render_nota="(demo) Aquí saldría el video que hizo tu compu.")
        ex._decir("ex_editor", "libre", "Video listo (demo) 🎬")
        return {"ok": True}
    try:
        zipf = _zip_render(eid)
    except Exception as exc:  # noqa: BLE001
        _poner(eid, error=str(exc)[:300], paso="render")
        return {"error": str(exc)}
    salida = ex.carpeta(eid) / "render-salida"
    shutil.rmtree(salida, ignore_errors=True)
    salida.mkdir(parents=True)
    try:
        r = requests.post(f"{SALA_URL}/interno/trabajo", timeout=15, json={
            "tipo": "expediente", "origen": "expedientes", "etiqueta": f"🕵️ Expediente #{f.get('numero')} · {f.get('marca')}"[:80],
            "parametros": {"carpeta": f.get("carpeta"), "nombre": f"Expediente-{f.get('numero')}"},
            "entradas": [str(zipf)], "salida": str(salida)}).json()
    except (requests.RequestException, ValueError) as exc:
        return {"error": f"La sala de edición no contestó ({exc})."}
    if not r.get("id"):
        return {"error": r.get("error") or "La sala no aceptó el trabajo."}
    _poner(eid, render_estado="en_fila", render_tid=r["id"], paso="render",
           hechos_pasos=sorted(set(f.get("hechos_pasos") or []) | {"verificacion"}), render_desde=time.time())
    ex._decir("ex_editor", "trabajando", f"Mandé #{f.get('numero')} a tu compu 🎬")
    return {"ok": True}


def _revisar_render(eid: str) -> None:
    import requests
    f = fab(eid)
    try:
        e = requests.get(f"{SALA_URL}/interno/trabajo/{f['render_tid']}", timeout=5).json()
    except (requests.RequestException, ValueError):
        return
    est = e.get("estado")
    if est in ("asignado", "trabajando"):
        ex._decir("ex_editor", "trabajando", f"{e.get('compu') or 'Tu compu'}: {e.get('paso') or 'renderizando'}"[:120])
        _poner(eid, render_paso=e.get("paso") or "", render_avance=e.get("avance") or 0)
        return
    if est == "listo":
        c = ex.carpeta(eid)
        salida, render = c / "render-salida", c / "render"
        render.mkdir(exist_ok=True)
        for p in salida.iterdir():
            shutil.move(str(p), render / p.name)
        video = next(iter(sorted(render.glob("*.mp4"))), None)
        if not video:
            _poner(eid, render_estado="error", error="La compu terminó pero no regresó el video.")
            return
        _poner(eid, render_estado="listo", paso="revision", render_ok=True, video=video.name,
               hechos_pasos=sorted(set(f.get("hechos_pasos") or []) | {"verificacion", "render"}), render_fin=time.time())
        ex._decir("ex_editor", "libre", f"#{f.get('numero')} {f.get('marca')}: ¡video listo! 🎬")
        if ex.al_avisar:
            ex.al_avisar("Beto", f"El video de ¿Quién MATÓ a {f.get('marca')}? está listo para que lo revises.")
        return
    if est in ("error", "cancelado"):
        _poner(eid, render_estado="error", error=f"Tu compu no pudo hacer el video: {e.get('error') or est}"[:300])
        ex._decir("ex_editor", "libre", "Tu compu no pudo con el video 😕")


# ---------------------------------------------------------------- 7. tu revisión → programar en privado
def _fechas_libres(canal: str) -> list[dict]:
    ag = agenda.agenda(dias=400)
    c = next((x for x in ag["canales"] if x["id"] == canal), None)
    return [f for f in (c["fechas"] if c else []) if not f["caso"]]


def revisar(eid: str, d: dict) -> dict:
    f = fab(eid)
    a = d.get("accion")
    if a == "rehacer_video":
        _poner(eid, render_estado=None, render_ok=None, paso="render", error=None)
        return enviar_render(eid)
    if a not in ("programar", "privado"):
        return {"error": "¿Qué hago?"}
    if f.get("paso") != "revision":
        return {"error": "El video todavía no está listo para revisar."}
    canal = f.get("canal") or "quien_mato"
    c = next((x for x in agenda.lista() if x["id"] == canal), {})
    fecha = None
    if a == "programar":
        libres = _fechas_libres(canal)
        if not libres:
            return {"error": "No hay fechas libres en la agenda de ese canal."}
        fecha = libres[0]
    with ex._candado:
        t = ex.trabajo(eid)
        if fecha:
            t["programado"] = {"canal": canal, "fecha": fecha["fecha"], "hora": fecha["hora"]}
        t["fabrica"].update(paso="programado", aprobado=time.time(), subida="subiendo", error=None)
        ex._guardar_trabajo(eid, t)
    threading.Thread(target=_subir, args=(eid, c, fecha), daemon=True).start()
    return {"ok": True, "fecha": fecha["fecha"] if fecha else None}


def _subir(eid: str, canal: dict, fecha: dict | None) -> None:
    from . import youtube
    f = fab(eid)
    c = ex.carpeta(eid)
    tarea = ex._tarea("ex_publicacion", "Subir a YouTube (privado)", f"#{f.get('numero')} · {f.get('marca')}")
    ex._decir("ex_publicacion", "trabajando", "Subiendo en privado 📤")
    try:
        g = ex._leer_json(c / "fabrica" / "guion.json", {})
        render = c / "render"
        cap = next(iter(render.glob("*-capitulos.txt")), None)
        cre = next(iter(render.glob("*-creditos.txt")), None)
        descripcion = (g.get("descripcion", "").strip() + "\n\n⏱️ CAPÍTULOS\n" + (cap.read_text(encoding="utf-8").strip() if cap else "")
                       + "\n\n📷 CRÉDITOS DEL MATERIAL\n" + (cre.read_text(encoding="utf-8").strip() if cre else "")
                       + "\n\nEste video es de análisis y opinión; no está patrocinado ni afiliado a ninguna de las marcas "
                         "mencionadas. Las cifras vienen de las fuentes citadas.")[:4900]
        titulo = (canal.get("plantilla") or "¿Quién MATÓ a [Marca]?").replace("[Marca]", f.get("marca", ""))[:100]
        publicar_en = None
        if fecha:
            from zoneinfo import ZoneInfo
            local = dt.datetime.fromisoformat(f"{fecha['fecha']}T{fecha['hora']}:00").replace(tzinfo=agenda.ZONA)
            publicar_en = local.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")
        if _demo():
            vid = "demo123"
        else:
            if not canal.get("canal_youtube"):
                raise RuntimeError("Elige en la pestaña Canales a qué canal de YouTube sube esta serie.")
            video = render / f["video"]
            mini = render / "miniatura-A.jpg"
            vid = youtube.subir(video, mini if mini.exists() else None, titulo, descripcion, g.get("etiquetas", [])[:30],
                                sintetico=True, privacidad="private", publicar_en=publicar_en, canal=canal["canal_youtube"])
        _poner(eid, subida="listo", video_id=vid, url=f"https://youtu.be/{vid}", publicar_en=publicar_en,
               hechos_pasos=sorted(set(fab(eid).get("hechos_pasos") or []) | {"revision", "programado"}))
        ex._fin_tarea(tarea, resultado=f"https://youtu.be/{vid}")
        ex._decir("ex_publicacion", "libre", "Subido en privado ✔ 📤")
        with _candado:
            lista = temas()
            for x in lista:
                if x.get("eid") == eid:
                    x["estado"] = "hecho"
            _guardar_temas(lista)
        if ex.al_avisar:
            ex.al_avisar("Pepe", f"Subí ¿Quién MATÓ a {f.get('marca')}? en privado"
                         + (f", programado para el {fecha['fecha']} a las {fecha['hora']}" if fecha else "") + f": https://youtu.be/{vid}")
    except Exception as exc:  # noqa: BLE001
        _poner(eid, subida="error", error=f"No se pudo subir: {str(exc)[:250]}", paso="revision")
        ex._fin_tarea(tarea, error=str(exc)[:300])
        ex._decir("ex_publicacion", "libre", "No pude subirlo 😕")


# ---------------------------------------------------------------- el ciclo automático
def _plan_disponible() -> bool:
    if _demo():
        return True
    if not claude.suscripcion_lista() and TAREA not in claude._api_permitida:
        return False
    return time.time() >= getattr(claude, "_suscripcion_pausada_hasta", 0)


def _material_por_delante() -> int:
    """Casos de la fábrica que todavía no se publican (en producción, por verificar, por revisar o programados)."""
    n = 0
    for x in ex.lista():
        t = ex.trabajo(x["id"])
        f = t.get("fabrica")
        if not f:
            continue
        prog = t.get("programado") or {}
        if f.get("subida") == "listo" and prog.get("fecha") and prog["fecha"] < agenda._hoy().isoformat():
            continue
        n += 1
    return n


def meta_videos() -> int:
    e = estado()
    ritmo = min((int(c.get("ritmo_dias") or 3) for c in agenda.lista() if c.get("activo", True)), default=3)
    return math.ceil(e["meta_dias"] / ritmo)


def vuelta() -> None:
    """Una pasada: renders que revisar, casos que mandar a tu compu y, si toca, el siguiente tema."""
    for x in ex.lista():
        t = ex.trabajo(x["id"])
        f = t.get("fabrica")
        if not f:
            continue
        if f.get("render_estado") == "en_fila" and f.get("render_tid"):
            _revisar_render(x["id"])
        elif _listo_para_render(x["id"], t) and not f.get("error"):
            enviar_render(x["id"])
    e = estado()
    if not e["activa"] or e.get("en_curso") or time.time() < e.get("espera_hasta", 0):
        return
    if not _plan_disponible():
        return
    if _material_por_delante() >= meta_videos():
        return
    siguiente = next((x for x in temas() if x["estado"] == "pendiente"), None)
    if not siguiente:
        if not any(x["estado"] == "propuesto" for x in temas()):
            try:
                proponer_temas()
            except Exception as exc:  # noqa: BLE001
                print(f"  · no pude proponer temas: {exc}", flush=True)
        return
    producir(siguiente["id"])


def iniciar() -> None:
    """La oficina lo llama al arrancar: una vuelta cada minuto, para siempre."""
    if _hilo.get("ciclo") and _hilo["ciclo"].is_alive():
        return

    def ciclo():
        time.sleep(20)
        while True:
            try:
                vuelta()
            except Exception as exc:  # noqa: BLE001 — la fábrica nunca tumba la oficina
                print(f"  · fábrica de expedientes: {exc}", flush=True)
            time.sleep(60)
    _hilo["ciclo"] = threading.Thread(target=ciclo, daemon=True)
    _hilo["ciclo"].start()


def resumen() -> dict:
    e = estado()
    lista = temas()
    casos = []
    for x in ex.lista():
        t = ex.trabajo(x["id"])
        f = t.get("fabrica")
        if f:
            casos.append({"id": x["id"], "numero": x["numero"], "marca": x["marca"], "paso": f.get("paso"),
                          "error": f.get("error"), "render_estado": f.get("render_estado"), "render_paso": f.get("render_paso"),
                          "render_avance": f.get("render_avance"), "video": f.get("video"), "url": f.get("url"),
                          "programado": t.get("programado"), "subida": f.get("subida"), "dudosas": f.get("dudosas", 0),
                          "palabras": f.get("palabras"), "material": f.get("material"), "render_nota": f.get("render_nota"),
                          "verificacion": t["verificacion"].get("estado"), "cuenta": ex._cuenta(t["datos"])})
    return {"estado": e, "temas": lista, "casos": casos, "meta": meta_videos(), "por_delante": _material_por_delante(),
            "plan": _plan_disponible(), "pexels": (CANAL_DIR / ".pexels_key").exists(), "demo": _demo()}


def archivo_render(eid: str, nombre: str) -> Path | None:
    c = ex.carpeta(eid) / "render"
    ruta = (c / Path(nombre).name).resolve()
    if ruta.is_file() and ruta.is_relative_to(c.resolve()) and ruta.suffix.lower() in (".mp4", ".jpg", ".srt", ".txt"):
        return ruta
    return None
