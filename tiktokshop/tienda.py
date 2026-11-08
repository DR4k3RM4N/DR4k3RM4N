"""Oficina de TikTok Shop: el ala derecha del edificio.

    python tienda.py           # usa Claude y Google (las mismas claves de autocanal/.env)
    python tienda.py --demo    # simulación sin APIs

Solo escucha en 127.0.0.1: se entra por el edificio (la oficina de YouTube la conecta en /tiktok/,
con la misma contraseña). Tiene su propio estado, su propio gasto y su propio tope diario.
Configuración propia (opcional) en tiktokshop/.env; lo que no esté ahí se toma de autocanal/.env.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import shutil
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from zoneinfo import ZoneInfo

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent / "autocanal"))
try:  # primero el .env propio; agentes/config.py completa con el de autocanal sin pisarlo
    from dotenv import load_dotenv
    load_dotenv(AQUI / ".env")
except ImportError:  # pragma: no cover
    pass

from agentes import claude as ia  # noqa: E402
from agentes import config  # noqa: E402

import requests  # noqa: E402

import cris  # noqa: E402
import shop  # noqa: E402

ESTADO = AQUI / "tienda_estado.json"
ZONA = config.env("IDEAS_ZONA", "America/Mexico_City")
LIMITE_DIARIO = float(config.env("LIMITE_DIARIO", "1") or 0)
SALA_URL = config.env("SALA_URL", "http://127.0.0.1:8767").rstrip("/")  # sala de edición (tus compus)
PUERTO = 8766

EQUIPO = [
    # id, nombre, rol, color, peinado, qué hace
    ("tt_cazador", "Toño", "Cazador de productos", "#0ea5e9", "corto", "Busca el producto en Google: precio, reseñas y la duda que frena la compra. Solo guarda datos con enlace."),
    ("tt_guionista", "Sofi", "Guionista de Shop", "#f43f5e", "largo", "Escribe guiones que venden: 3 ganchos, cuerpo, caption, hashtags y comentario fijado."),
    ("tt_director", "Diego", "Director de grabación", "#a3e635", "rizos", "Te arma la lista de tomas para grabar todo en una sola sesión con tu celular."),
    ("tt_editor", "Cris", "Editor vertical", "#f97316", "copete", "Edita tus clips en vertical: los ordena según el guion, quita silencios, cortes rápidos, textos y subtítulos karaoke con tu voz."),
    ("tt_disenadora", "Vale", "Diseñadora de portadas", "#d946ef", "bob", "Saca la portada de un cuadro de tu video con el texto del gancho, para que se vea chida en tu perfil."),
    ("tt_analista", "Ana", "Analista de ventas", "#22c55e", "chongo", "Lee lo que vendió cada video y le dice al equipo qué repetir. (Llega en el paso 4.)"),
]
ETAPAS = [("ficha", "tt_cazador"), ("guion", "tt_guionista"), ("tomas", "tt_director")]
ACCION = {"ficha": "Investigar el producto", "guion": "Escribir el guion con 3 ganchos", "tomas": "Armar la lista de tomas",
          "video": "Editar tu video vertical", "portada": "Hacer la portada"}
MAX_SUBIDA = 1536 * 1024 * 1024  # 1.5 GB por clip
FRASES = {
    "tt_cazador": ["Buscando reseñas reales…", "¿Cuánto cuesta en otras tiendas?", "¿Qué duda tiene la gente?"],
    "tt_guionista": ["Probando ganchos…", "¿Problema → solución o antes y después?", "Puliendo el caption…"],
    "tt_director": ["Ordenando tomas por lugar…", "Close-up de manos aquí…", "Que se entienda sin sonido…"],
    "tt_editor": ["Escuchando tus clips…", "Quitando silencios…", "Cortes cada 2 segundos…", "Subtítulos karaoke…"],
    "tt_disenadora": ["Buscando el mejor cuadro…", "Más grande el texto…"],
}
ACTIVAS = ("esperando", "trabajando")


class Tienda:
    def __init__(self, demo: bool):
        self.demo = demo
        self.lock = threading.RLock()
        self.version = 0
        self.agentes = {
            i: {"id": i, "nombre": n, "rol": r, "color": c, "pelo": p, "desc": d, "lentes": i == "tt_editor",
                "estado": "libre", "ubicacion": "casa", "dice": "", "dice_t": 0}
            for i, n, r, c, p, d in EQUIPO
        }
        datos = json.loads(ESTADO.read_text(encoding="utf-8")) if ESTADO.exists() else {}
        self.productos: dict = datos.get("productos", {})
        self.tareas: list = datos.get("tareas", [])
        self.log: list = datos.get("log", [])
        self.gasto: dict = datos.get("gasto", {})
        for p in self.productos.values():  # lo que quedó a medias al apagar
            if p["estado"] == "trabajando":
                p["estado"], p["error"] = "error", "Se interrumpió al apagar la oficina. Dale Reintentar."
                for e, v in p["etapas"].items():
                    if v == "trabajando":
                        p["etapas"][e] = "fallo"
        for t in self.tareas:
            if t["estado"] in ACTIVAS:
                t["estado"], t["error"] = "cancelada", "Se interrumpió al apagar la oficina."
        ia.al_gastar = self._gastar
        ia.antes_de_llamar = self._revisar_tope

    # ---------- estado ----------
    def _tocar(self) -> None:
        self.version += 1
        ESTADO.write_text(json.dumps({"productos": self.productos, "tareas": self.tareas[-200:],
                                      "log": self.log[-200:], "gasto": dict(sorted(self.gasto.items())[-120:])},
                                     ensure_ascii=False, indent=1), encoding="utf-8")

    def _hoy(self) -> str:
        return dt.datetime.now(ZoneInfo(ZONA)).date().isoformat()

    def resumen_gasto(self) -> dict:
        hoy = self._hoy()
        return {"hoy": round(self.gasto.get(hoy, 0), 4),
                "mes": round(sum(v for k, v in self.gasto.items() if k.startswith(hoy[:7])), 4), "tope": LIMITE_DIARIO}

    def snapshot(self) -> dict:
        """Lo que se ve en el edificio (sin el guion completo: ese se pide aparte)."""
        with self.lock:
            productos = []
            for p in sorted(self.productos.values(), key=lambda x: -x["creado"]):
                productos.append({k: p.get(k) for k in ("id", "nombre", "estado", "etapas", "error", "costo", "creado",
                                                         "de_marca", "duracion", "enlace", "precio", "gancho")}
                                 | {"formato": (p.get("guion") or {}).get("formato"),
                                    "guion_id": (p.get("guion") or {}).get("id"),
                                    "videos": len(p.get("videos") or []),
                                    "clips": len((p.get("clips") or {}).get("tomas", {})) + bool((p.get("clips") or {}).get("completo"))})
            return {"version": self.version, "demo": self.demo, "ahora": time.time(),
                    "agentes": list(self.agentes.values()), "productos": productos,
                    "tareas": [t for t in self.tareas[-120:] if t["estado"] in ACTIVAS]
                              + [t for t in self.tareas[-120:] if t["estado"] not in ACTIVAS][-40:],
                    "log": self.log[-30:], "gasto": self.resumen_gasto()}

    def decir(self, agente: str, texto: str) -> None:
        with self.lock:
            self.agentes[agente].update(dice=texto, dice_t=time.time())
            self.log.append({"t": time.time(), "quien": agente, "texto": texto})
            self._tocar()

    def poner(self, agente: str, **campos) -> None:
        with self.lock:
            self.agentes[agente].update(campos)
            self._tocar()

    # ---------- gasto ----------
    def _revisar_tope(self) -> None:
        if LIMITE_DIARIO and self.resumen_gasto()["hoy"] >= LIMITE_DIARIO:
            raise ia.ErrorIA(f"Se alcanzó el tope de gasto de hoy de la oficina de TikTok (${LIMITE_DIARIO:.2f}). "
                             "Dale Rehacer mañana o sube LIMITE_DIARIO en tiktokshop/.env.")

    def _gastar(self, proyecto, etapa, modelo, usd, entrada, salida, que: str = "") -> None:
        with self.lock:
            dia = self._hoy()
            self.gasto[dia] = self.gasto.get(dia, 0) + usd
            t = getattr(ia.contexto, "tarea", None)
            if t is not None:
                t["costo"] = t.get("costo", 0) + usd
                t["modelo"] = modelo
                t.setdefault("llamadas", []).append({"que": que or etapa, "modelo": modelo, "costo": usd,
                                                     "entrada": entrada, "salida": salida})
            p = self.productos.get(proyecto) if proyecto else None
            if p is not None:
                p["costo"] = p.get("costo", 0) + usd
            self._tocar()

    # ---------- productos ----------
    def nuevo_producto(self, d: dict) -> dict:
        nombre = str(d.get("nombre", "")).strip()[:120]
        if len(nombre) < 2:
            return {"error": "Ponle nombre al producto."}
        enlace = str(d.get("enlace", "")).strip()[:500]
        if enlace and not enlace.startswith(("http://", "https://")):
            return {"error": "El enlace debe empezar con https://"}
        p = {"id": f"{self._hoy()}_{shop.slug(nombre, 30)}_{uuid.uuid4().hex[:4]}", "nombre": nombre, "enlace": enlace,
             "precio": str(d.get("precio", "")).strip()[:20], "comision": str(d.get("comision", "")).strip()[:10],
             "notas": str(d.get("notas", "")).strip()[:1500], "de_marca": bool(d.get("de_marca", True)),
             "duracion": d.get("duracion") if d.get("duracion") in ("normal", "corta") else "auto",
             "estado": "trabajando", "etapas": {e: "pendiente" for e, _ in ETAPAS}, "creado": time.time(),
             "costo": 0, "error": None}
        with self.lock:
            self.productos[p["id"]] = p
            self._tocar()
        threading.Thread(target=self._producir, args=(p["id"], "ficha"), daemon=True).start()
        return {"ok": True, "id": p["id"]}

    def accion(self, pid: str, accion: str, desde: str = "") -> dict:
        p = self.productos.get(pid)
        if not p:
            return {"error": "No encontré ese producto."}
        if accion == "gancho":  # con cuál gancho vas a grabar (o los 3 para probar cuál jala)
            if desde not in ("A", "B", "C", "todos"):
                return {"error": "Gancho inválido."}
            with self.lock:
                p["gancho"] = desde
                self._tocar()
            return {"ok": True}
        if accion == "borrar":
            if p["estado"] == "trabajando":
                return {"error": "Espera a que terminen de trabajar en él."}
            with self.lock:
                del self.productos[pid]
                self._tocar()
            shutil.rmtree(cris.SALIDA / pid, ignore_errors=True)
            return {"ok": True}
        if accion == "quitar_clip":
            clips = p.get("clips") or {}
            archivo = clips.get("completo") if desde == "completo" else clips.get("tomas", {}).get(desde)
            if not archivo:
                return {"error": "Ese clip no está."}
            (cris.SALIDA / pid / "clips" / archivo["archivo"]).unlink(missing_ok=True)
            with self.lock:
                if desde == "completo":
                    clips.pop("completo", None)
                else:
                    clips["tomas"].pop(desde, None)
                self._tocar()
            return {"ok": True}
        if accion == "editar" or (accion == "rehacer" and desde == "video"):
            if p["estado"] == "trabajando":
                return {"error": "Ya están trabajando en él."}
            modo = desde if desde in ("tomas", "completo") else p.get("modo_edicion", "tomas")
            clips = p.get("clips") or {}
            if modo == "completo" and not clips.get("completo"):
                return {"error": "Primero sube tu video completo."}
            if modo == "tomas" and not clips.get("tomas"):
                return {"error": "Primero sube al menos un clip de las tomas."}
            with self.lock:
                p["estado"], p["error"], p["modo_edicion"] = "trabajando", None, modo
                p["etapas"].update(video="pendiente", portada="pendiente")
                self._tocar()
            threading.Thread(target=self._editar, args=(pid,), daemon=True).start()
            return {"ok": True}
        if accion == "rehacer":
            if p["estado"] == "trabajando":
                return {"error": "Ya están trabajando en él."}
            if desde not in ("ficha", "guion", "tomas") and p["etapas"].get("video") == "fallo":
                return self.accion(pid, "editar", p.get("modo_edicion", "tomas"))
            etapas = [e for e, _ in ETAPAS]
            if desde not in etapas:  # desde donde falló, o el guion si todo salió bien
                desde = next((e for e in etapas if p["etapas"].get(e) != "hecha"), "guion")
            with self.lock:
                p["estado"], p["error"] = "trabajando", None
                for e in etapas[etapas.index(desde):]:
                    p["etapas"][e] = "pendiente"
                self._tocar()
            threading.Thread(target=self._producir, args=(pid, desde), daemon=True).start()
            return {"ok": True}
        return {"error": "Acción inválida."}

    def subir(self, pid: str, toma: str, nombre: str, entrada, largo: int) -> dict:
        """Guarda un clip que mandaste desde el cel (va directo al disco, sin llenar la memoria)."""
        p = self.productos.get(pid)
        if not p:
            return {"error": "No encontré ese producto."}
        if not (toma == "completo" or toma.isdigit()):
            return {"error": "¿De qué toma es?"}
        if largo <= 0 or largo > MAX_SUBIDA:
            return {"error": "El clip debe pesar menos de 1.5 GB."}
        if shutil.disk_usage(AQUI).free < largo + 1024 ** 3:
            return {"error": "Ya casi no queda espacio en el servidor. Borra productos viejos y vuelve a intentar."}
        ext = Path(nombre).suffix.lower()
        ext = ext if ext in cris.EXTENSIONES else ".mp4"
        carpeta = cris.SALIDA / pid / "clips"
        carpeta.mkdir(parents=True, exist_ok=True)
        clips = p.setdefault("clips", {"tomas": {}})
        clips.setdefault("tomas", {})
        anterior = clips.get("completo") if toma == "completo" else clips["tomas"].get(toma)
        destino = carpeta / f"{'completo' if toma == 'completo' else f'toma_{int(toma):02d}'}_{uuid.uuid4().hex[:4]}{ext}"
        restante = largo
        with open(destino, "wb") as f:
            while restante > 0:
                trozo = entrada.read(min(1024 * 1024, restante))
                if not trozo:
                    break
                f.write(trozo)
                restante -= len(trozo)
        if restante:
            destino.unlink(missing_ok=True)
            return {"error": "La subida se cortó. Vuelve a intentar."}
        try:
            segundos = round(cris.duracion(destino), 1)
        except cris.ErrorEdicion as exc:
            destino.unlink(missing_ok=True)
            return {"error": str(exc)}
        if anterior:
            (carpeta / anterior["archivo"]).unlink(missing_ok=True)
        info = {"archivo": destino.name, "mb": round(largo / 1024 / 1024, 1), "segundos": segundos, "nombre": nombre[:80]}
        with self.lock:
            if toma == "completo":
                clips["completo"] = info
            else:
                clips["tomas"][toma] = info
            self._tocar()
        return {"ok": True, **info}

    def _editar(self, pid: str) -> None:
        """Cris edita (un video por gancho elegido) y Vale hace la portada de cada uno."""
        p = self.productos[pid]
        g, carpeta = p["guion"], cris.SALIDA / pid
        letras = ["A", "B", "C"] if p.get("gancho", "todos") == "todos" else [p["gancho"]]
        pista = " ".join([*(x["voz"] for x in g["ganchos"]), *(c["voz"] for c in g["cuerpo"])])
        modo = p.get("modo_edicion", "tomas")
        clips = p.get("clips") or {}

        def tarea(etapa, agente):
            t = {"id": uuid.uuid4().hex[:8], "agente": agente, "etapa": etapa, "accion": ACCION[etapa], "proyecto": pid,
                 "titulo": p["nombre"], "estado": "trabajando", "creado": time.time(), "inicio": time.time(),
                 "fin": None, "error": None}
            with self.lock:
                self.tareas.append(t)
                p["etapas"][etapa] = "trabajando"
                self._tocar()
            self.poner(agente, estado="trabajando", ubicacion="casa")
            self.decir(agente, random.choice(FRASES[agente]))
            return t

        def fallo(t, etapa, agente, exc):
            with self.lock:
                t.update(estado="fallo", fin=time.time(), error=str(exc)[:300])
                p["etapas"][etapa] = "fallo"
                p["estado"], p["error"] = "error", str(exc)[:300]
                self._tocar()
            self.poner(agente, estado="libre")
            self.decir(agente, "No pude terminar, jefe. Revisa el mensaje y dale Reintentar.")

        t = tarea("video", "tt_editor")
        ia.contexto.proyecto, ia.contexto.etapa, ia.contexto.tarea = pid, "video", t

        def avance(paso, fraccion):
            with self.lock:
                t.update(paso=paso, avance=round(fraccion, 3))
                self._tocar()

        trabajo = {"guion": g, "tomas": (p.get("tomas") or {}).get("tomas", []), "letras": letras, "modo": modo,
                   "pista": pista, "archivos": {"tomas": {n: c["archivo"] for n, c in clips.get("tomas", {}).items()},
                                                "completo": (clips.get("completo") or {}).get("archivo")}}
        for viejo in [*carpeta.glob("video_*"), *carpeta.glob("portada_*")]:  # que no queden videos de la edición anterior
            viejo.unlink(missing_ok=True)
        videos = self._editar_en_compu(p, t, trabajo, carpeta, avance)  # primero tus compus; si no, el servidor
        try:
            if not videos:
                from agentes import cola_video
                with cola_video.turno("Cris (TikTok Shop)", lambda texto: (avance(texto, 0.0), self.decir("tt_editor", texto))):
                    if not cris.whisper_disponible() and not self.demo:
                        self.decir("tt_editor", "No tengo el oído instalado (Whisper): edito sin subtítulos esta vez.")
                    videos = cris.editar_todo(carpeta / "clips", trabajo, carpeta, avance)
        except Exception as exc:  # noqa: BLE001
            ia.contexto.tarea = None
            return fallo(t, "video", "tt_editor", exc)
        for v in videos:
            v["v"] = int(time.time())
        ia.contexto.tarea = None
        if cris.ultimo_error:
            self.decir("tt_editor", "No pude escuchar tus clips, así que esta vez van sin subtítulos karaoke. 😕")
            cris.ultimo_error = ""
        with self.lock:
            t.update(estado="hecha", fin=time.time(), resultado=f"{len(videos)} video(s) · " +
                     ", ".join(f"{v['segundos']} s" for v in videos), paso=None)
            p["etapas"]["video"] = "hecha"
            self._tocar()
        self.poner("tt_editor", estado="libre", ubicacion="visita:tt_disenadora")
        self.decir("tt_editor", "Vale, ya está el video. ¿Me haces la portada?")
        time.sleep(4)
        self.poner("tt_editor", ubicacion="casa")

        t = tarea("portada", "tt_disenadora")
        try:
            for v in videos:
                gancho = next((x for x in g["ganchos"] if x["letra"] == v["gancho"]), None)
                texto = gancho["texto_pantalla"] if gancho else p["nombre"]
                nombre = f"portada_{v['gancho'] or 'cuerpo'}.jpg"
                cris.portada(carpeta / v["video"], texto, carpeta / nombre)
                v["portada"] = nombre
        except Exception as exc:  # noqa: BLE001
            return fallo(t, "portada", "tt_disenadora", exc)
        with self.lock:
            t.update(estado="hecha", fin=time.time(), resultado=f"{len(videos)} portada(s)")
            p["etapas"]["portada"] = "hecha"
            p["videos"], p["estado"] = videos, "video_listo"
            self._tocar()
        self.poner("tt_disenadora", estado="libre")
        self.decir("tt_disenadora", f"¡Listo, jefe! Tus {len(videos)} videos de {p['nombre']} ya se pueden subir 🎬"
                   if len(videos) > 1 else f"¡Listo, jefe! Tu video de {p['nombre']} ya se puede subir 🎬")

    def _editar_en_compu(self, p: dict, t: dict, trabajo: dict, carpeta: Path, avance) -> list | None:
        """Si una de tus compus de la sala de edición está prendida, edita ahí (más rápido, con tu tarjeta de video).
        Si no hay compu, o falla, regresa None y edita el servidor: nada se detiene."""
        try:
            if not requests.get(f"{SALA_URL}/interno/disponible", params={"tipo": "cris"}, timeout=3).json().get("compus"):
                return None
        except (requests.RequestException, ValueError):
            return None
        archivos = trabajo["archivos"]
        nombres = [archivos["completo"]] if trabajo["modo"] == "completo" else list(archivos["tomas"].values())
        try:
            tid = requests.post(f"{SALA_URL}/interno/trabajo", timeout=10, json={
                "tipo": "cris", "origen": "tiktok", "etiqueta": p["nombre"], "parametros": trabajo,
                "entradas": [str(carpeta / "clips" / n) for n in nombres if n], "salida": str(carpeta),
                "clasificar": f"http://127.0.0.1:{PUERTO}/interno/clasificar/{p['id']}"}).json().get("id")
        except (requests.RequestException, ValueError):
            return None
        if not tid:
            return None
        self.decir("tt_editor", "Le paso tus clips a la sala de edición: tu compu lo hace más rápido 🚀")

        def cancelar(motivo: str):
            try:
                requests.post(f"{SALA_URL}/interno/cancelar/{tid}", json={}, timeout=5)
            except requests.RequestException:
                pass
            self.poner("tt_editor", ubicacion="casa")
            self.decir("tt_editor", f"{motivo} Lo edito aquí en el servidor.")

        en_cola_desde, fallas, sala_vista = time.time(), 0, None
        while True:
            time.sleep(2)
            try:
                e = requests.get(f"{SALA_URL}/interno/trabajo/{tid}", timeout=5).json()
                fallas = 0
            except (requests.RequestException, ValueError):
                fallas += 1
                if fallas >= 8:
                    return cancelar("Se perdió la sala de edición.")
                continue
            estado = e.get("estado")
            if estado == "listo":
                self.poner("tt_editor", ubicacion="casa")
                videos = (e.get("resultado") or {}).get("videos") or []
                if all((carpeta / v["video"]).exists() for v in videos) and videos:
                    with self.lock:
                        t["en"] = e.get("compu")
                    return videos
                return cancelar("La compu terminó pero no llegaron los videos.")
            if estado in ("error", "cancelado"):
                return cancelar(f"La compu no pudo ({(e.get('error') or '')[:90]}).")
            if estado == "en_cola":
                if time.time() - en_cola_desde > 90:
                    return cancelar("Ninguna compu lo agarró.")
                avance("Esperando a tu compu…", 0.0)
                continue
            en_cola_desde = time.time()
            if e.get("slot") and e["slot"] != sala_vista:
                sala_vista = e["slot"]
                self.poner("tt_editor", ubicacion=f"visita:sala_{sala_vista}")
            avance(f"En {e.get('compu') or 'tu compu'}: {e.get('paso') or 'editando'}", float(e.get("avance") or 0))

    def clasificar(self, pid: str, datos: dict) -> dict:
        """Lo pide la compu que edita un video completo: qué parte del guion es cada trozo (el gasto va al producto)."""
        p = self.productos.get(pid)
        if not p:
            return {"error": "No encontré ese producto."}
        ia.contexto.proyecto, ia.contexto.etapa = pid, "video"
        ia.contexto.tarea = next((t for t in reversed(self.tareas) if t["proyecto"] == pid and t["etapa"] == "video"), None)
        try:
            return {"partes": cris.clasificar(datos.get("trozos") or [], datos.get("guion") or p["guion"])}
        except ia.ErrorIA as exc:
            return {"error": str(exc)}
        finally:
            ia.contexto.tarea = None

    def detalle(self, pid: str) -> dict:
        with self.lock:
            p = self.productos.get(pid)
            return dict(p) if p else {"error": "No encontré ese producto."}

    def _producir(self, pid: str, desde: str) -> None:
        etapas = [e for e, _ in ETAPAS]
        for i, (etapa, agente) in enumerate(ETAPAS[etapas.index(desde):], etapas.index(desde)):
            p = self.productos[pid]
            t = {"id": uuid.uuid4().hex[:8], "agente": agente, "etapa": etapa, "accion": ACCION[etapa],
                 "proyecto": pid, "titulo": p["nombre"], "estado": "trabajando", "creado": time.time(),
                 "inicio": time.time(), "fin": None, "error": None}
            with self.lock:
                self.tareas.append(t)
                p["etapas"][etapa] = "trabajando"
                self._tocar()
            self.poner(agente, estado="trabajando", ubicacion="casa")
            self.decir(agente, random.choice(FRASES[agente]))
            ia.contexto.proyecto, ia.contexto.etapa, ia.contexto.tarea = pid, etapa, t
            try:
                if etapa == "ficha":
                    resultado = shop.ficha(p)
                    resumen = f"{len(resultado['datos'])} datos y {len(resultado['opiniones'])} opiniones con fuente"
                elif etapa == "guion":
                    resultado = shop.guion(p, p.get("ficha") or {})
                    resumen = f"{shop.FORMATOS.get(resultado['formato'], resultado['formato'])} · {resultado['id']}"
                else:
                    resultado = shop.tomas(p, p["guion"])
                    resumen = f"{len(resultado['tomas'])} tomas"
            except Exception as exc:  # noqa: BLE001 — el error se muestra en la oficina
                with self.lock:
                    t.update(estado="fallo", fin=time.time(), error=str(exc)[:300])
                    p["etapas"][etapa] = "fallo"
                    p["estado"], p["error"] = "error", str(exc)[:300]
                    self._tocar()
                self.poner(agente, estado="libre")
                self.decir(agente, "Algo salió mal, jefe. Revisa el producto y dale Rehacer.")
                return
            finally:
                ia.contexto.tarea = None
            with self.lock:
                p[etapa] = resultado
                p["etapas"][etapa] = "hecha"
                t.update(estado="hecha", fin=time.time(), resultado=resumen)
                self._tocar()
            self.poner(agente, estado="libre")
            if i + 1 < len(ETAPAS):  # le lleva su trabajo al siguiente
                siguiente = ETAPAS[i + 1][1]
                self.poner(agente, ubicacion=f"visita:{siguiente}")
                self.decir(agente, {"ficha": "Ten la ficha del producto, Sofi.", "guion": "Diego, ya está el guion. ¡A grabar!"}[etapa])
                time.sleep(4)
                self.poner(agente, ubicacion="casa")
        with self.lock:
            p["estado"] = "listo"
            self._tocar()
        self.decir("tt_director", f"¡Listo, jefe! Ya puedes grabar {p['nombre']} 🎥")


# ---------- modo demo: sin APIs ----------
def activar_demo() -> None:
    global ESTADO
    ESTADO = AQUI / "tienda_estado_demo.json"

    def ficha(p):
        time.sleep(random.uniform(3, 5))
        return {"resumen": f"{p['nombre']} (ficha de ejemplo del modo demo)", "problema": "Se te enreda todo en la mochila.",
                "publico": "Estudiantes y oficinistas", "objecion": "¿De qué tamaño es?", "precio": f"${p['precio']} MXN" if p.get("precio") else "",
                "datos": [], "opiniones": [], "cuidado": "", "fuentes": 0}

    def guion(p, f):
        time.sleep(random.uniform(4, 6))
        cuerpo = [("3–8 s", "puente", "Producto en la mano, lo giro a cámara", "PENSÉ QUE ERA PURO CHORO", "Neta pensé que era puro choro…"),
                  ("8–18 s", "problema", "Mochila revuelta, saco cables enredados", "SIEMPRE ASÍ 😩", "…porque siempre me pasa esto."),
                  ("18–30 s", "solucion", "Acomodo todo en 10 segundos, close-up", "10 SEGUNDOS", "Mira, todo en su lugar en diez segundos."),
                  ("30–42 s", "beneficios", "Lo cierro y lo meto a la mochila", "CABE EN CUALQUIER LADO", "Como es delgadito, cabe en cualquier lado. La pega: el cierre es un poco duro."),
                  ("42–50 s", "cta", "Señalo abajo a la izquierda", "👇 CARRITO NARANJA", "Si te pasa lo mismo, pícale al carrito naranja.")]
        return {"formato": "problema_solucion", "angulo": "Problema → solución: el desorden se ve y la solución también (demo).",
                "duracion": "normal", "supuestos": "Modo demo: guion de ejemplo, no se llamó a Claude.",
                "ganchos": [{"letra": "A", "tipo": "Advertencia", "toma": "Saco un cable roto de la mochila", "texto_pantalla": "DEJA DE ROMPER TUS CABLES", "voz": "Deja de romper tus cables así."},
                            {"letra": "B", "tipo": "Curiosidad", "toma": "Abro el producto despacio", "texto_pantalla": "¿POR QUÉ TODOS LO COMPRAN?", "voz": "¿Por qué todo mundo está comprando esto?"},
                            {"letra": "C", "tipo": "Demo muda", "toma": "Antes/después en 2 s, sin hablar", "texto_pantalla": "ANTES 😵 → DESPUÉS 😌", "voz": ""}],
                "cuerpo": [dict(zip(("tiempo", "bloque", "toma", "texto_pantalla", "voz"), c)) for c in cuerpo],
                "caption": "Mi mochila ya no es un desastre 🙌", "hashtags": ["#TikTokShop", "#TikTokMeHizoComprarlo", "#organizacion"],
                "comentario_fijado": "Mide como una libreta y le caben 2 cargadores y los audífonos 👌",
                "mejoraria": "Las medidas exactas del producto.",
                "id": f"{dt.date.today().isoformat()}_{shop.slug(p['nombre'], 30)}_problema_solucion"}

    def tomas(p, g):
        time.sleep(random.uniform(3, 5))
        lista = [("Mesa", "Producto cerrado, lo giro despacio", "Close-up", 4, "Puente", "Luz de ventana de frente"),
                 ("Mesa", "Abro el producto despacio", "Desde arriba", 4, "Gancho B", "Uñas y mesa limpias"),
                 ("Mesa", "Acomodo los cables en 10 s", "Close-up de manos", 12, "Solución", "Graba de corrido, luego se corta"),
                 ("Mochila", "Saco cables enredados", "Plano medio", 5, "Problema", "Exagéralo un poquito"),
                 ("Mochila", "Saco un cable roto", "Close-up", 4, "Gancho A", ""),
                 ("Mochila", "Meto el producto cerrado", "Plano medio", 4, "Beneficios", ""),
                 ("Cualquier lado", "Señalo abajo a la izquierda", "Plano medio con cara", 4, "Llamado a la acción", "Sonríe 😄")]
        return {"material": ["El producto", "Cables y audífonos", "Tu mochila"],
                "tomas": [dict(zip(("lugar", "que_grabar", "encuadre", "segundos", "para", "tip"), x), n=i) for i, x in enumerate(lista, 1)],
                "consejos": ["Celular en vertical y con la lente limpia.", "Nada importante arriba ni abajo del cuadro: ahí van los botones de TikTok."]}

    def transcribir(ruta, pista=""):  # demo: reparte las palabras del guion a lo largo del clip
        if not cris.tiene_audio(ruta):
            return []
        dur = cris.duracion(ruta)
        palabras = (pista or "hola").split()[:max(3, int(dur * 2.2))]
        paso = (dur - 0.6) / max(1, len(palabras))
        return [{"w": w, "t": round(0.3 + i * paso, 3), "d": round(paso * 0.8, 3)} for i, w in enumerate(palabras)]

    def clasificar(trozos, guion):
        orden = ["gancho_A", "gancho_B", "gancho_C", *cris.BLOQUES]
        return [orden[min(i, len(orden) - 1)] for i in range(len(trozos))]

    shop.ficha, shop.guion, shop.tomas = ficha, guion, tomas
    cris.transcribir, cris.clasificar = transcribir, clasificar
    ia.json_estructurado = lambda *a, **k: (_ for _ in ()).throw(ia.ErrorIA("modo demo"))


def crear_servidor(tienda: Tienda, puerto: int) -> ThreadingHTTPServer:
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

        def do_GET(self):
            ruta = unquote(urlparse(self.path).path)
            if ruta == "/api/estado":
                return self._json(tienda.snapshot())
            if ruta.startswith("/api/producto/"):
                r = tienda.detalle(ruta.rsplit("/", 1)[-1])
                return self._json(r, 200 if r.get("id") else 404)
            if ruta.startswith("/salida/"):
                return self._archivo(ruta[len("/salida/"):])
            self._json({"error": "no encontrado"}, 404)

        def _archivo(self, relativa: str):
            """Videos y portadas terminados (con rangos, para poder adelantar el video)."""
            ruta = (cris.SALIDA / relativa).resolve()
            if not ruta.is_relative_to(cris.SALIDA.resolve()) or not ruta.is_file() or "clips" in ruta.parts:
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

        def do_POST(self):
            url = urlparse(self.path)
            if url.path == "/api/subir":
                if "application/octet-stream" not in self.headers.get("Content-Type", ""):
                    return self._json({"error": "tipo no permitido"}, 403)
                q = parse_qs(url.query)
                r = tienda.subir(q.get("producto", [""])[0], q.get("toma", [""])[0], q.get("nombre", ["clip.mp4"])[0],
                                 self.rfile, int(self.headers.get("Content-Length") or 0))
                return self._json(r, 400 if "error" in r else 200)
            if "application/json" not in self.headers.get("Content-Type", ""):
                return self._json({"error": "tipo no permitido"}, 403)
            try:
                datos = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            except json.JSONDecodeError:
                return self._json({"error": "JSON inválido"}, 400)
            ruta = unquote(urlparse(self.path).path)
            if ruta.startswith("/interno/clasificar/"):  # solo desde la sala (no pasa por internet)
                r = tienda.clasificar(ruta.rsplit("/", 1)[-1], datos)
                return self._json(r, 400 if "error" in r else 200)
            if ruta == "/api/producto":
                r = tienda.nuevo_producto(datos)
            elif ruta.startswith("/api/producto/"):
                r = tienda.accion(ruta.rsplit("/", 1)[-1], str(datos.get("accion")), str(datos.get("desde", "")))
            else:
                return self._json({"error": "no encontrado"}, 404)
            self._json(r, 400 if "error" in r else 200)

    return ThreadingHTTPServer(("127.0.0.1", puerto), Manejador)


def main() -> None:
    a = argparse.ArgumentParser(description="Oficina de TikTok Shop (ala derecha del edificio)")
    a.add_argument("--demo", action="store_true", help="simula Claude y Google")
    a.add_argument("--puerto", type=int, default=int(config.env("TIENDA_PUERTO", "8766") or 8766))
    args = a.parse_args()
    global PUERTO
    PUERTO = args.puerto
    if args.demo:
        activar_demo()
    servidor = crear_servidor(Tienda(args.demo), args.puerto)
    print(f"🛒 Oficina de TikTok Shop en http://127.0.0.1:{args.puerto}" + ("  (modo demo)" if args.demo else "")
          + f"  · tope diario ${LIMITE_DIARIO:.2f}", flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nOficina de TikTok cerrada.")


if __name__ == "__main__":
    main()
