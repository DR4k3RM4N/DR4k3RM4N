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
TAREA = "fabrica_exp"          # lo mecánico (Sonnet por tu plan)
TAREA_GUION = "fabrica_guion"  # investigar y escribir (Opus por tu plan)
_candado = threading.RLock()
_hilo: dict[str, threading.Thread] = {}

PASOS_FAB = [("investigacion", "Investigación", "ex_guion"), ("guion", "Guion", "ex_guion"),
             ("material", "Material", "ex_archivista"), ("storyboard", "Storyboard", "ex_graficas"),
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
        e.setdefault("activa", True)   # Miguel: «que continúe haciendo y haciendo en automático»
        e.setdefault("subir_solo", True)  # al terminar el video lo sube en PRIVADO programado (tú lo haces público)
        e.setdefault("meta_dias", 180)  # juntar material para ~6 meses
        e.setdefault("compus", {})  # 🖥️ id de compu → "preferida" | "respaldo" | "no"
        e.setdefault("servidor_respaldo", True)  # si no hay compu que pueda, el video lo hace el servidor
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
    if "subir_solo" in d:
        e["subir_solo"] = bool(d["subir_solo"])
    if "servidor_respaldo" in d:
        e["servidor_respaldo"] = bool(d["servidor_respaldo"])
    if d.get("compu"):
        if d.get("pref") not in ("preferida", "respaldo", "no"):
            return {"error": "Elige preferida, respaldo o no usar."}
        if d["pref"] == "preferida":  # solo una preferida
            e["compus"] = {k: ("respaldo" if v == "preferida" else v) for k, v in e["compus"].items()}
        e["compus"][str(d["compu"])[:40]] = d["pref"]
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
                          "grupo": x["grupo"][:60] or "Propuestos", "orden": 999, "eid": None,
                          # 🤖 en automático entran directo a la fila (tú puedes saltarlos o borrarlos en 🧾 Temas)
                          "estado": "pendiente" if estado().get("subir_solo", True) else "propuesto"})
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
        f = t.setdefault("fabrica", {})
        campos.setdefault("t_mov", time.time())  # último movimiento (para que veas que sí está trabajando)
        if campos.get("error") and not f.get("error"):
            campos.setdefault("error_t", time.time())  # para reintentarlo solo al rato
        f.update(campos)
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
        from concurrent.futures import ThreadPoolExecutor
        malos = ("youtube.", "tiktok.", "facebook.", "instagram.", "x.com", "twitter.")
        urls, dominios = [], {}
        for x in resultados:
            url = x.get("url") or ""
            dominio = re.sub(r"^www\.", "", url.split("/")[2]) if url.count("/") >= 2 else url
            if not url or any(b in dominio for b in malos) or dominios.get(dominio, 0) >= 2:
                continue
            dominios[dominio] = dominios.get(dominio, 0) + 1
            urls.append((url, x))
        urls = urls[:20]

        def leer(par):
            url, x = par
            try:
                texto, titulo = _bajar_pagina(url)
            except Exception:  # noqa: BLE001 — una página que no abre no detiene la investigación
                return None
            if len(texto) < 800:
                return None
            # solo los párrafos que sirven (hablan de la marca o traen cifras): menos texto = menos plan
            clave = marca.lower().split()[0]
            utiles = [p for p in texto.split("\n") if len(p) > 60 and (clave in p.lower() or re.search(r"\d", p))]
            return {"url": url, "titulo": titulo or x.get("titulo") or x.get("title") or url, "texto": "\n".join(utiles)[:5000]}

        with ThreadPoolExecutor(max_workers=8) as pool:  # varias páginas a la vez
            fuentes = [f for f in pool.map(leer, urls) if f and len(f["texto"]) > 400][:8]
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
            f"MARCA: {marca}\nGANCHO PROPUESTO: {gancho}\n\nFUENTES:\n{bloque}\n\nSaca 25 a 40 hechos útiles para un "
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
                    "required": ["titulo", "capitulo", "texto_pantalla", "frases"],
                    "properties": {
                        "titulo": {"type": "string"}, "capitulo": {"type": "string", "description": "título corto del capítulo de YouTube"},
                        "texto_pantalla": {"type": "array", "items": {"type": "string"}, "description": "un texto corto (máx. 6 palabras) por frase, en orden"},
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
    j = texto.find("## ESCENA 2")
    return "\n".join(ln for ln in texto[i:j].splitlines() if ln.startswith(("## ", "> ")))  # solo el gancho


def _sistema_canal() -> str:
    """Las reglas del canal en corto (antes iba todo el CLAUDE.md: gastaba mucho plan en cada guion)."""
    return ("ESTRUCTURA: 1) Gancho 30-60 s con el contraste más fuerte y cifras. 2) Presentación: «Expediente #00X» y "
            "3 sospechosos. 3) La víctima: origen y época de gloria con anécdotas reales. 4-6) Un sospechoso por escena "
            "(título de la escena «Sospechoso #N: …»), con datos y fechas. 7) El giro de México (qué pasó aquí y por qué), "
            "si hay datos. 8) «¿Final feliz?»: riesgos actuales. 9) Veredicto como OPINIÓN + pregunta para comentarios. "
            "10) Adelanto del próximo expediente. TONO: caso policiaco, frases cortas, de tú, palabras de México "
            "(tóper, plaza, a meses, quincena).")


def escribir_guion(tema: dict, inv: dict, numero: str, siguiente: str) -> dict:
    hechos = "\n".join(f"{h['id']}: {h['dato']}  (cita: «{h['cita'][:200]}»)" for h in inv["hechos"])
    pedido = (f"EXPEDIENTE #{numero} · MARCA: {tema['marca']}\nGANCHO PROPUESTO: {tema.get('gancho', '')}\n"
              f"SOSPECHOSOS QUE SALEN DE LA INVESTIGACIÓN: {'; '.join(inv['sospechosos'])}\n"
              f"GIRO DE MÉXICO: {inv['giro_mexico'] or '(no hay datos: no lo inventes)'}\n¿FINAL FELIZ?: {inv['final_feliz']}\n"
              f"DUDAS (no las afirmes): {'; '.join(inv['dudas'][:12])}\nPRÓXIMO EXPEDIENTE SUGERIDO: {siguiente}\n\n"
              f"HECHOS COMPROBADOS (lo único que puedes afirmar; cita su H# en cada frase que los use):\n{hechos}\n\n"
              f"EJEMPLO DE TONO (el gancho de Tupperware):\n{_ejemplo_guion()[:3000]}")
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
        "Eres Vera, guionista del canal «¿Quién MATÓ a…?». Escribes guiones técnicos de 15 a 18 minutos (2,000 a "
        "2,400 palabras de narración, 10 a 13 escenas) para un video que se arma solo con un motor: cada «frase» se "
        "vuelve una tarjeta en pantalla (da un texto_pantalla por frase). Reglas del canal:\n\n"
        + _sistema_canal() + "\n\nREGLAS DURAS: toda cifra, fecha, nombre o hecho de la narración tiene que venir de "
        "los HECHOS COMPROBADOS (pon su H#). Si un dato no está, no lo digas. Opinión solo en el veredicto y dicha como "
        "opinión. No acuses a nadie de delitos. Frases cortas, tono de caso policiaco, palabras de México. La primera "
        "escena es el gancho (30-60 s) y la última el adelanto del próximo expediente. El título del video es fijo: "
        f"«¿Quién MATÓ a {tema['marca']}?».",
        pedido, ESQ_GUION, tarea=TAREA_GUION, que=f"guion {tema['marca']}")


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
        s += [f"## ESCENA {n} · {e['titulo']}", "",
              f"**Texto en pantalla:** " + " · ".join(f"\"{x}\"" for x in e.get("texto_pantalla") or []), ""]
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


MARCA_DE_AGUA = ("shutterstock", "gettyimages", "istockphoto", "alamy", "dreamstime", "depositphotos", "123rf",
                 "stock.adobe", "agefotostock", "bigstock", "vectorstock", "pond5", "freepik.com/premium", "pinterest", "lookaside")


def _imagenes_web(q: str, n: int = 10) -> list[dict]:
    """Imágenes de cualquier sitio (Google Imágenes por Serper), sin las de bancos con marca de agua."""
    import requests
    if not buscar_web.SERPER:
        return []
    r = requests.post("https://google.serper.dev/images", timeout=30,
                      headers={"X-API-KEY": buscar_web.SERPER, "Content-Type": "application/json"},
                      json={"q": q, "gl": "mx", "hl": "es", "num": n})
    if r.status_code != 200:
        return []
    salida = []
    for x in r.json().get("images", [])[:n]:
        url = x.get("imageUrl") or ""
        dominio = (x.get("domain") or x.get("source") or url.split("/")[2] if url.count("/") >= 2 else "").lower()
        if not url.startswith("http") or any(m in url.lower() or m in dominio for m in MARCA_DE_AGUA):
            continue
        if (x.get("imageWidth") or 0) and int(x.get("imageWidth") or 0) < 700:
            continue
        salida.append({"titulo": (x.get("title") or "")[:120], "url": url, "pagina": x.get("link") or "",
                       "fuente": re.sub(r"^www\.", "", dominio)[:60] or "web", "licencia": "",
                       "autor": "", "ancho": x.get("imageWidth"), "alto": x.get("imageHeight"), "mime": "image/web"})
    return salida


def _bajar_imagen(url: str, destino: Path) -> bool:
    """La baja aquí en el servidor y la revisa (que de verdad sea imagen y no esté rota); la guarda en JPG."""
    import requests
    from PIL import Image
    try:
        r = requests.get(url, timeout=25, stream=True, headers={"User-Agent": "Mozilla/5.0 (Agencia de Expedientes)",
                                                                "Referer": url})
        if r.status_code != 200:
            return False
        datos = r.raw.read(12_000_000, decode_content=True)
        im = Image.open(io.BytesIO(datos))
        im.load()
        im = im.convert("RGB")
        if im.width < 600 or im.height < 340:
            return False
        if im.width > 1920:
            im = im.resize((1920, int(im.height * 1920 / im.width)))
        im.save(destino, quality=90)
        return True
    except Exception:  # noqa: BLE001 — una imagen que no baja simplemente no se usa
        return False


def buscar_material(tema: dict, g: dict, destino: Path | None = None) -> dict:
    """🗄️ Inés: fotos de TODOS lados (Google Imágenes + Wikimedia) y videos cortos de stock. Las fotos se bajan y se
    revisan aquí (van dentro del paquete a tu compu); los videos los baja la compu."""
    from concurrent.futures import ThreadPoolExecutor
    if _demo():
        return {"fotos": [], "videos": [], "lista": []}
    # las búsquedas se arman solas (sin gastar Claude): la marca + el tema de cada escena
    generales = [f"{tema['marca']} logo", f"{tema['marca']} tienda", f"{tema['marca']} store", f"{tema['marca']} México",
                 f"{tema['marca']} historia", f"{tema['marca']} producto"]
    limpio = [re.sub(r"sospechoso\s*#?\d+\s*[:·-]?", "", e["titulo"], flags=re.I).strip() for e in g["escenas"]]
    b = {"escenas": [{"commons": [(tema["marca"] + " " + limpio[n - 1])[:80],
                                  generales[(n - 1) % len(generales)]],
                      "videos": [["store closing sale", "empty shopping mall", "money falling", "office business meeting",
                                  "city night traffic", "old television static", "warehouse boxes"][(n - 1) % 7]]}
                     for n, e in enumerate(g["escenas"], 1)]}
    fl = _fuentes_libres()
    trabajos = []
    for n, e in enumerate(b["escenas"][:len(g["escenas"])], 1):
        for q in e["commons"][:3]:
            trabajos.append(("web", q, n))
        trabajos.append(("commons", e["commons"][0] if e["commons"] else tema["marca"], n))
        if (CANAL_DIR / ".pexels_key").exists():
            for q in e["videos"][:2]:
                trabajos.append(("pexels", q, n))

    def correr(tr):
        tipo, q, n = tr
        try:
            res = _imagenes_web(q, 8) if tipo == "web" else fl.commons(q, 8) if tipo == "commons" else fl.pexels_video(q, 3)
        except Exception:  # noqa: BLE001
            res = []
        return [(x, n) for x in res]

    with ThreadPoolExecutor(max_workers=6) as pool:  # varias búsquedas a la vez
        resultados = [y for lista in pool.map(correr, trabajos) for y in lista]
    candidatos, vistos = [], set()
    for x, n in resultados:
        clave = x.get("url") or x.get("titulo")
        if clave in vistos:
            continue
        if x["fuente"] == "Wikimedia Commons" and not (x.get("mime") or "").startswith(("image/jpeg", "image/png", "video/webm")):
            continue
        vistos.add(clave)
        pref = "P" if x["fuente"] == "Pexels" else "C" if x["fuente"] == "Wikimedia Commons" else "W"
        candidatos.append({**x, "id": f"{pref}{len(candidatos) + 1}", "escena": n})
    if not candidatos:
        return {"fotos": [], "videos": [], "lista": []}
    # se escogen solas (sin gastar Claude): hasta 3 fotos y 1 video por escena, las más grandes primero
    el = {"elegidos": []}
    cuenta = {}
    for c in sorted(candidatos, key=lambda c: (c["escena"], c["fuente"] == "Pexels", -(int(c.get("ancho") or 0)))):
        clave = (c["escena"], c["fuente"] == "Pexels")
        if cuenta.get(clave, 0) >= (1 if c["fuente"] == "Pexels" else 3):
            continue
        cuenta[clave] = cuenta.get(clave, 0) + 1
        el["elegidos"].append({"id": c["id"], "nombre": f"{_slug(tema['marca'], 16)}-{c['escena']}-{c['id'].lower()}",
                               "describe": c["titulo"][:90], "escenas": [c["escena"]]})
    por_id = {c["id"]: c for c in candidatos}
    fotos_dir = (destino / "material" / "fotos") if destino else None
    if fotos_dir:
        fotos_dir.mkdir(parents=True, exist_ok=True)
    commons_fotos = [por_id[x["id"]]["titulo"] for x in el["elegidos"] if x["id"] in por_id
                     and por_id[x["id"]]["fuente"] == "Wikimedia Commons" and not por_id[x["id"]]["mime"].startswith("video")]
    try:
        thumbs = fl.commons_thumbs(commons_fotos) if commons_fotos else {}
    except Exception:  # noqa: BLE001
        thumbs = {}
    pedidos, videos, usados = [], [], set()
    for x in el["elegidos"]:
        c = por_id.get(x["id"])
        if not c:
            continue
        nombre = _slug(x["nombre"], 40)
        while nombre in usados:
            nombre += "-b"
        usados.add(nombre)
        es_video = c["fuente"] == "Pexels" or (c.get("mime") or "").startswith("video")
        if es_video:
            url = c["url"]
            if c["fuente"] == "Wikimedia Commons":
                try:
                    url = fl.commons_video_transcode(c["titulo"]) or ""
                except Exception:  # noqa: BLE001
                    url = ""
            if url:
                ext = ".mp4" if c["fuente"] == "Pexels" else ".webm"
                videos.append(({"nombre": nombre + ext, "url": url, "fuente": c["fuente"], "licencia": c.get("licencia"),
                                "autor": c.get("autor"), "pagina": c.get("pagina"), "titulo": c.get("titulo")}, x))
            continue
        url = thumbs.get(c["titulo"]) if c["fuente"] == "Wikimedia Commons" else c["url"]
        pedidos.append((nombre + ".jpg", url or c["url"], c, x))
    fotos, lista_final, creditos = [], [], {}

    def bajar(p):
        nombre, url, c, x = p
        return (p, bool(fotos_dir) and _bajar_imagen(url, fotos_dir / nombre))

    with ThreadPoolExecutor(max_workers=6) as pool:  # se bajan varias a la vez
        for (nombre, url, c, x), ok in pool.map(bajar, pedidos):
            if not ok:
                continue
            creditos[nombre] = {"fuente": c["fuente"], "licencia": c.get("licencia") or "", "autor": c.get("autor") or "",
                                "pagina": c.get("pagina") or url, "titulo": c.get("titulo") or ""}
            lista_final.append({"archivo": f"material/fotos/{nombre}", "describe": x["describe"], "escenas": x["escenas"],
                                "video": False, "fuente": c["fuente"]})
    if fotos_dir:
        _escribir(fotos_dir / "creditos.json", creditos)
    for item, x in videos:
        lista_final.append({"archivo": f"material/videos/{item['nombre']}", "describe": x["describe"], "escenas": x["escenas"],
                            "video": True, "fuente": item["fuente"]})
    return {"fotos": fotos, "videos": [v for v, _ in videos], "lista": lista_final}


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


