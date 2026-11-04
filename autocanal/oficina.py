"""Oficina de agentes: tu equipo trabajando en una oficina pixel art que ves en el navegador.

    python oficina.py          # usa las APIs reales (Claude, Play Store, WordPress, YouTube)
    python oficina.py --demo   # simulación sin APIs para ver cómo funciona

Abre http://localhost:8765
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import random
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from agentes import config

WEB = config.BASE / "oficina"
ESTADO = config.BASE / "oficina_estado.json"
PASEO = 6.0  # segundos que tarda un agente en ir a otro escritorio, hablar y volver

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
    "recolectar": "investigador", "investigar": "investigador", "guion": "guionista",
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
        for p in self.proyectos.values():  # lo que quedó a medias al cerrar
            if p["estado"] in ("produccion", "publicando"):
                p["estado"], p["error"] = "error", "Se interrumpió al cerrar la oficina."
        threading.Thread(target=self._ambiente, daemon=True).start()

    # ---------- estado ----------
    def _tocar(self) -> None:
        with self.cambio:
            self.version += 1
            self.cambio.notify_all()
            ESTADO.write_text(json.dumps({
                "propuestas": self.propuestas[-200:], "proyectos": self.proyectos,
                "preferencias": self.preferencias[-30:], "log": self.log[-300:],
            }, ensure_ascii=False, indent=1), encoding="utf-8")

    def snapshot(self) -> dict:
        with self.lock:
            return {"version": self.version, "demo": self.demo, "agentes": list(self.agentes.values()),
                    "propuestas": [p for p in self.propuestas if p["estado"] == "pendiente"],
                    "proyectos": sorted(self.proyectos.values(), key=lambda p: -p["creado"]),
                    "preferencias": self.preferencias[-10:], "log": self.log[-60:],
                    "etapas": ETAPAS_PROYECTO}

    def decir(self, agente: str, texto: str, al_log: bool = True) -> None:
        with self.lock:
            a = self.agentes[agente]
            a["dice"], a["dice_t"] = texto, time.time()
            if al_log:
                self.log.append({"t": time.time(), "quien": agente, "texto": texto})
            self._tocar()

    def poner(self, agente: str, **campos) -> None:
        with self.lock:
            self.agentes[agente].update(campos)
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

    def visitar(self, quien: str, a_quien: str, texto: str) -> None:
        """`quien` camina al escritorio de `a_quien`, le dice algo y regresa."""
        self.poner(quien, ubicacion=f"visita:{a_quien}")
        time.sleep(PASEO * 0.5)
        self.decir(quien, texto)
        time.sleep(PASEO * 0.5)
        self.poner(quien, ubicacion="casa")

    def avisar_jefe(self, texto: str) -> None:
        self.visitar("productora", "jefe", texto)

    # ---------- ideas ----------
    def pedir_ideas(self, guia: str = "") -> None:
        threading.Thread(target=self._ideas, args=(guia,), daemon=True).start()

    def _ideas(self, guia: str) -> None:
        from agentes import buscador

        if guia:
            with self.lock:
                self.preferencias.append(f"Pidió: {guia}")
        self.poner("productora", estado="trabajando")
        self.decir("productora", "¡Voy! Busco apps nuevas en Play Store" + (f" ({guia})" if guia else ""))
        try:
            gustos = "\n".join(f"- {p}" for p in self.preferencias[-15:])
            candidatas = buscador.ideas(5, gustos)
        except Exception as exc:  # noqa: BLE001
            self.poner("productora", estado="libre")
            self.decir("productora", f"Uy, no pude buscar ideas: {exc}")
            return
        with self.lock:
            for c in candidatas:
                self.propuestas.append({**c, "id": uuid.uuid4().hex[:8], "estado": "pendiente",
                                        "creado": time.time(), "comentarios": []})
        self.poner("productora", estado="libre")
        self.avisar_jefe(f"¡Jefe! Te traje {len(candidatas)} ideas. ¿Qué opinas? Están en tu bandeja.")

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
                                      "estado": "produccion", "etapa": "investigar", "creado": time.time(),
                                      "error": None, "notas": notas, "publicado": None}
            self._tocar()
        threading.Thread(target=self._producir, args=(app_id, notas, None), daemon=True).start()

    def _producir(self, app_id: str, notas: str, desde: str | None) -> None:
        import canal

        coord = Coordinador(self, app_id)
        self.decir("productora", f"¡Perfecto! Arrancamos con {self.proyectos[app_id]['titulo']}")
        try:
            canal.crear(app_id, con_web=True, desde=desde, notas=notas, hook=coord.etapa)
        except Exception as exc:  # noqa: BLE001
            coord.fallo(exc)
            return
        with self.lock:
            p = self.proyectos[app_id]
            p["estado"], p["etapa"] = "revision", "revision"
            self._tocar()
        self.avisar_jefe(f"¡Jefe! El video de {self.proyectos[app_id]['titulo']} está listo. ¿Lo revisas?")

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
                threading.Thread(target=self._producir, args=(app_id, p["notas"], "guion"), daemon=True).start()
            elif accion == "reintentar" and p["estado"] == "error":
                p["estado"], p["error"] = "produccion", None
                self._tocar()
                threading.Thread(target=self._producir, args=(app_id, p.get("notas", ""), None), daemon=True).start()
            elif accion == "descartar" and p["estado"] in ("revision", "error"):
                p["estado"] = "descartado"
                self.log.append({"t": time.time(), "quien": "jefe", "texto": f"🗑️ Descartado: {p['titulo']}"})
                self._tocar()
            else:
                return {"error": "Esa acción no se puede hacer ahora."}
        return {"ok": True}

    def _publicar(self, app_id: str, titulo_n: int) -> None:
        import canal

        coord = Coordinador(self, app_id)
        try:
            coord.etapa("publicar")
            pub = canal.publicar(app_id, titulo_n)
            coord.etapa("fin")
        except Exception as exc:  # noqa: BLE001
            coord.fallo(exc)
            return
        with self.lock:
            p = self.proyectos[app_id]
            p["estado"], p["etapa"], p["publicado"] = "publicado", "publicado", pub
            self._tocar()
        self.avisar_jefe(f"¡Publicado! {self.proyectos[app_id]['titulo']} ya está en YouTube y en el blog 🎉")

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


class Coordinador:
    """Pasa el proyecto de un agente a otro: caminan, se entregan el trabajo y esperan turno."""

    def __init__(self, oficina: Oficina, app_id: str):
        self.o, self.app_id = oficina, app_id
        self.actual = "productora"
        self.con_turno = None

    def _soltar(self) -> None:
        if self.con_turno:
            self.o.poner(self.con_turno, estado="libre", proyecto=None)
            self.o.turnos[self.con_turno].release()
            self.con_turno = None

    def etapa(self, etapa: str) -> None:
        siguiente = "productora" if etapa == "fin" else ETAPA_AGENTE[etapa]
        if etapa in ETAPAS_PROYECTO:
            with self.o.lock:
                self.o.proyectos[self.app_id]["etapa"] = etapa
                self.o._tocar()
        if siguiente == self.actual:
            return
        nombre = self.o.agentes[siguiente]["nombre"]
        titulo = self.o.proyectos[self.app_id]["titulo"]
        texto = (f"{nombre}, te paso {ENTREGA[self.actual]} de {titulo}" if siguiente != "productora"
                 else f"Paola, listo {ENTREGA[self.actual]} de {titulo} ✔")
        self.o.visitar(self.actual, siguiente, texto)
        self._soltar()
        if siguiente != "productora":
            if not self.o.turnos[siguiente].acquire(blocking=False):
                self.o.decir(siguiente, f"Termino lo que tengo y sigo con {titulo}", al_log=False)
                self.o.turnos[siguiente].acquire()
            self.con_turno = siguiente
            self.o.poner(siguiente, estado="trabajando", proyecto=self.app_id)
            self.o.decir(siguiente, random.choice(FRASES[siguiente]), al_log=False)
        self.actual = siguiente

    def fallo(self, exc: Exception) -> None:
        quien = self.actual
        self._soltar()
        with self.o.lock:
            p = self.o.proyectos[self.app_id]
            p["estado"], p["error"] = "error", str(exc)[:400]
            self.o._tocar()
        self.o.decir(quien, f"¡Ups! Algo falló con {p['titulo']}: {str(exc)[:120]}")
        self.o.avisar_jefe(f"Jefe, {p['titulo']} tuvo un problema. Está en tu bandeja.")


def crear_servidor(oficina: Oficina, puerto: int) -> ThreadingHTTPServer:
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

        def do_GET(self):
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
            largo = int(self.headers.get("Content-Length") or 0)
            try:
                datos = json.loads(self.rfile.read(largo) or b"{}")
            except json.JSONDecodeError:
                return self._json({"error": "JSON inválido"}, 400)
            ruta = urlparse(self.path).path
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

    return ThreadingHTTPServer(("127.0.0.1", puerto), Manejador)


def main() -> None:
    global ESTADO
    p = argparse.ArgumentParser(description="Oficina visual de agentes")
    p.add_argument("--demo", action="store_true", help="simula Claude, Play Store y la publicación")
    p.add_argument("--puerto", type=int, default=8765)
    p.add_argument("--sin-navegador", action="store_true")
    a = p.parse_args()
    if a.demo:
        from agentes import simulado

        simulado.activar()
        ESTADO = config.BASE / "oficina_estado_demo.json"
    oficina = Oficina(a.demo)
    servidor = crear_servidor(oficina, a.puerto)
    url = f"http://localhost:{a.puerto}"
    print(f"🏢 Oficina abierta en {url}" + ("  (modo demo)" if a.demo else "") + "  — Ctrl+C para cerrar")
    if not a.sin_navegador:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nOficina cerrada.")


if __name__ == "__main__":
    main()
