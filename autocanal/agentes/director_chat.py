"""🎯 Platicar con el director (WhatsApp, Telegram o su página).

Con tu plan de Claude conectado, el director es un agente de verdad (Claude Code con Opus en el servidor): lee los
registros, los archivos de cada oficina y el código para diagnosticar cualquier falla, y luego ejecuta órdenes de su
lista segura (o se las pasa a Paola, que maneja todo el edificio de YouTube). No toca el código ni ve tus claves:
si encuentra un error del programa, te deja el diagnóstico listo para pasárselo a Claude Code.
Sin el plan, contesta con la foto del estado (sin herramientas).
"""
from __future__ import annotations

import json
import subprocess
import threading
import time

from . import claude, config, director

REPO = config.BASE.parent
_candado = threading.Lock()

ESQ_CHAT = {"type": "object", "additionalProperties": False, "required": ["respuesta", "ordenes", "recordar", "falla_codigo"],
            "properties": {
                "respuesta": {"type": "string", "description": "lo que le contestas a Miguel (corto, claro, en español de México)"},
                "ordenes": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                            "required": ["orden", "motivo", "canal", "texto"],
                            "properties": {"orden": {"type": "string", "enum": list(director.ORDENES)}, "motivo": {"type": "string"},
                                           "canal": {"type": "string"}, "texto": {"type": "string"}}}},
                "recordar": {"type": "array", "items": {"type": "string"},
                             "description": "lo que debes recordar para siempre de esta plática (preferencias, decisiones); vacío si nada"},
                "falla_codigo": {"type": "string", "description": "si es un error del programa: diagnóstico técnico (archivo, "
                                 "función, qué pasa y cómo arreglarlo) para que Miguel se lo pase a Claude Code; vacío si no"}}}

# 🔒 Lo que puede hacer el agente en el servidor: leer y diagnosticar, nunca editar ni ver claves.
HERRAMIENTAS = "Read,Grep,Glob,Bash"
PERMITIDAS = ["Read", "Grep", "Glob", "Bash(journalctl:*)", "Bash(systemctl status:*)", "Bash(df:*)", "Bash(free:*)",
              "Bash(uptime)", "Bash(nproc)", "Bash(ps aux)", "Bash(ffprobe:*)", "Bash(git log:*)", "Bash(git status)",
              "Bash(du:*)", "Bash(nvidia-smi)"]
PROHIBIDAS = ["Read(**/.env)", "Read(**/.env.*)", "Read(**/*token*)", "Read(**/*secret*)", "Read(**/*credencial*)",
              "Read(**/*password*)", "Read(**/.claude_casa/**)", "Read(**/llaves_ssh/**)", "Read(**/*.pem)", "Read(**/*.key)",
              "Edit", "Write", "NotebookEdit", "WebFetch", "WebSearch"]


def _foto(oficina) -> str:
    """Todo lo que el director necesita saber de un vistazo (va en su mensaje)."""
    from . import quienmato
    e = director.estado()
    partes = [f"HORA DEL SERVIDOR: {time.strftime('%Y-%m-%d %H:%M')}",
              "PRIORIDADES: " + " → ".join(director.CATEGORIAS[c] for c in e["orden"])
              + f" · ENFOQUE: {director.CATEGORIAS.get(e['enfoque'], 'ninguno')} · luz verde: {'sí' if e['autonomo'] else 'no'}"]
    try:
        partes.append("PENDIENTES POR OFICINA:\n" + json.dumps(director.pendientes(oficina), ensure_ascii=False)[:5000])
    except Exception as exc:  # noqa: BLE001
        partes.append(f"PENDIENTES: no los pude leer ({exc})")
    try:
        r = quienmato.resumen()
        actual = next((c for c in r["casos"] if c["id"] == r["actual"]), None)
        partes.append(f"¿QUIÉN MATÓ A…?: {'prendida' if r['activa'] else 'APAGADA'} · plan: {r.get('plan')} · azure: {r['azure']} · "
                      f"canal: {r['canal']} · temas en fila: {sum(1 for t in r['temas'] if t['estado'] == 'pendiente')}")
        if actual:
            partes.append(f"CASO ACTUAL #{actual['numero']} {actual['marca']} (carpeta salida/quienmato/{actual['id']}/), pasos: "
                          + "; ".join(f"{p['nombre']}={p['estado']}" + (f" (error: {p['error'][:160]})" if p.get("error") else "")
                                      for p in actual["pasos"])
                          + "\nBITÁCORA: " + " | ".join(str(x.get("texto", x))[:140] for x in actual["log"][-8:]))
    except Exception as exc:  # noqa: BLE001
        partes.append(f"¿QUIÉN MATÓ A…?: no lo pude leer ({exc})")
    try:
        s = oficina.edicion_central()
        partes.append("SALA DE EDICIÓN:\n" + json.dumps({k: s.get(k) for k in ("compus", "fila", "sala", "error") if k in s},
                                                        ensure_ascii=False)[:3000])
    except Exception as exc:  # noqa: BLE001
        partes.append(f"SALA: no la pude leer ({exc})")
    with oficina.lock:
        log = [f"{time.strftime('%d %H:%M', time.localtime(m['t']))} {m.get('quien')}: {str(m.get('texto'))[:160]}"
               for m in oficina.log[-25:]]
        errores = [f"{p.get('titulo') or p.get('tema')}: {str(p.get('error'))[:160]}" for p in oficina.proyectos.values()
                   if p.get("estado") == "error"][:8]
    partes.append("LO ÚLTIMO EN EL EDIFICIO (YouTube):\n" + "\n".join(log))
    if errores:
        partes.append("VIDEOS DEL EDIFICIO CON ERROR:\n" + "\n".join(errores))
    partes.append("TUS ÚLTIMAS ÓRDENES:\n" + "\n".join(f"- {o['texto'][:200]}" for o in e["ordenes"][-8:]))
    partes.append("TUS REVISIONES DE VIDEOS:\n" + "\n".join(
        f"- {r['titulo']}: {r.get('nota')} · {'; '.join(r.get('problemas') or [])[:200]}" for r in e["revisiones"][-5:]))
    return "\n\n".join(partes)