ENCABEZADO_SB = '''"""Storyboard hecho por la Agencia de Expedientes (estilo «cine»). Una entrada de cards por frase del guion."""
import json
from pathlib import Path

from sb import *  # noqa: F401,F403

AQUI = Path(__file__).parent
_CRED = {}
for _sub in ("fotos", "videos"):
    _c = AQUI / "material" / _sub / "creditos.json"
    if _c.exists():
        _CRED.update(json.loads(_c.read_text(encoding="utf-8")))


def F(nombre):
    return f"material/fotos/{nombre}"


def V(nombre):
    """Video por nombre de archivo (con su extensión: .mp4 o .webm)."""
    return f"material/videos/{nombre}"


def cr(path, extra=""):
    """Crédito corto para la esquina: de dónde salió la foto o el video."""
    c = _CRED.get(Path(path).name) or {}
    fuente, lic = c.get("fuente") or "", c.get("licencia") or ""
    if fuente == "Wikimedia Commons":
        lic = "dominio público" if lic.lower() in ("public domain", "no restrictions") else lic
        partes = [extra, lic, "Wikimedia Commons"]
    elif fuente in ("Pexels", "Mixkit", "Pixabay"):
        partes = [extra, f"Video: {fuente}"]
    else:
        partes = [extra, f"Foto: {fuente}" if fuente else ""]
    return " · ".join(p for p in partes if p)[:110]


def P(nombre, **k):
    f = F(nombre)
    k.setdefault("src", cr(f, k.pop("extra", "")))
    return PHOTO(f, **k)


def M(nombre, **k):
    f = V(nombre)
    k.setdefault("src", cr(f, k.pop("extra", "")))
    return VIDEO(f, **k)


'''


def _storyboard_demo(tema: dict, numero: str, g: dict) -> str:
    escenas = []
    for e in g["escenas"]:
        cards = ", ".join(f"Q({json.dumps(f['texto'][:60].upper(), ensure_ascii=False)})" for f in e["frases"])
        escenas.append(f"        dict(capitulo={json.dumps(e['capitulo'], ensure_ascii=False)}, cards=[{cards}]),")
    return (ENCABEZADO_SB + "EP = dict(\n"
            f"    label=\"EXPEDIENTE #{numero} · {tema['marca'].upper()}\",\n    nombre=\"Expediente-{numero}-{_slug(tema['marca']).title()}\",\n"
            "    guion=\"01-guion-tecnico.md\",\n    salida=\"render\",\n    estilo=\"cine\",\n    voz_motor=\"azure\",\n"
            "    voz=\"es-MX-JorgeNeural\",\n    voz_velocidad=\"+12%\",\n    musica_vol=0.35,\n    fonetica_azure={},\n"
            "    end=END(),\n    escenas=[\n" + "\n".join(escenas) + "\n    ],\n)\n")


def _corto(t: str, n: int = 7) -> str:
    t = re.sub(r"[<>\[\]]", "", t or "").strip()
    palabras = t.split()
    return " ".join(palabras[:n]) + ("…" if len(palabras) > n else "")


def _storyboard_auto(tema: dict, numero: str, g: dict, material: dict) -> str:
    """📊 Nico arma el storyboard SIN gastar Claude: estilo «cine» (foto real a pantalla completa con su texto,
    videos de ambiente, carátula del expediente y tablero de sospechosos), una entrada por frase. Siempre cuadra."""
    marca = tema["marca"]
    fotos = [m for m in material["lista"] if not m["video"]]
    videos = [m for m in material["lista"] if m["video"]]
    nombre = lambda m: m["archivo"].split("/")[-1]  # noqa: E731
    por_escena = {}
    for m in material["lista"]:
        for n in m.get("escenas") or []:
            por_escena.setdefault(n, []).append(m)
    def _cabe(t, n=26):  # corta por palabra completa, sin comas colgando
        t = t.split(",")[0].strip()
        while len(t) > n and " " in t:
            t = t.rsplit(" ", 1)[0]
        return t[:n]
    sospechosos = [_cabe(re.sub(r"^sospechoso\s*#?\d+\s*[:·-]\s*", "", e["titulo"], flags=re.I).upper())
                   for e in g["escenas"] if re.match(r"sospechoso", e["titulo"], re.I)][:3]
    sospechosos = (sospechosos + ["?", "?", "?"])[:3]  # el tablero siempre tiene 3
    usado = {"f": 0, "v": 0}

    def foto(n):
        lista = [m for m in por_escena.get(n, []) if not m["video"]] or fotos
        if not lista:
            return None
        m = lista[usado["f"] % len(lista)]
        usado["f"] += 1
        return nombre(m)

    def video(n):
        lista = [m for m in por_escena.get(n, []) if m["video"]] or videos
        if not lista:
            return None
        m = lista[usado["v"] % len(lista)]
        usado["v"] += 1
        return nombre(m)

    escenas_py = []
    n_sosp = 0
    for n, e in enumerate(g["escenas"], 1):
        tp = [x for x in (e.get("texto_pantalla") or []) if x]
        etiqueta = e["titulo"].upper()[:40]
        cards = []
        es_sosp = bool(re.match(r"sospechoso", e["titulo"], re.I))
        if es_sosp:
            n_sosp += 1
        for k, f in enumerate(e["frases"]):
            texto = tp[k] if k < len(tp) else ""
            fo = foto(n)
            if n == 1 and k == 0:
                c = (f"P({fo!r}, head={_corto(texto or ('¿QUIÉN MATÓ A ' + marca.upper() + '?'), 8)!r}, bw=True)" if fo
                     else f"TITLE({('¿QUIÉN MATÓ A ' + marca.upper() + '?')!r}, tape=True)")
            elif n == 2 and k == 0:
                c = (f"FILE({marca.upper()!r}, num={('EXPEDIENTE N.º ' + numero)!r}, "
                     f"lines={[_corto(x, 6) for x in sospechosos[:3]]!r}, stamp='CASO ABIERTO')")
            elif es_sosp and k == 0:
                rev = [i < n_sosp for i in range(3)]
                c = (f"BOARD({rev!r}, new={min(n_sosp, 3) - 1}, hi={min(n_sosp, 3) - 1}, labels={sospechosos!r}, "
                     f"label={'SOSPECHOSO #' + str(n_sosp)!r})")
            elif k % 3 == 2 and video(n):
                c = f"M({video(n)!r}, text={_corto(texto, 6)!r}, label={etiqueta!r})" if texto else f"M({video(n)!r})"
            elif fo and len(f["texto"].split()) > 38 and foto(n):
                otra = foto(n)
                c = (f"[P({fo!r}, text={_corto(texto, 6)!r}, label={etiqueta!r}, w=1), "
                     f"P({otra!r}, mode='frame', side='right', w=1)]")
            elif fo:
                c = (f"P({fo!r}, text={_corto(texto, 6)!r}, label={etiqueta!r})" if texto
                     else f"P({fo!r}, label={etiqueta!r})")
            else:
                c = f"Q({_corto(texto or f['texto'], 9)!r})"
            cards.append(c)
        fondo = foto(n)
        escenas_py.append(f"        dict(capitulo={e.get('capitulo') or e['titulo']!r}, "
                          + (f"fondo=F({fondo!r}), " if fondo else "") + "cards=[\n            "
                          + ",\n            ".join(cards) + ",\n        ]),")
    fin = foto(len(g["escenas"]))
    return (ENCABEZADO_SB + "EP = dict(\n"
            f"    label={('EXPEDIENTE #' + numero + ' · ' + marca.upper())!r},\n"
            f"    nombre={('Expediente-' + numero + '-' + _slug(marca, 30).title())!r},\n"
            "    guion='01-guion-tecnico.md',\n    salida='render',\n    estilo='cine',\n    voz_motor='azure',\n"
            "    voz='es-MX-JorgeNeural',\n    voz_velocidad='+12%',\n    musica_vol=0.35,\n"
            f"    fonetica_azure={g.get('fonetica') or {}!r},\n"
            f"    end=END({('bg=F(' + repr(fin) + ')') if fin else ''}),\n    escenas=[\n" + "\n".join(escenas_py) + "\n    ],\n)\n")


def escribir_storyboard(tema: dict, numero: str, g: dict, material: dict, carpeta: Path) -> str:
    """El storyboard se arma solo (sin Claude) y se prueba con el motor antes de seguir."""
    codigo = _storyboard_auto(tema, numero, g, material)
    problema = codigo_seguro(codigo)
    if problema:
        raise RuntimeError(f"Storyboard inválido: {problema}")
    (carpeta / "storyboard.py").write_text(codigo, encoding="utf-8")
    r = _probar_storyboard(carpeta)
    if r.get("errores"):
        raise RuntimeError("El storyboard no cuadró: " + "; ".join(r["errores"])[:300])
    return codigo


# ---------------------------------------------------------------- 🖼️ Mina: miniaturas que jalan
REGLAS_MINIATURA = """Lo que SÍ funciona en miniaturas de documentales de negocios (y lo que hace este canal):
- UNA escena con tensión o un contraste claro (un momento decisivo, ANTES vs AHORA, la marca enorme vs su caída).
  Nunca intentes resumir todo el video en la miniatura.
- Una CARA humana con emoción contenida (seria, preocupada, incrédula; mirando a cámara o hacia la evidencia): está en
  la gran mayoría de los videos que explotan; en negocios funciona mejor seria que exagerada. Nunca una persona real
  privada; la cara la genera la imagen realista (persona genérica) o es una figura pública del caso.
- La MARCA reconocible: su logo, su tienda o su producto real, en grande, como «evidencia» del caso.
- 2 a 4 palabras GIGANTES arriba a la izquierda (lo primero que ve el ojo y lejos del reloj de abajo a la derecha),
  en blanco con una palabra en amarillo o rojo. De preferencia un número o un contraste («QUEDAN 5», «DE 9,000 A 1»,
  «¿QUIÉN LA MATÓ?», «QUEBRÓ… Y VIVE»). Nunca repitas el título del video.
- Mucho contraste: fondo oscuro/desaturado, la evidencia y el texto brillantes. Nada abajo a la derecha.
- Curiosidad sin mentir: lo que promete la miniatura está en el video. No deformes logos.
- Variante B diferente para «Probar y comparar»: contraste lado a lado con fotos reales (ALLÁ vs MÉXICO, ANTES vs
  HOY) con 1 palabra o número grande de cada lado."""

ESQ_MINI = {"type": "object", "additionalProperties": False, "required": ["a", "b"], "properties": {
    "a": {"type": "object", "additionalProperties": False,
          "required": ["fondo", "archivo", "prompt_ia", "lineas", "evidencia", "sello"],
          "properties": {
              "fondo": {"type": "string", "enum": ["ia", "foto"], "description": "ia = escena realista con una persona (lo mejor); foto = una del material"},
              "archivo": {"type": "string", "description": "si fondo=foto: ruta material/fotos/… exacta (la tienda o un lugar)"},
              "prompt_ia": {"type": "string", "description": "si fondo=ia, en inglés: persona genérica (edad, ropa) con emoción contenida mirando a cámara, de la cintura para arriba, en el TERCIO DERECHO; detrás la escena del caso (tienda cerrada, anaquel vacío, oficina en crisis…); el tercio izquierdo oscuro y limpio para el texto; SIN letras, logos ni marcas"},
              "lineas": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["texto", "color"],
                         "properties": {"texto": {"type": "string"}, "color": {"type": "string", "enum": ["blanco", "amarillo", "rojo"]}}},
                         "description": "1 o 2 renglones, 2 a 4 palabras en total"},
              "evidencia": {"type": "string", "description": "ruta material/fotos/… del LOGO, el PRODUCTO o la fachada con el logo (va como polaroid de evidencia); vacío si no hay"},
              "sello": {"type": "string", "description": "sello rojo corto opcional («QUEBRÓ», «CERRADO»…) o vacío"}}},
    "b": {"type": "object", "additionalProperties": False, "required": ["izq_archivo", "izq_texto", "izq_etiqueta", "der_archivo", "der_texto", "der_etiqueta"],
          "properties": {"izq_archivo": {"type": "string"}, "izq_texto": {"type": "string"}, "izq_etiqueta": {"type": "string"},
                         "der_archivo": {"type": "string"}, "der_texto": {"type": "string"}, "der_etiqueta": {"type": "string"}}}}}


PROMPT_FOTO = ("\n\nPhotorealistic YouTube thumbnail photo, cinematic lighting, sharp subject, shallow depth of field, "
               "slightly desaturated background, strong contrast, the person in the right third, the left third dark and "
               "uncluttered for a headline, nothing important in the bottom-right corner. ABSOLUTELY NO text, letters, "
               "numbers, signs with words, logos, brand names or watermarks. The person is a generic, non-famous adult "
               "(not a real public figure).")


def motor_imagenes() -> str:
    """Quién dibuja la escena realista de la miniatura: Cloudflare (gratis) primero, Gemini (de paga) de respaldo."""
    if config.env("CLOUDFLARE_ACCOUNT_ID") and config.env("CLOUDFLARE_AI_TOKEN"):
        return "cloudflare"
    if config.env("GEMINI_API_KEY"):
        return "gemini"
    return ""


def _guardar_imagen(datos: bytes, destino: Path) -> None:
    from PIL import Image, ImageOps
    img = Image.open(io.BytesIO(datos)).convert("RGB")
    ImageOps.fit(img, (1920, 1080), centering=(0.5, 0.4)).save(destino, quality=95)


