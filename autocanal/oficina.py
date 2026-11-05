"""Oficina de agentes: tu equipo trabajando en una oficina pixel art que ves en el navegador.

    python oficina.py          # usa las APIs reales (Claude, Play Store, WordPress, YouTube)
    python oficina.py --demo   # simulación sin APIs para ver cómo funciona

Abre http://localhost:8765
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import hmac
import json
import mimetypes
import random
import threading
import time
import uuid
import webbrowser
from zoneinfo import ZoneInfo
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import requests

from agentes import chat_jefe
from agentes import claude as ia
from agentes import whatsapp as wa
from agentes import config
from agentes import telegram as tg

WEB = config.BASE / "oficina"
ESTADO = config.BASE / "oficina_estado.json"
PASEO = 6.0  # segundos que tarda un agente en ir a otro escritorio, hablar y volver

# Acceso y automatización (ver .env.example)
USUARIO = config.env("OFICINA_USUARIO", "jefe")
PASSWORD = config.env("OFICINA_PASSWORD")
URL_PUBLICA = config.env("OFICINA_URL")
# importante = ideas, videos listos, publicados y problemas · todo = también cada entrega entre agentes
NIVEL_AVISOS = config.env("AVISOS_NIVEL") or config.env("WHATSAPP_NIVEL", "importante")
IDEAS_HORA = config.env("IDEAS_HORA")          # ej. 09:00 — vacío = no buscar solas
IDEAS_ZONA = config.env("IDEAS_ZONA", "America/Mexico_City")
IDEAS_GUIA = config.env("IDEAS_GUIA")
LIMPIAR_DIAS = int(config.env("LIMPIAR_DIAS", "30") or 30)

AGENTES = [
    # id, nombre, rol, color de ropa, peinado
    ("productora", "Paola", "Productora", "#e84d8a", "coleta"),
    ("investigador", "Iván", "Investigador", "#3b82f6", "lentes"),
    ("guionista", "Gabi", "Guionista", "#f59e0b", "rizos"),
    ("locutor", "Leo", "Locutor", "#8b5cf6", "audifonos"),
    ("disenadora", "Dani", "Diseñadora", "#10b981", "chongo"),
    ("editor", "Edu", "Editor de video", "#ef4444", "gorra"),
    ("redactora", "Rosa", "Redactora SEO", "#06b6d4", "largo"),
    ("community", "Carla", "Community manager", "#f97316", "bob"),
    ("jefe", "Tú", "Jefe", "#334155", "corto"),
]

ETAPA_AGENTE = {
    "investigar": "investigador", "guion": "guionista",
    "voz": "locutor", "miniatura": "disenadora", "video": "editor", "blog": "redactora",
    "publicar": "community",
}
ENTREGA = {  # qué se pasa al siguiente
    "investigador": "el expediente", "guionista": "el guion", "locutor": "la narración",
    "disenadora": "la miniatura", "editor": "el video", "redactora": "el post del blog",
    "community": "los enlaces", "productora": "el encargo",
}
FRASES = {
    "productora": ["Revisando tendencias en Play Store…", "Comparando descargas…", "Filtrando las que ya hicimos…"],
    "investigador": ["Leyendo reseñas de 1 estrella…", "Buscando en Reddit y Trustpilot…", "¿Quién es este desarrollador?",
                     "Revisando el pago mínimo…", "Armando el expediente…"],
    "guionista": ["Escribiendo el gancho…", "¿Cómo lo digo con humor?", "Ordenando las señales de alerta…", "Puliendo los títulos…"],
    "locutor": ["Mi mi mi mi… calentando la voz", "Grabando escena…", "Una más, con más energía"],
    "disenadora": ["Probando colores…", "Más grande el texto…", "Poniendo el sello"],
    "editor": ["Renderizando escenas…", "Sincronizando subtítulos…", "Mezclando la música…", "Exportando video…"],
    "redactora": ["Escribiendo para Google…", "Metiendo capturas en el post…", "Preguntas frecuentes…"],
    "community": ["Subiendo a YouTube…", "Publicando en el blog…", "Poniendo el video en el post…"],
}
ETAPAS_PROYECTO = ["investigar", "guion", "voz", "miniatura", "video", "blog", "revision", "publicar", "publicado"]
ACCION = {
    "ideas": "Buscar apps nuevas en Play Store", "investigar": "Investigar reseñas y evidencia",
    "guion": "Escribir el guion", "voz": "Narrar el guion", "miniatura": "Diseñar la miniatura",
    "video": "Editar el video", "blog": "Escribir el post del blog", "publicar": "Publicar en YouTube y el blog",
}
QUE_ES = {"investigar": "el expediente de Iván", "guion": "el guion de Gabi", "voz": "la narración de Leo"}
ACTIVAS = ("esperando", "en_cola", "trabajando")


class Oficina:
    def __init__(self, demo: bool):
        self.demo = demo
        self.lock = threading.RLock()
        self.cambio = threading.Condition(self.lock)
        self.version = 0
        self.agentes = {
            a: {"id": a, "nombre": n, "rol": r, "color": c, "pelo": p, "estado": "libre",
                "ubicacion": "casa", "dice": "", "dice_t": 0, "proyecto": None}
            for a, n, r, c, p in AGENTES
        }
        self.turnos = {a: threading.Lock() for a in self.agentes}
        datos = json.loads(ESTADO.read_text(encoding="utf-8")) if ESTADO.exists() else {}
        self.propuestas = datos.get("propuestas", [])
        self.proyectos = datos.get("proyectos", {})
        self.preferencias = datos.get("preferencias", [])
        self.log = datos.get("log", [])
        for i, p in enumerate(sorted([p for p in self.propuestas if p["estado"] == "pendiente"], key=lambda p: p["creado"]), 1):
            p.setdefault("num", i)
        self.tareas = datos.get("tareas", [])
        for p in self.proyectos.values():  # lo que quedó a medias al cerrar
            if p["estado"] in ("produccion", "publicando"):
                p["estado"], p["error"] = "error", "Se interrumpió al cerrar la oficina."
        for t in self.tareas:
            if t["estado"] in ACTIVAS:
                t["estado"], t["error"] = "cancelada", "Se interrumpió al cerrar la oficina."
        self.ultima_busqueda = datos.get("ultima_busqueda", "")
        self.gasto = datos.get("gasto", {})  # USD por día (AAAA-MM-DD)
        ia.al_gastar = self._gasto
        self.wa = datos.get("whatsapp", {"ultimo_entrante": 0, "numero": "", "vistos": []})
        self.chat_cola: list[tuple[float, str, bool, bool]] = []  # (cuándo, línea, importante, con botones)
        self.chat_lock = threading.Lock()
        self.tg_vistos: list[str] = []
        if wa.activo() or tg.activo():
            threading.Thread(target=self._chat_despachar, daemon=True).start()
        if tg.activo():
            threading.Thread(target=tg.escuchar, args=(self.recibir_telegram,), daemon=True).start()
        threading.Thread(target=self._ambiente, daemon=True).start()
        threading.Thread(target=self._agenda, daemon=True).start()

    # ---------- estado ----------
    def _tocar(self) -> None:
        with self.cambio:
            self.version += 1
            self.cambio.notify_all()
            ESTADO.write_text(json.dumps({
                "propuestas": self.propuestas[-200:], "proyectos": self.proyectos,
                "preferencias": self.preferencias[-30:], "log": self.log[-300:],
                "ultima_busqueda": self.ultima_busqueda, "tareas": self.tareas[-300:],
                "gasto": dict(sorted(self.gasto.items())[-120:]),
                "whatsapp": {**self.wa, "vistos": self.wa.get("vistos", [])[-200:]},
            }, ensure_ascii=False, indent=1), encoding="utf-8")

    def snapshot(self) -> dict:
        with self.lock:
            return {"version": self.version, "demo": self.demo, "agentes": list(self.agentes.values()),
                    "propuestas": [p for p in self.propuestas if p["estado"] == "pendiente"],
                    "proyectos": sorted(self.proyectos.values(), key=lambda p: -p["creado"]),
                    "preferencias": self.preferencias[-10:], "log": self.log[-60:],
                    "etapas": ETAPAS_PROYECTO, "ahora": time.time(), "gasto": self._resumen_gasto(),
                    "tareas": [t for t in self.tareas[-250:] if t["estado"] in ACTIVAS]
                              + [t for t in self.tareas[-250:] if t["estado"] not in ACTIVAS][-120:]}

    def decir(self, agente: str, texto: str, al_log: bool = True) -> None:
        with self.lock:
            a = self.agentes[agente]
            a["dice"], a["dice_t"] = texto, time.time()
            if al_log:
                self.log.append({"t": time.time(), "quien": agente, "texto": texto})
            self._tocar()
        if al_log and NIVEL_AVISOS == "todo" and agente != "jefe":
            self.avisar_chat(agente, texto)

    def poner(self, agente: str, **campos) -> None:
        with self.lock:
            self.agentes[agente].update(campos)
            self._tocar()

    # ---------- chat con el jefe (WhatsApp y Telegram) ----------
    EMOJI = {"productora": "📋", "investigador": "🔎", "guionista": "✍️", "locutor": "🎙️", "disenadora": "🎨",
             "editor": "🎬", "redactora": "📝", "community": "📤"}

    def avisar_chat(self, agente: str, texto: str, importante: bool = False, botones: bool = False) -> None:
        """Pone un aviso en la cola; se juntan varios en un solo mensaje (en WhatsApp cada mensaje cuesta)."""
        if not (wa.activo() or tg.activo()):
            return
        a = self.agentes.get(agente, {})
        linea = f"{self.EMOJI.get(agente, '💬')} *{a.get('nombre', agente)}*: {texto}"
        with self.chat_lock:
            if any(texto in l for _, l, _, _ in self.chat_cola):
                return
            self.chat_cola.append((time.time(), linea, importante, botones))

    def _chat_despachar(self) -> None:
        while True:
            time.sleep(3)
            with self.chat_lock:
                if not self.chat_cola:
                    continue
                primero = self.chat_cola[0][0]
                urgente = any(imp for _, _, imp, _ in self.chat_cola)
                if time.time() - primero < (6 if urgente else 60):
                    continue
                lineas = [l for _, l, _, _ in self.chat_cola]
                con_botones = any(b for _, _, _, b in self.chat_cola)
                self.chat_cola.clear()
            texto = "\n\n".join(lineas)
            if URL_PUBLICA:
                texto += f"\n\n👉 {URL_PUBLICA}"
            if wa.activo():
                self._wa_enviar(texto)
            if tg.activo():
                self._tg_enviar(texto, tg.botones_ideas(self._pendientes()) if con_botones else None)

    def _tg_enviar(self, texto: str, botones=None, teclado: bool = False) -> None:
        try:
            tg.enviar(texto, botones=botones, teclado=teclado)
        except Exception as exc:  # noqa: BLE001
            print(f"aviso: Telegram: {exc}", flush=True)
            with self.lock:
                self.log.append({"t": time.time(), "quien": "productora", "texto": f"⚠️ No pude mandarte Telegram: {exc}"})
                self._tocar()

    def _responder(self, canal: str, texto: str, botones=None, teclado: bool = False) -> None:
        if canal == "telegram":
            self._tg_enviar(texto, botones, teclado)
        else:
            self._wa_enviar(texto)

    def _wa_enviar(self, texto: str) -> None:
        para = self.wa.get("numero") or wa.JEFE
        try:
            if time.time() - self.wa.get("ultimo_entrante", 0) < 23.5 * 3600:
                wa.enviar_texto(para, texto)
            else:  # fuera de la ventana de 24 h, WhatsApp solo deja mandar una plantilla aprobada
                wa.enviar_plantilla(para, texto)
        except Exception as exc:  # noqa: BLE001
            print(f"aviso: WhatsApp: {exc}", flush=True)
            with self.lock:
                self.log.append({"t": time.time(), "quien": "productora", "texto": f"⚠️ No pude mandarte WhatsApp: {exc}"})
                self._tocar()

    def _pendientes(self) -> list[dict]:
        return sorted([p for p in self.propuestas if p["estado"] == "pendiente"], key=lambda p: p["creado"])

    def _lista_ideas(self) -> str:
        ideas = self._pendientes()
        if not ideas:
            return "No hay ideas pendientes."
        return "\n".join(f"*{p.get('num', i)}.* {p['titulo']} — {p.get('angulo', '')}" for i, p in enumerate(ideas[:12], 1))

    def _resumen_estado(self) -> str:
        lineas = []
        with self.lock:
            activos = [p for p in self.proyectos.values() if p["estado"] in ("produccion", "publicando")]
            for p in activos:
                trabajando = [t for t in self.tareas if t["proyecto"] == p["id"] and t["estado"] == "trabajando"]
                quien = ", ".join(f"{self.agentes[t['agente']]['nombre']} ({t['accion'].lower()})" for t in trabajando)
                lineas.append(f"🎞️ *{p['titulo']}*: {quien or 'pasando de un escritorio a otro'}")
            revision = [p["titulo"] for p in self.proyectos.values() if p["estado"] == "revision"]
            errores = [p["titulo"] for p in self.proyectos.values() if p["estado"] == "error"]
            ideas = len(self._pendientes())
            gasto = self._resumen_gasto()
        if not lineas:
            lineas.append("Nadie está produciendo ahorita ☕")
        if revision:
            lineas.append("👀 Esperan tu revisión: " + ", ".join(revision))
        if errores:
            lineas.append("⚠️ Con problema: " + ", ".join(errores))
        if ideas:
            lineas.append(f"💡 {ideas} ideas esperan tu opinión (escribe *pendientes*)")
        lineas.append(f"💰 Hoy van ${gasto['hoy']:.2f} · mes ${gasto['mes']:.2f}")
        return "\n".join(lineas)

    def recibir_whatsapp(self, mensaje: dict) -> None:
        """Un mensaje tuyo por WhatsApp."""
        with self.lock:
            if mensaje["id"] in self.wa.setdefault("vistos", []):
                return  # Meta a veces reenvía el mismo aviso
            self.wa["vistos"] = (self.wa["vistos"] + [mensaje["id"]])[-200:]
            if not wa.es_el_jefe(mensaje["de"]):
                return
            self.wa["ultimo_entrante"], self.wa["numero"] = time.time(), mensaje["de"]
            self._tocar()
        self._atender("whatsapp", mensaje)

    def recibir_telegram(self, mensaje: dict) -> None:
        """Un mensaje (o botón) tuyo por Telegram. tg.escuchar ya filtró que seas tú."""
        with self.lock:
            if mensaje["id"] in self.tg_vistos:
                return
            self.tg_vistos = (self.tg_vistos + [mensaje["id"]])[-200:]
        self._atender("telegram", mensaje)

    BOTONES_FIJOS = {"💡 pendientes": "pendientes", "📊 ¿cómo van?": "¿cómo van?", "🔍 buscar ideas": "ideas",
                     "❓ ayuda": "ayuda", "/start": "ayuda", "/ayuda": "ayuda", "/help": "ayuda",
                     "/pendientes": "pendientes", "/estado": "estado", "/ideas": "ideas"}

    def _atender(self, canal: str, mensaje: dict) -> None:
        """Lo que escribes por chat: se entiende (comandos o Haiku) y se ejecuta."""
        icono = "✈️" if canal == "telegram" else "📱"
        with self.lock:
            self.log.append({"t": time.time(), "quien": "jefe", "texto": f"{icono} {mensaje['texto'] or '(' + str(mensaje['tipo']) + ')'}"})
            self._tocar()
        if not mensaje["texto"]:
            return self._responder(canal, "Por ahora solo entiendo mensajes de texto 🙂")
        texto_jefe = self.BOTONES_FIJOS.get(mensaje["texto"].strip().lower(), mensaje["texto"])
        if texto_jefe == "ayuda":
            return self._responder(canal, chat_jefe.AYUDA, teclado=True)
        ideas = self._pendientes()
        ia.contexto.proyecto, ia.contexto.etapa, ia.contexto.tarea = None, "whatsapp", None
        try:
            plan = chat_jefe.interpretar(texto_jefe, ideas, sorted(self.proyectos.values(), key=lambda p: -p["creado"]))
        except Exception as exc:  # noqa: BLE001
            return self._responder(canal, f"No te entendí bien ({exc}). Escribe *ayuda* para ver qué puedo hacer.")
        partes = [plan["respuesta"]] if plan.get("respuesta") else []
        for acc in plan.get("acciones", []):
            tipo, n, texto = acc["tipo"], acc.get("numero", 0), acc.get("texto", "")
            idea = next((p for p in ideas if p.get("num") == n), None)
            if tipo in ("aprobar", "rechazar", "comentar"):
                if not idea:
                    partes.append(f"No encontré la idea {n}. Escribe *pendientes* para ver la lista.")
                    continue
                if tipo == "comentar" and not texto:
                    continue
                r = self.responder_idea(idea["id"], tipo, texto)
                verbo = {"aprobar": "✅ Arrancamos con", "rechazar": "🗑️ Descartada:", "comentar": "💬 Anotado sobre"}[tipo]
                partes.append(f"{verbo} *{idea['titulo']}*" if "error" not in r else f"{idea['titulo']}: {r['error']}")
            elif tipo == "pedir_ideas":
                self.pedir_ideas(texto)
                partes.append("🔍 Voy a buscar ideas" + (f" de {texto}" if texto else "") + ". Te escribo cuando las tenga.")
            elif tipo == "estado":
                partes.append(self._resumen_estado())
            elif tipo == "pendientes":
                revision = [p["titulo"] for p in self.proyectos.values() if p["estado"] == "revision"]
                partes.append("💡 *Ideas:*\n" + self._lista_ideas()
                              + ("\n\n👀 *Para revisar en la oficina:* " + ", ".join(revision) if revision else ""))
        texto = "\n\n".join(x for x in partes if x) or "👍"
        pidio_lista = any(a["tipo"] == "pendientes" for a in plan.get("acciones", []))
        if pidio_lista and URL_PUBLICA:
            texto += f"\n\n👉 {URL_PUBLICA}"
        botones = tg.botones_ideas(self._pendientes()) if canal == "telegram" and pidio_lista and self._pendientes() else None
        self._responder(canal, texto, botones)

    def _hoy(self) -> str:
        return dt.datetime.now(ZoneInfo(IDEAS_ZONA)).date().isoformat()

    def _gasto(self, proyecto, etapa, modelo, usd, entrada, salida) -> None:
        """Lo llama agentes/claude.py después de cada llamada: suma al video, a la tarea y al día."""
        with self.lock:
            dia = self._hoy()
            self.gasto[dia] = self.gasto.get(dia, 0) + usd
            t = getattr(ia.contexto, "tarea", None)
            if t is not None:
                t["costo"] = t.get("costo", 0) + usd
                t["modelo"] = modelo
            p = self.proyectos.get(proyecto) if proyecto else None
            if p is not None:
                p["costo"] = p.get("costo", 0) + usd
                costos = p.setdefault("costos", {})
                costos[etapa or "otro"] = costos.get(etapa or "otro", 0) + usd
            self._tocar()

    def _resumen_gasto(self) -> dict:
        hoy = self._hoy()
        mes = hoy[:7]
        return {"hoy": round(self.gasto.get(hoy, 0), 4),
                "mes": round(sum(v for k, v in self.gasto.items() if k.startswith(mes)), 4)}

    def nueva_tarea(self, agente: str, etapa: str, proyecto: str | None = None, titulo: str = "") -> dict:
        t = {"id": uuid.uuid4().hex[:8], "agente": agente, "etapa": etapa, "accion": ACCION.get(etapa, etapa),
             "proyecto": proyecto, "titulo": titulo, "estado": "esperando", "espera": "",
             "creado": time.time(), "inicio": None, "fin": None, "error": None}
        with self.lock:
            self.tareas.append(t)
            self._tocar()
        return t

    def tarea(self, t: dict, **campos) -> None:
        with self.lock:
            t.update(campos)
            self._tocar()

    def _ambiente(self) -> None:
        """Mientras trabajan, los agentes comentan lo que hacen (sin llenar el chat)."""
        while True:
            time.sleep(7)
            with self.lock:
                for a in self.agentes.values():
                    if a["estado"] == "trabajando" and a["ubicacion"] == "casa" and a["id"] in FRASES:
                        a["dice"], a["dice_t"] = random.choice(FRASES[a["id"]]), time.time()
                self._tocar()

    def _agenda(self) -> None:
        """Cada minuto: ¿toca la búsqueda diaria de ideas? Cada hora: limpiar videos viejos."""
        ultima_limpieza = 0.0
        while True:
            time.sleep(60)
            try:
                if IDEAS_HORA:
                    ahora = dt.datetime.now(ZoneInfo(IDEAS_ZONA))
                    hoy = ahora.date().isoformat()
                    hh, _, mm = IDEAS_HORA.partition(":")
                    if (ahora.hour, ahora.minute) >= (int(hh), int(mm or 0)) and self.ultima_busqueda != hoy:
                        self.ultima_busqueda = hoy
                        self._tocar()
                        self.pedir_ideas(IDEAS_GUIA)
                if time.time() - ultima_limpieza > 3600:
                    ultima_limpieza = time.time()
                    self.limpiar()
            except Exception as exc:  # noqa: BLE001 — la agenda nunca debe morir
                print(f"aviso: agenda: {exc}")

    def limpiar(self) -> None:
        """Borra el video de los proyectos publicados hace más de LIMPIAR_DIAS (ya está en YouTube).
        Se conservan miniatura, guion, expediente y blog, que pesan poco."""
        limite = time.time() - LIMPIAR_DIAS * 86400
        for p in list(self.proyectos.values()):
            if p["estado"] == "publicado" and p.get("publicado_t", time.time()) < limite and not p.get("video_borrado"):
                carpeta = config.SALIDA / p["id"]
                for nombre in ("video.mp4", "subtitulos.srt"):
                    (carpeta / nombre).unlink(missing_ok=True)
                for sub in ("edicion", "audio"):
                    for f in (carpeta / sub).glob("*") if (carpeta / sub).exists() else []:
                        f.unlink(missing_ok=True)
                with self.lock:
                    p["video_borrado"] = True
                    self._tocar()

    def visitar(self, quien: str, a_quien: str, texto: str) -> None:
        """`quien` camina al escritorio de `a_quien`, le dice algo y regresa."""
        self.recorrido(quien, [(a_quien, texto)])

    def recorrido(self, quien: str, paradas: list, al_llegar=None) -> None:
        """Camina a varios escritorios, entrega algo en cada uno y regresa al suyo.
        `al_llegar(i)` se llama al llegar a la parada i (para que el otro empiece en ese momento)."""
        for i, (a_quien, texto) in enumerate(paradas):
            self.poner(quien, ubicacion=f"visita:{a_quien}")
            time.sleep(PASEO * 0.5)
            self.decir(quien, texto)
            if al_llegar:
                al_llegar(i)
            time.sleep(1.5)
        self.poner(quien, ubicacion="casa")
        time.sleep(PASEO * 0.4)

    def avisar_jefe(self, texto: str, extra_whatsapp: str = "", botones: bool = False) -> None:
        self.avisar_chat("productora", texto + (f"\n{extra_whatsapp}" if extra_whatsapp else ""), importante=True, botones=botones)
        self.visitar("productora", "jefe", texto)

    # ---------- ideas ----------
    def pedir_ideas(self, guia: str = "") -> None:
        threading.Thread(target=self._ideas, args=(guia,), daemon=True).start()

    def _ideas(self, guia: str) -> None:
        from agentes import buscador

        if guia:
            with self.lock:
                self.preferencias.append(f"Pidió: {guia}")
        t = self.nueva_tarea("productora", "ideas", titulo=guia or "Búsqueda general")
        ia.contexto.proyecto, ia.contexto.etapa, ia.contexto.tarea = None, "ideas", t
        self.tarea(t, estado="trabajando", inicio=time.time())
        self.poner("productora", estado="trabajando")
        self.decir("productora", "¡Voy! Busco apps nuevas en Play Store" + (f" ({guia})" if guia else ""))
        try:
            gustos = "\n".join(f"- {p}" for p in self.preferencias[-15:])
            candidatas = buscador.ideas(5, gustos)
        except Exception as exc:  # noqa: BLE001
            self.tarea(t, estado="fallo", fin=time.time(), error=str(exc)[:300])
            self.poner("productora", estado="libre")
            self.decir("productora", f"Uy, no pude buscar ideas: {exc}")
            return
        with self.lock:
            # no repetir apps que ya están en la bandeja o que ya son proyecto
            ya = {p["app_id"] for p in self.propuestas if p["estado"] == "pendiente"} | set(self.proyectos)
            nuevas = []
            for c in candidatas:
                if c["app_id"] in ya:
                    continue
                ya.add(c["app_id"])
                nuevas.append(c)
                pendientes = [p.get("num", 0) for p in self.propuestas if p["estado"] == "pendiente"]
                self.propuestas.append({**c, "id": uuid.uuid4().hex[:8], "estado": "pendiente",
                                        "creado": time.time(), "comentarios": [],
                                        "num": max(pendientes, default=0) + 1})
        self.tarea(t, estado="hecha", fin=time.time(), resultado=f"{len(nuevas)} ideas nuevas")
        self.poner("productora", estado="libre")
        if nuevas:
            self.avisar_jefe(f"¡Jefe! Te traje {len(nuevas)} ideas. ¿Qué opinas? Están en tu bandeja.",
                             extra_whatsapp=self._lista_ideas() + "\n\nContéstame *sí 1*, *no 2 (motivo)* u *opino 3 ...*",
                             botones=True)
        else:
            self.decir("productora", "Jefe, no encontré apps nuevas; las que vi ya están en tu bandeja.")

    def descartar_ideas(self) -> dict:
        """Limpia la bandeja de ideas sin contarlo como 'no me gustó' (no afecta lo que Paola aprende)."""
        with self.lock:
            n = 0
            for p in self.propuestas:
                if p["estado"] == "pendiente":
                    p["estado"], n = "descartada", n + 1
            self.log.append({"t": time.time(), "quien": "jefe", "texto": f"🧹 Limpió la bandeja ({n} ideas)"})
            self._tocar()
        threading.Thread(target=self.decir, args=("productora", "Listo jefe, bandeja limpia."), daemon=True).start()
        return {"ok": True, "descartadas": n}

    def responder_idea(self, pid: str, accion: str, texto: str = "") -> dict:
        with self.lock:
            p = next((x for x in self.propuestas if x["id"] == pid), None)
            if not p or p["estado"] != "pendiente":
                return {"error": "Esa idea ya no está pendiente."}
            self.log.append({"t": time.time(), "quien": "jefe", "texto": (
                {"aprobar": "👍 ", "rechazar": "👎 ", "comentar": "💬 "}[accion] + p["titulo"] + (f": {texto}" if texto else ""))})
            if accion == "comentar":
                p["comentarios"].append(texto)
                self.preferencias.append(f"Sobre '{p['titulo']}': {texto}")
                self._tocar()
                threading.Thread(target=self.decir, args=("productora", "Anotado, jefe. Lo tomo en cuenta."), daemon=True).start()
                return {"ok": True}
            p["estado"] = "aprobada" if accion == "aprobar" else "rechazada"
            if accion == "rechazar":
                self.preferencias.append(f"No le gustó '{p['titulo']}'" + (f": {texto}" if texto else ""))
            self._tocar()
        if accion == "aprobar":
            self.iniciar_proyecto(p, notas="\n".join(p["comentarios"]))
        else:
            threading.Thread(target=self.decir, args=(
                "productora", "Entendido, la descarto." + (" Ya aprendí qué no te gusta." if texto else "")), daemon=True).start()
        return {"ok": True}

    # ---------- proyectos ----------
    def iniciar_proyecto(self, propuesta: dict, notas: str = "") -> None:
        app_id = propuesta["app_id"]
        with self.lock:
            self.proyectos[app_id] = {"id": app_id, "titulo": propuesta["titulo"], "angulo": propuesta.get("angulo", ""),
                                      "estado": "produccion", "etapa": "investigar", "etapas": {},
                                      "creado": time.time(), "error": None, "notas": notas, "publicado": None}
            self._tocar()
        threading.Thread(target=self._producir, args=(app_id, notas, None, set()), daemon=True).start()

    def _marcar(self, app_id: str, etapa: str, estado: str) -> None:
        with self.lock:
            p = self.proyectos[app_id]
            p.setdefault("etapas", {})[etapa] = estado
            if estado == "trabajando":
                p["etapa"] = etapa
            self._tocar()

    def _producir(self, app_id: str, notas: str, desde: str | None, saltar: set) -> None:
        """Reparte el video entre el equipo. Cada etapa arranca en cuanto tiene lo que necesita,
        así que varias corren al mismo tiempo (ver canal.DEPENDE)."""
        import canal

        titulo = self.proyectos[app_id]["titulo"]
        try:
            prod = canal.Produccion(app_id, con_web=True, desde=desde, notas=notas)
            if desde:
                saltar = set(canal.DEPENDE) - prod.rehacer
            for e in canal.ETAPAS:  # lo que ya está hecho solo se carga (el orden respeta dependencias)
                if e in saltar:
                    prod.cargar(e)
        except Exception as exc:  # noqa: BLE001
            return self._fallo_proyecto(app_id, "productora", exc)

        etapas = [e for e in canal.ETAPAS if e not in saltar]
        listas = {e: threading.Event() for e in canal.DEPENDE}
        for e in saltar:
            listas[e].set()
            self._marcar(app_id, e, "hecha")
        fallo: dict = {}
        tareas = {e: self.nueva_tarea(ETAPA_AGENTE[e], e, app_id, titulo) for e in etapas}
        for e in etapas:
            self._marcar(app_id, e, "esperando")

        self.decir("productora", f"¡Perfecto! Arrancamos con {titulo}")
        primeras = [e for e in etapas if all(d in saltar for d in canal.DEPENDE[e])]
        for e in primeras:
            self.tarea(tareas[e], espera="Paola le está trayendo el encargo")
        encargos = []
        for e in primeras:
            ag = ETAPA_AGENTE[e]
            encargos.append((ag, f"{self.agentes[ag]['nombre']}, te toca: {ACCION[e].lower()} de {titulo}"))
        self.recorrido("productora", encargos)

        hilos = [threading.Thread(target=self._trabajar, args=(prod, e, tareas[e], listas, fallo), daemon=True)
                 for e in etapas]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()
        if fallo:
            return self._fallo_proyecto(app_id, fallo["agente"], fallo["exc"])
        try:
            prod.cerrar()
        except Exception as exc:  # noqa: BLE001
            return self._fallo_proyecto(app_id, "productora", exc)
        with self.lock:
            p = self.proyectos[app_id]
            p["estado"], p["etapa"] = "revision", "revision"
            self._tocar()
        self.avisar_jefe(f"¡Jefe! El video de {titulo} está listo. ¿Lo revisas?")

    def _trabajar(self, prod, etapa: str, t: dict, listas: dict, fallo: dict) -> None:
        """Una etapa: esperar lo que necesita, esperar turno del agente, trabajar y entregar."""
        import canal

        agente, app_id = t["agente"], t["proyecto"]
        nombre = self.agentes[agente]["nombre"]
        try:
            deps = canal.DEPENDE[etapa]
            if any(not listas[d].is_set() for d in deps):
                self.tarea(t, espera="Espera " + " y ".join(QUE_ES.get(d, d) for d in deps))
            for d in deps:
                listas[d].wait()
            if fallo:
                self.tarea(t, estado="cancelada", espera="", fin=time.time())
                self._marcar(app_id, etapa, "cancelada")
                listas[etapa].set()  # que las que dependen de esta también se enteren
                return
            turno = self.turnos[agente]
            self.tarea(t, estado="en_cola", espera="")
            if not turno.acquire(blocking=False):
                self.tarea(t, espera=f"{nombre} termina otra tarea primero")
                self.decir(agente, f"Termino lo que tengo y sigo con {t['titulo']}", al_log=False)
                turno.acquire()
        except Exception as exc:  # noqa: BLE001
            fallo.setdefault("exc", exc)
            fallo.setdefault("agente", agente)
            listas[etapa].set()
            return
        try:
            self.tarea(t, estado="trabajando", inicio=time.time(), espera="")
            self._marcar(app_id, etapa, "trabajando")
            self.poner(agente, estado="trabajando", proyecto=app_id)
            self.decir(agente, random.choice(FRASES[agente]), al_log=False)
            ia.contexto.proyecto, ia.contexto.etapa, ia.contexto.tarea = app_id, etapa, t
            try:
                prod.etapa(etapa)
            except Exception as exc:  # noqa: BLE001
                fallo.setdefault("exc", exc)
                fallo.setdefault("agente", agente)
                self.tarea(t, estado="fallo", fin=time.time(), error=str(exc)[:300])
                self._marcar(app_id, etapa, "fallo")
                self.poner(agente, estado="libre", proyecto=None)
                self.decir(agente, f"¡Ups! Algo falló: {str(exc)[:120]}")
                return
            self.tarea(t, estado="hecha", fin=time.time())
            self._marcar(app_id, etapa, "hecha")
            self.poner(agente, estado="libre", proyecto=None)
            # entregar: a quienes siguen (todos a la vez apenas llega con el primero) o a Paola si es lo último
            siguientes = sorted({ETAPA_AGENTE[e] for e, deps in canal.DEPENDE.items() if etapa in deps})
            if siguientes:
                paradas = [(s, f"{self.agentes[s]['nombre']}, te dejo {ENTREGA[agente]} de {t['titulo']}") for s in siguientes]
            else:
                paradas = [("productora", f"Paola, listo {ENTREGA[agente]} de {t['titulo']} ✔")]
            self.recorrido(agente, paradas, al_llegar=lambda i: listas[etapa].set())
        finally:
            listas[etapa].set()
            self.turnos[agente].release()

    def _fallo_proyecto(self, app_id: str, quien: str, exc: Exception) -> None:
        with self.lock:
            p = self.proyectos[app_id]
            p["estado"], p["error"] = "error", str(exc)[:400]
            self._tocar()
        self.decir(quien, f"¡Ups! Algo falló con {p['titulo']}: {str(exc)[:120]}")
        self.avisar_jefe(f"Jefe, {p['titulo']} tuvo un problema. Está en tu bandeja.")

    def accion_proyecto(self, app_id: str, accion: str, texto: str = "", titulo_n: int = 1) -> dict:
        with self.lock:
            p = self.proyectos.get(app_id)
            if not p:
                return {"error": "No existe ese proyecto."}
            if accion == "publicar" and p["estado"] == "revision":
                p["estado"], p["etapa"] = "publicando", "publicar"
                self.log.append({"t": time.time(), "quien": "jefe", "texto": f"✅ Aprobado para publicar: {p['titulo']}"})
                self._tocar()
                threading.Thread(target=self._publicar, args=(app_id, titulo_n), daemon=True).start()
            elif accion == "cambios" and p["estado"] in ("revision", "error"):
                p["estado"], p["etapa"], p["error"] = "produccion", "guion", None
                p["notas"] = (p.get("notas", "") + "\n" + texto).strip()
                self.log.append({"t": time.time(), "quien": "jefe", "texto": f"✏️ Cambios a {p['titulo']}: {texto}"})
                self.preferencias.append(f"En un guion pidió: {texto}")
                self._tocar()
                threading.Thread(target=self._producir, args=(app_id, p["notas"], "guion", set()), daemon=True).start()
            elif accion == "reintentar" and p["estado"] == "error":
                hechas = {e for e, est in (p.get("etapas") or {}).items() if est == "hecha"}
                p["estado"], p["error"] = "produccion", None
                self._tocar()
                threading.Thread(target=self._producir, args=(app_id, p.get("notas", ""), None, hechas), daemon=True).start()
            elif accion == "descartar" and p["estado"] in ("revision", "error"):
                p["estado"] = "descartado"
                self.log.append({"t": time.time(), "quien": "jefe", "texto": f"🗑️ Descartado: {p['titulo']}"})
                self._tocar()
            else:
                return {"error": "Esa acción no se puede hacer ahora."}
        return {"ok": True}

    def _publicar(self, app_id: str, titulo_n: int) -> None:
        import canal

        titulo = self.proyectos[app_id]["titulo"]
        t = self.nueva_tarea("community", "publicar", app_id, titulo)
        self.visitar("productora", "community", f"Carla, el jefe aprobó {titulo}. ¡A publicar!")
        with self.turnos["community"]:
            self.tarea(t, estado="trabajando", inicio=time.time())
            self.poner("community", estado="trabajando", proyecto=app_id)
            self.decir("community", random.choice(FRASES["community"]), al_log=False)
            try:
                pub = canal.publicar(app_id, titulo_n)
            except Exception as exc:  # noqa: BLE001
                self.tarea(t, estado="fallo", fin=time.time(), error=str(exc)[:300])
                self.poner("community", estado="libre", proyecto=None)
                return self._fallo_proyecto(app_id, "community", exc)
            self.tarea(t, estado="hecha", fin=time.time())
            self.poner("community", estado="libre", proyecto=None)
            self.visitar("community", "productora", f"Paola, ya está publicado {titulo} ✔")
        with self.lock:
            p = self.proyectos[app_id]
            p["estado"], p["etapa"], p["publicado"] = "publicado", "publicado", pub
            p["publicado_t"] = time.time()
            self._tocar()
        self.avisar_jefe(f"¡Publicado! {titulo} ya está en YouTube y en el blog 🎉")

    def detalle(self, app_id: str) -> dict:
        carpeta = config.SALIDA / app_id

        def leer(n):
            f = carpeta / n
            return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None

        exp, guion, blog = leer("expediente.json") or {}, leer("guion.json") or {}, leer("blog.json") or {}
        base = f"/salida/{app_id}/"
        return {
            "proyecto": self.proyectos.get(app_id),
            "video": base + "video.mp4" if (carpeta / "video.mp4").exists() else None,
            "miniatura": base + "miniatura.jpg" if (carpeta / "miniatura.jpg").exists() else None,
            "blog_preview": base + "blog_preview.html" if (carpeta / "blog_preview.html").exists() else None,
            "veredicto": exp.get("veredicto"), "resumen": exp.get("resumen"), "senales": exp.get("senales", []),
            "pendiente": exp.get("pendiente_de_probar", []), "fuentes": exp.get("fuentes_web", []),
            "titulos": guion.get("titulos", []), "escenas": [e["narracion"] for e in guion.get("escenas", [])],
            "blog_titulo": blog.get("titulo"),
        }


def configurar_telegram() -> None:
    """Asistente: valida el token de @BotFather, espera tu primer mensaje y guarda tu chat."""
    import getpass
    import os
    import re as _re

    env = config.BASE / ".env"
    texto = env.read_text(encoding="utf-8") if env.exists() else ""

    def pon(clave, valor):
        nonlocal texto
        if _re.search(rf"^{clave}=", texto, flags=_re.M):
            texto = _re.sub(rf"^{clave}=.*$", lambda _: f"{clave}={valor}", texto, flags=_re.M)
        else:
            texto = texto.rstrip("\n") + f"\n{clave}={valor}\n"

    print("Configurar Telegram.\n1) En Telegram busca @BotFather, escríbele /newbot y sigue los pasos.")
    token = getpass.getpass("2) Pega aquí el token que te dio (no se ve al pegarlo): ").strip()
    try:
        bot = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=20).json()
    except requests.RequestException as exc:
        raise SystemExit(f"No pude hablar con Telegram: {exc}")
    if not bot.get("ok"):
        raise SystemExit("Ese token no sirve. Cópialo completo de @BotFather e inténtalo otra vez.")
    usuario = bot["result"]["username"]
    print(f"\n✔ Tu bot es @{usuario}")
    print(f"3) En tu celular abre  https://t.me/{usuario}  y dale INICIAR (o mándale 'hola').")
    print("   Esperando tu mensaje (hasta 3 minutos)…")
    chat = None
    for _ in range(6):
        r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", params={"timeout": 30}, timeout=45).json()
        if not r.get("ok"):
            if r.get("error_code") == 409:
                raise SystemExit("La oficina está usando este bot. Detenla: sudo systemctl stop oficina, y repite.")
            continue
        mensajes = [u["message"] for u in r.get("result", []) if "message" in u]
        if mensajes:
            chat = mensajes[-1]["chat"]
            break
    if not chat:
        raise SystemExit("No me llegó tu mensaje. Vuelve a correr esto y mándale 'hola' a tu bot.")
    pon("TELEGRAM_TOKEN", token)
    pon("TELEGRAM_CHAT_ID", str(chat["id"]))
    env.write_text(texto, encoding="utf-8")
    os.chmod(env, 0o600)
    requests.post(f"https://api.telegram.org/bot{token}/sendMessage", timeout=20, json={
        "chat_id": chat["id"], "reply_markup": tg.TECLADO,
        "text": "¡Hola jefe! 👋 Soy Paola. Desde aquí el equipo te va a avisar y tú nos puedes contestar. "
                "Reinicia la oficina y escríbeme 'ayuda'."})
    print(f"\n✔ Listo, {chat.get('first_name', 'jefe')}. Te mandé un mensaje de bienvenida.")
    print("4) Reinicia la oficina:  sudo systemctl restart oficina")


def configurar_whatsapp() -> None:
    """Asistente: pide los datos de Meta, los guarda en .env y dice qué pegar en Meta."""
    import getpass
    import os
    import re
    import secrets

    env = config.BASE / ".env"
    texto = env.read_text(encoding="utf-8") if env.exists() else ""

    def actual(clave):
        valores = [v.strip() for v in re.findall(rf"^{clave}=(.*)$", texto, flags=re.M) if v.strip()]
        return valores[-1] if valores else ""

    def pon(clave, valor):
        nonlocal texto
        if re.search(rf"^{clave}=", texto, flags=re.M):
            texto = re.sub(rf"^{clave}=.*$", lambda _: f"{clave}={valor}", texto, flags=re.M)
        else:
            texto = texto.rstrip("\n") + f"\n{clave}={valor}\n"

    print("Configurar WhatsApp. Deja vacío y da Enter para conservar lo que ya está.\n")
    preguntas = [
        ("WHATSAPP_PHONE_ID", "Identificador del número de teléfono (Phone number ID)", False),
        ("WHATSAPP_TOKEN", "Token de acceso (no se ve al pegarlo)", True),
        ("WHATSAPP_APP_SECRET", "Clave secreta de la app (App Secret, no se ve al pegarla)", True),
        ("WHATSAPP_JEFE", "Tu número de WhatsApp con lada, solo dígitos (ej. 5216641234567)", False),
    ]
    for clave, pregunta, oculta in preguntas:
        tiene = " [ya hay uno]" if actual(clave) else ""
        valor = (getpass.getpass if oculta else input)(f"{pregunta}{tiene}: ").strip()
        if valor:
            pon(clave, re.sub(r"\D", "", valor) if clave == "WHATSAPP_JEFE" else valor)
    if not actual("WHATSAPP_VERIFY_TOKEN"):
        pon("WHATSAPP_VERIFY_TOKEN", secrets.token_urlsafe(18))
    for clave, defecto in [("WHATSAPP_PLANTILLA", "novedad_oficina"), ("WHATSAPP_IDIOMA", "es_MX"), ("WHATSAPP_NIVEL", "importante")]:
        if not actual(clave):
            pon(clave, defecto)
    env.write_text(texto, encoding="utf-8")
    os.chmod(env, 0o600)
    url = actual("OFICINA_URL") or "https://TU-DIRECCION"
    print("\n✔ Guardado en .env\n")
    print("Ahora en Meta → WhatsApp → Configuración → Webhook, pega esto:")
    print(f"  URL de devolución de llamada:  {url}/whatsapp/webhook")
    print(f"  Token de verificación:          {actual('WHATSAPP_VERIFY_TOKEN')}")
    print("  y suscríbete al campo: messages\n")
    print("Después reinicia la oficina:  sudo systemctl restart oficina")


def probar_whatsapp() -> None:
    faltan = [n for n, v in [("WHATSAPP_TOKEN", wa.TOKEN), ("WHATSAPP_PHONE_ID", wa.PHONE_ID), ("WHATSAPP_JEFE", wa.JEFE)] if not v]
    if faltan:
        raise SystemExit("Faltan en .env: " + ", ".join(faltan))
    try:
        r = wa.enviar_plantilla(wa.JEFE, "Prueba: tu oficina ya te puede escribir por WhatsApp ✅")
        print(f"✔ Enviado con la plantilla '{wa.PLANTILLA}'. Revisa tu WhatsApp. ({r.get('messages', [{}])[0].get('id', '')})")
    except wa.ErrorWhatsApp as exc:
        print(f"✖ No se pudo: {exc}")
        if "132001" in str(exc) or "template" in str(exc).lower():
            print("  Revisa que la plantilla exista, esté APROBADA y se llame igual que WHATSAPP_PLANTILLA (idioma WHATSAPP_IDIOMA).")
        if "131030" in str(exc):
            print("  Con el número de prueba de Meta, tu número debe estar en la lista de destinatarios permitidos.")
        if "190" in str(exc) or "OAuth" in str(exc):
            print("  El token no sirve o caducó: usa un token permanente de usuario del sistema.")


def crear_servidor(oficina: Oficina, puerto: int, host: str = "127.0.0.1") -> ThreadingHTTPServer:
    class Manejador(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _autorizado(self) -> bool:
            """Usuario y contraseña (HTTP Basic). Sin OFICINA_PASSWORD no se pide (solo uso local)."""
            if not PASSWORD:
                return True
            cabecera = self.headers.get("Authorization", "")
            if cabecera.startswith("Basic "):
                try:
                    usuario, _, clave = base64.b64decode(cabecera[6:]).decode().partition(":")
                except (ValueError, UnicodeDecodeError):
                    usuario, clave = "", ""
                if hmac.compare_digest(usuario.encode(), USUARIO.encode()) and \
                        hmac.compare_digest(clave.encode(), PASSWORD.encode()):
                    return True
            time.sleep(1)  # frena intentos de adivinar la contraseña
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="Oficina AutoCanal", charset="UTF-8"')
            self.send_header("Content-Length", "0")
            self.end_headers()
            return False

        def _mismo_origen(self) -> bool:
            """Evita que otra página use tu sesión para aprobar o publicar (CSRF)."""
            if "application/json" not in self.headers.get("Content-Type", ""):
                return False
            origen = self.headers.get("Origin")
            return not origen or urlparse(origen).netloc == self.headers.get("Host")

        def _json(self, datos, codigo=200):
            cuerpo = json.dumps(datos, ensure_ascii=False).encode()
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def _archivo(self, ruta: Path, raiz: Path):
            ruta = ruta.resolve()
            if not ruta.is_relative_to(raiz.resolve()) or not ruta.is_file():
                return self._json({"error": "no encontrado"}, 404)
            tam = ruta.stat().st_size
            ini, fin = 0, tam - 1
            rango = self.headers.get("Range")
            if rango and rango.startswith("bytes="):  # para poder adelantar el video
                a, _, b = rango[6:].partition("-")
                ini = int(a) if a else max(0, tam - int(b))
                fin = int(b) if a and b else tam - 1
                self.send_response(206)
                self.send_header("Content-Range", f"bytes {ini}-{fin}/{tam}")
            else:
                self.send_response(200)
            self.send_header("Content-Type", (mimetypes.guess_type(ruta.name)[0] or "application/octet-stream")
                             + ("; charset=utf-8" if ruta.suffix in (".html", ".js", ".css") else ""))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(fin - ini + 1))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            with open(ruta, "rb") as f:
                f.seek(ini)
                restante = fin - ini + 1
                try:
                    while restante > 0:
                        trozo = f.read(min(65536, restante))
                        if not trozo:
                            break
                        self.wfile.write(trozo)
                        restante -= len(trozo)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        def _texto(self, texto: str, codigo: int = 200):
            cuerpo = texto.encode()
            self.send_response(codigo)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def do_GET(self):
            url = urlparse(self.path)
            if url.path == "/whatsapp/webhook":  # Meta verifica la dirección al configurarla
                q = parse_qs(url.query)
                if q.get("hub.mode") == ["subscribe"] and wa.VERIFY_TOKEN and \
                        hmac.compare_digest(q.get("hub.verify_token", [""])[0], wa.VERIFY_TOKEN):
                    return self._texto(q.get("hub.challenge", [""])[0])
                return self._texto("token inválido", 403)
            if not self._autorizado():
                return
            ruta = unquote(urlparse(self.path).path)
            if ruta == "/":
                return self._archivo(WEB / "index.html", WEB)
            if ruta.startswith("/static/"):
                return self._archivo(WEB / ruta[len("/static/"):], WEB)
            if ruta.startswith("/salida/"):
                return self._archivo(config.SALIDA / ruta[len("/salida/"):], config.SALIDA)
            if ruta == "/api/estado":
                return self._json(oficina.snapshot())
            if ruta.startswith("/api/proyecto/"):
                return self._json(oficina.detalle(ruta.rsplit("/", 1)[-1]))
            if ruta == "/eventos":
                return self._eventos()
            self._json({"error": "no encontrado"}, 404)

        def _eventos(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            visto = -1
            try:
                while True:
                    with oficina.cambio:
                        if oficina.version == visto:
                            oficina.cambio.wait(timeout=15)
                    if oficina.version != visto:
                        datos = oficina.snapshot()
                        visto = datos["version"]
                        self.wfile.write(f"data: {json.dumps(datos, ensure_ascii=False)}\n\n".encode())
                    else:
                        self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass

        def do_POST(self):
            if urlparse(self.path).path == "/whatsapp/webhook":
                crudo = self.rfile.read(min(int(self.headers.get("Content-Length") or 0), 1_000_000))
                if not wa.firma_valida(crudo, self.headers.get("X-Hub-Signature-256", "")):
                    return self._texto("firma inválida", 403)
                self._texto("ok")  # contestar rápido; el trabajo sigue en otro hilo
                try:
                    for m in wa.mensajes_entrantes(json.loads(crudo)):
                        threading.Thread(target=oficina.recibir_whatsapp, args=(m,), daemon=True).start()
                except (json.JSONDecodeError, AttributeError):
                    pass
                return
            if not self._autorizado():
                return
            if not self._mismo_origen():
                return self._json({"error": "origen no permitido"}, 403)
            largo = int(self.headers.get("Content-Length") or 0)
            try:
                datos = json.loads(self.rfile.read(largo) or b"{}")
            except json.JSONDecodeError:
                return self._json({"error": "JSON inválido"}, 400)
            ruta = urlparse(self.path).path
            if ruta == "/api/ideas/descartar":
                return self._json(oficina.descartar_ideas())
            if ruta == "/api/ideas":
                oficina.pedir_ideas(str(datos.get("guia", ""))[:500])
                return self._json({"ok": True})
            if ruta.startswith("/api/idea/"):
                accion = datos.get("accion")
                if accion not in ("aprobar", "rechazar", "comentar"):
                    return self._json({"error": "acción inválida"}, 400)
                r = oficina.responder_idea(ruta.rsplit("/", 1)[-1], accion, str(datos.get("texto", ""))[:1000])
                return self._json(r, 400 if "error" in r else 200)
            if ruta.startswith("/api/proyecto/"):
                r = oficina.accion_proyecto(ruta.rsplit("/", 1)[-1], str(datos.get("accion")),
                                            str(datos.get("texto", ""))[:2000], int(datos.get("titulo", 1) or 1))
                return self._json(r, 400 if "error" in r else 200)
            self._json({"error": "no encontrado"}, 404)

    return ThreadingHTTPServer((host, puerto), Manejador)


def main() -> None:
    global ESTADO
    p = argparse.ArgumentParser(description="Oficina visual de agentes")
    p.add_argument("--demo", action="store_true", help="simula Claude, Play Store y la publicación")
    p.add_argument("--puerto", type=int, default=8765)
    p.add_argument("--host", default="127.0.0.1",
                   help="0.0.0.0 para aceptar conexiones de fuera (exige OFICINA_PASSWORD)")
    p.add_argument("--sin-navegador", action="store_true")
    p.add_argument("--configurar-telegram", "--telegram-id", action="store_true", dest="configurar_telegram",
                   help="asistente para conectar tu Telegram")
    p.add_argument("--probar-whatsapp", action="store_true", help="te manda un WhatsApp de prueba y sale")
    p.add_argument("--configurar-whatsapp", action="store_true", help="asistente para poner los datos de WhatsApp")
    a = p.parse_args()
    if a.configurar_whatsapp:
        return configurar_whatsapp()
    if a.configurar_telegram:
        return configurar_telegram()
    if a.probar_whatsapp:
        return probar_whatsapp()
    a.demo = a.demo or config.env("OFICINA_DEMO") == "1"
    if a.host not in ("127.0.0.1", "localhost") and not PASSWORD:
        raise SystemExit("Para abrir la oficina a internet pon OFICINA_PASSWORD en .env.")
    if a.demo:
        from agentes import simulado

        simulado.activar()
        ESTADO = config.BASE / "oficina_estado_demo.json"
    oficina = Oficina(a.demo)
    servidor = crear_servidor(oficina, a.puerto, a.host)
    url = f"http://localhost:{a.puerto}"
    print(f"🏢 Oficina abierta en {url}" + ("  (modo demo)" if a.demo else "")
          + (f"  · ideas diarias a las {IDEAS_HORA} ({IDEAS_ZONA})" if IDEAS_HORA else "")
          + ("  · Telegram" if tg.activo() else "") + ("  · WhatsApp" if wa.activo() else "")
          + (f" (avisos: {NIVEL_AVISOS})" if tg.activo() or wa.activo() else "")
          + "  — Ctrl+C para cerrar", flush=True)
    if not a.sin_navegador:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nOficina cerrada.")


if __name__ == "__main__":
    main()
