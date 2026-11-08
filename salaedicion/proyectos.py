"""Proyectos y chat de la sala de edición (se mezcla con la clase Sala de sala.py).

- Cada compu tiene su editor (se llama como la compu). Si la compu está apagada, su editor descansa.
- Un proyecto es una carpeta de clips: en tu compu (Videos\\Sala de edicion\\<Proyecto>) o subidos al servidor.
  Se crea desde la oficina o haciendo una carpeta nueva en tu compu.
- Chat general: le dices qué quieres y el editor libre lo toma. Chat de cada proyecto: correcciones con su encargado.
- Lo que escribes lo entiende Claude Haiku (centavos) y lo convierte en un "plan de edición"; tu compu hace el video.
"""
from __future__ import annotations

import json
import re
import shutil
import threading
import time
import uuid
from pathlib import Path

AQUI = Path(__file__).resolve().parent
SALIDA = AQUI / "salida"
EXT_VIDEO = {".mp4", ".mov", ".m4v", ".webm", ".3gp", ".mkv"}
COLORES = ["#a78bfa", "#22d3ee", "#f472b6", "#facc15"]
PEINADOS = ["gorra", "audifonos", "rizos", "lentes"]

AYUDA = ("Sé cortar y ordenar clips, quitar silencios y tomas repetidas, saltarme las partes movidas/borrosas/oscuras, "
         "estabilizar tomas temblorosas, cambiar velocidad, hacer acercamientos cada ~2 s, ajustar brillo/contraste/"
         "saturación, poner textos en pantalla, subtítulos karaoke con tu voz, quitar ruido de fondo, dejar solo tu voz o "
         "silenciar el audio de los clips, música de tu carpeta Musica (baja sola cuando hablas), vertical u horizontal y "
         "ajustar la duración. No hago efectos tipo After Effects, recortar personas, seguir objetos ni generar imágenes.")


def limpio(nombre: str) -> str:
    return re.sub(r'[<>:"/\\|?*\[\]]+', " ", nombre or "").strip(" .")[:60] or "Proyecto"


def respuesta_schema(con_plan: bool) -> dict:
    from editor_libre import PLAN_SCHEMA
    props = {
        "respuesta": {"type": "string", "description": "lo que le contestas a Miguel (corto, español de México)"},
        "accion": {"type": "string", "enum": ["preguntar", "editar", "nada"]},
        "formato": {"type": "string", "enum": ["vertical", "horizontal", ""], "description": "si ya lo sabes"},
        "cambios": {"type": "array", "items": {"type": "string"},
                    "description": "si accion=editar: lista corta de lo que hiciste/cambiaste en esta versión"},
        "no_puedo": {"type": "string", "description": "lo que pidió y NO se puede hacer (o vacío)"},
    }
    if con_plan:
        props["plan"] = PLAN_SCHEMA
    return {"type": "object", "additionalProperties": False, "required": list(props), "properties": props}


ROUTER_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["proyecto", "crear", "donde", "respuesta"],
    "properties": {
        "proyecto": {"type": "string", "description": "id del proyecto existente del que habla (o vacío)"},
        "crear": {"type": "string", "description": "nombre del proyecto nuevo si pide crear uno (o vacío)"},
        "donde": {"type": "string", "description": "id de la compu donde crearlo, 'servidor', o vacío si no dijo"},
        "respuesta": {"type": "string", "description": "si no es de un proyecto: lo que le contestas"},
    },
}