def _cloudflare(texto: str, destino: Path) -> bool:
    """FLUX.1 [schnell] en Cloudflare Workers AI: cuota gratis diaria (sin tarjeta)."""
    import base64
    import requests
    cuenta, token = config.env("CLOUDFLARE_ACCOUNT_ID"), config.env("CLOUDFLARE_AI_TOKEN")
    modelo = config.env("CLOUDFLARE_MODELO_IMAGEN", "@cf/black-forest-labs/flux-1-schnell")
    r = requests.post(f"https://api.cloudflare.com/client/v4/accounts/{cuenta}/ai/run/{modelo}", timeout=120,
                      headers={"Authorization": f"Bearer {token}"}, json={"prompt": texto[:2000], "steps": 8})
    if r.status_code != 200:
        raise RuntimeError(f"Cloudflare ({r.status_code}): {r.text[:200]}")
    img = (r.json().get("result") or {}).get("image")
    if not img:
        raise RuntimeError("Cloudflare no regresó imagen.")
    _guardar_imagen(base64.b64decode(img), destino)
    return True


def _gemini(texto: str, destino: Path) -> bool:
    import base64
    from . import ilustrador
    modelos = list(dict.fromkeys([m for m in (config.env("GEMINI_MODELO_IMAGEN"), "gemini-3.1-flash-image-preview",
                                              "gemini-2.5-flash-image") if m]))
    ultimo = ""
    for modelo in modelos:
        for con_formato in (True, False):
            r = ilustrador._pedir(modelo, [{"text": texto}], con_formato)
            if r.status_code != 200:
                ultimo = f"{modelo} ({r.status_code}): {r.text[:150]}"
                if r.status_code in (401, 403, 429):
                    raise RuntimeError(f"Gemini: {ultimo}")
                continue
            for cand in r.json().get("candidates", []):
                for parte in (cand.get("content") or {}).get("parts", []):
                    datos = (parte.get("inlineData") or parte.get("inline_data") or {}).get("data")
                    if datos:
                        _guardar_imagen(base64.b64decode(datos), destino)
                        gasto = float(config.env("PRECIO_IMAGEN", "0.04") or 0)
                        if claude.al_gastar and gasto:
                            claude.al_gastar(None, "miniatura", "gemini (imagen)", gasto, 0, 0, "miniatura realista (Expedientes)")
                        return True
    raise RuntimeError(f"Gemini no dibujó: {ultimo}")


def _dibujar_realista(prompt: str, destino: Path) -> bool:
    """La escena realista de la miniatura (persona genérica + el lugar del caso), sin texto ni logos."""
    texto = prompt + PROMPT_FOTO
    errores = []
    for motor_ in ("cloudflare", "gemini"):
        if motor_ == "cloudflare" and not (config.env("CLOUDFLARE_ACCOUNT_ID") and config.env("CLOUDFLARE_AI_TOKEN")):
            continue
        if motor_ == "gemini" and not config.env("GEMINI_API_KEY"):
            continue
        try:
            return (_cloudflare if motor_ == "cloudflare" else _gemini)(texto, destino)
        except Exception as exc:  # noqa: BLE001 — si uno falla, se intenta con el otro
            errores.append(str(exc)[:200])
    if errores:
        print("  · imagen realista: " + " | ".join(errores), flush=True)
    return False


def disenar_miniaturas(tema: dict, g: dict, material: dict, destino: Path) -> dict:
    """Mina decide las dos miniaturas (A y B) con las reglas que jalan; si no hay foto buena, una imagen realista."""
    fotos = [m for m in material["lista"] if not m["video"]]
    lista = "\n".join(f"- {m['archivo']}: {m['describe']}" for m in fotos) or "(no hay fotos libres)"
    # sin gastar Claude: las palabras salen del guion (Vera ya las pensó) y la escena realista de una plantilla
    ideas_a = [x for x in (g.get("miniatura_a") or []) if x][:2] or ["¿QUIÉN LA", "MATÓ?"]
    ideas_b = (g.get("miniatura_b") or []) + ["ANTES", "HOY", "ANTES", "HOY"]
    evid = next((m["archivo"] for m in fotos if re.search(r"logo|tienda|store|fachada|producto", m["archivo"] + m["describe"], re.I)),
                fotos[0]["archivo"] if fotos else "")
    lugar = next((m["archivo"] for m in fotos if m["archivo"] != evid), evid)
    cfg = {"a": {"fondo": "ia" if motor_imagenes() else "foto", "archivo": lugar,
                 "prompt_ia": ("A serious, worried Mexican man in his 30s looking straight at the camera, waist-up, standing in "
                               f"the right third of the frame in front of a closed-down, abandoned store at dusk (the kind of "
                               f"place where {tema['marca']} used to be), empty parking lot, faded signage without letters, "
                               "moody cinematic light"),
                 "lineas": [{"texto": ideas_a[0], "color": "blanco"}] + ([{"texto": ideas_a[1], "color": "amarillo"}] if len(ideas_a) > 1 else []),
                 "evidencia": evid, "sello": "QUEBRÓ"},
           "b": {"izq_archivo": evid, "izq_texto": ideas_b[0], "izq_etiqueta": ideas_b[2],
                 "der_archivo": lugar, "der_texto": ideas_b[1], "der_etiqueta": ideas_b[3]}}
    validas = {m["archivo"] for m in fotos}
    a = cfg["a"]
    if a.get("evidencia") not in validas:
        a["evidencia"] = next((m["archivo"] for m in fotos if re.search(r"logo|tienda|store|fachada|producto", m["archivo"] + m["describe"], re.I)),
                              fotos[0]["archivo"] if fotos else "")
    if a["fondo"] == "ia" and a.get("prompt_ia"):
        try:
            if _dibujar_realista(a["prompt_ia"][:900], destino / "miniatura-fondo.jpg"):
                a["archivo"] = "miniatura-fondo.jpg"
        except Exception as exc:  # noqa: BLE001 — sin imagen nueva se usa una foto del material
            print(f"  · miniatura realista: {exc}", flush=True)
    if a.get("archivo") not in validas | {"miniatura-fondo.jpg"}:
        a["archivo"] = fotos[0]["archivo"] if fotos else ""
    b = cfg["b"]
    for k in ("izq_archivo", "der_archivo"):
        if b.get(k) not in validas:
            b[k] = ""
    _escribir(destino / "miniatura.json", cfg)
    return cfg


