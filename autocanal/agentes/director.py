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
    e.setdefault("autonomo", True)   # 🟢 luz verde: el director ejecuta sus órdenes él solo
    e.setdefault("ordenes", [])      # bitácora de lo que ordenó y ejecutó
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
    if "autonomo" in d:
        e["autonomo"] = bool(d["autonomo"])
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
    from . import canales  # noqa: F401
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
    try:  # 🕵️ la oficina nueva
        from . import quienmato
        r = quienmato.resumen()
        for c in r["casos"]:
            if c.get("hecho") or c.get("saltado"):
                continue
            err = next((x.get("error") for x in c["pasos"] if x["estado"] == "error"), None)
            p["expedientes"]["error" if err else "produccion"] += 1
            p["expedientes"]["detalle"].append(f"#{c.get('numero')} {c.get('marca')}: {err or c.get('paso')}"[:140])
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
ORDENES = {
    "continuar_todo": "▶ Continuar: reintentar todo lo que falló (sala, Quién mató, edificio)",
    "reinicio_forzoso": "🔄 Reinicio forzoso de la sala (suelta lo trabado y lo vuelve a mandar)",
    "reintentar_quienmato": "▶ Reintentar el paso que va en ¿Quién MATÓ a…?",
    "saltar_quienmato": "⏭ Saltar el caso de ¿Quién MATÓ a…? (solo si lleva más de 6 h atorado)",
    "prender_quienmato": "▶ Prender la oficina de ¿Quién MATÓ a…?",
    "piloto_on": "🚀 Prender el piloto automático del edificio",
    "pedir_ideas": "💡 Pedir ideas nuevas para un canal (canal: fraudes o apps; texto: tema opcional)",
}
ESQ = {"type": "object", "additionalProperties": False, "required": ["resumen", "atorado", "acciones", "ordenes"],
       "properties": {"resumen": {"type": "string"},
                      "atorado": {"type": "array", "items": {"type": "string"}},
                      "acciones": {"type": "array", "items": {"type": "string"}},
                      "ordenes": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                  "required": ["orden", "motivo", "canal", "texto"],
                                  "properties": {"orden": {"type": "string", "enum": list(ORDENES)}, "motivo": {"type": "string"},
                                                 "canal": {"type": "string"}, "texto": {"type": "string"}}}}}}


def _anotar(e: dict, texto: str, quien: str = "reglas") -> None:
    e["ordenes"] = (e["ordenes"] + [{"t": time.time(), "texto": texto[:300], "quien": quien}])[-80:]


def ejecutar(oficina, orden: str, motivo: str = "", canal: str = "", texto: str = "", quien: str = "cerebro") -> str:
    """Hace una orden de la lista segura. Regresa qué pasó (para la bitácora)."""
    from . import quienmato
    try:
        if orden == "continuar_todo":
            hecho = "; ".join(oficina.edicion_continuar().get("hechos") or [])
        elif orden == "reinicio_forzoso":
            hecho = "; ".join(oficina.edicion_reinicio().get("hechos") or [])
        elif orden == "reintentar_quienmato":
            quienmato.accion({"accion": "reintentar"})
            hecho = "reintenté el paso de ¿Quién MATÓ a…?"
        elif orden == "saltar_quienmato":
            c = quienmato.caso(quienmato._caso_actual() or "")
            if not c or time.time() - (c.get("mov") or time.time()) < 6 * 3600:
                return "no salté el caso: no lleva 6 h atorado"
            quienmato.accion({"accion": "saltar"})
            hecho = f"salté #{c.get('numero')} {c.get('marca')}"
        elif orden == "prender_quienmato":
            quienmato.accion({"accion": "prender"})
            hecho = "prendí ¿Quién MATÓ a…?"
        elif orden == "piloto_on":
            with oficina.lock:
                oficina.piloto = True
                oficina._tocar()
            hecho = "prendí el piloto automático"
        elif orden == "pedir_ideas":
            from . import canales
            cid = next((c["id"] for c in canales.lista() if c.get("nicho") == "fraudes"), "") if canal == "fraudes" else ""
            oficina.pedir_ideas(texto[:200], cid)
            hecho = f"pedí ideas{' para Cuida Tu Lana' if cid else ''}{f': {texto[:60]}' if texto else ''}"
        else:
            return "orden desconocida"
    except Exception as exc:  # noqa: BLE001
        hecho = f"no se pudo ({str(exc)[:120]})"
    e = estado()
    _anotar(e, f"{ORDENES.get(orden, orden).split(':')[0]} → {hecho}" + (f" · porque {motivo[:140]}" if motivo else ""), quien)
    _guardar(e)
    return hecho


