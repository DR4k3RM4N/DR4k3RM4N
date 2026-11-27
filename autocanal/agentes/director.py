"""🎯 Director de producción: decide qué va primero en todas las oficinas y te informa.

- **Prioridades** (las cambias en /director): por defecto Cuida Tu Lana → ¿Quién MATÓ a…? → Apps que sí pagan →
  tus videos personales (sala de edición) → TikTok Shop → Tampiqueando. La sala de edición reparte las compus y el
  servidor en ese orden (lee este mismo archivo), y el piloto del edificio arranca primero los videos del canal que va
  más arriba.
- **Enfoque**: eliges UNA categoría y solo esa usa las máquinas y arranca videos nuevos; lo demás espera (no se pierde).
- **Cerebro**: cada pocas horas revisa los pendientes de todas las oficinas y te deja un informe corto (qué está
  atorado, qué conviene hacer). Usa tu plan de Claude (Sonnet) y aprende de tus correcciones («notas»).
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from . import claude, config

ARCHIVO = config.BASE / "director.json"  # la sala de edición también lo lee (mismo servidor)
CATEGORIAS = {
    "fraudes": "🐑 Cuida Tu Lana", "expedientes": "🕵️ ¿Quién MATÓ a…?", "apps": "▶ Apps que sí pagan",
    "personal": "🎞️ Tus videos personales", "tiktok": "🛒 TikTok Shop", "tampico": "🌮 Tampiqueando",
}
ORDEN_BASE = ["fraudes", "expedientes", "apps", "personal", "tiktok", "tampico"]
_candado = threading.Lock()


def estado() -> dict:
    try:
        e = json.loads(ARCHIVO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        e = {}
    orden = [c for c in e.get("orden") or [] if c in CATEGORIAS]
    e["orden"] = orden + [c for c in ORDEN_BASE if c not in orden]
    e.setdefault("enfoque", None)
    e.setdefault("notas", [])
    e.setdefault("informes", [])
    return e


def _guardar(e: dict) -> None:
    with _candado:
        ARCHIVO.write_text(json.dumps(e, ensure_ascii=False, indent=1), encoding="utf-8")


def ajustar(d: dict) -> dict:
    e = estado()
    if isinstance(d.get("orden"), list):
        e["orden"] = [c for c in d["orden"] if c in CATEGORIAS] + [c for c in ORDEN_BASE if c not in d["orden"]]
    if "subir" in d and d["subir"] in e["orden"]:  # ⬆ un lugar
        i = e["orden"].index(d["subir"])
        if i:
            e["orden"][i - 1], e["orden"][i] = e["orden"][i], e["orden"][i - 1]
    if "enfoque" in d:
        e["enfoque"] = d["enfoque"] if d["enfoque"] in CATEGORIAS else None
    if d.get("nota"):
        e["notas"] = (e["notas"] + [{"t": time.time(), "texto": str(d["nota"])[:400]}])[-30:]
    if d.get("quitar_nota") is not None:
        e["notas"] = [n for i, n in enumerate(e["notas"]) if i != int(d["quitar_nota"])]
    _guardar(e)
    return e


def categoria_canal(canal: str | None) -> str:
    """El canal de YouTube de un video → su categoría (Cuida Tu Lana = fraudes; los demás, apps)."""
    from . import canales
    return "fraudes" if canales.get(canal or canales.PRINCIPAL).get("nicho") == "fraudes" else "apps"


def permitido(categoria: str) -> bool:
    """¿Esta categoría puede arrancar cosas nuevas ahorita? (con enfoque, solo la enfocada)."""
    enfoque = estado().get("enfoque")
    return not enfoque or enfoque == categoria


def rango(categoria: str) -> int:
    e = estado()
    return e["orden"].index(categoria) if categoria in e["orden"] else len(e["orden"])


# ---------------------------------------------------------------- lo que hay pendiente en cada oficina
def pendientes(oficina) -> dict:
    """Conteos por categoría: lo que espera, lo que se está haciendo y lo que tiene problema."""
    from . import canales, expedientes_fabrica
    p = {c: {"produccion": 0, "revision": 0, "error": 0, "ideas": 0, "detalle": []} for c in CATEGORIAS}
    with oficina.lock:
        proyectos = list(oficina.proyectos.values())
        ideas = list(oficina.propuestas)
    for x in proyectos:
        c = categoria_canal(x.get("canal"))
        if x["estado"] in ("produccion", "publicando"):
            p[c]["produccion"] += 1
        elif x["estado"] in ("revision", "error"):
            p[c][x["estado"]] += 1
            p[c]["detalle"].append(f"{x['titulo']} ({x['estado']}{': ' + str(x.get('error'))[:80] if x.get('error') else ''})")
    for i in ideas:
        if i.get("estado") == "pendiente":
            p[categoria_canal(i.get("canal"))]["ideas"] += 1
    try:
        r = expedientes_fabrica.resumen()
        for c in r.get("casos") or []:
            if c["id"] in (r.get("en_marcha_todos") or []):
                k = "error" if c.get("error") else "revision" if c.get("paso") == "revision" else "produccion"
                p["expedientes"][k] += 1
                p["expedientes"]["detalle"].append(f"#{c.get('numero')} {c.get('marca')}: {c.get('error') or c.get('render_paso') or c.get('paso')}"[:140])
        p["expedientes"]["ideas"] = sum(1 for t in r.get("temas") or [] if t.get("estado") == "pendiente")
    except Exception:  # noqa: BLE001
        pass
    try:  # la sala de edición: tus proyectos personales y la fila de trabajos
        import requests
        sala = requests.get(f"{config.env('SALA_URL', 'http://127.0.0.1:8767').rstrip('/')}/api/estado", timeout=4).json()
        for pr in sala.get("proyectos") or []:
            c = "tampico" if "tampiq" in str(pr.get("nombre", "")).lower() else "personal"
            if pr.get("estado") in ("editando",):
                p[c]["produccion"] += 1
            elif pr.get("estado") in ("error",):
                p[c]["error"] += 1
        p["_sala"] = {"cola": sala.get("cola", 0), "compus": sum(1 for x in sala.get("compus") or [] if x.get("viva"))}
    except Exception:  # noqa: BLE001
        p["_sala"] = {"cola": "?", "compus": "?"}
    try:
        import requests
        tt = requests.get(f"{config.env('TIENDA_URL', 'http://127.0.0.1:8766').rstrip('/')}/api/estado", timeout=4).json()
        for pr in tt.get("productos") or []:
            k = {"trabajando": "produccion", "error": "error"}.get(pr.get("estado"))
            if k:
                p["tiktok"][k] += 1
    except Exception:  # noqa: BLE001
        pass
    return p


# ---------------------------------------------------------------- 🧠 el informe (cada pocas horas, con tu plan)
ESQ = {"type": "object", "additionalProperties": False, "required": ["resumen", "atorado", "acciones"],
       "properties": {"resumen": {"type": "string"},
                      "atorado": {"type": "array", "items": {"type": "string"}},
                      "acciones": {"type": "array", "items": {"type": "string"}}}}


def informe(oficina, forzar: bool = False) -> dict:
    e = estado()
    ultimo = (e["informes"] or [{}])[-1]
    if not forzar and time.time() - ultimo.get("t", 0) < 4 * 3600:
        return ultimo
    p = pendientes(oficina)
    orden = [f"{i + 1}. {CATEGORIAS[c]}" for i, c in enumerate(e["orden"])]
    texto = (f"PRIORIDADES DEL JEFE:\n" + "\n".join(orden) + f"\nENFOQUE: {CATEGORIAS.get(e['enfoque'], 'ninguno (todas)')}\n\n"
             f"PENDIENTES (por categoría):\n{json.dumps(p, ensure_ascii=False)[:6000]}\n\n"
             "NOTAS Y CORRECCIONES DEL JEFE (aprende de ellas):\n" + ("\n".join(f"- {n['texto']}" for n in e["notas"][-15:]) or "(ninguna)")
             + "\n\nINFORMES ANTERIORES (no repitas lo mismo si ya se resolvió):\n"
             + "\n".join(f"- {i.get('resumen', '')[:200]}" for i in e["informes"][-3:]))
    try:
        r = claude.json_estructurado(
            "Eres el director de producción de Miguel (México): coordinas sus oficinas de video (canales de YouTube, "
            "TikTok Shop, Tampiqueando y la sala de edición con sus compus). Lees lo pendiente y le dices, en español de "
            "México, breve y directo: «resumen» (2-3 frases: cómo va todo, siguiendo SU orden de prioridades), «atorado» "
            "(lo que lleva problema o espera algo de él, lo más importante primero, máx. 5) y «acciones» (máx. 4 cosas "
            "concretas que él puede hacer HOY, con el nombre del botón o la página: «▶ Continuar» en la Sala central, "
            "«🔄 Reinicio forzoso», revisar un video en Proyectos, etc.). Nada inventado: solo lo que viene en los datos.",
            texto, ESQ, tarea="director", que="informe del director de producción")
    except Exception as exc:  # noqa: BLE001 — sin plan ahorita: el informe espera
        return {**ultimo, "error": str(exc)[:200]}
    nuevo = {"t": time.time(), **r}
    e["informes"] = (e["informes"] + [nuevo])[-20:]
    _guardar(e)
    return nuevo


def iniciar(oficina) -> None:
    """Un informe cada 4 horas (si hay plan); lo demás (prioridades y enfoque) actúa al momento."""
    def ciclo():
        time.sleep(120)
        while True:
            try:
                if not oficina.demo:
                    informe(oficina)
            except Exception as exc:  # noqa: BLE001
                print(f"  · director: {exc}", flush=True)
            time.sleep(1800)
    threading.Thread(target=ciclo, daemon=True).start()