MINIATURA_PY = r'''"""Miniaturas A y B del expediente (1280×720 JPG), según miniatura.json (las diseña Mina en la Agencia).

Uso: python miniatura.py
"""
import json
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent / "motor"))
import motor as m  # noqa: E402
from PIL import Image, ImageDraw, ImageEnhance  # noqa: E402

CFG = json.loads((AQUI / "miniatura.json").read_text(encoding="utf-8"))
OUT = AQUI / "render"
OUT.mkdir(exist_ok=True)
COLOR = {"amarillo": "tape", "rojo": "red", "blanco": "ink", "verde": "green"}


def abrir(rel):
    p = AQUI / rel if rel else None
    if not p or not p.is_file():
        return None
    try:
        return Image.open(p).convert("RGB")
    except Exception:
        return None


def deslavar(im, color=0.0):
    return ImageEnhance.Contrast(ImageEnhance.Color(im).enhance(color)).enhance(1.3)


def texto(d, xy, s, size, color, anchor="la", maxw=None):
    f = m.font("display", size)
    while maxw and f.getlength(s) > maxw and size > 60:
        size -= 8
        f = m.font("display", size)
    d.text(xy, s, font=f, fill=m.C[color], anchor=anchor, stroke_width=max(5, size // 22), stroke_fill=(0, 0, 0))
    return size


def sombra_lado(img, izquierda):
    """Oscurece el lado del texto para que se lea sobre cualquier foto."""
    tira = Image.new("L", (256, 1))
    valores = [int(215 * max(0.0, 1 - i / 150)) for i in range(256)]  # oscuro en el lado del texto, nada en el otro
    tira.putdata(valores if izquierda else valores[::-1])
    negro = Image.new("RGB", img.size, (0, 0, 0))
    return Image.composite(negro, img, tira.resize(img.size))


def guardar(img, nombre):
    img.convert("RGB").resize((1280, 720), Image.LANCZOS).save(OUT / nombre, quality=90, optimize=True)


# --- A: escena (persona + lugar) a pantalla completa, texto arriba a la izquierda y la «evidencia» de la marca
a = CFG["a"]
img, d = m.canvas()
f = abrir(a.get("archivo"))
ia = a.get("archivo") == "miniatura-fondo.jpg"
if f:
    img = m.cover(f, m.W, m.H, (0.6, 0.4))
    img = ImageEnhance.Contrast(ImageEnhance.Color(img).enhance(0.85 if ia else 0.15)).enhance(1.15)
    img = sombra_lado(img, True)
d = ImageDraw.Draw(img)
lineas = [x for x in a.get("lineas", []) if x.get("texto")][:2]
palabras = sum(len(x["texto"].split()) for x in lineas) or 1
tam = 250 if palabras <= 2 else 200 if palabras <= 3 else 170
y = 60
for x in lineas:
    tam_real = texto(d, (70, y), x["texto"].upper()[:18], tam, COLOR.get(x["color"], "ink"), anchor="la", maxw=m.W * 0.62)
    y += tam_real * 0.95
ev = abrir(a.get("evidencia"))
if ev:  # polaroid de evidencia con cinta amarilla, abajo a la izquierda (lejos del reloj de YouTube)
    fw, fh = 560, 430
    marco = Image.new("RGB", (fw + 44, fh + 110), (238, 234, 224))
    marco.paste(m.cover(ev, fw, fh), (22, 22))
    dm = ImageDraw.Draw(marco)
    dm.text((fw // 2 + 22, fh + 66), "EVIDENCIA", font=m.font("display", 54), fill=(40, 36, 32), anchor="mm")
    sombra = Image.new("RGBA", (marco.width + 40, marco.height + 40), (0, 0, 0, 0))
    ImageDraw.Draw(sombra).rectangle([20, 26, marco.width + 20, marco.height + 26], fill=(0, 0, 0, 150))
    sombra.paste(marco, (10, 10))
    pol = sombra.rotate(5, expand=True, resample=Image.BICUBIC)
    img.paste(pol, (60, m.H - pol.height + 20), pol)
    cinta = Image.new("RGBA", (230, 64), m.C["tape"] + (235,)).rotate(-8, expand=True)
    img.paste(cinta, (60 + pol.width // 2 - 110, m.H - pol.height + 8), cinta)
    d = ImageDraw.Draw(img)
if a.get("sello"):
    capa = m.stamp_layer(a["sello"].upper()[:12], "", "red", 14, 0.85)
    m.paste_scaled(img, capa, 760, m.H - 260, 0.85)
img.paste(m.hazard(m.W, 14), (0, 0))
guardar(img, "miniatura-A.jpg")

# --- B: pantalla dividida (allá en blanco y negro vs aquí a color)
b = CFG["b"]
img, d = m.canvas()
mitad = m.W // 2
izq_f, der_f = abrir(b.get("izq_archivo")), abrir(b.get("der_archivo")) or abrir(a.get("archivo"))
if izq_f:
    img.paste(ImageEnhance.Brightness(deslavar(m.cover(izq_f, mitad, m.H), 0.0)).enhance(0.55), (0, 0))
else:
    d.rectangle([0, 0, mitad, m.H], fill=(30, 14, 16))
if der_f:
    img.paste(ImageEnhance.Brightness(m.cover(der_f, mitad, m.H)).enhance(0.6), (mitad, 0))
else:
    d.rectangle([mitad, 0, m.W, m.H], fill=(12, 30, 18))
d = ImageDraw.Draw(img)
texto(d, (mitad // 2, m.H * 0.45), b.get("izq_texto", "").upper()[:10], 300, "red", anchor="mm", maxw=mitad - 80)
texto(d, (mitad + mitad // 2, m.H * 0.45), b.get("der_texto", "").upper()[:10], 300, "green", anchor="mm", maxw=mitad - 80)
texto(d, (mitad // 2, m.H * 0.8), b.get("izq_etiqueta", "").upper()[:18], 90, "ink", anchor="mm", maxw=mitad - 80)
texto(d, (mitad + mitad // 2, m.H * 0.8), b.get("der_etiqueta", "").upper()[:18], 90, "ink", anchor="mm", maxw=mitad - 80)
d.rectangle([mitad - 7, 0, mitad + 7, m.H], fill=m.C["tape"])
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
    _hilo["produccion"] = threading.Thread(target=_producir, args=(tema_id,), daemon=True)
    _hilo["produccion"].start()
    return {"ok": True}


ESQ_ARREGLO = {"type": "object", "additionalProperties": False, "required": ["frases"], "properties": {"frases": {
    "type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["n", "texto"],
                               "properties": {"n": {"type": "integer"}, "texto": {"type": "string"}}}}}}


def _arreglar_dudosas(g: dict, inv: dict, dudosas: list[dict]) -> int:
    """Las frases con cifras que no salen de su fuente se reescriben sin esas cifras (una sola llamada, sin Ramos)."""
    if not dudosas:
        return 0
    # sin gastar Claude: se quita la oración con la cifra sin fuente (si era la única, queda una transición)
    arreglos = {}
    for k, d in enumerate(dudosas):
        oraciones = [o for o in re.split(r"(?<=[.!?…])\s+", d["frase"]) if o.strip()]
        quedan = [o for o in oraciones if not (ex.numeros(o) & set(d["cifras"]))]
        arreglos[k] = " ".join(quedan).strip() if quedan else "Y la historia no termina ahí."
    hechos = 0
    for k, d in enumerate(dudosas):
        nuevo = arreglos.get(k, "")
        if not nuevo or (ex.numeros(nuevo) - (ex.numeros(d["frase"]) - set(d["cifras"]))):
            nuevo = "Y la historia no termina ahí."  # si aún trae cifras sin fuente, mejor una transición
        e = g["escenas"][d["escena"] - 1]
        for f in e["frases"]:
            if f["texto"] == d["frase"]:
                f["texto"] = nuevo
                hechos += 1
                break
    return hechos


def _producir(tema_id: str) -> None:
    """Un video completo, con varios del equipo trabajando a la vez: Vera investiga y escribe; luego Inés junta el
    material mientras el caso ya aparece en Casos; luego Nico (storyboard) y Mina (miniaturas) al mismo tiempo."""
    from concurrent.futures import ThreadPoolExecutor
    tema = next(x for x in temas() if x["id"] == tema_id)
    numero = _siguiente_numero()
    tarea = ex._tarea("ex_guion", "Producir el expediente", f"#{numero} · {tema['marca']}")
    claude.contexto.proyecto, claude.contexto.etapa, claude.contexto.tarea = None, "expedientes", tarea
    eid, mesa = None, None
    try:
        _paso(None, "investigacion", "ex_guion", f"Investigando {tema['marca']}: buscando y leyendo fuentes… 🔎", tarea)
        guardada = ex.CARPETA / "investigaciones" / f"{_slug(tema_id, 60)}.json"
        inv = None
        if guardada.exists() and time.time() - guardada.stat().st_mtime < 14 * 86400:
            try:  # ya se había investigado (p. ej. se acabó el plan en el guion): no se gasta otra vez
                inv = json.loads(guardada.read_text(encoding="utf-8"))
                _paso(None, "investigacion", "ex_guion", f"Retomo la investigación de {tema['marca']} que ya tenía ♻️", tarea)
            except ValueError:
                inv = None
        if not inv:
            inv = investigar(tema)
            guardada.parent.mkdir(parents=True, exist_ok=True)
            _escribir(guardada, inv)
        siguiente = next((x["marca"] for x in temas() if x["estado"] == "pendiente" and x["id"] != tema_id), "otra marca")
        _paso(None, "guion", "ex_guion", f"Escribiendo el guion de {tema['marca']} ({len(inv['hechos'])} datos con fuente) ✍️", tarea)
        g = escribir_guion(tema, inv, numero, siguiente)
        if len(g["escenas"]) < 3 or sum(len(e["frases"]) for e in g["escenas"]) < 6:
            raise RuntimeError("El guion salió demasiado corto.")
        dudosas = _revisar_cifras(g, inv)
        arregladas = _arreglar_dudosas(g, inv, dudosas)
        ex._decir("ex_guion", "libre", f"Guion de {tema['marca']} listo ✔")
        partes = {"01-guion-tecnico.md": _md_guion(tema, numero, g), "04-fuentes.md": _md_fuentes(tema, g, inv, []),
                  "03-publicacion.md": _md_publicacion(tema, g)}
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for nombre, texto in partes.items():
                z.writestr(nombre, texto)
        r = ex.importar(f"expediente-{numero}.zip", buf.getvalue())  # ya sale en Casos mientras sigue el trabajo
        eid = r["id"]
        destino = ex.carpeta(eid) / "fabrica"
        shutil.rmtree(destino, ignore_errors=True)
        destino.mkdir(parents=True)
        for nombre, texto in partes.items():
            (destino / nombre).write_text(texto, encoding="utf-8")
        _escribir(destino / "investigacion.json", inv)
        _escribir(destino / "guion.json", g)
        with ex._candado:  # sin Ramos: Vera ya comprobó la cita de cada dato en su página (ahorra mucho plan)
            t = ex.trabajo(eid)
            t["verificacion"].update(estado="aprobada", aprobada=time.time(), cambios=arregladas,
                                     nota="Vera comprobó la cita literal de cada dato en su página.")
            t["chat"].append({"quien": "ex_guion", "t": time.time(), "texto": (
                f"✔ Cada dato del guion salió de una página real (comprobé la cita). {len(inv['hechos'])} datos con fuente"
                + (f"; reescribí {arregladas} frase(s) que traían cifras sin fuente." if arregladas else ".")
                + " Ya va Inés por el material.")})
            ex._guardar_trabajo(eid, t)
        _poner(eid, tema=tema_id, canal=tema.get("canal") or "quien_mato", numero=numero, marca=tema["marca"],
               carpeta=f"{numero[-2:]}-{_slug(tema['marca'], 30)}", hechos_pasos=["investigacion", "guion", "verificacion"],
               paso="material", dudosas=len(dudosas), creado=time.time(),
               palabras=sum(len(f["texto"].split()) for e in g["escenas"] for f in e["frases"]))
        _paso(eid, "material", "ex_archivista", "Buscando fotos de todos lados y videos cortos 🗄️", tarea)
        material = buscar_material(tema, g, destino)
        ex._decir("ex_archivista", "libre", f"{len(material['lista'])} fotos y videos para {tema['marca']} ✔")
        _poner(eid, material=len(material["lista"]), hechos_pasos=sorted(set(fab(eid).get("hechos_pasos") or []) | {"material"}),
               paso="storyboard")
        _escribir(destino / "manifiesto-fotos.json", material["fotos"])
        _escribir(destino / "manifiesto-videos.json", material["videos"])
        (destino / "miniatura.py").write_text(MINIATURA_PY, encoding="utf-8")
        ex._decir("ex_graficas", "trabajando", "Armando el storyboard 📊")
        ex._decir("ex_miniaturas", "trabajando", "Diseñando las miniaturas 🖼️")
        _poner(eid, render_paso="Nico arma el storyboard y Mina las miniaturas, al mismo tiempo")

        def nico():
            escribir_storyboard(tema, numero, g, material, destino)
            ex._decir("ex_graficas", "libre", "Storyboard listo y revisado ✔")

        def mina():
            disenar_miniaturas(tema, g, material, destino)
            ex._decir("ex_miniaturas", "libre", "Miniaturas A y B listas ✔")

        with ThreadPoolExecutor(max_workers=2) as pool:  # 👥 los dos trabajan a la vez
            for fut in [pool.submit(nico), pool.submit(mina)]:
                fut.result()
        _poner(eid, hechos_pasos=sorted(set(fab(eid).get("hechos_pasos") or []) | {"storyboard"}), paso="render", render_paso="")
        with _candado:
            lista = temas()
            for x in lista:
                if x["id"] == tema_id:
                    x["estado"], x["eid"] = "listo", eid
            _guardar_temas(lista)
        ex._fin_tarea(tarea, resultado=f"Expediente #{numero} listo para hacer el video")
        threading.Thread(target=vuelta, daemon=True).start()  # directo al video, sin esperar el minuto
    except Exception as exc:  # noqa: BLE001 — se ve en la Bandeja; el tema regresa a la lista
        limite = isinstance(exc, claude.ErrorIA) and "límite" in str(exc).lower()
        ex._fin_tarea(tarea, error=str(exc)[:300])
        if eid:  # el caso ya existe: se queda y se retoma desde donde falló (no se empieza otro con otro número)
            _poner(eid, error=("Se acabó el límite de tu plan; sigo en cuanto vuelva." if limite else f"Falló: {str(exc)[:250]}"))
            with _candado:
                lista = temas()
                for x in lista:
                    if x["id"] == tema_id:
                        x["estado"], x["eid"] = "listo", eid
                _guardar_temas(lista)
                if limite:
                    e = estado()
                    e["espera_hasta"] = time.time() + 3600
                    e["nota"] = "Se acabó el límite de tu plan de Claude: sigo sola en cuanto vuelva."
                    _guardar_estado(e)
            ex._decir("ex_guion", "libre", "Me quedé a medias; lo retomo solo ⏳")
            return
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
    if not f or f.get("render_estado") in ("en_fila", "listo", "servidor") or f.get("render_ok") is False:
        return False
    v = t["verificacion"].get("estado")
    if v == "aprobada":
        return True
    if v == "lista":  # sin nada que corregir → directo a render (los ✅ no necesitan tu OK)
        c = ex._cuenta(t["datos"])
        return not c.get("corregir") and not c.get("no_confirmado") and not c.get("pendiente")
    return False


def _aplicar_cambios(texto: str, cambios: list[dict]) -> tuple[str, list[dict]]:
    """Aplica los cambios de Ramos (antes → después) dentro de cada frase, sin quitar ni mover frases (el storyboard
    va frase por frase). Regresa (guion, cambios que dejarían una frase vacía o que no se encontraron)."""
    lineas, escena, problemas = texto.splitlines(), 0, []
    pos = []
    for i, ln in enumerate(lineas):
        m = re.match(r"^## ESCENA\s+(\d+)", ln)
        if m:
            escena = int(m.group(1))
        elif ln.startswith("> "):
            pos.append((escena, i))
    for c in cambios:
        hecho = False
        for esc_n, i in pos:
            if c.get("escena") and esc_n != c["escena"]:
                continue
            if c["antes"] and c["antes"] in lineas[i]:
                nuevo = re.sub(r"\s{2,}", " ", lineas[i][2:].replace(c["antes"], c.get("despues") or "", 1)).strip()
                if len(re.sub(r"[\W_]+", "", nuevo)) < 8:
                    problemas.append(c)
                else:
                    lineas[i] = "> " + nuevo
                hecho = True
                break
        if not hecho:
            problemas.append(c)
    return "\n".join(lineas) + "\n", problemas


def _guion_final(eid: str) -> str:
    """El guion técnico con la narración corregida si se aprobaron cambios de Ramos."""
    c = ex.carpeta(eid)
    texto = (c / "fabrica" / "01-guion-tecnico.md").read_text(encoding="utf-8")
    corregida = ex._leer_json(c / "narracion-corregida.json", None) or {}
    return _aplicar_cambios(texto, corregida.get("cambios") or [])[0]




def _reescribir_sin_dato(texto: str, c: dict) -> str:
    """Una frase sin el dato que no se pudo confirmar. Sin gastar plan: quita la oración que lo cita y, si no queda
    nada, deja una transición corta para que la narración siga fluyendo (nunca agrega cifras nuevas)."""
    linea = next((ln[2:] for ln in texto.splitlines() if ln.startswith("> ") and c["antes"] in ln), c["antes"])
    oraciones = [o for o in re.split(r"(?<=[.!?…])\s+", linea.strip()) if o and c["antes"] not in o]
    nueva = " ".join(oraciones).strip() or "Y la historia no termina ahí."
    return nueva if not (ex.numeros(nueva) - ex.numeros(linea)) else "Y la historia no termina ahí."


def _auto_aprobar(eid: str, t: dict) -> bool:
    """🤖 Modo automático: si las correcciones de Ramos se pueden aplicar sin dejar frases vacías, se aprueban solas
    (cambiar o quitar el dato dudoso es lo seguro). Si no, el caso espera a que tú lo revises."""
    if ex._cuenta(t["datos"]).get("pendiente"):
        return False
    texto = (ex.carpeta(eid) / "fabrica" / "01-guion-tecnico.md").read_text(encoding="utf-8")
    cambios = [{"escena": d["escena"], "antes": d["frase"], "despues": d["frase_nueva"], "dato": d["id"]} for d in ex._aplicables(t)]
    for c in _aplicar_cambios(texto, cambios)[1]:  # quitar el dato dejaría la frase vacía: Vera la reescribe sin él
        nueva = _reescribir_sin_dato(texto, c)
        if nueva:
            r = ex.accion(eid, {"accion": "editar", "dato": c["dato"], "frase_nueva": nueva})
            if "error" in r:
                print(f"  · no pude reescribir la frase: {r['error']}", flush=True)
    t = ex.trabajo(eid)
    cambios = [{"escena": d["escena"], "antes": d["frase"], "despues": d["frase_nueva"]} for d in ex._aplicables(t)]
    if _aplicar_cambios(texto, cambios)[1]:
        _poner(eid, nota_auto="Ramos quiere quitar una frase completa: revísalo tú para que el video no quede cojo.")
        return False
    r = ex.aprobar(eid, forzar=True)
    return bool(r.get("ok"))


def _zip_render(eid: str) -> Path:
    c = ex.carpeta(eid)
    f = fab(eid)
    salida = c / "render-envio.zip"
    with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("01-guion-tecnico.md", _guion_final(eid))
        for nombre in ("storyboard.py", "miniatura.py", "miniatura.json", "miniatura-fondo.jpg", "manifiesto-fotos.json",
                       "manifiesto-videos.json", "04-fuentes.md", "03-publicacion.md"):
            p = c / "fabrica" / nombre
            if p.exists():
                z.write(p, nombre)
        fotos = c / "fabrica" / "material" / "fotos"
        if fotos.exists():  # las fotos ya bajadas y revisadas en el servidor viajan dentro del paquete
            for p in fotos.iterdir():
                if p.suffix.lower() in (".jpg", ".json") and re.fullmatch(r"[a-z0-9._-]+", p.name):
                    z.write(p, f"material/fotos/{p.name}")
    if codigo_seguro((c / "fabrica" / "storyboard.py").read_text(encoding="utf-8")):
        raise RuntimeError("El storyboard no pasó la revisión de seguridad.")
    return salida


def _azure() -> dict:
    """La clave de Azure vive en el servidor (.env); se le presta a la compu que hace el video y ella la borra."""
    clave, region = config.env("AZURE_SPEECH_KEY"), config.env("AZURE_SPEECH_REGION", "eastus")
    if not clave:  # la leo del .env en este momento: así no hace falta reiniciar la oficina después de pegarla
        try:
            from dotenv import dotenv_values
            vals = dotenv_values(config.BASE / ".env")
            clave = (vals.get("AZURE_SPEECH_KEY") or "").strip().strip('"').strip("'")
            region = (vals.get("AZURE_SPEECH_REGION") or region or "eastus").strip().strip('"').strip("'")
        except Exception:  # noqa: BLE001
            pass
    archivo = CANAL_DIR / ".azure_speech"
    if not clave and archivo.exists():
        partes = [x.strip() for x in archivo.read_text(encoding="utf-8-sig").splitlines() if x.strip()]
        clave, region = (partes + ["", "eastus"])[0], (partes + ["", "eastus"])[1]
    return {"clave": clave, "region": region or "eastus"} if clave else {}


def compus_sala() -> list[dict]:
    import requests
    try:
        compus = requests.get(f"{SALA_URL}/api/estado", timeout=5).json().get("compus") or []
    except (requests.RequestException, ValueError):
        return []
    pref = estado().get("compus") or {}
    return [{"id": c["id"], "nombre": c.get("nombre") or c["id"], "viva": bool(c.get("viva")),
             "puede": "expediente" in (c.get("tipos") or []), "motivo": c.get("expedientes") or "versión vieja",
             "pref": pref.get(c["id"], "respaldo"), "ocupada": bool(c.get("trabajo"))} for c in compus]


def _elegir_compu(evitar=()) -> dict | None:
    """La preferida si está prendida y puede; si no, cualquier otra de respaldo (las desocupadas primero).
    `evitar`: compus donde este video ya se trabó."""
    orden = {"preferida": 0, "respaldo": 1}
    vivas = [c for c in compus_sala() if c["viva"] and c["puede"] and c["pref"] != "no" and c["id"] not in evitar]
    vivas.sort(key=lambda c: (orden.get(c["pref"], 2), c["ocupada"]))
    return vivas[0] if vivas else None


_render_srv = threading.Lock()


def enviar_render(eid: str) -> dict:
    import requests
    f = fab(eid)
    if _demo():
        _poner(eid, render_estado="listo", paso="revision", hechos_pasos=sorted(set(f.get("hechos_pasos") or []) | {"verificacion", "render"}),
               render_ok=True, video=None, render_nota="(demo) Aquí saldría el video que hizo tu compu.")
        ex._decir("ex_editor", "libre", "Video listo (demo) 🎬")
        canal = next((x for x in agenda.lista() if x["id"] == (f.get("canal") or "quien_mato")), {})
        if estado().get("subir_solo") and canal.get("canal_youtube"):
            revisar(eid, {"accion": "programar"})
        return {"ok": True}
    azure = _azure()
    if not azure:
        _poner(eid, paso="render", render_paso="Falta la clave de Azure en el servidor (AZURE_SPEECH_KEY en el .env).")
        return {"error": "Falta la clave de Azure en el servidor."}
    # 🎙️ la voz de Azure gratis (F0) da 500 mil caracteres al mes: no pasarse (si no, el video sale sin voz)
    chars = sum(len(ln) - 2 for ln in _guion_final(eid).splitlines() if ln.startswith("> "))
    mes = dt.date.today().strftime("%Y-%m")
    e = estado()
    uso = e.get("azure") if (e.get("azure") or {}).get("mes") == mes else {"mes": mes, "chars": 0, "casos": []}
    uso.setdefault("casos", [])
    if eid in uso["casos"]:
        chars = 0  # 🔁 reenviar el mismo video no vuelve a contar su voz
    tope = int(config.env("AZURE_LIMITE_MES", "480000") or 480000)
    if uso["chars"] + chars > tope:
        e["nota"] = (f"La voz gratis de Azure ya casi se acaba este mes ({uso['chars']:,} de {tope:,} caracteres): "
                     "los videos que faltan se hacen el día 1 del siguiente mes.")
        _guardar_estado(e)
        _poner(eid, paso="render", render_paso=f"⏸️ Sin voz gratis de Azure este mes ({uso['chars']:,} de {tope:,}): sigue el día 1")
        return {"error": "Azure sin caracteres este mes"}
    try:
        zipf = _zip_render(eid)
    except Exception as exc:  # noqa: BLE001
        _poner(eid, error=str(exc)[:300], paso="render")
        return {"error": str(exc)}
    compu = None if f.get("render_forzar_srv") else _elegir_compu(f.get("render_evitar") or [])
    if compu:  # 🏢 va a la fila de la sala central: la toma la primera compu libre (tus compus primero, luego el servidor)
        evitar = sorted(set(f.get("render_evitar") or []) | {c["id"] for c in compus_sala() if c["pref"] == "no"})
        salida = ex.carpeta(eid) / "render-salida"
        shutil.rmtree(salida, ignore_errors=True)
        salida.mkdir(parents=True)
        try:
            preferida = f.get("render_preferir") if any(c["id"] == f.get("render_preferir") and c["viva"] for c in compus_sala()) else None
            r = requests.post(f"{SALA_URL}/interno/trabajo", timeout=15, json={
                "tipo": "expediente", "origen": "expedientes", "evitar": evitar, **({"compu": preferida} if preferida else {}),
                "etiqueta": f"🕵️ Expediente #{f.get('numero')} · {f.get('marca')}"[:80],
                "parametros": {"carpeta": f.get("carpeta"), "nombre": f"Expediente-{f.get('numero')}", "azure": azure},
                "entradas": [str(zipf)], "salida": str(salida)}).json()
        except (requests.RequestException, ValueError) as exc:
            r = {"error": f"La sala de edición no contestó ({exc})."}
        if not r.get("id"):  # la sala no lo aceptó: se dice en el caso y, si se puede, lo hace el servidor
            motivo = r.get("error") or "La sala no aceptó el trabajo."
            if estado().get("servidor_respaldo", True):
                _poner(eid, render_forzar_srv=True, render_paso=f"La sala no lo aceptó ({motivo[:80]}): lo hace el servidor")
                return enviar_render(eid)
            _poner(eid, paso="render", render_paso=f"⚠️ La sala no lo aceptó: {motivo[:120]}")
            return {"error": motivo}
        _poner(eid, render_estado="en_fila", render_tid=r["id"], render_compu=None, paso="render", render_preferir=None,
               render_paso="En la fila de la sala de edición", hechos_pasos=sorted(set(f.get("hechos_pasos") or []) | {"verificacion"}),
               render_desde=time.time(), render_mov_t=time.time(), render_avance=0)
        ex._decir("ex_editor", "trabajando", f"Mandé #{f.get('numero')} a la sala de edición 🎬")
    elif estado().get("servidor_respaldo"):
        if not _render_srv.acquire(blocking=False):
            _poner(eid, paso="render", render_paso="El servidor está haciendo otro video; este sigue en cuanto termine.")
            return {"ok": True, "espera": True}
        _poner(eid, render_estado="servidor", paso="render", render_forzar_srv=None, render_mov_t=time.time(),
               render_paso="Lo está haciendo el servidor" + (" (ninguna compu lo tomó)" if f.get("render_forzar_srv") else " (no hay compu disponible)"),
               hechos_pasos=sorted(set(f.get("hechos_pasos") or []) | {"verificacion"}), render_desde=time.time())
        threading.Thread(target=_render_servidor, args=(eid, zipf, azure), daemon=True).start()
    else:
        _poner(eid, paso="render", render_paso=_motivo_sin_compu() or "Esperando a una compu")
        return {"ok": True, "espera": True}
    e = estado()
    e["azure"] = {"mes": mes, "chars": uso["chars"] + chars, "casos": sorted(set(uso["casos"]) | {eid})[-60:]}
    if e.get("nota", "").startswith("La voz gratis de Azure"):
        e["nota"] = ""
    _guardar_estado(e)
    return {"ok": True}


def _render_servidor(eid: str, zipf: Path, azure: dict) -> None:
    """🖥️ Sin compu disponible: el servidor hace el video con el motor (letras libres en lugar de las de Windows)."""
    f = fab(eid)
    raiz = ex.carpeta(eid) / "render-servidor"
    ex._decir("ex_editor", "trabajando", f"Haciendo #{f.get('numero')} en el servidor 🎬")
    try:
        shutil.rmtree(raiz, ignore_errors=True)
        raiz.mkdir(parents=True)
        shutil.copytree(MOTOR, raiz / "motor", ignore=shutil.ignore_patterns("__pycache__"))
        (raiz / ".azure_speech").write_text(f"{azure['clave']}\n{azure['region']}\n", encoding="utf-8")
        ep = raiz / f["carpeta"]
        ep.mkdir()
        with zipfile.ZipFile(zipf) as z:
            for n in z.namelist():
                if "/" not in n and "\\" not in n and not n.startswith(".") and n.endswith((".md", ".py", ".json", ".jpg")):
                    (ep / n).write_bytes(z.read(n))
                elif re.fullmatch(r"material/fotos/[a-z0-9._-]+\.(jpg|json)", n):
                    (ep / "material" / "fotos").mkdir(parents=True, exist_ok=True)
                    (ep / n).write_bytes(z.read(n))
        if codigo_seguro((ep / "storyboard.py").read_text(encoding="utf-8")):
            raise RuntimeError("El storyboard no pasó la revisión de seguridad.")

        def correr(cmd, que):
            p = subprocess.Popen([sys.executable, "-E", *cmd], cwd=str(raiz), stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True, errors="replace")
            ultimas, señal = [], [time.time()]

            def vigilante():  # 🐕 20 min sin decir nada = trabado: se mata y el caso se reintenta
                while p.poll() is None:
                    time.sleep(20)
                    if time.time() - señal[0] > 1200 and p.poll() is None:
                        ultimas.append("se quedó 20 min sin avanzar")
                        p.kill()
            threading.Thread(target=vigilante, daemon=True).start()
            for linea in p.stdout:
                linea = linea.strip()
                if linea:
                    señal[0] = time.time()
                    ultimas = (ultimas + [linea])[-12:]
                    m = re.search(r"(\d+)/(\d+)", linea)
                    extra = {"render_avance": round(int(m.group(1)) / max(1, int(m.group(2))), 3)} if m and que == "haciendo el video" else {}
                    _poner(eid, render_paso=f"Servidor · {que}: {linea[:70]}", render_mov_t=time.time(), **extra)
            if p.wait() != 0:
                raise RuntimeError(f"{que} falló: " + " | ".join(ultimas[-4:])[-400:])

        for sub in ("fotos", "videos"):
            man = ep / f"manifiesto-{sub}.json"
            if man.exists() and json.loads(man.read_text(encoding="utf-8")):
                correr(["motor/fuentes_libres.py", "descargar", str(man), str(ep / "material" / sub)], f"bajando {sub}")
        correr(["motor/motor.py", f["carpeta"], "--render"], "haciendo el video")
        correr([f"{f['carpeta']}/miniatura.py"], "miniaturas")
        render = ep / "render"
        salida = ex.carpeta(eid) / "render-salida"
        shutil.rmtree(salida, ignore_errors=True)
        salida.mkdir(parents=True)
        video = next((v for v in sorted(render.glob("*.mp4")) if "solo-video" not in v.name), None)
        if not video:
            raise RuntimeError("El motor terminó pero no encontré el MP4.")
        for x in [video, *render.glob("*.srt"), *render.glob("*-capitulos.txt"), *render.glob("*-creditos.txt"),
                  *render.glob("miniatura-*.jpg")]:
            shutil.move(str(x), salida / x.name)
        _terminar_render(eid, f)
    except Exception as exc:  # noqa: BLE001
        _poner(eid, render_estado="error", error=f"El servidor no pudo hacer el video: {str(exc)[:250]}")
        ex._decir("ex_editor", "libre", "No pude hacer el video en el servidor 😕")
    finally:
        shutil.rmtree(raiz, ignore_errors=True)  # incluye la clave prestada
        _render_srv.release()


def _terminar_render(eid: str, f: dict) -> None:
    c = ex.carpeta(eid)
    salida, render = c / "render-salida", c / "render"
    render.mkdir(exist_ok=True)
    for p in salida.iterdir():
        shutil.move(str(p), render / p.name)
    video = next(iter(sorted(render.glob("*.mp4"))), None)
    if not video:
        _poner(eid, render_estado="error", error="No regresó el video.")
        return
    _poner(eid, render_estado="listo", paso="revision", render_ok=True, video=video.name, render_paso="",
           hechos_pasos=sorted(set(fab(eid).get("hechos_pasos") or []) | {"verificacion", "render"}), render_fin=time.time())
    ex._decir("ex_editor", "libre", f"#{f.get('numero')} {f.get('marca')}: ¡video listo! 🎬")
    canal = next((x for x in agenda.lista() if x["id"] == (f.get("canal") or "quien_mato")), {})
    if estado().get("subir_solo") and canal.get("canal_youtube"):
        revisar(eid, {"accion": "programar"})  # 🤖 sube solo en PRIVADO con su fecha; tú lo haces público
    elif ex.al_avisar:
        ex.al_avisar("Beto", f"El video de ¿Quién MATÓ a {f.get('marca')}? está listo para que lo revises.")


def _destrabar_render(eid: str, f: dict, motivo: str) -> None:
    """🔀 El video se quedó atorado en una compu: se cancela ahí y va a otra (o al servidor). No regresa a esa compu."""
    import requests
    try:
        requests.post(f"{SALA_URL}/interno/cancelar/{f['render_tid']}", json={}, timeout=5)
    except requests.RequestException:
        pass
    evitar = sorted(set(f.get("render_evitar") or []) | ({f["render_compu"]} if f.get("render_compu") else set()))
    _poner(eid, render_estado=None, render_tid=None, render_compu=None, render_evitar=evitar,
           render_paso=f"{motivo}: lo mando a otra compu (o al servidor)…", t_mov=time.time())
    ex._decir("ex_editor", "trabajando", f"#{f.get('numero')}: {motivo.lower()}, lo cambio de compu 🔀"[:120])


def _revisar_render(eid: str, paciencia: int = 1500) -> None:
    """`paciencia`: segundos sin que avance el video antes de quitárselo a esa compu (25 min; 8 con ▶ Continuar)."""
    import requests
    f = fab(eid)
    try:
        e = requests.get(f"{SALA_URL}/interno/trabajo/{f['render_tid']}", timeout=5).json()
    except (requests.RequestException, ValueError):
        if time.time() - (f.get("render_desde") or time.time()) > 600 and estado().get("servidor_respaldo", True):
            _poner(eid, render_estado=None, render_tid=None, render_forzar_srv=True,
                   render_paso="La sala de edición no contesta: lo hace el servidor")
        elif not str(f.get("render_paso") or "").startswith("La sala de edición no contesta"):
            _poner(eid, render_paso="La sala de edición no contesta (¿se reinició?): reintento")
        return
    est = e.get("estado")
    if e.get("compu_id") and e["compu_id"] != f.get("render_compu"):  # ya lo tomó una compu (o el servidor)
        _poner(eid, render_compu=e["compu_id"], render_mov_t=time.time())
        f = fab(eid)
    if est == "en_cola" and not f.get("render_compu") and time.time() - (f.get("render_desde") or time.time()) > 300 \
            and estado().get("servidor_respaldo", True):
        # ⏳ 5 min en la fila y ninguna compu lo tomó (ocupadas o trabadas): lo hace el servidor aquí mismo
        try:
            requests.post(f"{SALA_URL}/interno/cancelar/{f['render_tid']}", json={}, timeout=5)
        except requests.RequestException:
            pass
        _poner(eid, render_estado=None, render_tid=None, render_forzar_srv=True,
               render_paso="Ninguna compu lo tomó en 5 min: lo hace el servidor")
        ex._decir("ex_editor", "trabajando", f"#{f.get('numero')}: ninguna compu lo tomó, lo hago en el servidor 🖥️")
        return
    if est == "en_cola":
        compu = next((c for c in compus_sala() if c["id"] == f.get("render_compu")), None)
        if f.get("render_compu") and (not compu or not compu["viva"] or not compu["puede"] or compu["pref"] == "no") \
                and time.time() - (f.get("render_desde") or 0) > 180:
            try:  # 🔀 esa compu se apagó (o ya no quieres usarla): se le quita y va a otra o al servidor
                requests.post(f"{SALA_URL}/interno/cancelar/{f['render_tid']}", json={}, timeout=5)
            except requests.RequestException:
                pass
            _poner(eid, render_estado=None, render_tid=None, render_compu=None, render_paso="Cambiando de compu…")
            return
        motivo = _motivo_sin_compu()
        if motivo != (f.get("render_paso") or "") and (motivo or f.get("render_paso", "").startswith(("Ninguna", "Tu compu", "La sala"))):
            _poner(eid, render_paso=motivo or "En fila para tu compu")
            if motivo and ex.al_avisar and not f.get("avisado_compu"):
                ex.al_avisar("Beto", f"¿Quién MATÓ a {f.get('marca')}? espera a tu compu: {motivo}")
                _poner(eid, avisado_compu=True)
        return
    if est in ("asignado", "trabajando"):
        avance, paso = e.get("avance") or 0, e.get("paso") or ""
        if avance != f.get("render_avance") or paso != f.get("render_paso"):
            _poner(eid, render_paso=paso, render_avance=avance, render_mov_t=time.time())
            ex._decir("ex_editor", "trabajando", f"{e.get('compu') or 'Tu compu'}: {paso or 'renderizando'}"[:120])
            return
        quieto = time.time() - (f.get("render_mov_t") or f.get("render_desde") or time.time())
        compu = next((c for c in compus_sala() if c["id"] == f.get("render_compu")), None)
        if compu is not None and not compu["viva"] and quieto > 180:
            _destrabar_render(eid, f, f"{compu['nombre']} se apagó a medio video")
        elif quieto > paciencia:
            _destrabar_render(eid, f, f"Se trabó en {round(float(avance) * 100) if float(avance) <= 1 else round(float(avance))} %")
        return
    if est == "listo":
        _terminar_render(eid, f)
        return
    if est == "cancelado" or (est == "error" and "reinici" in str(e.get("error") or "")):
        # la sala se reinició (p. ej. al actualizarse) o soltó el trabajo: se vuelve a mandar ya, sin contarlo como falla
        _poner(eid, render_estado=None, render_tid=None, render_compu=None,
               render_paso="La sala soltó el video (se reinició): lo vuelvo a mandar")
        return
    if est == "error" and re.search(r"subir|Connection|SSL|Max retries|timed out|tiempo|apag|internet|quedó guardado",
                                    str(e.get("error") or ""), re.I):
        # 🔌 falló la conexión (casi siempre al subir): esa compu ya tiene el video hecho → se le vuelve a mandar YA,
        # solo lo sube (no lo rehace) y no cuenta como falla
        _poner(eid, render_estado=None, render_tid=None, render_compu=None, render_preferir=e.get("compu_id"),
               render_paso=f"Se cortó la conexión con {e.get('compu') or 'la compu'}: lo retomo ahí mismo (ya tiene el video hecho)")
        return
    if est == "error":
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
def _ligar_canal() -> None:
    """Si el canal de la agencia no tiene a dónde subir y ya conectaste uno nuevo (quienmato…), se liga solo."""
    from . import canales as yt
    datos = agenda.lista()
    cambio = False
    for c in datos:
        if c.get("canal_youtube"):
            continue
        candidato = next((y["id"] for y in yt.lista() if y["id"] != yt.PRINCIPAL and yt.conectado(y["id"])
                          and ("quien" in y["id"] or "mato" in y["id"] or "expediente" in y["id"])), None)
        if candidato:
            c["canal_youtube"] = candidato
            cambio = True
    if cambio:
        agenda._guardar(datos)
        ex._avisa_pantalla()


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


def _casos_en_marcha() -> list[str]:
    """Los casos que todavía no quedan programados (primero el que se está preparando)."""
    vivos = []
    for x in ex.lista():
        f = ex.trabajo(x["id"]).get("fabrica")
        if f and f.get("subida") != "listo" and not (f.get("error") and (f.get("reintentos") or 0) >= 2):
            vivos.append((f.get("paso") in ("render", "revision", "programado"), x["id"]))
    return [i for _, i in sorted(vivos, key=lambda v: v[0])]


def _caso_en_marcha() -> str | None:
    c = _casos_en_marcha()
    return c[0] if c else None


def _caso_sin_terminar() -> str | None:
    """🏭 Video tras video: mientras un caso se renderiza en las compus, el equipo ya puede preparar el siguiente.
    Se espera solo si hay un caso todavía en preparación (investigación → storyboard) o si ya hay tantos videos
    esperando compu como compus (y servidor) prendidas. Los que fallaron 2 veces no detienen todo."""
    en_render = 0
    for x in ex.lista():
        f = ex.trabajo(x["id"]).get("fabrica")
        if not f or f.get("subida") == "listo" or (f.get("error") and (f.get("reintentos") or 0) >= 2):
            continue
        if f.get("paso") not in ("render", "revision", "programado"):
            return x["id"]  # uno a la vez en preparación (cuida tu plan de Claude)
        en_render += 1
    maquinas = max(1, min(3, sum(1 for c in compus_sala() if c["viva"] and c["puede"])))
    return "renders" if en_render >= maquinas else None


def meta_videos() -> int:
    e = estado()
    ritmo = min((int(c.get("ritmo_dias") or 3) for c in agenda.lista() if c.get("activo", True)), default=3)
    return math.ceil(e["meta_dias"] / ritmo)


def _produciendo() -> bool:
    h = _hilo.get("produccion")
    return bool(h and h.is_alive())


def _curar() -> None:
    """🩹 Lo que se quedó a medias (servidor reiniciado, compu apagada, verificación cortada) se destraba solo."""
    e = estado()
    if e.get("en_curso") and not _produciendo():  # la producción se cortó (p. ej. se actualizó el servidor)
        with _candado:
            lista = temas()
            for x in lista:
                if x["id"] == e["en_curso"] and x["estado"] == "produciendo":
                    x["estado"] = "pendiente"
            _guardar_temas(lista)
        e["en_curso"] = None
        _guardar_estado(e)
    for x in ex.lista():
        t = ex.trabajo(x["id"])
        f = t.get("fabrica")
        if not f:
            continue
        v = t["verificacion"].get("estado")
        if x["id"] not in ex._corriendo and v in ("sin_empezar", "interrumpida", "error") and "storyboard" in (f.get("hechos_pasos") or []):
            if v != "error" or time.time() - (t["verificacion"].get("inicio") or f.get("error_t") or 0) > 1200:
                ex.verificar(x["id"])  # Ramos vuelve a verificar lo que se cortó
        if (f.get("error") and time.time() - (f.get("error_t") or 0) > 1200 and (f.get("reintentos") or 0) < 2
                and _plan_disponible()):  # con el plan en pausa no se quema un reintento: espera a que se restablezca
            reintentar(x["id"], auto=True)
        hilo = _hilo.get(f"convertir-{x['id']}")
        if (f.get("paso") in ("material", "storyboard") and not f.get("error") and not _produciendo()
                and not (hilo and hilo.is_alive())):
            _retomar(x["id"])  # se cortó a medias (p. ej. se reinició el servidor): se retoma solo


def reintentar(eid: str, auto: bool = False) -> dict:
    """Vuelve a intentar el paso que falló de un caso (el video, la subida o la verificación)."""
    f = fab(eid)
    t = ex.trabajo(eid)
    _poner(eid, error=None, error_t=None, nota_auto=None, reintentos=(f.get("reintentos") or 0) + (1 if auto else 0))
    if f.get("subida") == "error":
        return revisar(eid, {"accion": "programar"})
    if f.get("paso") in ("material", "storyboard") or (f and "storyboard" not in (f.get("hechos_pasos") or [])):
        return _retomar(eid)
    if f.get("render_estado") in ("error", "en_fila") or f.get("paso") == "render":
        if f.get("render_tid"):  # que la compu suelte el trabajo viejo (no se hagan dos al mismo tiempo)
            try:
                import requests
                requests.post(f"{SALA_URL}/interno/cancelar/{f['render_tid']}", json={}, timeout=5)
            except Exception:  # noqa: BLE001
                pass
        _poner(eid, render_estado=None, render_tid=None)
        if t["verificacion"].get("estado") in ("aprobada", "lista"):
            return enviar_render(eid)
        return {"ok": True}
    if t["verificacion"].get("estado") in ("error", "interrumpida", "sin_empezar") and eid not in ex._corriendo:
        return ex.verificar(eid)
    return {"ok": True}


def continuar() -> dict:
    """▶ «Ya hay recursos: sigue». Quita las esperas, destraba lo atorado y reintenta lo que falló, ahorita."""
    e = estado()
    e.update(activa=True, espera_hasta=0, nota="")
    _guardar_estado(e)
    try:
        claude._suscripcion_pausada_hasta = 0  # si el plan se había pausado por el límite, se vuelve a intentar
    except AttributeError:
        pass
    with _candado:
        lista = temas()
        for x in lista:
            if x["estado"] == "saltado" and x.get("intentos"):  # saltados por fallas, no por ti
                x.update(estado="pendiente", intentos=0, error=None)
        _guardar_temas(lista)
    if _ciclo_colgado():
        _arrancar_ciclo()
    reintentos = 0
    for x in ex.lista():
        f = fab(x["id"])
        if f.get("error") or f.get("nota_auto"):
            reintentar(x["id"])
            reintentos += 1
        elif f.get("render_estado") == "en_fila" and f.get("render_tid"):
            _revisar_render(x["id"], paciencia=480)  # ▶ si lleva 8 min sin moverse, se cambia de compu ya
        elif f.get("render_estado") == "servidor" and not _render_srv.locked():
            _poner(x["id"], render_estado=None, render_paso="El servidor se reinició a medio video: lo vuelvo a mandar")
    _curar()
    threading.Thread(target=vuelta, daemon=True).start()
    return {"ok": True, "reintentos": reintentos}


def reinicio_forzoso() -> dict:
    """🔄 Botón de pánico: destraba TODO lo de la fábrica ya mismo. Renders sin moverse 2 min → a otra compu o al
    servidor; casos con error → otra vez desde donde iban (con reintentos nuevos); producción cortada → se retoma."""
    hechos = []
    e = estado()
    e.update(activa=True, espera_hasta=0, nota="")
    if e.get("en_curso") and not _produciendo():
        e["en_curso"] = None
    _guardar_estado(e)
    try:
        claude._suscripcion_pausada_hasta = 0
    except AttributeError:
        pass
    with _candado:
        lista = temas()
        for x in lista:
            if x["estado"] == "produciendo" and not _produciendo():
                x["estado"] = "pendiente"
            if x["estado"] == "saltado" and x.get("intentos"):
                x.update(estado="pendiente", intentos=0, error=None)
        _guardar_temas(lista)
    if _ciclo_colgado():  # la vuelta de la fábrica se quedó esperando algo: se arranca otra limpia
        _arrancar_ciclo()
        hechos.append("la fábrica estaba colgada: la reinicié")
    for x in ex.lista():
        f = fab(x["id"])
        if not f or f.get("subida") == "listo":
            continue
        nombre = f"#{f.get('numero')} {f.get('marca')}"
        quieto = time.time() - (f.get("render_mov_t") or f.get("t_mov") or 0)
        if f.get("paso") == "render" and quieto > 900 and not (f.get("render_estado") == "servidor" and _render_srv.locked()):
            # 💥 a la fuerza: se tira todo lo del render y se manda otra vez YA (la sala o, si nadie, el servidor)
            if f.get("render_tid"):
                try:
                    import requests
                    requests.post(f"{SALA_URL}/interno/cancelar/{f['render_tid']}", json={}, timeout=5)
                except Exception:  # noqa: BLE001
                    pass
            _poner(x["id"], render_estado=None, render_tid=None, render_compu=None, render_evitar=[], render_ok=None,
                   render_forzar_srv=None, error=None, error_t=None, reintentos=0, render_paso="Reinicio forzoso: lo mando otra vez")
            try:
                r = enviar_render(x["id"])
            except Exception as exc:  # noqa: BLE001
                r = {"error": str(exc)}
            hechos.append(f"{nombre}: " + (f"no se pudo mandar ({r['error']})" if r.get("error")
                                           else "lo hace el servidor" if fab(x["id"]).get("render_estado") == "servidor"
                                           else "en la fila de la sala (si ninguna compu lo toma en 5 min, el servidor)"))
            continue
        if f.get("error"):
            _poner(x["id"], reintentos=0)
            reintentar(x["id"])
            hechos.append(f"{nombre}: reintento")
        elif f.get("render_estado") == "en_fila" and f.get("render_tid"):
            antes = f.get("render_tid")
            _revisar_render(x["id"], paciencia=120)
            if fab(x["id"]).get("render_tid") != antes:
                hechos.append(f"{nombre}: render cambiado de compu")
        elif f.get("render_estado") == "servidor" and not _render_srv.locked():
            _poner(x["id"], render_estado=None, render_paso="Reinicio forzoso: lo vuelvo a mandar")
            hechos.append(f"{nombre}: render reenviado")
        elif f.get("paso") in ("material", "storyboard") and not _produciendo():
            hilo = _hilo.get(f"convertir-{x['id']}")
            if not (hilo and hilo.is_alive()):
                _retomar(x["id"])
                hechos.append(f"{nombre}: retomado")
    threading.Thread(target=vuelta, daemon=True).start()
    return {"ok": True, "hechos": hechos}


def vuelta() -> None:
    """Una pasada: renders que revisar, casos que mandar a tu compu y, si toca, el siguiente tema."""
    try:
        _curar()
    except Exception as exc:  # noqa: BLE001
        LATIDO["error"] = f"curar: {exc}"[:200]
    for x in ex.lista():
        try:
            _vuelta_caso(x)
        except Exception as exc:  # noqa: BLE001 — un caso con problema no detiene a los demás
            LATIDO["error"] = f"#{x.get('numero')}: {exc}"[:200]
            print(f"  · fábrica: caso {x.get('numero')}: {exc}", flush=True)
    _vuelta_resto()


def _vuelta_caso(x: dict) -> None:
    if True:  # (antes era el cuerpo del for de vuelta())
        t = ex.trabajo(x["id"])
        f = t.get("fabrica")
        if not f:
            return
        if f.get("render_estado") == "en_fila" and f.get("render_tid"):
            _revisar_render(x["id"])
        elif f.get("render_estado") == "servidor" and not _render_srv.locked():  # la oficina se reinició a medio video
            _poner(x["id"], render_estado=None, render_paso="El servidor se reinició a medio video: lo vuelvo a mandar")
        elif _listo_para_render(x["id"], t) and not f.get("error"):
            enviar_render(x["id"])
        elif (estado().get("subir_solo") and t["verificacion"].get("estado") == "lista" and not f.get("nota_auto")
              and not f.get("render_estado")):
            if _auto_aprobar(x["id"], t):
                enviar_render(x["id"])


def _vuelta_resto() -> None:
    """Después de revisar los casos: ligar el canal y, si toca, arrancar el siguiente tema."""
    _ligar_canal()
    e = estado()
    if not e["activa"] or e.get("en_curso") or time.time() < e.get("espera_hasta", 0):
        return
    if not _plan_disponible():
        return
    if _caso_sin_terminar():
        return  # ☝️ primero se termina el video que va (hasta quedar en el calendario) y luego otro
    if _material_por_delante() >= meta_videos():
        return
    siguiente = next((x for x in temas() if x["estado"] == "pendiente"), None)
    if not siguiente:
        if estado().get("subir_solo", True) or not any(x["estado"] == "propuesto" for x in temas()):
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

    _arrancar_ciclo(espera=20)


LATIDO = {"inicio": 0.0, "fin": 0.0, "error": "", "hilo": 0}  # 💓 cada vuelta de la fábrica (para ver si se colgó)


def _arrancar_ciclo(espera: int = 0) -> None:
    LATIDO["hilo"] += 1
    mio = LATIDO["hilo"]

    def ciclo():
        time.sleep(espera)
        while LATIDO["hilo"] == mio:  # si se arrancó otro ciclo (este se colgó), este se retira al despertar
            LATIDO["inicio"] = time.time()
            try:
                vuelta()
                LATIDO["error"] = ""
            except Exception as exc:  # noqa: BLE001 — la fábrica nunca tumba la oficina
                LATIDO["error"] = str(exc)[:200]
                print(f"  · fábrica de expedientes: {exc}", flush=True)
            LATIDO["fin"] = time.time()
            time.sleep(60)
    _hilo["ciclo"] = threading.Thread(target=ciclo, daemon=True)
    _hilo["ciclo"].start()


def _ciclo_colgado() -> bool:
    """La vuelta empezó hace más de 10 min y no ha terminado (algo se quedó esperando para siempre)."""
    return LATIDO["inicio"] > LATIDO["fin"] and time.time() - LATIDO["inicio"] > 600


def _diagnostico() -> dict:
    """🩺 Para saber qué pasa sin entrar al servidor: versión instalada, la vuelta de la fábrica y la sala."""
    import subprocess as sp
    raiz = Path(__file__).resolve().parents[2]
    try:
        version = sp.run(["git", "-C", str(raiz), "log", "-1", "--format=%h · %cd", "--date=format:%d/%m %H:%M"],
                         capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, sp.SubprocessError):
        version = ""
    try:
        import requests
        sala = "ok" if requests.get(f"{SALA_URL}/api/estado", timeout=3).ok else "no contesta"
    except Exception:  # noqa: BLE001
        sala = "no contesta"
    return {"version": version, "vuelta_hace": round(time.time() - LATIDO["fin"]) if LATIDO["fin"] else None,
            "colgada": _ciclo_colgado(), "error": LATIDO["error"], "sala": sala}


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
                          "verificacion": t["verificacion"].get("estado"), "cuenta": ex._cuenta(t["datos"]),
                          "pasos": pasos(t), "t_mov": f.get("t_mov"), "creado": f.get("creado")})
    return {"estado": e, "temas": lista, "casos": casos, "meta": meta_videos(), "por_delante": _material_por_delante(),
            "en_marcha": _caso_en_marcha(), "en_marcha_todos": _casos_en_marcha(), "ahora": time.time(),
            "diagnostico": _diagnostico(),
            "chat": historial_chat()[-60:], "produciendo": _produciendo(), "compus": compus_sala(),
            "azure_ok": bool(_azure()) or _demo(), "imagenes": motor_imagenes(),
            "plan": _plan_disponible(), "pexels": (CANAL_DIR / ".pexels_key").exists(), "demo": _demo()}


def archivo_render(eid: str, nombre: str) -> Path | None:
    c = ex.carpeta(eid) / "render"
    ruta = (c / Path(nombre).name).resolve()
    if ruta.is_file() and ruta.is_relative_to(c.resolve()) and ruta.suffix.lower() in (".mp4", ".jpg", ".srt", ".txt"):
        return ruta
    return None


# ---------------------------------------------------------------- 💬 el chat de la agencia (instrucciones reales)
CHAT = ex.CARPETA / "chat_agencia.json"
ACCIONES = ["continuar", "pausar", "prender", "producir", "hacer_video", "agregar_tema", "primero", "saltar", "aprobar_tema",
            "proponer_temas", "reintentar", "rehacer_video", "subir", "meta_dias", "ritmo", "hora", "subir_solo",
            "mensaje_caso", "usar_compu", "servidor_respaldo", "editar_video", "miniatura_video", "ninguna"]
ESQ_CHAT = {"type": "object", "additionalProperties": False, "required": ["quien", "respuesta", "acciones"], "properties": {
    "quien": {"type": "string", "enum": [i for i, *_ in ex.EQUIPO]},
    "respuesta": {"type": "string", "description": "lo que le contestas a Miguel (corto, español de México, de tú)"},
    "acciones": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                 "required": ["tipo", "marca", "gancho", "caso", "texto", "numero", "si"],
                 "properties": {"tipo": {"type": "string", "enum": ACCIONES}, "marca": {"type": "string"},
                                "gancho": {"type": "string"}, "caso": {"type": "string", "description": "número (003) o marca del caso"},
                                "texto": {"type": "string"}, "numero": {"type": "string"}, "si": {"type": "boolean"}}}}}}


def historial_chat() -> list[dict]:
    return _leer(CHAT, [])[-120:]


def _chat_poner(m: dict) -> None:
    with _candado:
        h = _leer(CHAT, [])
        h.append({"t": time.time(), **m})
        _escribir(CHAT, h[-300:])
    ex._avisa_pantalla()


def _tema(marca: str) -> dict | None:
    s = _slug(marca)
    lista = temas()
    return next((x for x in lista if x["id"] == s), None) or next((x for x in lista if s and (s in x["id"] or x["id"] in s)), None)


def _caso(ref: str) -> str | None:
    ref = (ref or "").strip().lstrip("#")
    for x in ex.lista():
        if ref and (ref == x["id"] or ref.lstrip("0") == str(x["numero"]).lstrip("0") or _slug(ref) in x["id"]):
            return x["id"]
    return None


def _contexto_chat() -> str:
    r = resumen()
    e = r["estado"]
    ag = agenda.agenda(dias=40)
    lineas = [f"FÁBRICA: {'prendida' if e['activa'] else 'pausada'} · subir sola: {'sí' if e.get('subir_solo') else 'no'} · "
              f"meta {e['meta_dias']} días ({r['meta']} videos) · por delante {r['por_delante']} · plan de Claude "
              f"{'disponible' if r['plan'] else 'NO disponible (límite o sin conectar)'} · produciendo: {e.get('en_curso') or 'nada'}"
              + (f" · nota: {e['nota']}" if e.get("nota") else "")]
    for x in ex.lista():
        if not ex.trabajo(x["id"]).get("fabrica"):
            lineas.append(f"CASO #{x['numero']} {x['marca']} ({x['id']}): {situacion_caso(x['id'])}")
    for c in r["casos"]:
        lineas.append(f"CASO #{c['numero']} {c['marca']}: {situacion_caso(c['id'])} · paso {c['paso']}, verificación {c['verificacion']}, "
                      f"video {c.get('render_estado') or '-'}, subida {c.get('subida') or '-'}"
                      + (f", programado {c['programado']['fecha']}" if c.get("programado") else "")
                      + (f", ERROR: {c['error']}" if c.get("error") else ""))
    lineas.append("COMPUS: " + ("; ".join(f"{c['nombre']} ({'prendida' if c['viva'] else 'apagada'}, "
                                          f"{'puede' if c['puede'] else 'no puede: ' + c['motivo']}, {c['pref']})"
                                          for c in r["compus"]) or "ninguna en la sala")
                  + f" · servidor de respaldo: {'sí' if e.get('servidor_respaldo') else 'no'}")
    vids = videos_canal()
    lineas.append("VIDEOS EN TU CANAL (YouTube): " + ("; ".join(f"«{v['titulo']}» ({v['estado']}{', programado ' + v['programado'][:10] if v.get('programado') else ''}, {v['url']})" for v in vids[:25])
                                                     or ("ninguno o no pude leerlos" if _canal_yt() else "el canal de YouTube no está elegido en Canales")))
    sig = [x for x in r["temas"] if x["estado"] in ("pendiente", "propuesto", "produciendo")][:15]
    lineas.append("TEMAS: " + "; ".join(f"{x['marca']} ({x['estado']})" for x in sig))
    for c in ag["canales"]:
        lineas.append(f"CANAL {c['nombre']}: cada {c['ritmo_dias']} días a las {c['hora']}, sube a «{c.get('canal_youtube') or 'sin elegir'}», "
                      f"{c['llenos']} programados")
    return "\n".join(lineas)


def _ejecutar(a: dict) -> str:
    tipo = a["tipo"]
    if tipo == "ninguna":
        return ""
    if tipo == "continuar":
        r = continuar()
        return f"▶ Seguimos (reintenté {r['reintentos']} caso(s) atorado(s))."
    if tipo in ("pausar", "prender"):
        ajustar({"activa": tipo == "prender"})
        return "⏸ Fábrica en pausa." if tipo == "pausar" else "🏭 Fábrica prendida."
    if tipo == "subir_solo":
        ajustar({"subir_solo": a["si"]})
        return "📤 Subirá sola en privado." if a["si"] else "📤 Ya no sube sola: te los deja para revisar."
    if tipo == "editar_video":
        r = editar_video_canal(a["marca"] or a["caso"], titulo=a["texto"], descripcion=a["gancho"])
        return f"✖ {r['error']}" if "error" in r else f"✏️ Cambié «{r['video']}» en YouTube."
    if tipo == "miniatura_video":
        r = miniatura_video(a["marca"] or a["caso"])
        return f"✖ {r['error']}" if "error" in r else f"🖼️ Mina ya está haciendo la miniatura de «{r['video']}» (te aviso aquí cuando la suba)."
    if tipo == "usar_compu":
        nombre = _slug(a["marca"] or a["texto"])
        c = next((x for x in compus_sala() if nombre and (nombre in _slug(x["nombre"]) or nombre in _slug(x["id"]))), None)
        if not c:
            return f"✖ No encontré la compu «{a['marca']}»."
        pref = {"preferida": "preferida", "respaldo": "respaldo", "no": "no"}.get((a["numero"] or "").strip().lower(), "preferida")
        r = ajustar({"compu": c["id"], "pref": pref})
        return r.get("error") or f"🖥️ {c['nombre']}: {'⭐ preferida' if pref == 'preferida' else 'respaldo' if pref == 'respaldo' else '🚫 no se usa'}."
    if tipo == "servidor_respaldo":
        ajustar({"servidor_respaldo": a["si"]})
        return "🖥️ Si no hay compu, lo hace el servidor." if a["si"] else "🖥️ El servidor ya no hace videos: espera a una compu."
    if tipo == "meta_dias":
        r = ajustar({"meta_dias": a["numero"]})
        return r.get("error") or f"📦 Juntar material para {estado()['meta_dias']} días."
    if tipo in ("ritmo", "hora"):
        c = agenda.lista()[0]
        r = agenda.guardar_canal({"id": c["id"], "ritmo_dias" if tipo == "ritmo" else "hora": a["numero"] if tipo == "ritmo" else a["texto"]})
        return r.get("error") or ("📅 Ritmo cambiado." if tipo == "ritmo" else "🕖 Hora cambiada.")
    if tipo == "proponer_temas":
        r = proponer_temas(n=max(1, min(12, int(a["numero"] or 6) if str(a["numero"]).isdigit() else 6)))
        return f"💡 {r['nuevos']} tema(s) nuevo(s) para que los apruebes."
    if tipo in ("producir", "agregar_tema", "primero", "saltar", "aprobar_tema"):
        t = _tema(a["marca"])
        if not t and tipo in ("producir", "agregar_tema"):
            r = mover_tema({"op": "nuevo", "marca": a["marca"], "gancho": a["gancho"]})
            if "error" in r:
                return f"✖ {r['error']}"
            t = _tema(a["marca"])
            if tipo == "agregar_tema":
                return f"🧾 Agregué «{a['marca']}» a la fila."
        if not t:
            return f"✖ No encontré el tema «{a['marca']}»."
        if tipo == "saltar":
            mover_tema({"op": "saltar", "id": t["id"]})
            return f"⏭️ Salté «{t['marca']}»."
        if tipo == "aprobar_tema" or t["estado"] in ("propuesto", "saltado"):
            mover_tema({"op": "aprobar", "id": t["id"]})
        mover_tema({"op": "primero", "id": t["id"]})
        if tipo == "producir":
            if estado().get("en_curso"):
                return f"⬆ «{t['marca']}» es el siguiente (en cuanto termine el que está en producción)."
            r = producir(t["id"])
            return f"⚙️ Arranqué «{t['marca']}»." if "ok" in r else f"✖ {r.get('error')}"
        return f"⬆ «{t['marca']}» quedó primero en la fila."
    eid = _caso(a["caso"])
    if not eid:
        return f"✖ No encontré el caso «{a['caso']}»."
    if tipo == "hacer_video":
        r = convertir(eid)
    elif tipo == "reintentar":
        r = reintentar(eid)
    elif tipo == "rehacer_video":
        r = revisar(eid, {"accion": "rehacer_video"})
    elif tipo == "subir":
        _poner(eid, paso="revision")
        r = revisar(eid, {"accion": "programar" if a["si"] else "privado"})
    elif tipo == "mensaje_caso":
        r = ex.chat(eid, a["texto"][:1500])
    else:
        return ""
    return f"✖ {r['error']}" if "error" in r else {"reintentar": "🔁 Reintentando", "rehacer_video": "🎬 Rehaciendo el video de",
                                                    "subir": "📤 Subiendo", "mensaje_caso": "💬 Le pasé tu mensaje al equipo del",
                                                    "hacer_video": "🎬 Preparando el video del"}[tipo] + f" caso {eid}."


def _demo_chat(texto: str) -> dict:
    t = texto.lower()
    acc = {"tipo": "ninguna", "marca": "", "gancho": "", "caso": "", "texto": "", "numero": "", "si": False}
    if any(k in t for k in ("continúa", "continua", "sigue", "reinicia", "dale")):
        acc["tipo"] = "continuar"
    elif "pausa" in t:
        acc["tipo"] = "pausar"
    elif any(k in t for k in ("haz", "produce", "hazme")):
        acc.update(tipo="producir", marca=texto.split()[-1].strip("?.!"))
    return {"quien": "ex_guion", "respuesta": "Va, jefe (demo).", "acciones": [acc]}


def chat_agencia(texto: str) -> dict:
    texto = texto.strip()[:1500]
    if not texto:
        return {"error": "Escribe algo."}
    _chat_poner({"quien": "jefe", "texto": texto})
    threading.Thread(target=_responder_agencia, args=(texto,), daemon=True).start()
    return {"ok": True}


def _responder_agencia(texto: str) -> None:
    tarea = ex._tarea("ex_guion", "Contestar el chat de la agencia", texto[:80])
    try:
        if _demo():
            r = _demo_chat(texto)
        else:
            previos = "\n".join(f"{'Miguel' if m['quien'] == 'jefe' else ex.NOMBRES.get(m['quien'], m['quien'])}: {m['texto'][:300]}"
                                for m in historial_chat()[-12:-1])
            equipo = "\n".join(f"- {i} = {n} ({rol}): {d}" for i, n, rol, _, _, d in ex.EQUIPO)
            r = claude.json_estructurado(
                "Eres el equipo de la Agencia de Expedientes (canal de YouTube «¿Quién MATÓ a…?»). Miguel, el jefe, te "
                "escribe instrucciones reales. Contesta como el del equipo que toque y HAZ lo que pide con las acciones "
                "disponibles (puedes poner varias). Si pide algo que no puedes hacer con esas acciones, dile qué sí puedes "
                "y cómo. No inventes estados: usa la SITUACIÓN de abajo. Si pregunta algo, contéstalo con esos datos.\n\n"
                "ACCIONES: continuar (destrabar y seguir ya), pausar, prender, producir {marca}, agregar_tema {marca, "
                "gancho}, primero {marca}, saltar {marca}, aprobar_tema {marca}, proponer_temas {numero}, reintentar "
                "{caso}, hacer_video {caso} (convierte en video un caso importado, o reintenta), rehacer_video {caso}, subir {caso, si=con fecha}, meta_dias {numero}, ritmo {numero de días}, "
                "hora {texto HH:MM}, subir_solo {si}, usar_compu {marca = nombre de la compu, numero = preferida|respaldo|no}, servidor_respaldo {si}, editar_video {marca = cuál video de VIDEOS EN TU CANAL, texto = título nuevo (vacío = no cambiar), gancho = descripción nueva completa (vacío = no cambiar)}, miniatura_video {marca = cuál video} (Mina le hace miniatura nueva y la sube), mensaje_caso {caso, texto} (para cambiar frases o datos de un "
                "guion: lo atiende Ramos), ninguna.\n\nEQUIPO:\n" + equipo,
                f"SITUACIÓN AHORA:\n{_contexto_chat()}\n\nPLÁTICA RECIENTE:\n{previos or '(nada)'}\n\nMIGUEL: {texto}",
                ESQ_CHAT, tarea=TAREA, que="chat de la agencia")
        hechos = []
        for a in r["acciones"][:6]:
            try:
                x = _ejecutar(a)
            except Exception as exc:  # noqa: BLE001
                x = f"✖ {a['tipo']}: {str(exc)[:150]}"
            if x:
                hechos.append(x)
        _chat_poner({"quien": r["quien"], "texto": r["respuesta"], "hechos": hechos})
        ex._decir(r["quien"], "libre", r["respuesta"][:120])
        ex._fin_tarea(tarea, resultado="contestado")
    except Exception as exc:  # noqa: BLE001
        limite = "límite" in str(exc).lower()
        _chat_poner({"quien": "ex_guion", "texto": ("Se acabó el límite de tu plan de Claude; en cuanto vuelva te contesto. "
                                                    "Mientras, el botón «▶ Continuar ahora» sí funciona.") if limite
                     else f"Uy, no pude contestar: {str(exc)[:200]}"})
        ex._fin_tarea(tarea, error=str(exc)[:200])


# ---------------------------------------------------------------- 🎬 hacer video de un caso importado (paquete propio)
def _guion_de_md(md: str) -> dict:
    """El guion técnico (.md) de un paquete como lo usa la fábrica: escenas con sus frases «> »."""
    escenas, cur = [], None
    for linea in md.splitlines():
        m = re.match(r"^## ESCENA\s+(\d+)\s*·\s*(.*)$", linea)
        if m:
            cur = {"titulo": m.group(2).strip(), "capitulo": m.group(2).strip(), "visual": [], "texto_pantalla": [],
                   "audio": "", "frases": []}
            escenas.append(cur)
        elif cur is not None and linea.startswith("> "):
            cur["frases"].append({"texto": linea[2:].strip(), "hechos": []})
        elif cur is not None and linea.startswith("- ") and not cur["frases"]:
            cur["visual"].append(linea[2:].strip())
        elif cur is not None and linea.startswith("**Texto en pantalla:**"):
            cur["texto_pantalla"] = re.findall(r'"([^"]+)"', linea)
    return {"escenas": escenas}


def _retomar(eid: str) -> dict:
    with _candado:
        if _hilo.get(f"convertir-{eid}") and _hilo[f"convertir-{eid}"].is_alive():
            return {"ok": True}
        _hilo[f"convertir-{eid}"] = threading.Thread(target=_convertir, args=(eid,), daemon=True)
        _hilo[f"convertir-{eid}"].start()
    return {"ok": True}


def convertir(eid: str) -> dict:
    """🎬 Un caso que importaste (con su guion ya verificado) se vuelve video con la fábrica: material libre,
    storyboard, miniaturas, voz de Azure en tu compu y subida en privado."""
    f = fab(eid)
    if "storyboard" in (f.get("hechos_pasos") or []):
        return reintentar(eid)
    return _retomar(eid)


def _convertir(eid: str) -> None:
    p = ex.paquete(eid)
    c = ex.carpeta(eid)
    tema = {"id": _slug(p["marca"]), "marca": p["marca"], "gancho": ""}
    numero = p["numero"]
    tarea = ex._tarea("ex_archivista", "Preparar el video", f"#{numero} · {p['marca']}")
    claude.contexto.proyecto, claude.contexto.etapa, claude.contexto.tarea = None, "expedientes", tarea
    try:
        md = (c / "01-guion-tecnico.md").read_text(encoding="utf-8")
        g = _guion_de_md(md)
        if not g["escenas"]:
            raise RuntimeError("El guion del paquete no trae escenas «## ESCENA N · …» con frases «> ».")
        pub = p.get("publicacion") or {}
        desc = "\n".join(ln for ln in (pub.get("descripcion") or "").splitlines()
                         if not re.match(r"^\s*\d{1,2}:\d{2}", ln) and "CAPÍTULOS" not in ln.upper())
        g.update(descripcion=desc.strip(), etiquetas=pub.get("etiquetas") or [], comentario_fijado=pub.get("comentario_fijado") or "",
                 miniatura_a=[], miniatura_b=[], proximo="")
        destino = c / "fabrica"
        destino.mkdir(exist_ok=True)
        (destino / "01-guion-tecnico.md").write_text(md, encoding="utf-8")
        previo = fab(eid)
        _poner(eid, tema=previo.get("tema") or tema["id"], canal=previo.get("canal") or "quien_mato", numero=numero, marca=p["marca"],
               carpeta=previo.get("carpeta") or f"{numero[-2:]}-{_slug(p['marca'], 30)}",
               hechos_pasos=sorted(set(previo.get("hechos_pasos") or []) | {"investigacion", "guion"}), paso="material", error=None,
               creado=time.time(), palabras=sum(len(f["texto"].split()) for e in g["escenas"] for f in e["frases"]))
        _paso(eid, "material", "ex_archivista", "Buscando fotos y videos libres 🗄️", tarea)
        material = buscar_material(tema, g, destino)
        ex._decir("ex_archivista", "libre", f"{len(material['lista'])} fotos y videos ✔")
        _paso(eid, "storyboard", "ex_graficas", "Armando el storyboard 📊", tarea)
        (destino / "miniatura.py").write_text(MINIATURA_PY, encoding="utf-8")
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as pool:  # 👥 Nico y Mina a la vez
            futs = [pool.submit(escribir_storyboard, tema, numero, g, material, destino),
                    pool.submit(disenar_miniaturas, tema, g, material, destino)]
            for fut in futs:
                fut.result()
        ex._decir("ex_graficas", "libre", "Storyboard listo ✔")
        _escribir(destino / "manifiesto-fotos.json", material["fotos"])
        _escribir(destino / "manifiesto-videos.json", material["videos"])
        if not (destino / "guion.json").exists():
            _escribir(destino / "guion.json", g)
        f = fab(eid)
        aprobada = ex.trabajo(eid)["verificacion"].get("estado") == "aprobada"
        _poner(eid, hechos_pasos=sorted(set(f.get("hechos_pasos") or []) | {"material", "storyboard"} | ({"verificacion"} if aprobada else set())),
               paso="render" if aprobada else "verificacion", material=len(material["lista"]), error=None)
        ex._fin_tarea(tarea, resultado="Listo para hacer el video")
        t = ex.trabajo(eid)
        if t["verificacion"].get("estado") in ("sin_empezar", "interrumpida"):
            ex.verificar(eid)
    except Exception as exc:  # noqa: BLE001
        _poner(eid, error=f"No pude preparar el video: {str(exc)[:250]}")
        ex._fin_tarea(tarea, error=str(exc)[:300])
        ex._decir("ex_archivista", "libre", "Uy, algo falló 😕")
    finally:
        claude.contexto.tarea = None


# ---------------------------------------------------------------- ¿por qué tu compu no lo toma?
def _motivo_sin_compu() -> str:
    import requests
    try:
        compus = requests.get(f"{SALA_URL}/api/estado", timeout=5).json().get("compus") or []
    except (requests.RequestException, ValueError):
        return "La sala de edición no contesta."
    vivas = [c for c in compus if c.get("viva")]
    if not vivas:
        return "Ninguna compu de la sala está prendida: prende tu PC china con el programa de la sala."
    if any("expediente" in (c.get("tipos") or []) for c in vivas):
        return ""
    return "Tu compu todavía no puede hacer videos de Expedientes: " + "; ".join(
        f"{c.get('nombre') or c.get('id')}: {c.get('expedientes') or 'versión vieja (se actualiza sola en unos minutos)'}" for c in vivas)


def situacion_caso(eid: str) -> str:
    """En qué va un caso, en palabras (para el chat)."""
    t = ex.trabajo(eid)
    f = t.get("fabrica") or {}
    if not f:
        return ("Este caso es un PAQUETE IMPORTADO: todavía no se ha convertido en video. Con la acción «hacer_video» la "
                "fábrica busca material libre, arma el storyboard y las miniaturas, y tu compu lo hace con voz de Azure "
                f"(verificación: {t['verificacion'].get('estado')}).")
    pasos_txt = ", ".join(f"{p['etiqueta']}: {p['estado']}" for p in pasos(t))
    extra = []
    if f.get("render_estado") == "en_fila":
        extra.append(f"video: esperando/en tu compu ({f.get('render_paso') or 'en fila'})")
    if f.get("video"):
        extra.append(f"video listo: {f['video']}")
    if f.get("url"):
        extra.append(f"subido: {f['url']}" + (f" programado {t.get('programado', {}).get('fecha')}" if t.get("programado") else ""))
    if f.get("error"):
        extra.append(f"ERROR: {f['error']}")
    if f.get("nota_auto"):
        extra.append(f"espera a Miguel: {f['nota_auto']}")
    return f"Caso de la FÁBRICA. Pasos → {pasos_txt}. " + " · ".join(extra)


def subir_ya(eid: str, con_fecha: bool = True) -> dict:
    """Subir ya el video hecho (desde el chat): con la siguiente fecha libre o en privado sin fecha."""
    f = fab(eid)
    if not f.get("video") and not _demo():
        return {"error": "Todavía no hay video: primero hay que hacerlo (hacer_video)."}
    _poner(eid, paso="revision")
    return revisar(eid, {"accion": "programar" if con_fecha else "privado"})


# ---------------------------------------------------------------- 📺 videos que ya están en tu canal
_cache_videos: dict = {"t": 0, "lista": []}


def _canal_yt() -> str:
    return next((c.get("canal_youtube") for c in agenda.lista() if c.get("canal_youtube")), "")


def videos_canal(forzar: bool = False) -> list[dict]:
    """Los videos del canal de la serie (con caché de 10 min para no gastar cuota de YouTube)."""
    if _demo():
        return [{"id": "demoSears", "titulo": "¿Quién MATÓ a Sears?", "estado": "public", "programado": "", "fecha": "2026-11-20",
                 "url": "https://youtu.be/demoSears"},
                {"id": "demoTupp", "titulo": "¿Quién MATÓ a Tupperware?", "estado": "private", "programado": "", "fecha": "2026-11-24",
                 "url": "https://youtu.be/demoTupp"}]
    canal = _canal_yt()
    if not canal:
        return []
    if forzar or time.time() - _cache_videos["t"] > 600:
        from . import youtube
        try:
            _cache_videos.update(t=time.time(), lista=youtube.videos_del_canal(canal=canal))
        except Exception as exc:  # noqa: BLE001
            print(f"  · no pude leer los videos del canal: {exc}", flush=True)
    return _cache_videos["lista"]


def _buscar_video(ref: str) -> dict | None:
    ref = (ref or "").strip()
    lista = videos_canal()
    if not ref:
        return None
    vid = ref.rstrip("/").split("/")[-1].split("=")[-1]
    s = _slug(ref)
    return (next((v for v in lista if v["id"] == vid), None)
            or next((v for v in lista if s and s in _slug(v["titulo"])), None)
            or next((v for v in lista if s and any(p in _slug(v["titulo"]) for p in s.split("-") if len(p) > 3)), None))


def editar_video_canal(ref: str, titulo: str = "", descripcion: str = "") -> dict:
    v = _buscar_video(ref)
    if not v:
        return {"error": f"No encontré en tu canal un video que se llame como «{ref}»."}
    if not titulo and not descripcion:
        return {"error": "¿Qué le cambio? (título o descripción)"}
    if not _demo():
        from . import youtube
        youtube.editar_video(v["url"], titulo=titulo or None, descripcion=descripcion or None, canal=_canal_yt())
        _cache_videos["t"] = 0
    return {"ok": True, "video": v["titulo"]}


def miniatura_video(ref: str) -> dict:
    """🖼️ Mina le hace miniatura nueva (A, la que jala) a un video que ya está en tu canal y la sube."""
    v = _buscar_video(ref)
    if not v:
        return {"error": f"No encontré en tu canal un video que se llame como «{ref}»."}
    threading.Thread(target=_miniatura_video, args=(v,), daemon=True).start()
    return {"ok": True, "video": v["titulo"]}


def _miniatura_video(v: dict) -> None:
    m = re.search(r"MAT[OÓ] a (.+?)\??$", v["titulo"], flags=re.I)
    marca = (m.group(1) if m else v["titulo"]).strip(" ?¿")
    tarea = ex._tarea("ex_miniaturas", "Miniatura nueva", v["titulo"][:60])
    ex._decir("ex_miniaturas", "trabajando", f"Haciendo la miniatura de {marca} 🖼️")
    raiz = ex.CARPETA / "_miniaturas" / _slug(marca)
    try:
        shutil.rmtree(raiz, ignore_errors=True)
        ep = raiz / "01-miniatura"
        (ep / "material" / "fotos").mkdir(parents=True)
        material = {"lista": [], "fotos": [], "videos": []}
        if not _demo():  # fotos libres de la marca en Wikimedia (sin gastar Claude)
            fl = _fuentes_libres()
            vistos = set()
            for q in (f"{marca} store", f"{marca} logo", f"{marca}", f"{marca} building"):
                try:
                    res = fl.commons(q, 10)
                except Exception:  # noqa: BLE001
                    continue
                for x in res:
                    if x["titulo"] in vistos or not _licencia_libre(x.get("licencia")) or (x.get("ancho") or 0) < 900 \
                            or not (x.get("mime") or "").startswith(("image/jpeg", "image/png")):
                        continue
                    vistos.add(x["titulo"])
                    material["fotos"].append(x)
                if len(material["fotos"]) >= 6:
                    break
            thumbs = fl.commons_thumbs([x["titulo"] for x in material["fotos"]]) if material["fotos"] else {}
            manif = []
            for i, x in enumerate(material["fotos"][:6], 1):
                nombre = f"{_slug(marca, 20)}-{i}" + (Path((thumbs.get(x["titulo"]) or x["url"]).split("?")[0]).suffix.lower() or ".jpg")
                manif.append({"nombre": nombre, "url": thumbs.get(x["titulo"]) or x["url"], "fuente": x["fuente"],
                              "licencia": x.get("licencia"), "autor": x.get("autor"), "pagina": x.get("pagina"), "titulo": x["titulo"]})
                material["lista"].append({"archivo": f"material/fotos/{nombre}", "describe": x["titulo"][:80], "video": False,
                                          "escenas": [1], "fuente": x["fuente"]})
            _escribir(raiz / "manifiesto.json", manif)
            if manif:
                fl.descargar(str(raiz / "manifiesto.json"), str(ep / "material" / "fotos"))
        disenar_miniaturas({"marca": marca, "gancho": ""}, {"miniatura_a": [], "miniatura_b": []}, material, ep)
        (ep / "miniatura.py").write_text(MINIATURA_PY, encoding="utf-8")
        if _demo():
            resultado = "(demo) Aquí Mina haría la miniatura y la subiría."
        else:
            shutil.copytree(MOTOR, raiz / "motor", ignore=shutil.ignore_patterns("__pycache__"))
            r = subprocess.run([sys.executable, "-E", "01-miniatura/miniatura.py"], cwd=str(raiz), capture_output=True,
                               text=True, timeout=300)
            mini = ep / "render" / "miniatura-A.jpg"
            if r.returncode != 0 or not mini.exists():
                raise RuntimeError((r.stderr or r.stdout or "no salió la imagen")[-300:])
            from . import youtube
            youtube.poner_miniatura(v["url"], mini, canal=_canal_yt())
            destino = ex.CARPETA / "miniaturas"
            destino.mkdir(exist_ok=True)
            shutil.copyfile(mini, destino / f"{_slug(marca)}-A.jpg")
            resultado = f"✔ Le puse miniatura nueva a «{v['titulo']}» ({v['url']})."
        _chat_poner({"quien": "ex_miniaturas", "texto": resultado})
        ex._fin_tarea(tarea, resultado=resultado[:120])
        ex._decir("ex_miniaturas", "libre", "Miniatura lista ✔")
    except Exception as exc:  # noqa: BLE001
        _chat_poner({"quien": "ex_miniaturas", "texto": f"😕 No pude con la miniatura de «{v['titulo']}»: {str(exc)[:250]}"})
        ex._fin_tarea(tarea, error=str(exc)[:200])
        ex._decir("ex_miniaturas", "libre", "No pude con la miniatura 😕")
    finally:
        shutil.rmtree(raiz, ignore_errors=True)
