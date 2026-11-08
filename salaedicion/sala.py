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
sys.path.insert(0, str(REPO / "autocanal"))

import requests  # noqa: E402

ESTADO = AQUI / "sala_estado.json"
DESCARGAS = AQUI / "windows"
VIVA = 30  # segundos sin noticias para dar una compu por apagada
CODIGO_DURA = 15 * 60
RAICES = [REPO / "tiktokshop" / "salida", REPO / "autocanal" / "salida"]  # de dónde se pueden mandar clips
EXT_RESULTADO = {".mp4", ".jpg", ".json"}
MAX_RESULTADO = 2 * 1024 ** 3


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class Sala:
    def __init__(self, demo: bool):
        self.demo = demo
        self.lock = threading.RLock()
        self.version = 0
        datos = json.loads(ESTADO.read_text(encoding="utf-8")) if ESTADO.exists() else {}
        self.compus: dict = datos.get("compus", {})
        self.trabajos: dict = datos.get("trabajos", {})
        self.codigos: dict = {}  # código → vence
        self.intentos: list[float] = []
        for t in self.trabajos.values():  # lo que quedó a medias al apagar: lo vuelve a pedir la oficina
            if t["estado"] in ("en_cola", "asignado", "trabajando"):
                t["estado"], t["error"] = "cancelado", "La sala se reinició."
        for c in self.compus.values():
            c["trabajo"] = None

    def _tocar(self) -> None:
        self.version += 1
        viejos = sorted(self.trabajos.values(), key=lambda t: t["creado"])[:-80]
        for t in viejos:
            self.trabajos.pop(t["id"], None)
        ESTADO.write_text(json.dumps({"compus": self.compus, "trabajos": self.trabajos}, ensure_ascii=False, indent=1),
                          encoding="utf-8")

    # ---------- lo que se ve en el edificio ----------
    def viva(self, c: dict) -> bool:
        return time.time() - c.get("ultimo", 0) < VIVA

    def snapshot(self) -> dict:
        with self.lock:
            compus = []
            for c in sorted(self.compus.values(), key=lambda c: c["slot"]):
                t = self.trabajos.get(c.get("trabajo") or "")
                compus.append({k: c.get(k) for k in ("id", "nombre", "slot", "gpu", "sistema", "version", "ultimo",
                                                     "nvenc", "oido", "editados")}
                              | {"viva": self.viva(c),
                                 "trabajo": {k: t.get(k) for k in ("id", "etiqueta", "origen", "paso", "avance")} if t else None})
            trabajos = [{k: t.get(k) for k in ("id", "tipo", "origen", "etiqueta", "estado", "compu", "creado", "inicio",
                                                "fin", "error", "paso", "avance")}
                        for t in sorted(self.trabajos.values(), key=lambda t: -t["creado"])[:15]]
            return {"version": self.version, "demo": self.demo, "ahora": time.time(), "compus": compus, "trabajos": trabajos}

    # ---------- dar de alta una compu ----------
    def nuevo_codigo(self) -> dict:
        codigo = f"{secrets.randbelow(1_000_000):06d}"
        with self.lock:
            ahora = time.time()
            self.codigos = {k: v for k, v in self.codigos.items() if v > ahora}
            self.codigos[codigo] = ahora + CODIGO_DURA
        return {"codigo": codigo, "vence": ahora + CODIGO_DURA}

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
            t = self.trabajos.get(c.get("trabajo") or "")
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
        t = {"id": uuid.uuid4().hex[:10], "tipo": str(d.get("tipo", "cris")), "origen": str(d.get("origen", "")),
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
                    c["trabajo"] = None
                self._tocar()
            return {k: t.get(k) for k in ("id", "estado", "paso", "avance", "error", "resultado", "slot")} | {
                "compu": c["nombre"] if c else None}

    def cancelar(self, tid: str) -> dict:
        with self.lock:
            t = self.trabajos.get(tid)
            if t and t["estado"] not in ("listo", "error"):
                t.update(estado="cancelado", fin=time.time())
                c = self.compus.get(t.get("compu") or "")
                if c and c.get("trabajo") == tid:
                    c["trabajo"] = None
                self._tocar()
        return {"ok": True}

    # ---------- lo que hacen tus compus ----------
    def latido(self, c: dict, d: dict) -> dict:
        """La compu avisa que está prendida y pregunta si hay trabajo."""
        with self.lock:
            c.update(ultimo=time.time(), gpu=str(d.get("gpu") or c.get("gpu") or "")[:60],
                     version=str(d.get("version") or "")[:12], nvenc=bool(d.get("nvenc")), oido=str(d.get("oido") or "")[:40],
                     tipos=[x for x in (d.get("tipos") or ["cris"]) if isinstance(x, str)][:5])
            actual = self.trabajos.get(c.get("trabajo") or "")
            if actual and actual["estado"] in ("asignado", "trabajando"):
                return {"trabajo": self._para_compu(actual)}
            c["trabajo"] = None
            libre = d.get("libre", True)
            pendiente = next((t for t in sorted(self.trabajos.values(), key=lambda t: t["creado"])
                              if t["estado"] == "en_cola" and t["tipo"] in c["tipos"]), None) if libre else None
            if pendiente:
                pendiente.update(estado="asignado", compu=c["id"], slot=c["slot"], inicio=time.time(), paso="Bajando tus clips")
                c["trabajo"] = pendiente["id"]
            self._tocar()
            return {"trabajo": self._para_compu(pendiente) if pendiente else None}

    def _para_compu(self, t: dict) -> dict:
        return {"id": t["id"], "tipo": t["tipo"], "etiqueta": t["etiqueta"], "parametros": t["parametros"],
                "entradas": [{"n": i, "nombre": Path(e).name, "bytes": Path(e).stat().st_size if Path(e).exists() else 0}
                             for i, e in enumerate(t["entradas"])]}

    def del_compu(self, c: dict, tid: str) -> dict | None:
        t = self.trabajos.get(tid)
        return t if t and t.get("compu") == c["id"] and t["estado"] in ("asignado", "trabajando") else None

    def avance(self, c: dict, tid: str, d: dict) -> dict:
        with self.lock:
            t = self.del_compu(c, tid)
            if not t:
                return {"error": "Ese trabajo ya no es tuyo (se canceló).", "cancelado": True}
            t.update(estado="trabajando", paso=str(d.get("paso", ""))[:120], avance=max(0.0, min(1.0, float(d.get("avance") or 0))))
            c["ultimo"] = time.time()
            self._tocar()
        return {"ok": True}

    def subir(self, c: dict, tid: str, nombre: str, entrada, largo: int) -> dict:
        t = self.del_compu(c, tid)
        if not t:
            return {"error": "Ese trabajo ya no es tuyo."}
        nombre = Path(nombre).name
        if Path(nombre).suffix.lower() not in EXT_RESULTADO or not nombre.replace(".", "").replace("_", "").replace("-", "").isalnum():
            return {"error": "Nombre de archivo no permitido."}
        if largo <= 0 or largo > MAX_RESULTADO:
            return {"error": "Archivo demasiado grande."}
        destino = Path(t["salida"]) / nombre
        temporal = destino.with_name(destino.name + ".subiendo")
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
            c["trabajo"] = None
            self._tocar()
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
            if ruta == "/api/estado":
                return self._json(sala.snapshot())
            if ruta.startswith("/descargar/"):
                archivo = (DESCARGAS / Path(ruta).name).resolve()
                if archivo.is_relative_to(DESCARGAS.resolve()) and archivo.is_file():
                    return self._mandar(archivo)
                return self._json({"error": "no encontrado"}, 404)
            if ruta == "/interno/disponible":
                return self._json({"compus": sala.disponibles(parse_qs(url.query).get("tipo", ["cris"])[0])})
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

        def do_POST(self):
            url = urlparse(self.path)
            ruta = unquote(url.path)
            if ruta.startswith("/api/maquina/subir/"):
                c = self._compu()
                if not c:
                    return
                if "application/octet-stream" not in self.headers.get("Content-Type", ""):
                    return self._json({"error": "tipo no permitido"}, 403)
                r = sala.subir(c, ruta.rsplit("/", 1)[-1], parse_qs(url.query).get("nombre", [""])[0], self.rfile,
                               int(self.headers.get("Content-Length") or 0))
                return self._json(r, 400 if "error" in r else 200)
            if "application/json" not in self.headers.get("Content-Type", ""):
                return self._json({"error": "tipo no permitido"}, 403)
            d = self._datos()
            # el edificio (con tu contraseña)
            if ruta == "/api/codigo":
                return self._json(sala.nuevo_codigo())
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
                    return self._json(sala.latido(c, d))
                if accion == "avance":
                    return self._json(sala.avance(c, tid, d))
                if accion == "terminar":
                    return self._json(sala.terminar(c, tid, d))
                if accion == "clasificar":
                    return self._json(sala.clasificar(c, tid, d))
            self._json({"error": "no encontrado"}, 404)

    return ThreadingHTTPServer(("127.0.0.1", puerto), Manejador)


def main() -> None:
    global ESTADO
    a = argparse.ArgumentParser(description="Sala de edición (tus compus editan en lugar del servidor)")
    a.add_argument("--demo", action="store_true")
    a.add_argument("--puerto", type=int, default=8767)
    args = a.parse_args()
    if args.demo:
        ESTADO = AQUI / "sala_estado_demo.json"
    servidor = crear_servidor(Sala(args.demo), args.puerto)
    print(f"🎬 Sala de edición en http://127.0.0.1:{args.puerto}" + ("  (modo demo)" if args.demo else ""), flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nSala de edición cerrada.")


if __name__ == "__main__":
    main()