def _sistema() -> str:
    e = director.estado()
    memoria = "\n".join(f"- {m['texto']}" for m in e.get("memoria", [])[-40:]) or "(nada todavía)"
    notas = "\n".join(f"- {n['texto']}" for n in e["notas"][-15:]) or "(ninguna)"
    return (
        "Eres el DIRECTOR DE PRODUCCIÓN de los canales de Miguel (México): Cuida Tu Lana (fraudes), ¿Quién MATÓ a…? "
        "(expedientes de marcas que quebraron), Apps que sí pagan, sus videos personales, TikTok Shop y Tampiqueando. "
        "Eres el mejor productor y solucionador de problemas del mundo: Miguel te habla por WhatsApp o por tu página "
        "y espera que resuelvas TODO tú, como un ingeniero senior. Háblale en español de México, casual y directo "
        "(«jefe», «va»), corto (es WhatsApp), sin tecnicismos salvo que los pida.\n\n"
        "CÓMO TRABAJAS:\n"
        "1. Si pregunta algo o reporta una falla, INVESTIGA antes de contestar: lee los archivos de estado y registros "
        f"(el proyecto está en {REPO}: autocanal/oficina_estado.json, autocanal/director.json, autocanal/salida/quienmato/<caso>/caso.json, "
        "salaedicion/sala_estado.json, el código en autocanal/ y salaedicion/), usa `journalctl -u oficina -n 200 --no-pager` y "
        "`journalctl -u sala -n 200 --no-pager`, `df -h`, `free -h`. Encuentra la causa real; no adivines.\n"
        "2. Arréglalo con tus ÓRDENES (se ejecutan al final, en orden). La orden «paola» le pasa una instrucción a Paola, "
        "la productora del edificio de YouTube, que puede aprobar/rechazar ideas, publicar, reintentar, reeditar o rehacer "
        "videos, borrar de YouTube (solo si Miguel lo pidió explícito), prender el piloto, corregir a un agente, etc.\n"
        "3. Si es un error del PROGRAMA que no se arregla con órdenes: llena «falla_codigo» con el diagnóstico técnico "
        "completo (archivos, funciones, causa exacta y el arreglo propuesto). Si puedes programar (ver abajo), el arreglo "
        "lo haces tú en automático en una copia del código, se prueba solo y se instala en 1-2 min: díselo a Miguel así. "
        "Si no puedes, dile que se lo pase a Claude Code. Aquí no editas archivos: eso pasa en tu taller.\n"
        "4. Nunca reveles claves, tokens ni contraseñas, ni le pidas a Miguel que te las pegue: van en el .env del servidor.\n"
        "5. Nada inventado: si no lo verificaste, dilo. Cuida su plan de Claude y su dinero.\n"
        "6. En «recordar» guarda lo que debas saber para siempre (sus gustos, decisiones, reglas nuevas).\n\n"
        "ÓRDENES DISPONIBLES:\n" + "\n".join(f"- {k}: {v}" for k, v in director.ORDENES.items())
        + f"\n\nLO QUE YA SABES DE MIGUEL (tu memoria):\n{memoria}\n\nSUS NOTAS EN TU PÁGINA:\n{notas}"
        + "\n\n🛠️ TU TALLER: " + _taller_txt()
    )


def _taller_txt() -> str:
    from . import director_taller
    t = director.estado().get("taller") or {}
    base = ("PUEDES programar arreglos (token de GitHub y plan conectados)." if director_taller.listo() else
            "NO puedes programar todavía: falta conectar GitHub (Miguel corre en el servidor `oficina.py --configurar-github`).")
    return base + (f" Último arreglo: {t.get('estado')} · {t.get('resumen') or t.get('error') or ''}"[:400] if t else "")


def _platica() -> str:
    return "\n".join(f"{'MIGUEL' if m['quien'] == 'jefe' else 'TÚ'}: {m['texto'][:600]}" for m in director.estado().get("chat", [])[-12:])


def _env_ia() -> dict:
    from . import director_taller
    return director_taller._env_ia()  # sin ninguna clave de la oficina en su entorno


