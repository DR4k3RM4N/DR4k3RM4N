"""Sala de edición: la tercera oficina del edificio.

Tus compus (con tarjeta de video) editan en lugar del servidor. Cada compu corre `compu.py`: le pregunta a la sala
"¿hay algo que editar?", baja los clips, edita y sube el video. No hay que abrir puertos en tu casa.

    python sala.py          # en el servidor (127.0.0.1:8767); se entra por el edificio en /sala/
    python sala.py --demo

Las oficinas (TikTok Shop, y luego YouTube) le mandan trabajos por /interno/… (solo desde el mismo servidor).
Tus compus entran por /sala/api/maquina/… con su propia llave (se la da un código de 6 números al instalarla).
"""
from __future__ import annotations

import argparse
import base64
import os
import subprocess
import hashlib
import hmac
import json
import secrets
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

AQUI = Path(__file__).resolve().parent
REPO = AQUI.parent
sys.path[:0] = [str(REPO / "autocanal"), str(REPO / "tiktokshop"), str(AQUI)]

import requests  # noqa: E402

from aprendizaje import Aprendizaje  # noqa: E402
from proyectos import Proyectos  # noqa: E402

ESTADO = AQUI / "sala_estado.json"
DESCARGAS = AQUI / "windows"
VIVA = 30  # segundos sin noticias para dar una compu por apagada
CODIGO_DURA = 15 * 60
# de dónde se pueden mandar archivos a las compus (🕵️ Expedientes incluido: antes faltaba y la sala rechazaba sus videos)
RAICES = [REPO / "tiktokshop" / "salida", REPO / "autocanal" / "salida", AQUI / "salida", REPO / "autocanal" / "expedientes",
          *([Path(os.environ["AUTOCANAL_EXPEDIENTES"])] if os.environ.get("AUTOCANAL_EXPEDIENTES") else [])]