def informe(oficina, forzar: bool = False) -> dict:
    e = estado()
    ultimo = (e["informes"] or [{}])[-1]
    if not forzar and time.time() - ultimo.get("t", 0) < 3 * 3600 - 300:
        return ultimo
    p = pendientes(oficina)
    orden = [f"{i + 1}. {CATEGORIAS[c]}" for i, c in enumerate(e["orden"])]
    texto = (f"PRIORIDADES DEL JEFE:\n" + "\n".join(orden) + f"\nENFOQUE: {CATEGORIAS.get(e['enfoque'], 'ninguno (todas)')}\n\n"
             f"PENDIENTES (por categoría):\n{json.dumps(p, ensure_ascii=False)[:6000]}\n\n"
             "NOTAS Y CORRECCIONES DEL JEFE (aprende de ellas):\n" + ("\n".join(f"- {n['texto']}" for n in e["notas"][-15:]) or "(ninguna)")
             + "\n\nINFORMES ANTERIORES (no repitas lo mismo si ya se resolvió):\n"
             + "\n".join(f"- {i.get('resumen', '')[:200]}" for i in e["informes"][-3:])
             + "\n\nÓRDENES RECIENTES (las tuyas y las automáticas):\n"
             + "\n".join(f"- hace {int((time.time() - o['t']) / 60)} min: {o['texto'][:160]}" for o in e["ordenes"][-10:]))
    try:
        r = claude.json_estructurado(
            "Eres el director de producción de Miguel (México): coordinas sus oficinas de video (canales de YouTube, "
            "TikTok Shop, Tampiqueando y la sala de edición con sus compus). Lees lo pendiente y le dices, en español de "
            "México, breve y directo: «resumen» (2-3 frases: cómo va todo, siguiendo SU orden de prioridades), «atorado» "
            "(lo que lleva problema o espera algo de él, lo más importante primero, máx. 5) y «acciones» (máx. 4 cosas "
            "concretas que él puede hacer HOY, con el nombre del botón o la página: «▶ Continuar» en la Sala central, "
            "«🔄 Reinicio forzoso», revisar un video en Proyectos, etc.). Nada inventado: solo lo que viene en los datos. "
            "TIENES LUZ VERDE para dar «ordenes» (de la lista) que se ejecutan solas: úsalas cuando de verdad destraben o "
            "adelanten trabajo siguiendo SUS prioridades (algo con error o quieto → continuar_todo; la sala trabada → "
            "reinicio_forzoso; un canal prioritario sin ideas ni videos en marcha → pedir_ideas con su canal). No repitas una "
            "orden que ya se dio hace menos de 1 h si no cambió nada (mira ÓRDENES RECIENTES). Si todo fluye, «ordenes» vacío.\n"
            "ÓRDENES DISPONIBLES:\n" + "\n".join(f"- {k}: {v}" for k, v in ORDENES.items()),
            texto, ESQ, tarea="director", que="informe del director de producción")
    except Exception as exc:  # noqa: BLE001 — sin plan ahorita: el informe espera
        return {**ultimo, "error": str(exc)[:200]}
    nuevo = {"t": time.time(), **{k: v for k, v in r.items() if k != "ordenes"}}
    e["informes"] = (e["informes"] + [nuevo])[-20:]
    _guardar(e)
    hechas = []
    if e.get("autonomo", True):  # 🟢 luz verde: el director ejecuta lo que ordenó
        for o in (r.get("ordenes") or [])[:4]:
            hechas.append(f"{ORDENES[o['orden']].split(':')[0]} → {ejecutar(oficina, o['orden'], o.get('motivo', ''), o.get('canal', ''), o.get('texto', ''))}")
    if hechas and hasattr(oficina, "avisar_jefe"):
        oficina.avisar_jefe("🎯 Director: " + " · ".join(hechas)[:600])
    nuevo["ordenes_hechas"] = hechas
    return nuevo


def reglas(oficina) -> list[str]:
    """Cada 10 min, sin gastar plan: lo obvio se destraba solo (con luz verde)."""
    from . import quienmato
    e = estado()
    if not e.get("autonomo", True):
        return []
    hechas = []

    def reciente(clave: str) -> bool:
        return any(clave in o["texto"] and time.time() - o["t"] < 3600 for o in e["ordenes"])
    cid = quienmato._caso_actual()  # ¿Quién MATÓ a…?: un paso agotó sus 3 intentos → otra ronda (máx. 1 por hora)
    if cid:
        c = quienmato.caso(cid)
        if any(p.get("estado") == "error" and (p.get("intentos") or 0) >= 3 for p in (c.get("pasos") or {}).values()) \
                and not reciente("Reintentar el paso"):
            hechas.append(ejecutar(oficina, "reintentar_quienmato", "un paso agotó sus 3 intentos", quien="reglas"))
    with oficina.lock:  # edificio: videos con error → continuar (máx. 1 por hora)
        errores = [p for p in oficina.proyectos.values() if p["estado"] == "error"]
    if errores and not reciente("Continuar"):
        hechas.append(ejecutar(oficina, "continuar_todo", f"{len(errores)} video(s) del edificio con error", quien="reglas"))
    return hechas


def iniciar(oficina) -> None:
    """Un informe cada 4 horas (si hay plan); lo demás (prioridades y enfoque) actúa al momento."""
    def ciclo():
        time.sleep(120)
        vueltas = 0
        while True:
            try:
                if not oficina.demo:
                    reglas(oficina)          # cada 10 min, gratis
                    if vueltas % 18 == 0:    # cada 3 h, el cerebro (Opus, tu plan)
                        informe(oficina)
            except Exception as exc:  # noqa: BLE001
                print(f"  · director: {exc}", flush=True)
            vueltas += 1
            time.sleep(600)
    threading.Thread(target=ciclo, daemon=True).start()
