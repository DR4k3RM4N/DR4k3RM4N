"""📅 Canales y agenda de la Agencia de Expedientes.

Cada canal de la agencia tiene su plantilla de título, su ritmo (un video cada N días), su hora y a qué canal de
YouTube sube (los de `agentes/canales.py`). La agenda reparte los casos terminados en los días que tocan, para ir
juntando material por meses. Todo se sube SIEMPRE en privado/programado: solo Miguel lo hace público.
"""
from __future__ import annotations

import datetime as dt
import threading
from zoneinfo import ZoneInfo

from . import canales as yt_canales
from . import config
from . import expedientes as ex

ARCHIVO = ex.CARPETA / "canales.json"
ZONA = ZoneInfo(config.env("IDEAS_ZONA", "America/Mexico_City"))
_candado = threading.RLock()
DEFECTO = [{"id": "quien_mato", "nombre": "¿Quién MATÓ a…?", "plantilla": "¿Quién MATÓ a [Marca]?",
            "tema": "Marcas famosas de EE.UU., México o Latinoamérica que murieron (o están por morir) y qué pasó en México.",
            "ritmo_dias": 3, "hora": "19:00", "canal_youtube": "", "activo": True, "inicio": ""}]


def lista() -> list[dict]:
    with _candado:
        datos = ex._leer_json(ARCHIVO, None)
        if not datos:
            datos = [dict(c) for c in DEFECTO]
        return datos


def _guardar(datos: list[dict]) -> None:
    ex.CARPETA.mkdir(parents=True, exist_ok=True)
    ex._escribir_json(ARCHIVO, datos)


def guardar_canal(d: dict) -> dict:
    """Crea o cambia un canal de la agencia (nombre, tema, ritmo, hora, canal de YouTube)."""
    with _candado:
        datos = lista()
        cid = str(d.get("id") or "").strip()
        c = next((x for x in datos if x["id"] == cid), None)
        if d.get("borrar"):
            if len(datos) <= 1:
                return {"error": "Tiene que quedar al menos un canal."}
            datos = [x for x in datos if x["id"] != cid]
            _guardar(datos)
            ex._avisa_pantalla()
            return {"ok": True}
        if not c:
            nombre = str(d.get("nombre") or "").strip()[:80]
            if len(nombre) < 2:
                return {"error": "Ponle nombre al canal."}
            c = {**DEFECTO[0], "id": yt_canales.slug(nombre) or f"canal{len(datos) + 1}", "nombre": nombre, "tema": "",
                 "plantilla": "", "canal_youtube": ""}
            if any(x["id"] == c["id"] for x in datos):
                return {"error": "Ya hay un canal con ese nombre."}
            datos.append(c)
        for k, largo in (("nombre", 80), ("plantilla", 120), ("tema", 600), ("hora", 5), ("canal_youtube", 60), ("inicio", 10)):
            if k in d:
                c[k] = str(d[k] or "").strip()[:largo]
        if "ritmo_dias" in d:
            try:
                c["ritmo_dias"] = max(1, min(14, int(d["ritmo_dias"])))
            except (TypeError, ValueError):
                return {"error": "El ritmo es un número de días (1 = diario, 3 = cada 3 días)."}
        if "activo" in d:
            c["activo"] = bool(d["activo"])
        try:
            dt.time.fromisoformat(c["hora"])
        except ValueError:
            return {"error": "La hora va como 19:00."}
        _guardar(datos)
    ex._avisa_pantalla()
    return {"ok": True, "canales": datos}


def _hoy() -> dt.date:
    return dt.datetime.now(ZONA).date()


def agenda(dias: int = 45) -> dict:
    """Los próximos días de publicación de cada canal y qué caso va en cada uno."""
    casos = ex.lista()
    hoy = _hoy()
    salida = []
    for c in lista():
        if not c.get("activo", True):
            continue
        ritmo = int(c.get("ritmo_dias") or 3)
        try:
            inicio = dt.date.fromisoformat(c["inicio"]) if c.get("inicio") else hoy + dt.timedelta(days=1)
        except ValueError:
            inicio = hoy + dt.timedelta(days=1)
        while inicio < hoy:
            inicio += dt.timedelta(days=ritmo)
        programados = {}
        for x in casos:
            prog = ex.trabajo(x["id"]).get("programado") or {}
            if prog.get("canal") == c["id"] and prog.get("fecha"):
                programados[prog["fecha"]] = x
        fechas, d = [], inicio
        while d <= hoy + dt.timedelta(days=dias):
            caso = programados.get(d.isoformat())
            fechas.append({"fecha": d.isoformat(), "hora": c.get("hora", "19:00"),
                           "caso": {"id": caso["id"], "numero": caso["numero"], "marca": caso["marca"]} if caso else None})
            d += dt.timedelta(days=ritmo)
        llenos = [f for f in fechas if f["caso"]]
        hasta = llenos[-1]["fecha"] if llenos else None
        salida.append({**c, "fechas": fechas, "llenos": len(llenos), "cubierto_hasta": hasta,
                       "dias_cubiertos": (dt.date.fromisoformat(hasta) - hoy).days if hasta else 0})
    return {"hoy": hoy.isoformat(), "canales": salida,
            "youtube": [{"id": y["id"], "nombre": y.get("nombre", y["id"]), "conectado": yt_canales.conectado(y["id"])}
                        for y in yt_canales.lista()]}