EXT_RESULTADO = {".mp4", ".jpg", ".json", ".srt", ".txt"}  # video, miniaturas, subtítulos, capítulos y créditos
TIENDA_URL = "http://127.0.0.1:8766"  # oficina de TikTok (para saber a qué productos hacerles carpeta en tus compus)
MAX_RESULTADO = 2 * 1024 ** 3
SERVIDOR_ID = "servidor"  # 🖥️ el propio servidor, como una compu más de la sala (se prende desde la oficina central)
SERVIDOR_CARPETA = Path.home() / ".salaedicion-servidor"
ESPERA_SERVIDOR = 30  # segundos que un video espera a tus compus antes de que lo tome el servidor


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class Sala(Aprendizaje, Proyectos):
    def __init__(self, demo: bool):
        self.demo = demo
        self.lock = threading.RLock()
        self.version = 0
        datos = json.loads(ESTADO.read_text(encoding="utf-8")) if ESTADO.exists() else {}
        self.compus: dict = datos.get("compus", {})
        self.trabajos: dict = datos.get("trabajos", {})
        self.proyectos: dict = datos.get("proyectos", {})
        self.chat: list = datos.get("chat", [])
        self.gasto: dict = datos.get("gasto", {})
        self.ignoradas: list = datos.get("ignoradas", [])  # carpetas de tus compus que borraste: no vuelven a ser proyecto
        # ⚙️ oficina central: ¿el servidor también edita? y cuántos videos a la vez
        self.ajustes: dict = {"usar_servidor": False, "servidor_a_la_vez": 1, **(datos.get("ajustes") or {})}
        self.cargar_estilo(datos)  # el cuaderno de estilo que comparten los editores
        for pr in self.proyectos.values():
            if pr.get("estado") == "editando":
                pr.update(estado="error", trabajo=None, error="La sala se reinició a medio trabajo. Escribe «otra vez».")
        self.codigos: dict = {}  # código → vence
        self.locales: dict = {}  # compu → {producto: [clips en su carpeta]}  (solo nombres y miniaturas, nunca videos)
        self.pedidos_carpeta: dict = {}  # «📂 Elegir carpeta…»: id → {compu, estado, ruta}
        self.miniaturas: dict = {}  # (compu, producto, archivo) → jpg chiquito
        self.analisis: dict = {}  # (compu, carpeta, archivo) → {frases, calidad}  (qué dices y partes movidas)
        self.hojas: dict = {}  # (compu, carpeta, archivo) → tira de 4 cuadros (para que el editor vea el clip)
        self.intentos: list[float] = []
        # 🔁 lo que estaba a medias NO se tira al reiniciar: la compu sigue trabajando y lo entrega (si se apagó, `ver`
        # lo marca y su oficina lo vuelve a mandar)
        for c in self.compus.values():
            vivos = [tid for tid, t in self.trabajos.items() if t.get("compu") == c["id"] and t["estado"] in ("asignado", "trabajando")]
            c["activos"], c["trabajo"] = vivos, (vivos[0] if vivos else None)
            c["ultimo"] = time.time()  # le damos chance de volver a dar señales antes de darla por apagada

    def _tocar(self) -> None:
        self.version += 1
        viejos = sorted(self.trabajos.values(), key=lambda t: t["creado"])[:-80]
        for t in viejos:
            self.trabajos.pop(t["id"], None)
        ESTADO.write_text(json.dumps({"compus": self.compus, "trabajos": self.trabajos, "proyectos": self.proyectos,
                                      "chat": self.chat[-200:], "gasto": dict(sorted(self.gasto.items())[-90:]),
                                      "estilo": self.estilo, "ignoradas": self.ignoradas[-300:], "ajustes": self.ajustes},
                                     ensure_ascii=False, indent=1), encoding="utf-8")

    # ---------- lo que se ve en el edificio ----------
    def viva(self, c: dict) -> bool:
        return time.time() - c.get("ultimo", 0) < VIVA

    def snapshot(self) -> dict:
        with self.lock:
            compus = []
            for c in sorted(self.compus.values(), key=lambda c: c["slot"]):
                t = self.trabajos.get(c.get("trabajo") or "") or self.trabajos.get(c.get("trabajo_cel") or "")
                varios = len(c.get("activos") or []) + (1 if c.get("trabajo_cel") else 0)
                activos = [self.trabajos[x] for x in (c.get("activos") or []) if x in self.trabajos]
                compus.append({k: c.get(k) for k in ("id", "nombre", "slot", "gpu", "sistema", "version", "ultimo",
                                                     "nvenc", "oido", "editados", "estado_texto", "claude_code", "motion",
                                                     "celular", "expedientes", "tipos", "uso", "capacidad", "interno")}
                              | {"viva": self.viva(c),
                                 "trabajo": {k: t.get(k) for k in ("id", "etiqueta", "origen", "paso", "avance")} if t else None,
                                 "activos": [{k: x.get(k) for k in ("id", "tipo", "etiqueta", "origen", "paso", "avance", "inicio", "mov")}
                                             for x in activos if x["estado"] in ("asignado", "trabajando")],
                                 "a_la_vez": varios})
            trabajos = [{k: t.get(k) for k in ("id", "tipo", "origen", "etiqueta", "estado", "compu", "creado", "inicio",
                                                "fin", "error", "paso", "avance", "mov")}
                        | {"compu_nombre": (self.compus.get(t.get("compu") or "") or {}).get("nombre")}
                        for t in sorted(self.trabajos.values(), key=lambda t: -t["creado"])[:30]]
            tareas = [{"id": t["id"], "agente": self.editor_id(t["compu"]), "etapa": "edicion",
                       "accion": {"pensar": "Pensar", "claude_libre": "Editor IA", "probar_app": "📱 Probar app",
                                "edu": "🎬 Video de YouTube", "edu_ia": "🎬 Claude edita video", "edu_estilo": "🐑 Video con estilo", "probar_ssh": "🔑 Probar SSH",
                                "expediente": "🕵️ Video de Expedientes"}.get(t["tipo"], "Editar"),
                       "titulo": t["etiqueta"], "estado": {"listo": "hecha", "error": "fallo", "cancelado": "cancelada"}.get(t["estado"], "trabajando"),
                       "inicio": t.get("inicio"), "fin": t.get("fin"), "error": t.get("error"), "paso": t.get("paso"),
                       "avance": t.get("avance")} for t in sorted(self.trabajos.values(), key=lambda t: t["creado"])[-40:] if t.get("compu")]
            hoy = time.strftime("%Y-%m-%d")
            return {"version": self.version, "demo": self.demo, "ahora": time.time(), "compus": compus, "trabajos": trabajos,
                    "ajustes": self.ajustes,
                    "cola": sum(1 for t in self.trabajos.values() if t["estado"] == "en_cola"),
                    "locales": self.resumen_locales(), "editores": self.editores(), "proyectos": self.resumen_proyectos(),
                    "chat": self.chat[-60:], "tareas": tareas,
                    "gasto": {"hoy": round(self.gasto.get(hoy, 0), 4),
                              "mes": round(sum(v for k, v in self.gasto.items() if k.startswith(hoy[:7])), 4)}}

    def _gastar(self, proyecto, etapa, modelo, usd, entrada, salida, que: str = "") -> None:
        with self.lock:
            hoy = time.strftime("%Y-%m-%d")
            self.gasto[hoy] = self.gasto.get(hoy, 0) + usd
            self._tocar()

    def vigilar(self) -> None:
        """Si la compu de un trabajo de la sala se apaga a medio camino, se avisa en el chat del proyecto."""
        while True:
            time.sleep(10)
            for t in list(self.trabajos.values()):
                if t.get("proyecto") and t["estado"] in ("asignado", "trabajando"):
                    self.ver(t["id"])
                    if t["estado"] == "error":
                        self.termino_trabajo(t)

    # ---------- dar de alta una compu ----------
    def nuevo_codigo(self) -> dict:
        codigo = f"{secrets.randbelow(1_000_000):06d}"
        with self.lock:
            ahora = time.time()
            self.codigos = {k: v for k, v in self.codigos.items() if v > ahora}
            self.codigos[codigo] = ahora + CODIGO_DURA
        return {"codigo": codigo, "vence": ahora + CODIGO_DURA}

    # ---------- ⚙️ oficina central ----------
    def ajustar(self, d: dict) -> dict:
        with self.lock:
            if "usar_servidor" in d:
                self.ajustes["usar_servidor"] = bool(d["usar_servidor"])
            if "servidor_a_la_vez" in d:
                self.ajustes["servidor_a_la_vez"] = max(1, min(4, int(d.get("servidor_a_la_vez") or 1)))
            self._tocar()
        return {"ok": True, "ajustes": self.ajustes}

    def reinicio(self, minutos: float = 10) -> dict:
        """🔄 Reinicio forzoso: lo que se quedó trabado (compu apagada o sin avanzar `minutos`) se cancela para que su
        oficina lo vuelva a mandar a otra compu."""
        cancelados = []
        with self.lock:
            for t in self.trabajos.values():
                if t["estado"] not in ("asignado", "trabajando"):
                    continue
                c = self.compus.get(t.get("compu") or "")
                quieto = time.time() - (t.get("mov") or t.get("inicio") or time.time())
                if not c or not self.viva(c) or quieto > minutos * 60:
                    t.update(estado="cancelado", error="Reinicio forzoso: se había trabado.", fin=time.time())
                    if c:
                        self._soltar(c, t["id"])
                    cancelados.append(t["etiqueta"])
            self._tocar()
        return {"ok": True, "cancelados": cancelados}

    def servidor_compu(self) -> str | None:
        """Da de alta (una vez) al servidor como compu de la sala y deja su llave en su carpeta. Regresa la carpeta."""
        with self.lock:
            cfg = SERVIDOR_CARPETA / "config.json"
            c = self.compus.get(SERVIDOR_ID)
            if c and cfg.exists():
                return str(SERVIDOR_CARPETA)
            token = secrets.token_urlsafe(32)
            libres = sorted(set(range(1, 9)) - {x["slot"] for x in self.compus.values() if x["id"] != SERVIDOR_ID})
            self.compus[SERVIDOR_ID] = {"id": SERVIDOR_ID, "nombre": "Servidor", "token": _hash(token), "interno": True,
                                        "slot": libres[0] if libres else 9, "gpu": "", "sistema": "Linux (servidor)",
                                        "creado": time.time(), "ultimo": 0, "trabajo": None, "editados": 0}
            SERVIDOR_CARPETA.mkdir(parents=True, exist_ok=True)
            cfg.write_text(json.dumps({"servidor": f"http://127.0.0.1:{PUERTO}", "token": token, "nombre": "Servidor",
                                       "id": SERVIDOR_ID}), encoding="utf-8")
            os.chmod(cfg, 0o600)
            self._tocar()
        return str(SERVIDOR_CARPETA)

    def vigilar_servidor(self) -> None:
        """🖥️ Si prendiste «usar también el servidor», corre aquí mismo el programa de las compus (en modo servidor)."""
        proceso = None
        while True:
            try:
                quiere = self.ajustes.get("usar_servidor") and not self.demo
                n = str(self.ajustes.get("servidor_a_la_vez") or 1)
                if quiere and (proceso is None or proceso.poll() is not None or getattr(proceso, "n", n) != n):
                    if proceso and proceso.poll() is None:
                        proceso.terminate()
                    carpeta = self.servidor_compu()
                    proceso = subprocess.Popen([sys.executable, str(AQUI / "compu.py")], cwd=str(AQUI),
                                               env={**os.environ, "SALA_SERVIDOR": "1", "SALA_CARPETA": carpeta,
                                                    "SALA_A_LA_VEZ": n, "PYTHONUNBUFFERED": "1"},
                                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    proceso.n = n
                elif not quiere and proceso and proceso.poll() is None:
                    proceso.terminate()
                    proceso = None
            except Exception as exc:  # noqa: BLE001
                print(f"  · no pude prender al servidor como compu: {exc}", flush=True)
            time.sleep(10)

    def vincular(self, d: dict) -> dict:
        codigo = str(d.get("codigo", "")).replace(" ", "").strip()
        with self.lock:
            ahora = time.time()
            self.intentos = [x for x in self.intentos if ahora - x < 600]
            if len(self.intentos) >= 10:
                return {"error": "Demasiados intentos. Espera 10 minutos y genera otro código."}
            if not any(hmac.compare_digest(codigo, k) for k, v in self.codigos.items() if v > ahora):
                self.intentos.append(ahora)
                return {"error": "Código incorrecto o vencido. Genera otro en la pestaña Sala."}
            self.codigos.pop(codigo, None)
            token = secrets.token_urlsafe(32)
            libres = sorted({1, 2, 3, 4} - {c["slot"] for c in self.compus.values()})
            cid = uuid.uuid4().hex[:8]
            self.compus[cid] = {"id": cid, "nombre": str(d.get("nombre") or "Mi compu")[:40], "token": _hash(token),
                                "slot": libres[0] if libres else len(self.compus) + 1, "gpu": str(d.get("gpu") or "")[:60],
                                "sistema": str(d.get("sistema") or "")[:40], "creado": ahora, "ultimo": ahora,
                                "trabajo": None, "editados": 0}
            self._tocar()
        return {"ok": True, "token": token, "id": cid, "nombre": self.compus[cid]["nombre"]}

    def quitar(self, cid: str) -> dict:
        with self.lock:
            c = self.compus.pop(cid, None)
            if not c:
                return {"error": "No encontré esa compu."}
            for t in [self.trabajos.get(x or "") for x in (c.get("trabajo"), c.get("trabajo_cel"), *(c.get("activos") or []))]:
                if t and t["estado"] in ("asignado", "trabajando"):
                    t.update(estado="en_cola", compu=None, slot=None)
            self._tocar()
        return {"ok": True}

    def autenticar(self, token: str) -> dict | None:
        if not token:
            return None
        h = _hash(token)
        return next((c for c in self.compus.values() if hmac.compare_digest(c["token"], h)), None)

    # ---------- trabajos ----------
    def libres(self, tipo: str) -> int:
        """Lugares libres ahorita en las compus prendidas que saben hacer ese tipo."""
        with self.lock:
            total = 0
            for c in self.compus.values():
                if not self.viva(c) or tipo not in (c.get("tipos") or ["cris"]):
                    continue
                if c.get("capacidad"):
                    vivos = [x for x in (c.get("activos") or [])
                             if (self.trabajos.get(x) or {}).get("estado") in ("asignado", "trabajando")]
                    total += max(0, c["capacidad"] - len(vivos))
                else:
                    t = self.trabajos.get(c.get("trabajo") or "")
                    total += 0 if t and t["estado"] in ("asignado", "trabajando") else 1
            return total

    def disponibles(self, tipo: str) -> int:
        with self.lock:
            return sum(1 for c in self.compus.values() if self.viva(c) and tipo in (c.get("tipos") or ["cris"]))

    def crear(self, d: dict) -> dict:
        entradas = []
        for e in d.get("entradas") or []:
            ruta = Path(e).resolve()
            if not any(ruta.is_relative_to(r.resolve()) for r in RAICES) or not ruta.is_file():
                return {"error": f"Archivo no permitido: {Path(e).name}"}
            entradas.append(str(ruta))
        salida = Path(d.get("salida", "")).resolve()
        if not any(salida.is_relative_to(r.resolve()) for r in RAICES):
            return {"error": "Carpeta de salida no permitida."}
        fija = str(d.get("compu") or "")
        if fija and fija not in self.compus:
            return {"error": "Esa compu ya no está en la sala."}
        t = {"id": uuid.uuid4().hex[:10], "tipo": str(d.get("tipo", "cris")), "origen": str(d.get("origen", "")),
             "fija": fija or None, "local": d.get("local") or None,
             "evitar": [str(x) for x in (d.get("evitar") or [])][:10],  # compus donde ya se trabó
             "etiqueta": str(d.get("etiqueta", ""))[:80], "parametros": d.get("parametros") or {}, "entradas": entradas,
             "salida": str(salida), "clasificar": str(d.get("clasificar", "")), "estado": "en_cola", "compu": None,
             "slot": None, "creado": time.time(), "inicio": None, "fin": None, "error": None, "paso": "", "avance": 0,
             "resultado": None}
        with self.lock:
            self.trabajos[t["id"]] = t
            self._tocar()
        return {"ok": True, "id": t["id"]}

    def ver(self, tid: str) -> dict:
        with self.lock:
            t = self.trabajos.get(tid)
            if not t:
                return {"estado": "cancelado", "error": "La sala no conoce ese trabajo."}
            c = self.compus.get(t.get("compu") or "")
            if t["estado"] in ("asignado", "trabajando") and (not c or not self.viva(c)):
                t.update(estado="error", error="La compu se apagó o perdió internet a medio trabajo.", fin=time.time())
                if c:
                    self._soltar(c, tid)
                self._tocar()
            return {k: t.get(k) for k in ("id", "estado", "paso", "avance", "error", "resultado", "slot", "mov")} | {
                "compu": c["nombre"] if c else None, "compu_id": c["id"] if c else None}

    def cancelar(self, tid: str) -> dict:
        with self.lock:
            t = self.trabajos.get(tid)
            if t and t["estado"] not in ("listo", "error"):
                t.update(estado="cancelado", fin=time.time())
                c = self.compus.get(t.get("compu") or "")
                if c:
                    self._soltar(c, tid)
                self._tocar()
        return {"ok": True}

    # ---------- lo que hacen tus compus ----------
    def latido(self, c: dict, d: dict) -> dict:
        """La compu avisa que está prendida y pregunta si hay trabajo."""
        with self.lock:
            if d.get("estado"):
                c["estado_texto"] = str(d["estado"])[:80]
            c.update(ultimo=time.time(), gpu=str(d.get("gpu") or c.get("gpu") or "")[:60],
                     version=str(d.get("version") or "")[:12], nvenc=bool(d.get("nvenc")), oido=str(d.get("oido") or "")[:40],
                     tipos=[x for x in (d.get("tipos") or ["cris"]) if isinstance(x, str)][:12],
                     claude_code=str(d.get("claude_code") or "")[:20], motion=str(d.get("motion") or "")[:20],
                     celular=str(d.get("celular") or "")[:40],
                     expedientes=str(d.get("expedientes") or "sin actualizar")[:120],  # 🕵️ ¿puede hacer videos de Expedientes?
                     uso={k: v for k, v in (d.get("uso") or {}).items() if isinstance(v, (int, float))} or c.get("uso"))
            extra = {}
            if not d.get("pulso"):  # «📂 Elegir carpeta…»: se entrega en el latido normal (no en el pulso)
                pedir = next((pid for pid, x in self.pedidos_carpeta.items() if x["compu"] == c["id"] and x["estado"] == "nuevo"), None)
                if pedir:
                    self.pedidos_carpeta[pedir]["estado"] = "esperando"
                    extra = {"pedir_carpeta": {"id": pedir}}
            activo = lambda t: bool(t) and t["estado"] in ("asignado", "trabajando")  # noqa: E731
            dos_carriles = "libre_cel" in d  # compus nuevas: el robot del cel va aparte y no les quita la edición
            cel_t = None
            if dos_carriles:
                cel_t = self.trabajos.get(c.get("trabajo_cel") or "")
                if not activo(cel_t):
                    c["trabajo_cel"], cel_t = None, None
                    if d.get("libre_cel") and "probar_app" in c["tipos"]:
                        cel_t = next((t for t in sorted(self.trabajos.values(), key=lambda t: t["creado"])
                                      if t["estado"] == "en_cola" and t["tipo"] == "probar_app"
                                      and t.get("fija") in (None, c["id"])), None)
                        if cel_t:
                            cel_t.update(estado="asignado", compu=c["id"], slot=c["slot"], inicio=time.time(),
                                         paso="Preparando el cel")
                            c["trabajo_cel"] = cel_t["id"]
                            self._tocar()
                extra["trabajo_cel"] = self._para_compu(cel_t) if cel_t else None
            def sirve(t: dict) -> bool:
                if c["id"] in (t.get("evitar") or []):
                    return False
                if c.get("interno") and not t.get("fija") and time.time() - t["creado"] < ESPERA_SERVIDOR and any(
                        self.viva(o) and not o.get("interno") and t["tipo"] in (o.get("tipos") or []) for o in self.compus.values()):
                    return False  # primero tus compus; si en 30 s ninguna lo toma, lo hace el servidor
                return (t["estado"] == "en_cola" and t["tipo"] in c["tipos"] and t.get("fija") in (None, c["id"])
                        and not (dos_carriles and t["tipo"] == "probar_app")
                        and (d.get("oido_listo", True) or t["tipo"] in ("pensar", "claude_libre", "probar_app", "edu", "edu_ia", "edu_estilo", "probar_ssh", "expediente")))

            if "capacidad" in d:  # 🖥️ compus nuevas: editan VARIOS videos a la vez (según lo que aguantan)
                cap = max(1, min(6, int(d.get("capacidad") or 1)))
                c["capacidad"] = cap
                activos = [x for x in (c.get("activos") or []) if activo(self.trabajos.get(x))]
                libres = min(cap - len(activos), int(d.get("libres", cap)))
                for t in sorted(self.trabajos.values(), key=lambda t: t["creado"]):
                    if libres <= 0:
                        break
                    if sirve(t):
                        t.update(estado="asignado", compu=c["id"], slot=c["slot"], inicio=time.time(), paso="Bajando tus clips")
                        activos.append(t["id"])
                        libres -= 1
                c["activos"], c["trabajo"] = activos, (activos[0] if activos else None)
                self._tocar()
                return {"trabajos": [self._para_compu(self.trabajos[x]) for x in activos], **extra}
            actual = self.trabajos.get(c.get("trabajo") or "")
            if actual and actual["estado"] in ("asignado", "trabajando"):
                return {"trabajo": self._para_compu(actual), **extra}
            c["trabajo"] = None
            libre = d.get("libre", True)
            pendiente = next((t for t in sorted(self.trabajos.values(), key=lambda t: t["creado"])
                              if t["estado"] == "en_cola" and t["tipo"] in c["tipos"] and t.get("fija") in (None, c["id"])
                              and not (dos_carriles and t["tipo"] == "probar_app")
                              and (d.get("oido_listo", True) or t["tipo"] in ("pensar", "claude_libre", "probar_app", "edu", "edu_ia", "edu_estilo", "probar_ssh", "expediente"))),
                             None) if libre else None
            if pendiente:
                pendiente.update(estado="asignado", compu=c["id"], slot=c["slot"], inicio=time.time(), paso="Bajando tus clips")
                c["trabajo"] = pendiente["id"]
            self._tocar()
            return {"trabajo": self._para_compu(pendiente) if pendiente else None, **extra}

    def _para_compu(self, t: dict) -> dict:
        return {"id": t["id"], "tipo": t["tipo"], "etiqueta": t["etiqueta"], "parametros": t["parametros"], "local": t.get("local"),
                "entradas": [{"n": i, "nombre": Path(e).name, "bytes": Path(e).stat().st_size if Path(e).exists() else 0}
                             for i, e in enumerate(t["entradas"])]}

    # ---------- carpetas en tus compus (los clips se quedan allá) ----------
    def carpetas_pedidas(self) -> list[dict]:
        """Productos de TikTok listos para grabar: tus compus les hacen carpeta."""
        try:
            prods = requests.get(f"{TIENDA_URL}/api/estado", timeout=5).json().get("productos", [])
        except (requests.RequestException, ValueError):
            return []
        return [{"id": p["id"], "nombre": p["nombre"]} for p in prods
                if (p.get("etapas") or {}).get("tomas") == "hecha"][:40]

    def reportar_carpetas(self, c: dict, d: dict) -> dict:
        """La compu dice qué clips hay en cada carpeta (nombre, duración y una miniatura chiquita)."""
        carpetas = {}
        for pid, clips in list((d.get("carpetas") or {}).items())[:40]:
            lista = []
            for x in (clips or [])[:80]:
                nombre = Path(str(x.get("nombre", ""))).name[:120]
                if not nombre:
                    continue
                lista.append({"nombre": nombre, "mb": float(x.get("mb") or 0), "segundos": float(x.get("segundos") or 0),
                              "tiene_audio": bool(x.get("tiene_audio", True)), "firma": str(x.get("firma", ""))[:40]})
                if isinstance(x.get("analisis"), dict):
                    self.analisis[(c["id"], pid, nombre)] = {"frases": (x["analisis"].get("frases") or [])[:60],
                                                             "calidad": (x["analisis"].get("calidad") or [])[:120]}
                if x.get("hoja"):
                    try:
                        hoja = base64.b64decode(x["hoja"])
                        if len(hoja) < 200_000 and hoja[:2] == b"\xff\xd8":
                            self.hojas[(c["id"], pid, nombre)] = hoja
                    except ValueError:
                        pass
                if x.get("miniatura"):
                    try:
                        jpg = base64.b64decode(x["miniatura"])
                        if len(jpg) < 80_000 and jpg[:2] == b"\xff\xd8":
                            self.miniaturas[(c["id"], pid, nombre)] = jpg
                    except ValueError:
                        pass
            carpetas[str(pid)[:80]] = lista
        with self.lock:
            self.locales[c["id"]] = {"carpetas": carpetas, "ruta": str(d.get("ruta") or "")[:200], "t": time.time(),
                                     "musica": [Path(str(m)).name[:100] for m in (d.get("musica") or [])][:60],
                                     "errores": {str(k)[:120]: str(v)[:200] for k, v in (d.get("errores") or {}).items()},
                                     "lugares": [{"ruta": str(x.get("ruta", ""))[:300], "nombre": str(x.get("nombre", ""))[:120],
                                                  "videos": int(x.get("videos") or 0)} for x in (d.get("lugares") or [])[:80]
                                                 if isinstance(x, dict)]}
        self.proyectos_de_carpetas(c["id"], list(carpetas))
        # firmas que la sala ya tiene con miniatura: la compu no las vuelve a mandar
        return {"ok": True, "con_miniatura": [f"{pid}/{x['nombre']}/{x['firma']}" for pid, xs in carpetas.items()
                                              for x in xs if (c["id"], pid, x["nombre"]) in self.miniaturas],
                "con_analisis": [f"{pid}/{x['nombre']}/{x['firma']}" for pid, xs in carpetas.items()
                                 for x in xs if (c["id"], pid, x["nombre"]) in self.analisis]}

    def locales_de(self, pid: str) -> dict:
        with self.lock:
            compus = []
            for c in sorted(self.compus.values(), key=lambda c: c["slot"]):
                loc = self.locales.get(c["id"]) or {}
                compus.append({"id": c["id"], "nombre": c["nombre"], "viva": self.viva(c), "ruta": loc.get("ruta", ""),
                               "carpeta": next((k for k in (loc.get("carpetas") or {}) if k == pid), None) is not None,
                               "clips": (loc.get("carpetas") or {}).get(pid, [])})
            return {"compus": compus}

    def resumen_locales(self) -> dict:
        with self.lock:
            return {cid: {"ruta": loc.get("ruta", ""), "lugares": loc.get("lugares", []),
                          "carpetas": {pid: len(xs) for pid, xs in loc.get("carpetas", {}).items()},
                          "muestra": {pid: [x["nombre"] for x in xs[:6]] for pid, xs in loc.get("carpetas", {}).items()}}
                    for cid, loc in self.locales.items()}

    def pedir_carpeta(self, cid: str) -> dict:
        c = self.compus.get(cid)
        if not c:
            return {"error": "Esa compu no está en la sala."}
        if not self.viva(c):
            return {"error": f"{c['nombre']} está apagada: préndela y vuelve a intentar."}
        pid = uuid.uuid4().hex[:8]
        with self.lock:
            self.pedidos_carpeta = {k: v for k, v in self.pedidos_carpeta.items() if time.time() - v["t"] < 600}
            self.pedidos_carpeta[pid] = {"compu": cid, "estado": "nuevo", "ruta": "", "error": "", "t": time.time()}
        return {"ok": True, "id": pid}

    def carpeta_elegida(self, c: dict, d: dict) -> dict:
        x = self.pedidos_carpeta.get(str(d.get("id", "")))
        if not x or x["compu"] != c["id"]:
            return {"error": "Ese pedido ya no existe."}
        if d.get("estado") == "abierta":  # la compu ya abrió la ventana (todavía no eliges)
            x["estado"] = "abierta"
            return {"ok": True}
        x.update(estado="elegida" if d.get("ruta") else "cancelada", ruta=str(d.get("ruta") or "")[:300],
                 error=str(d.get("error") or "")[:200])
        return {"ok": True}

    @staticmethod
    def _soltar(c: dict, tid: str) -> None:
        """La compu ya no trae ese trabajo (en su carril normal o en el del cel)."""
        if c.get("trabajo") == tid:
            c["trabajo"] = None
        if c.get("trabajo_cel") == tid:
            c["trabajo_cel"] = None
        if tid in (c.get("activos") or []):
            c["activos"] = [x for x in c["activos"] if x != tid]

    def del_compu(self, c: dict, tid: str) -> dict | None:
        t = self.trabajos.get(tid)
        return t if t and t.get("compu") == c["id"] and t["estado"] in ("asignado", "trabajando") else None

    def avance(self, c: dict, tid: str, d: dict) -> dict:
        with self.lock:
            t = self.del_compu(c, tid)
            if not t:
                return {"error": "Ese trabajo ya no es tuyo (se canceló).", "cancelado": True}
            paso, av = str(d.get("paso", ""))[:120], max(0.0, min(1.0, float(d.get("avance") or 0)))
            if paso != t.get("paso") or abs(av - (t.get("avance") or 0)) > 0.0005:
                t["mov"] = time.time()  # último momento en que se movió (para saber si se trabó)
            t.update(estado="trabajando", paso=paso, avance=av)
            c["ultimo"] = time.time()
            self._tocar()
        return {"ok": True}

    def subir(self, c: dict, tid: str, nombre: str, entrada, largo: int, desde: int | None = None, fin: bool = True) -> dict:
        """El resultado de una compu. Con `desde` va por pedazos: si se corta, se retoma donde se quedó (`recibido`)."""
        t = self.del_compu(c, tid)
        if not t:
            return {"error": "Ese trabajo ya no es tuyo."}
        nombre = Path(nombre).name
        if Path(nombre).suffix.lower() not in EXT_RESULTADO or not nombre.replace(".", "").replace("_", "").replace("-", "").isalnum():
            return {"error": "Nombre de archivo no permitido."}
        destino = Path(t["salida"]) / nombre
        temporal = destino.with_name(destino.name + ".subiendo")
        destino.parent.mkdir(parents=True, exist_ok=True)
        if desde is not None:  # 🧩 por pedazos
            with self.lock:
                c["ultimo"] = time.time()
            ya = temporal.stat().st_size if temporal.exists() else 0
            if desde < 0:  # solo pregunta cuánto ya llegó
                return {"ok": True, "recibido": ya}
            if desde != ya:
                return {"error": "desfase", "recibido": ya}
            if largo < 0 or ya + largo > MAX_RESULTADO:
                return {"error": "Archivo demasiado grande."}
            restante = largo
            with open(temporal, "ab") as f:
                while restante > 0:
                    trozo = entrada.read(min(1024 * 1024, restante))
                    if not trozo:
                        break
                    f.write(trozo)
                    restante -= len(trozo)
            if restante:  # se cortó a medio pedazo: se regresa a donde iba (el pedazo se vuelve a mandar)
                with open(temporal, "r+b") as f:
                    f.truncate(ya)
                return {"error": "La subida se cortó.", "recibido": ya}
            with self.lock:  # cada pedazo cuenta como avance (así nadie cree que se trabó mientras sube)
                t["paso"], t["mov"] = f"Subiendo {nombre}: {round((ya + largo) / 1e6)} MB", time.time()
                self._tocar()
            if fin:
                temporal.replace(destino)
                return {"ok": True, "recibido": destino.stat().st_size, "listo": True}
            return {"ok": True, "recibido": ya + largo}
        if largo <= 0 or largo > MAX_RESULTADO:
            return {"error": "Archivo demasiado grande."}
        restante = largo
        with open(temporal, "wb") as f:
            while restante > 0:
                trozo = entrada.read(min(1024 * 1024, restante))
                if not trozo:
                    break
                f.write(trozo)
                restante -= len(trozo)
        if restante:
            temporal.unlink(missing_ok=True)
            return {"error": "La subida se cortó."}
        temporal.replace(destino)
        return {"ok": True}

    def terminar(self, c: dict, tid: str, d: dict) -> dict:
        with self.lock:
            t = self.del_compu(c, tid)
            if not t:
                return {"error": "Ese trabajo ya no es tuyo."}
            if d.get("ok"):
                t.update(estado="listo", resultado=d.get("resultado") or {}, avance=1, paso="Listo", fin=time.time())
                c["editados"] = c.get("editados", 0) + 1
            else:
                t.update(estado="error", error=str(d.get("error") or "Falló en la compu.")[:300], fin=time.time())
            self._soltar(c, tid)
            self._tocar()
        if t.get("proyecto"):
            self.termino_trabajo(t)
        return {"ok": True}

    def clasificar(self, c: dict, tid: str, d: dict) -> dict:
        """La compu necesita a Claude (para el video completo): lo pide la oficina dueña del trabajo, que lleva el gasto."""
        t = self.del_compu(c, tid)
        if not t or not t.get("clasificar"):
            return {"error": "Ese trabajo ya no es tuyo."}
        try:
            return requests.post(t["clasificar"], json=d, timeout=120).json()
        except (requests.RequestException, ValueError) as exc:
            return {"error": f"No pude preguntarle a la oficina: {exc}"[:200]}


def crear_servidor(sala: Sala, puerto: int) -> ThreadingHTTPServer:
    class Manejador(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _json(self, datos, codigo=200):
            cuerpo = json.dumps(datos, ensure_ascii=False).encode()
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def _datos(self) -> dict:
            try:
                return json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            except (json.JSONDecodeError, ValueError):
                return {}

        def _compu(self):
            c = sala.autenticar(self.headers.get("X-Compu-Token", ""))
            if not c:
                time.sleep(1)
                self._json({"error": "Esta compu no está dada de alta (o la quitaste). Vuelve a instalarla con un código nuevo.",
                            "sin_alta": True}, 401)
            return c

        def _mandar(self, ruta: Path):
            tam = ruta.stat().st_size
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(tam))
            self.send_header("Content-Disposition", f'attachment; filename="{ruta.name}"')
            self.end_headers()
            with open(ruta, "rb") as f:
                try:
                    while trozo := f.read(1024 * 1024):
                        self.wfile.write(trozo)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        def do_GET(self):
            url = urlparse(self.path)
            ruta = unquote(url.path)
            if ruta.startswith("/sala/api/maquina/"):  # el servidor-compu entra directo (sin pasar por el edificio)
                ruta = ruta[len("/sala"):]
            if ruta == "/api/estilo":
                return self._json(sala.ver_estilo())
            if ruta == "/api/estado":
                return self._json(sala.snapshot())
            if ruta.startswith("/descargar/"):
                archivo = (DESCARGAS / Path(ruta).name).resolve()
                if archivo.is_relative_to(DESCARGAS.resolve()) and archivo.is_file():
                    return self._mandar(archivo)
                return self._json({"error": "no encontrado"}, 404)
            if ruta.startswith("/api/proyecto/"):
                r = sala.detalle_proyecto(ruta.rsplit("/", 1)[-1])
                return self._json(r, 200 if r.get("id") else 404)
            if ruta.startswith("/salida/"):
                return self._archivo(ruta[len("/salida/"):])
            if ruta.startswith("/api/elegir_carpeta/"):
                x = sala.pedidos_carpeta.get(ruta.rsplit("/", 1)[-1])
                if not x:
                    return self._json({"estado": "cancelada", "ruta": "", "error": ""})
                c = sala.compus.get(x["compu"]) or {}
                return self._json({**{k: x[k] for k in ("estado", "ruta", "error")}, "segundos": round(time.time() - x["t"]),
                                   "editando": bool(c.get("trabajo")), "version": c.get("version", "")})
            if ruta.startswith("/api/locales/"):
                return self._json(sala.locales_de(ruta.rsplit("/", 1)[-1]))
            if ruta.startswith("/api/miniatura/"):
                partes = ruta.split("/")
                jpg = sala.miniaturas.get((partes[3], partes[4], "/".join(partes[5:]))) if len(partes) >= 6 else None
                if not jpg:
                    return self._json({"error": "no encontrado"}, 404)
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(jpg)))
                self.send_header("Cache-Control", "max-age=300")
                self.end_headers()
                return self.wfile.write(jpg)
            if ruta == "/interno/disponible":
                tipo = parse_qs(url.query).get("tipo", ["cris"])[0]
                return self._json({"compus": sala.disponibles(tipo), "libres": sala.libres(tipo)})
            if ruta.startswith("/interno/trabajo/"):
                return self._json(sala.ver(ruta.rsplit("/", 1)[-1]))
            if ruta.startswith("/api/maquina/archivo/"):
                c = self._compu()
                if not c:
                    return
                _, tid, n = ruta.rsplit("/", 2)
                t = sala.del_compu(c, tid)
                if not t or not n.isdigit() or int(n) >= len(t["entradas"]):
                    return self._json({"error": "no encontrado"}, 404)
                return self._mandar(Path(t["entradas"][int(n)]))
            self._json({"error": "no encontrado"}, 404)

        def _archivo(self, relativa: str):
            """Versiones terminadas de tus proyectos (con rangos, para adelantar el video)."""
            base = (AQUI / "salida").resolve()
            ruta = (base / relativa).resolve()
            if not ruta.is_relative_to(base) or not ruta.is_file() or "clips" in ruta.parts:
                return self._json({"error": "no encontrado"}, 404)
            tam = ruta.stat().st_size
            ini, fin = 0, tam - 1
            rango = self.headers.get("Range", "")
            if rango.startswith("bytes="):
                a, _, b = rango[6:].partition("-")
                ini = int(a) if a else max(0, tam - int(b or 0))
                fin = min(tam - 1, int(b)) if a and b else tam - 1
                self.send_response(206)
                self.send_header("Content-Range", f"bytes {ini}-{fin}/{tam}")
            else:
                self.send_response(200)
            self.send_header("Content-Type", "video/mp4" if ruta.suffix == ".mp4" else "image/jpeg")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(fin - ini + 1))
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

        def do_POST(self):
            url = urlparse(self.path)
            ruta = unquote(url.path)
            if ruta.startswith("/sala/api/maquina/"):
                ruta = ruta[len("/sala"):]
            if ruta == "/api/subir":  # tus clips para un proyecto (desde la oficina, con tu contraseña)
                if "application/octet-stream" not in self.headers.get("Content-Type", ""):
                    return self._json({"error": "tipo no permitido"}, 403)
                q = parse_qs(url.query)
                r = sala.subir_clip(q.get("proyecto", [""])[0], q.get("nombre", ["clip.mp4"])[0], self.rfile,
                                    int(self.headers.get("Content-Length") or 0))
                return self._json(r, 400 if "error" in r else 200)
            if ruta.startswith("/api/maquina/subir/"):
                c = self._compu()
                if not c:
                    return
                if "application/octet-stream" not in self.headers.get("Content-Type", ""):
                    return self._json({"error": "tipo no permitido"}, 403)
                q = parse_qs(url.query)
                desde = q.get("desde", [None])[0]
                r = sala.subir(c, ruta.rsplit("/", 1)[-1], q.get("nombre", [""])[0], self.rfile,
                               int(self.headers.get("Content-Length") or 0),
                               int(desde) if desde not in (None, "") else None, q.get("fin", ["1"])[0] == "1")
                return self._json(r, 400 if "error" in r else 200)
            if "application/json" not in self.headers.get("Content-Type", ""):
                return self._json({"error": "tipo no permitido"}, 403)
            d = self._datos()
            # el edificio (con tu contraseña)
            if ruta == "/api/codigo":
                return self._json(sala.nuevo_codigo())
            if ruta == "/api/proyecto":
                r = sala.crear_proyecto(str(d.get("nombre", "")), str(d.get("donde", "")), ruta=str(d.get("ruta", ""))[:300])
                return self._json(r, 400 if "error" in r else 200)
            if ruta.startswith("/api/proyecto/") and ruta.endswith("/carpeta"):
                r = sala.usar_carpeta(ruta.split("/")[3], str(d.get("compu", "")), str(d.get("ruta", ""))[:300])
                return self._json(r, 400 if "error" in r else 200)
            if ruta == "/api/estilo":
                return self._json(sala.editar_estilo(d))
            if ruta.startswith("/api/proyecto/") and ruta.endswith("/calificar"):
                try:
                    n = int(d.get("version") or 0)
                except (TypeError, ValueError):
                    n = 0
                r = sala.calificar(ruta.split("/")[3], n, str(d.get("voto", "")), str(d.get("comentario", "")))
                return self._json(r, 400 if "error" in r else 200)
            if ruta == "/api/trabajos/limpiar":  # 🧹 quitar de la lista los trabajos terminados
                with sala.lock:
                    for tid in [k for k, t in sala.trabajos.items() if t["estado"] in ("listo", "error", "cancelado")]:
                        sala.trabajos.pop(tid, None)
                    sala._tocar()
                return self._json({"ok": True})
            if ruta.startswith("/api/proyecto/") and ruta.endswith("/borrar"):
                r = sala.borrar_proyecto(ruta.split("/")[3])
                return self._json(r, 400 if "error" in r else 200)
            if ruta == "/api/elegir_carpeta":
                r = sala.pedir_carpeta(str(d.get("compu", "")))
                return self._json(r, 400 if "error" in r else 200)
            if ruta == "/api/chat":
                r = sala.mensaje(str(d.get("proyecto") or "") or None, str(d.get("texto", "")))
                return self._json(r, 400 if "error" in r else 200)
            if ruta == "/api/ajustes":  # ⚙️ oficina central: usar también el servidor
                return self._json(sala.ajustar(d))
            if ruta == "/api/reinicio":  # 🔄 reinicio forzoso de lo trabado
                return self._json(sala.reinicio(float(d.get("minutos") or 10)))
            if ruta.startswith("/api/quitar/"):
                r = sala.quitar(ruta.rsplit("/", 1)[-1])
                return self._json(r, 400 if "error" in r else 200)
            # las oficinas, desde el mismo servidor
            if ruta == "/interno/trabajo":
                r = sala.crear(d)
                return self._json(r, 400 if "error" in r else 200)
            if ruta.startswith("/interno/cancelar/"):
                return self._json(sala.cancelar(ruta.rsplit("/", 1)[-1]))
            # tus compus (con su llave)
            if ruta == "/api/maquina/vincular":
                r = sala.vincular(d)
                if "error" in r:
                    time.sleep(1)
                return self._json(r, 400 if "error" in r else 200)
            if ruta.startswith("/api/maquina/"):
                c = self._compu()
                if not c:
                    return
                partes = ruta.split("/")
                accion, tid = partes[3], (partes[4] if len(partes) > 4 else "")
                if accion == "latido":
                    r = sala.latido(c, d)
                    if d.get("con_carpetas"):  # versión que maneja carpetas: le decimos a qué productos hacerles una
                        r["carpetas"] = sala.carpetas_pedidas()
                        r["proyectos"] = sala.carpetas_de_proyectos(c["id"])
                    return self._json(r)
                if accion == "carpetas":
                    return self._json(sala.reportar_carpetas(c, d))
                if accion == "carpeta_elegida":
                    return self._json(sala.carpeta_elegida(c, d))
                if accion == "avance":
                    return self._json(sala.avance(c, tid, d))
                if accion == "terminar":
                    return self._json(sala.terminar(c, tid, d))
                if accion in ("clasificar", "robot"):  # robot = el siguiente toque del robot del cel (lo decide la oficina)
                    return self._json(sala.clasificar(c, tid, d))
            self._json({"error": "no encontrado"}, 404)

    return ThreadingHTTPServer(("127.0.0.1", puerto), Manejador)