class Proyectos:
    """Se mezcla con Sala: usa self.lock, self.compus, self.locales, self.trabajos, self._tocar, self.viva, self.demo."""

    # ---------- editores (uno por compu) ----------
    def editor_id(self, cid: str) -> str:
        return f"sala_{cid}"

    def editores(self) -> list[dict]:
        salida = []
        for c in sorted(self.compus.values(), key=lambda c: c["slot"]):
            t = self.trabajos.get(c.get("trabajo") or "")
            salida.append({"id": self.editor_id(c["id"]), "nombre": c["nombre"], "rol": "Editor de la sala",
                           "color": COLORES[(c["slot"] - 1) % 4], "pelo": PEINADOS[(c["slot"] - 1) % 4], "slot": c["slot"],
                           "desc": f"Edita en {c['nombre']} con su tarjeta de video. " + AYUDA,
                           "estado": "trabajando" if t else "libre", "ubicacion": "casa", "compu": c["id"],
                           "viva": self.viva(c), "dice": c.get("dice", ""), "dice_t": c.get("dice_t", 0)})
        return salida

    def _editor_para(self, p: dict) -> str | None:
        """El encargado: el de la compu donde están los clips; si están en el servidor, el primero libre y prendido."""
        if p.get("compu"):
            return p["compu"]
        prendidas = [c for c in sorted(self.compus.values(), key=lambda c: c["slot"]) if self.viva(c)]
        libres = [c for c in prendidas if not c.get("trabajo")]
        elegida = (libres or prendidas or sorted(self.compus.values(), key=lambda c: c["slot"]) or [None])[0]
        return elegida["id"] if elegida else None

    def _nombre_editor(self, cid: str | None) -> str:
        c = self.compus.get(cid or "")
        return c["nombre"] if c else "La sala"

    # ---------- chat ----------
    def _decir(self, p: dict | None, quien: str, texto: str, **extra) -> None:
        m = {"t": time.time(), "quien": quien, "texto": texto[:2000], **extra}
        with self.lock:
            if p is None:
                self.chat.append(m)
                self.chat = self.chat[-200:]
            else:
                p.setdefault("mensajes", []).append(m)
                p["mensajes"] = p["mensajes"][-150:]
            c = self.compus.get(quien.replace("sala_", "")) if quien.startswith("sala_") else None
            if c:  # el muñequito del editor dice algo en la oficina
                c["dice"], c["dice_t"] = texto[:140], time.time()
            self._tocar()

    # ---------- proyectos ----------
    def crear_proyecto(self, nombre: str, donde: str = "", origen: str = "oficina") -> dict:
        nombre = " ".join((nombre or "").split())[:60]
        if len(nombre) < 2:
            return {"error": "Ponle nombre al proyecto."}
        compu = donde if donde in self.compus else None
        carpeta = limpio(nombre)
        with self.lock:
            if any(x.get("carpeta", "").lower() == carpeta.lower() and x.get("compu") == compu for x in self.proyectos.values()):
                return {"error": "Ya hay un proyecto con ese nombre ahí."}
            p = {"id": uuid.uuid4().hex[:8], "nombre": nombre, "carpeta": carpeta, "compu": compu, "origen": origen,
                 "estado": "esperando", "formato": "", "plan": None, "versiones": [], "mensajes": [], "creado": time.time(),
                 "trabajo": None, "error": None}
            p["encargado"] = self._editor_para(p)
            self.proyectos[p["id"]] = p
            self._tocar()
        quien = self.editor_id(p["encargado"]) if p["encargado"] else "sala"
        donde_txt = (f"Ya hice la carpeta «{carpeta}» en {self._nombre_editor(compu)} (Videos → Sala de edicion): pasa ahí tus clips"
                     if compu else "Súbeme tus clips aquí en el proyecto (📤 Subir clips)")
        if origen == "compu":
            self._decir(p, quien, f"Vi la carpeta nueva «{carpeta}» en tu compu: ya es un proyecto. ¿Qué video quieres que haga "
                                  "con estos clips? ¿Vertical (TikTok/Reels/Shorts) u horizontal (YouTube)?")
        else:
            self._decir(p, quien, f"¡Va! {donde_txt}. ¿Lo quieres vertical (TikTok/Reels/Shorts) u horizontal (YouTube)? "
                                  "Y dime qué video quieres: duración, si lleva subtítulos, textos, música…")
        return {"ok": True, "id": p["id"]}

    def proyectos_de_carpetas(self, cid: str, claves: list[str]) -> None:
        """Una carpeta nueva en tu compu (que no es de TikTok ni de otro proyecto) se vuelve proyecto."""
        for clave in claves:
            if not clave.startswith("carpeta:"):
                continue
            nombre = clave[len("carpeta:"):]
            if nombre.lower() in ("musica", "música", "ediciones"):
                continue
            if any(x.get("carpeta", "").lower() == nombre.lower() for x in self.proyectos.values()):
                continue
            self.crear_proyecto(nombre, cid, origen="compu")

    def carpetas_de_proyectos(self, cid: str) -> list[str]:
        """Carpetas que esa compu debe tener (proyectos creados desde la oficina)."""
        return [p["carpeta"] for p in self.proyectos.values() if p.get("compu") == cid]

    def clips(self, p: dict) -> list[dict]:
        lista = []
        if p.get("compu"):
            loc = (self.locales.get(p["compu"]) or {}).get("carpetas", {})
            for x in loc.get(f"carpeta:{p['carpeta']}", []):
                lista.append({**x, "donde": "compu"})
        carpeta = SALIDA / p["id"] / "clips"
        if carpeta.exists():
            nombres = {x["nombre"] for x in lista}
            for f in sorted(carpeta.iterdir()):
                if f.is_file() and f.suffix.lower() in EXT_VIDEO and f.name not in nombres:
                    lista.append({"nombre": f.name, "mb": round(f.stat().st_size / 1024 ** 2, 1),
                                  "segundos": (p.get("duraciones") or {}).get(f.name, 0), "tiene_audio": True, "donde": "servidor"})
        return lista

    def musica(self, p: dict) -> list[str]:
        cid = p.get("encargado") or p.get("compu")
        return (self.locales.get(cid or "") or {}).get("musica", [])

    def resumen_proyectos(self) -> list[dict]:
        with self.lock:
            salida = []
            for p in sorted(self.proyectos.values(), key=lambda x: -x["creado"]):
                v = p["versiones"][-1] if p["versiones"] else None
                t = self.trabajos.get(p.get("trabajo") or "")
                salida.append({"id": p["id"], "nombre": p["nombre"], "compu": p.get("compu"), "encargado": p.get("encargado"),
                               "estado": p["estado"], "formato": p.get("formato"), "clips": len(self.clips(p)),
                               "versiones": len(p["versiones"]), "ultima": v, "paso": t.get("paso") if t else "",
                               "avance": t.get("avance") if t else 0, "ultimo_mensaje": (p["mensajes"] or [{}])[-1],
                               "error": p.get("error")})
            return salida

    def detalle_proyecto(self, pid: str) -> dict:
        with self.lock:
            p = self.proyectos.get(pid)
            if not p:
                return {"error": "No encontré ese proyecto."}
            t = self.trabajos.get(p.get("trabajo") or "")
            return {**{k: v for k, v in p.items()}, "clips": self.clips(p), "musica": self.musica(p),
                    "editor": self._nombre_editor(p.get("encargado")), "paso": t.get("paso") if t else "",
                    "avance": t.get("avance") if t else 0}

    def borrar_proyecto(self, pid: str) -> dict:
        with self.lock:
            p = self.proyectos.pop(pid, None)
            if not p:
                return {"error": "No encontré ese proyecto."}
            self._tocar()
        shutil.rmtree(SALIDA / pid, ignore_errors=True)
        return {"ok": True}

    def subir_clip(self, pid: str, nombre: str, entrada, largo: int) -> dict:
        p = self.proyectos.get(pid)
        if not p:
            return {"error": "No encontré ese proyecto."}
        nombre = Path(nombre).name[:100]
        if Path(nombre).suffix.lower() not in EXT_VIDEO:
            return {"error": "Ese archivo no es un video."}
        if largo <= 0 or largo > 1536 * 1024 ** 2:
            return {"error": "El clip debe pesar menos de 1.5 GB."}
        if shutil.disk_usage(AQUI).free < largo + 1024 ** 3:
            return {"error": "Ya casi no queda espacio en el servidor."}
        carpeta = SALIDA / pid / "clips"
        carpeta.mkdir(parents=True, exist_ok=True)
        destino, restante = carpeta / nombre, largo
        with open(destino, "wb") as f:
            while restante > 0:
                trozo = entrada.read(min(1024 * 1024, restante))
                if not trozo:
                    break
                f.write(trozo)
                restante -= len(trozo)
        if restante:
            destino.unlink(missing_ok=True)
            return {"error": "La subida se cortó."}
        try:
            import cris
            segundos = round(cris.duracion(destino), 1)
        except Exception:  # noqa: BLE001
            segundos = 0
        with self.lock:
            p.setdefault("duraciones", {})[nombre] = segundos
            self._tocar()
        return {"ok": True, "segundos": segundos}

    # ---------- lo que escribes ----------
    def mensaje(self, pid: str | None, texto: str) -> dict:
        texto = " ".join((texto or "").split())[:1500]
        if not texto:
            return {"error": "Escribe algo."}
        p = self.proyectos.get(pid) if pid else None
        if pid and not p:
            return {"error": "No encontré ese proyecto."}
        self._decir(p, "jefe", texto)
        threading.Thread(target=self._atender, args=(p, texto), daemon=True).start()
        return {"ok": True}

    def _atender(self, p: dict | None, texto: str) -> None:
        try:
            if p is None:
                return self._atender_general(texto)
            self._atender_proyecto(p, texto)
        except Exception as exc:  # noqa: BLE001 — el error se dice en el chat
            quien = self.editor_id(p["encargado"]) if p and p.get("encargado") else "sala"
            self._decir(p, quien, f"Uy, no pude con eso: {str(exc)[:200]}")

    def _atender_general(self, texto: str) -> None:
        lista = [{"id": x["id"], "nombre": x["nombre"], "donde": self._nombre_editor(x.get("compu")) if x.get("compu") else "servidor",
                  "clips": len(self.clips(x))} for x in self.proyectos.values()]
        compus = [{"id": c["id"], "nombre": c["nombre"], "prendida": self.viva(c)} for c in self.compus.values()]
        if self.demo:
            r = self._router_demo(texto, lista, compus)
        else:
            from agentes import claude as ia
            r = ia.json_estructurado(
                "Eres el coordinador de la sala de edición de Miguel (creador mexicano). Decide a qué proyecto va su mensaje "
                "o si quiere crear uno nuevo. Español de México, corto.",
                f"Proyectos: {json.dumps(lista, ensure_ascii=False)}\nCompus: {json.dumps(compus, ensure_ascii=False)}\n"
                f"Mensaje de Miguel: «{texto}»\n\nSi habla de un proyecto que ya existe (aunque lo diga distinto), pon su id. "
                "Si pide hacer un video nuevo, pon el nombre en 'crear' y en 'donde' la compu que mencione (o vacío). "
                f"Si solo pregunta algo, contesta tú. Lo que la sala sabe hacer: {self.AYUDA}",
                ROUTER_SCHEMA, tarea="guion", effort="low", que="chat de la sala")
        if r.get("proyecto") in self.proyectos:
            p = self.proyectos[r["proyecto"]]
            self._decir(None, self.editor_id(p["encargado"]) if p.get("encargado") else "sala",
                        f"Va, me encargo de «{p['nombre']}». Te contesto en su chat 👉", proyecto=p["id"])
            self._decir(p, "jefe", texto)
            return self._atender_proyecto(p, texto)
        if r.get("crear"):
            donde = r.get("donde") if r.get("donde") in self.compus else ""
            if not donde and not any(self.viva(c) for c in self.compus.values()) and self.compus:
                donde = sorted(self.compus.values(), key=lambda c: c["slot"])[0]["id"]
            res = self.crear_proyecto(r["crear"], donde)
            if "error" in res:
                return self._decir(None, "sala", res["error"])
            p = self.proyectos[res["id"]]
            self._decir(None, self.editor_id(p["encargado"]) if p.get("encargado") else "sala",
                        f"Listo, abrí el proyecto «{p['nombre']}». Seguimos en su chat 👉", proyecto=p["id"])
            self._decir(p, "jefe", texto)
            if self.clips(p):
                return self._atender_proyecto(p, texto)
            return
        self._decir(None, "sala", r.get("respuesta") or "¿Con qué proyecto te ayudo? Dime cuál o pídeme uno nuevo.")

    AYUDA = AYUDA

    def _atender_proyecto(self, p: dict, texto: str) -> None:
        if not p.get("encargado"):
            p["encargado"] = self._editor_para(p)
        quien = self.editor_id(p["encargado"]) if p.get("encargado") else "sala"
        clips = self.clips(p)
        if p["estado"] == "editando":
            p.setdefault("pendientes", []).append(texto)
            return self._decir(p, quien, "Estoy terminando la versión anterior; en cuanto acabe aplico esto. 👌")
        historial = [f"{'Miguel' if m['quien'] == 'jefe' else 'Tú'}: {m['texto']}" for m in p["mensajes"][-14:]]
        fichas, imagenes = [], []
        clave = f"carpeta:{p['carpeta']}"
        for i, x in enumerate(clips, 1):
            a = self.analisis.get((p.get("compu"), clave, x["nombre"])) or {}
            malas = [f"{c[0]}-{c[1]} s {c[2]}" for c in a.get("calidad", []) if c[2] != "bien"]
            fichas.append(f"Clip {i}: «{x['nombre']}» · {x.get('segundos', 0)} s · {'con audio' if x.get('tiene_audio', True) else 'sin audio'}"
                          + (f"\n   Dice: " + " | ".join(f"[{f[0]}-{f[1]} s] {f[2]}" for f in a.get("frases", [])[:25]) if a.get("frases") else "\n   (no habla o no se escuchó)")
                          + (f"\n   Partes con problema: {', '.join(malas[:12])}" if malas else ("\n   Imagen: bien" if a.get("calidad") else "")))
            hoja = self.hojas.get((p.get("compu"), clave, x["nombre"]))
            if hoja and len(imagenes) < 24:
                import base64
                imagenes += [{"type": "text", "text": f"Clip {i} («{x['nombre']}»), 4 cuadros de principio a fin:"},
                             {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                          "data": base64.b64encode(hoja).decode()}}]
        if self.demo:
            r = self._cerebro_demo(p, texto, clips)
        else:
            from agentes import claude as ia
            r = ia.json_estructurado(
                f"Eres {self._nombre_editor(p.get('encargado'))}, editor de video en la sala de edición de Miguel (creador "
                f"mexicano). Hablas español de México, casual y breve, como compañero de trabajo. {self.AYUDA} Si te piden "
                "algo que no sabes hacer, dilo y ofrece una alternativa.",
                [*imagenes, {"type": "text", "text":
                f"Proyecto: {p['nombre']}\nFormato: {p.get('formato') or 'no lo ha dicho'}\n"
                "Clips (usa exactamente estos nombres en el plan):\n" + "\n".join(fichas) + "\n"
                f"Música disponible (carpeta Musica): {json.dumps(self.musica(p), ensure_ascii=False)}\n"
                f"Plan de la última versión: {json.dumps(p.get('plan'), ensure_ascii=False) if p.get('plan') else 'todavía no hay'}\n"
                f"Conversación:\n" + "\n".join(historial) + f"\n\nNuevo mensaje de Miguel: «{texto}»\n\n"
                "Reglas: si no sabes si es vertical u horizontal y no se deduce, accion='preguntar' y pregúntalo. Si no hay clips, "
                "pide que los pase/suba. Si ya puedes hacer el video (o la corrección), accion='editar' y arma el plan completo: "
                "para correcciones cambia SOLO lo que pidió y deja lo demás como en el plan anterior. Si solo platica, accion='nada'. "
                "Para elegir lo mejor: mira los cuadros y la calidad; si repitió algo, usa la última toma buena (desde/hasta "
                "con los tiempos de 'Dice'); evita partes movidas/borrosas (o activa saltar_malas/estabilizar). Si pide "
                "música: elige una de la lista y pon reducir_ruido=true; si el ruido de fondo molesta, audio_original="
                "'solo_voz' (o 'silenciar' si no habla). Si no hay música en la lista, dile que ponga MP3 en la carpeta "
                "Musica. En 'cambios' explica en frases cortas qué hiciste. Si accion no es 'editar', manda un plan "
                "cualquiera válido (se ignora)."}],
                respuesta_schema(True), tarea="sala", effort="medium", que="editor de la sala")
        if r.get("formato") in ("vertical", "horizontal"):
            p["formato"] = r["formato"]
        texto_resp = r.get("respuesta") or "Va."
        if r.get("accion") == "editar" and r.get("cambios"):
            texto_resp += "\n" + "\n".join(f"• {c}" for c in r["cambios"][:8])
        if r.get("no_puedo"):
            texto_resp += f"\n⚠️ Eso no lo puedo hacer: {r['no_puedo']}"
        plan = r.get("plan") or {}
        musica = (plan.get("musica") or {}).get("archivo")
        if r.get("accion") == "editar" and musica and musica not in self.musica(p):
            plan["musica"] = {"archivo": "", "volumen": 0.15}
            texto_resp += "\n🎵 No encontré esa canción: pon tus MP3 en la carpeta Musica de la sala en tu compu y me dices."
        self._decir(p, quien, texto_resp)
        if r.get("accion") == "editar":
            nombres = {x["nombre"] for x in clips}
            plan["clips"] = [c for c in plan.get("clips") or [] if c.get("archivo") in nombres]
            if not plan["clips"]:
                return self._decir(p, quien, "No encontré clips para usar. Pásalos a la carpeta o súbelos y me dices.")
            plan["formato"] = plan.get("formato") or p.get("formato") or "vertical"
            self.lanzar_edicion(p, plan)

    def lanzar_edicion(self, p: dict, plan: dict) -> None:
        n = len(p["versiones"]) + 1
        servidor = SALIDA / p["id"] / "clips"
        entradas = [str(f) for f in sorted(servidor.iterdir())] if servidor.exists() else []
        usados = {c["archivo"] for c in plan["clips"]}
        entradas = [e for e in entradas if Path(e).name in usados]
        (SALIDA / p["id"]).mkdir(parents=True, exist_ok=True)
        r = self.crear({"tipo": "libre", "origen": "sala", "etiqueta": f"{p['nombre']} · v{n}", "entradas": entradas,
                        "salida": str(SALIDA / p["id"]), "compu": p.get("compu") or None,
                        "local": {"carpeta": p["carpeta"]},
                        "parametros": {"plan": plan, "version": n, "proyecto": p["id"], "carpeta": p["carpeta"]}})
        if "error" in r:
            return self._decir(p, self.editor_id(p["encargado"]) if p.get("encargado") else "sala", r["error"])
        with self.lock:
            p.update(estado="editando", trabajo=r["id"], plan=plan, error=None)
            self.trabajos[r["id"]]["proyecto"] = p["id"]
            self._tocar()
        if p.get("compu") and not self.viva(self.compus.get(p["compu"], {})):
            self._decir(p, self.editor_id(p["encargado"]), "Mi compu está apagada: en cuanto la prendas me pongo a editar. 🖥️")

    def termino_trabajo(self, t: dict) -> None:
        """Lo llama la sala cuando una compu termina (o falla) un trabajo de un proyecto."""
        p = self.proyectos.get(t.get("proyecto") or "")
        if not p:
            return
        quien = self.editor_id(t.get("compu") or p.get("encargado") or "")
        if t["estado"] == "listo":
            v = {"n": t["parametros"]["version"], "video": (t.get("resultado") or {}).get("video"),
                 "cuadro": (t.get("resultado") or {}).get("cuadro"), "segundos": (t.get("resultado") or {}).get("segundos"),
                 "t": time.time(), "plan": t["parametros"]["plan"]}
            with self.lock:
                p["versiones"].append(v)
                p.update(estado="listo", trabajo=None)
                self._tocar()
            if p.get("compu"):  # lo que subiste al servidor ya quedó en la carpeta de tu compu: se libera espacio
                shutil.rmtree(SALIDA / p["id"] / "clips", ignore_errors=True)
            self._decir(p, quien, f"¡Listo la versión {v['n']}! ({v['segundos']} s). También quedó en tu compu, en la carpeta "
                                  f"Ediciones del proyecto. ¿Le cambio algo?", version=v["n"])
            pendientes = p.pop("pendientes", [])
            if pendientes:
                threading.Thread(target=self._atender_proyecto, args=(p, " / ".join(pendientes)), daemon=True).start()
        else:
            with self.lock:
                p.update(estado="error", trabajo=None, error=t.get("error"))
                self._tocar()
            self._decir(p, quien, f"No pude terminar la versión: {(t.get('error') or 'falló en la compu')[:200]}. "
                                  "Revisa y escríbeme «otra vez» para reintentar.")

    # ---------- modo demo (sin Claude) ----------
    def _router_demo(self, texto: str, lista: list, compus: list) -> dict:
        t = texto.lower()
        for x in lista:
            if x["nombre"].lower() in t:
                return {"proyecto": x["id"], "crear": "", "donde": "", "respuesta": ""}
        m = re.search(r"(?:proyecto|video)\s+(?:de|del|con)?\s*(?:los clips de)?\s*[«\"]?([\wáéíóúñ ]{3,40})", t)
        if m and any(w in t for w in ("haz", "crea", "nuevo", "hazme")):
            return {"proyecto": "", "crear": m.group(1).strip().title(), "donde": "", "respuesta": ""}
        return {"proyecto": "", "crear": "", "donde": "", "respuesta": "¿Con qué proyecto te ayudo? (demo)"}

    def _cerebro_demo(self, p: dict, texto: str, clips: list) -> dict:
        t = texto.lower()
        formato = "vertical" if "vertical" in t else "horizontal" if "horizontal" in t else p.get("formato") or ""
        base = {"formato": formato or "vertical", "clips": [{"archivo": x["nombre"], "desde": 0, "hasta": 0, "velocidad": 1} for x in clips],
                "quitar_silencios": True, "quitar_repetidas": True, "cortes_dinamicos": True, "saltar_malas": True,
                "estabilizar": "movid" in t, "audio_original": "solo_voz" if "música" in t or "musica" in t else "normal",
                "reducir_ruido": "ruido" in t or "música" in t or "musica" in t,
                "subtitulos": {"activar": "sin subt" not in t, "tamano": "grande" if "grande" in t else "normal", "posicion": "abajo",
                               "mayusculas": True, "color_resaltado": "#FFD23F"},
                "textos": [{"texto": p["nombre"], "desde": 0, "hasta": 3, "posicion": "arriba"}],
                "color": {"brillo": 0, "contraste": 1, "saturacion": 1}, "musica": {"archivo": "", "volumen": 0.15},
                "duracion_objetivo": 0}
        if p.get("plan"):
            base = {**p["plan"], "formato": formato or p["plan"].get("formato", "vertical")}
            if "grande" in t:
                base["subtitulos"] = {**base["subtitulos"], "tamano": "grande"}
        if not formato:
            return {"respuesta": "¿Lo quieres vertical (TikTok/Reels) u horizontal (YouTube)? (demo)", "accion": "preguntar",
                    "formato": "", "plan": base, "cambios": [], "no_puedo": ""}
        if not clips:
            return {"respuesta": "Pásame los clips a la carpeta y me avisas. (demo)", "accion": "nada", "formato": formato, "plan": base,
                    "cambios": [], "no_puedo": ""}
        return {"respuesta": f"Va, lo armo {formato} con {len(clips)} clips. (demo)", "accion": "editar", "formato": formato, "plan": base,
                "cambios": ["Quité silencios y partes movidas", "Subtítulos " + base["subtitulos"]["tamano"]], "no_puedo": ""}