def avisar(oficina, texto: str) -> None:
    """El director te escribe solo (sin que le preguntes): en su chat y por donde platicaron la última vez."""
    e = director.estado()
    canal = next((m.get("canal") for m in reversed(e.get("chat", [])) if m.get("quien") == "jefe"), "")
    e["chat"] = (e.get("chat", []) + [{"t": time.time(), "quien": "director", "texto": texto}])[-80:]
    director._guardar(e)
    if canal in ("whatsapp", "telegram"):
        oficina._responder(canal, texto, director=True)


def _agente(sistema: str, mensaje: str) -> dict:
    """Claude Code con herramientas de solo lectura, en la carpeta del proyecto, con tu plan."""
    modelo = config.env("SUSCRIPCION_MODELO_DIRECTOR", "opus")
    p = subprocess.run(
        [claude.claude_cli(), "-p", "--output-format", "json", "--model", modelo, "--effort", "high",
         "--json-schema", json.dumps(ESQ_CHAT), "--system-prompt", sistema, "--max-turns", "40",
         "--tools", HERRAMIENTAS, "--allowedTools", *PERMITIDAS, "--disallowedTools", *PROHIBIDAS,
         "--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence", "--setting-sources", "", "--", mensaje],
        capture_output=True, text=True, cwd=str(REPO), env=_env_ia(), timeout=900)
    try:
        r = json.loads(p.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError) as exc:
        raise claude.ErrorIA(f"el director no contestó bien: {(p.stderr or p.stdout)[-200:]}") from exc
    if r.get("is_error") or not r.get("structured_output"):
        detalle = str(r.get("result") or r.get("subtype") or "")[-300:]
        if any(x in detalle.lower() for x in claude.LIMITE_PALABRAS):
            raise claude.ErrorIA("se acabó el límite de tu plan de Claude por ahora; vuelvo a estar al 100 en un rato")
        raise claude.ErrorIA(f"el director no terminó ({detalle[:160]})")
    return r["structured_output"]


def contestar(oficina, texto: str, canal: str = "pagina") -> dict:
    """Miguel le escribe al director. Investiga, ejecuta órdenes y contesta. Regresa {respuesta, hechos}."""
    e = director.estado()
    e.setdefault("chat", []).append({"t": time.time(), "quien": "jefe", "texto": texto[:2000], "canal": canal})
    e["pensando"] = time.time()
    director._guardar(e)
    mensaje = (f"MENSAJE DE MIGUEL (por {canal}): {texto}\n\nPLÁTICA RECIENTE:\n{_platica()}\n\n"
               f"FOTO DEL ESTADO AHORITA:\n{_foto(oficina)}")
    try:
        with _candado:  # uno a la vez: no se le cruzan dos investigaciones
            if not config.env("AUTOCANAL_DEMO") and claude.claude_cli() and claude.suscripcion_lista():
                r = _agente(_sistema(), mensaje)
                director._gaste()
            else:
                r = claude.json_estructurado(_sistema() + "\n\n(Ahora no tienes herramientas: contesta con la foto del estado.)",
                                             mensaje, ESQ_CHAT, tarea="director", que="chat con el director")
                director._gaste()
    except Exception as exc:  # noqa: BLE001
        r = {"respuesta": f"Uy jefe, no pude pensar bien ahorita: {str(exc)[:200]}", "ordenes": [], "recordar": [], "falla_codigo": ""}
    hechos = [director.ejecutar(oficina, o["orden"], o.get("motivo", ""), o.get("canal", ""), o.get("texto", ""), quien="chat")
              for o in r.get("ordenes") or []]
    e = director.estado()
    for m in r.get("recordar") or []:
        e.setdefault("memoria", []).append({"t": time.time(), "texto": m[:300]})
    e["memoria"] = e.get("memoria", [])[-80:]
    respuesta = r.get("respuesta") or "Listo."
    if hechos:
        respuesta += "\n\n✅ Hice:\n" + "\n".join(f"• {h[:200]}" for h in hechos)
    if r.get("falla_codigo"):
        from . import director_taller
        e.setdefault("fallas", []).append({"t": time.time(), "texto": r["falla_codigo"][:3000], "pedido": texto[:300]})
        e["fallas"] = e["fallas"][-20:]
        if director_taller.listo() and not director_taller.ocupado() and not any(o.get("orden") == "programar" for o in r.get("ordenes") or []):
            threading.Thread(target=director_taller.programar, args=(oficina, r["falla_codigo"], texto, lambda t: avisar(oficina, t)),
                             daemon=True).start()
            respuesta += "\n\n🛠️ Es un error del programa: ya me puse a programar el arreglo. Te aviso cuando quede instalado."
        elif not director_taller.listo():
            respuesta += ("\n\n🛠️ Es un error del programa. Te dejé el diagnóstico en mi página. Si conectas GitHub "
                          "(oficina.py --configurar-github), la próxima vez lo arreglo yo solo.")
    e["chat"] = (e.get("chat", []) + [{"t": time.time(), "quien": "director", "texto": respuesta}])[-80:]
    e["pensando"] = 0
    director._guardar(e)
    return {"respuesta": respuesta, "hechos": hechos}