PUERTO = 8767


def main() -> None:
    global ESTADO, TIENDA_URL
    a = argparse.ArgumentParser(description="Sala de edición (tus compus editan en lugar del servidor)")
    a.add_argument("--demo", action="store_true")
    a.add_argument("--puerto", type=int, default=8767)
    a.add_argument("--tienda", default="http://127.0.0.1:8766")
    args = a.parse_args()
    TIENDA_URL = args.tienda.rstrip("/")
    if args.demo:
        ESTADO = AQUI / "sala_estado_demo.json"
    global PUERTO
    PUERTO = args.puerto
    sala = Sala(args.demo)
    threading.Thread(target=sala.vigilar, daemon=True).start()
    threading.Thread(target=sala.vigilar_servidor, daemon=True).start()
    if not args.demo:  # Claude: el gasto de la sala va en su propio contador, con el mismo tope diario
        from agentes import claude as ia
        from agentes import config
        tope = float(config.env("LIMITE_DIARIO", "1") or 0)
        ia.al_gastar = sala._gastar

        def revisar_tope():
            if tope and sala.gasto.get(time.strftime("%Y-%m-%d"), 0) >= tope:
                raise ia.ErrorIA(f"Se llegó al tope de gasto de hoy de la sala (${tope:.2f}).")
        ia.antes_de_llamar = revisar_tope
    servidor = crear_servidor(sala, args.puerto)
    print(f"🎬 Sala de edición en http://127.0.0.1:{args.puerto}" + ("  (modo demo)" if args.demo else ""), flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nSala de edición cerrada.")


if __name__ == "__main__":
    main()
