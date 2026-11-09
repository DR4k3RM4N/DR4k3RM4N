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

from manual_edicion import AYUDA, MANUAL  # noqa: E402 — el manual completo vive en su propio archivo


def limpio(nombre: str) -> str:
    return re.sub(r'[<>:"/\\|?*\[\]]+', " ", nombre or "").strip(" .")[:60] or "Proyecto"


def armar_instrucciones(sistema: str, contenido: list, carpeta: Path) -> tuple[str, list[str]]:
    """Lo que se le pediría a la API, pero en archivos para Claude Code: instrucciones.md + las imágenes aparte."""
    import base64
    partes, entradas = [], []
    for b in contenido:
        if b.get("type") == "image":
            nombre = f"hoja_{len(entradas) + 1:02d}.jpg"
            (carpeta / nombre).write_bytes(base64.b64decode(b["source"]["data"]))
            entradas.append(str(carpeta / nombre))
            partes.append(f"(Imagen: abre con Read el archivo {nombre})")
        else:
            partes.append(b.get("text", ""))
    return (f"# Tu papel\n{sistema}\n\n# El material\n" + "\n".join(partes) +
            "\n\n# Cómo responder\nAntes de decidir, mira con Read TODAS las imágenes hoja_*.jpg (4 cuadros de "
            "principio a fin de cada clip). Luego escribe el archivo respuesta.json con UN objeto JSON que cumpla "
            "exactamente el esquema de formato.json (todas las propiedades requeridas, sin propiedades extra, "
            "nombres de clips exactos). No escribas ningún otro archivo."), entradas


def respuesta_schema(con_plan: bool) -> dict:
    from editor_libre import PLAN_SCHEMA
    props = {
        "respuesta": {"type": "string", "description": "lo que le contestas a Miguel (corto, español de México)"},
        "accion": {"type": "string", "enum": ["preguntar", "editar", "nada"]},
        "formato": {"type": "string", "enum": ["vertical", "horizontal", ""], "description": "si ya lo sabes"},
        "estructura": {"type": "array", "items": {"type": "string"},
                       "description": "si accion=editar, ANTES del plan: la historia del video parte por parte "
                                      "('Gancho: clip 3 de 4.2 a 6 s, la frase «…» porque…', 'Desarrollo: …', 'Cierre: …')"},
        "cambios": {"type": "array", "items": {"type": "string"},
                    "description": "si accion=editar: lista corta de lo que hiciste/cambiaste en esta versión"},
        "no_puedo": {"type": "string", "description": "lo que pidió y NO se puede hacer (o vacío)"},
        "buscar_musica": {"type": "string", "description": "si quiere música y no hay una buena en su carpeta (o pide "
                          "otra): 3 a 6 palabras EN INGLÉS para buscar música libre, ej. 'upbeat acoustic travel'; si no, vacío"},
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
    def clave(self, p: dict) -> str:
        """Cómo reporta la compu los clips de este proyecto."""
        return f"proyecto:{p['id']}" if p.get("ruta") else f"carpeta:{p['carpeta']}"

    def crear_proyecto(self, nombre: str, donde: str = "", origen: str = "oficina", ruta: str = "") -> dict:
        ruta = (ruta or "").strip().strip('"')
        nombre = " ".join((nombre or "").split())[:60] or (ruta.replace("\\", "/").rstrip("/").split("/")[-1] if ruta else "")
        if len(nombre) < 2:
            return {"error": "Ponle nombre al proyecto."}
        compu = donde if donde in self.compus else None
        if ruta and not compu:
            return {"error": "Para usar una carpeta tuya, elige en qué compu está."}
        if ruta and any(x.get("ruta", "").lower() == ruta.lower() and x.get("compu") == compu for x in self.proyectos.values()):
            return {"error": "Ya hay un proyecto con esa carpeta."}
        carpeta = limpio(nombre)
        with self.lock:
            if not ruta and any(x.get("carpeta", "").lower() == carpeta.lower() and x.get("compu") == compu and not x.get("ruta")
                                for x in self.proyectos.values()):
                return {"error": "Ya hay un proyecto con ese nombre ahí."}
            p = {"id": uuid.uuid4().hex[:8], "nombre": nombre, "carpeta": carpeta, "compu": compu, "origen": origen, "ruta": ruta,
                 "estado": "esperando", "formato": "", "plan": None, "versiones": [], "mensajes": [], "creado": time.time(),
                 "trabajo": None, "error": None}
            p["encargado"] = self._editor_para(p)
            self.proyectos[p["id"]] = p
            self._tocar()
        quien = self.editor_id(p["encargado"]) if p["encargado"] else "sala"
        donde_txt = (f"Uso tu carpeta {ruta} en {self._nombre_editor(compu)} (las versiones las dejo en su subcarpeta Ediciones)" if ruta
                     else f"Ya hice la carpeta «{carpeta}» en {self._nombre_editor(compu)} (Videos → Sala de edicion): pasa ahí tus clips"
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
            if not clave.startswith("carpeta:"):  # "proyecto:…" ya es un proyecto con carpeta propia
                continue
            nombre = clave[len("carpeta:"):]
            if nombre.lower() in ("musica", "música", "ediciones"):
                continue
            if any(x.get("carpeta", "").lower() == nombre.lower() for x in self.proyectos.values()):
                continue
            self.crear_proyecto(nombre, cid, origen="compu")

    def carpetas_de_proyectos(self, cid: str) -> list[dict]:
        """Proyectos de esa compu: los de la sala (carpeta que debe tener) y los que usan una carpeta tuya (ruta)."""
        return [{"id": p["id"], "carpeta": p["carpeta"], "ruta": p.get("ruta", "")} for p in self.proyectos.values()
                if p.get("compu") == cid]

    def clips(self, p: dict) -> list[dict]:
        lista = []
        if p.get("compu"):
            loc = (self.locales.get(p["compu"]) or {}).get("carpetas", {})
            for x in loc.get(self.clave(p), []):
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
            error_carpeta = ((self.locales.get(p.get("compu") or "") or {}).get("errores") or {}).get(self.clave(p))
            return {**{k: v for k, v in p.items()}, "clips": self.clips(p), "musica": self.musica(p), "clave": self.clave(p),
                    "error_carpeta": error_carpeta,
                    "editor": self._nombre_editor(p.get("encargado")), "paso": t.get("paso") if t else "",
                    "avance": t.get("avance") if t else 0}

    def usar_carpeta(self, pid: str, compu: str, ruta: str) -> dict:
        """El proyecto trabaja con una carpeta de tu compu (no se sube nada). Lo subido por error al servidor se borra."""
        p = self.proyectos.get(pid)
        if not p:
            return {"error": "No encontré ese proyecto."}
        ruta = (ruta or "").strip().strip('"').strip()
        if compu not in self.compus or not ruta:
            return {"error": "Elige la compu y la carpeta."}
        if p["estado"] == "editando":
            return {"error": "Espera a que termine la versión que está haciendo."}
        with self.lock:
            p.update(compu=compu, ruta=ruta, encargado=compu, error=None)
            self._tocar()
        shutil.rmtree(SALIDA / pid / "clips", ignore_errors=True)
        self._decir(p, self.editor_id(compu), f"Listo: trabajo con tu carpeta {ruta} en {self._nombre_editor(compu)}. "
                                              "Tus clips se quedan ahí; las versiones caen en su subcarpeta Ediciones.")
        return {"ok": True}

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
        clave = self.clave(p)
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
        sistema = (f"Eres {self._nombre_editor(p.get('encargado'))}, editor de video en la sala de edición de Miguel (creador "
                f"mexicano). Hablas español de México, casual y breve, como compañero de trabajo. Eres un editor con mucho "
                f"oficio: piensas como editor de TikTok y YouTube, no como alguien que solo pega clips.\n{MANUAL}\n"
                f"Herramientas: {self.AYUDA}")
        pedido = (f"Proyecto: {p['nombre']}\nFormato: {p.get('formato') or 'no lo ha dicho'}\n"
                "Clips (usa exactamente estos nombres en el plan):\n" + "\n".join(fichas) + "\n"
                f"Música en su carpeta Musica: {json.dumps(self.musica(p), ensure_ascii=False)}\n"
                + (f"Música libre que ya le encontraste (úsala con archivo 'opcion:N'): "
                   + "; ".join(f"opcion:{o['n']} «{o['titulo']}» de {o['autor']} ({o['segundos']} s)" for o in p.get("musica_opciones") or []) + "\n"
                   if p.get("musica_opciones") else "") +
                f"Plan de la última versión: {json.dumps(p.get('plan'), ensure_ascii=False) if p.get('plan') else 'todavía no hay'}\n"
                f"Conversación:\n" + "\n".join(historial) + f"\n\nNuevo mensaje de Miguel: «{texto}»\n\n"
                "Primero llena 'estructura' (la historia del video) y luego el plan que la sigue al pie de la letra. "
                "Reglas: si no sabes si es vertical u horizontal y no se deduce, accion='preguntar' y pregúntalo. Si no hay clips, "
                "pide que los pase/suba. Si ya puedes hacer el video (o la corrección), accion='editar' y arma el plan completo: "
                "para correcciones cambia SOLO lo que pidió y deja lo demás como en el plan anterior. Si solo platica, accion='nada'. "
                "Para elegir lo mejor: mira los cuadros y la calidad; si repitió algo, usa la última toma buena (desde/hasta "
                "con los tiempos de 'Dice'); evita partes movidas/borrosas (o activa saltar_malas/estabilizar). Si pide "
                "música: usa una de su carpeta o una opción ya encontrada ('opcion:N'); si no hay ninguna que quede o pide "
                "otra, llena buscar_musica (en inglés) y en el plan pon musica.archivo='opcion:1'. Con música pon "
                "reducir_ruido=true; si el ruido de fondo molesta, audio_original='solo_voz' (o 'silenciar' si no habla). "
                "En 'cambios' explica en frases cortas qué hiciste. Si accion no es 'editar', manda un plan cualquiera "
                "válido (se ignora).")
        if self.demo and not self._compu_que_piensa(p):  # en demo solo piensa de verdad si hay una compu con Claude Code
            r = self._cerebro_demo(p, texto, clips)
        else:
            r = self._pensar(p, sistema, [*imagenes, {"type": "text", "text": pedido}], respuesta_schema(True))
        contexto = "\n".join(historial[-6:]) + f"\nÚltimo mensaje de Miguel: «{texto}»\nClips:\n" + "\n".join(fichas)
        if r.get("formato") in ("vertical", "horizontal"):
            p["formato"] = r["formato"]
        texto_resp = r.get("respuesta") or "Va."
        if r.get("accion") == "editar" and r.get("estructura") and not p.get("versiones"):
            texto_resp += "\n🎬 Cómo lo armé:\n" + "\n".join(f"  {x}" for x in r["estructura"][:7])
        if r.get("accion") == "editar" and r.get("cambios"):
            texto_resp += "\n" + "\n".join(f"• {c}" for c in r["cambios"][:8])
        if r.get("no_puedo"):
            texto_resp += f"\n⚠️ Eso no lo puedo hacer: {r['no_puedo']}"
        if r.get("_nota"):
            texto_resp += f"\n{r['_nota']}"
        from editor_libre import normalizar_plan
        plan = normalizar_plan(r.get("plan") or {})
        if r.get("buscar_musica"):
            self._buscar_musica(p, r["buscar_musica"], quien)
        musica = (plan.get("musica") or {}).get("archivo") or ""
        extra_musica = []
        if r.get("accion") == "editar" and musica.startswith("opcion:"):
            try:
                nombre, ruta_m, o = self._bajar_opcion(p, int(musica.split(":")[1] or 1))
                plan["musica"]["archivo"], extra_musica = nombre, [ruta_m]
                texto_resp += f"\n🎵 Música: «{o['titulo']}» de {o['autor']}." + (f"\n📝 Crédito para la descripción: {o['credito']}" if o["credito"] else "")
            except Exception as exc:  # noqa: BLE001
                plan["musica"] = {"archivo": "", "volumen": 0.15}
                texto_resp += f"\n🎵 No pude bajar esa música ({str(exc)[:80]}); va sin música."
        elif r.get("accion") == "editar" and musica and musica not in self.musica(p):
            plan["musica"] = {"archivo": "", "volumen": 0.15}
            texto_resp += "\n🎵 No encontré esa canción: pídeme que busque música libre o pon tus MP3 en la carpeta Musica."
        self._decir(p, quien, texto_resp)
        if r.get("accion") == "editar":
            nombres = {x["nombre"] for x in clips}
            plan["clips"] = [c for c in plan.get("clips") or [] if c.get("archivo") in nombres]
            if not plan["clips"]:
                return self._decir(p, quien, "No encontré clips para usar. Pásalos a la carpeta o súbelos y me dices.")
            plan["formato"] = plan.get("formato") or p.get("formato") or "vertical"
            self.lanzar_edicion(p, plan, extra_musica, contexto)

    def _compu_que_piensa(self, p: dict) -> str | None:
        """La compu del proyecto si tiene Claude Code listo; si no, cualquier otra prendida que lo tenga."""
        with self.lock:
            buenas = [c for c in self.compus.values() if self.viva(c) and "pensar" in (c.get("tipos") or [])]
        propia = next((c for c in buenas if c["id"] == (p.get("compu") or p.get("encargado"))), None)
        return (propia or (buenas[0] if buenas else {})).get("id")

    def _pensar(self, p: dict, sistema: str, contenido: list, schema: dict) -> dict:
        """Primero Claude Code en tu compu (gratis con tu plan); si no se puede, la IA del servidor (Sonnet, con costo)."""
        cid, nota = self._compu_que_piensa(p), ""
        if cid:
            try:
                r = self._pensar_en_compu(p, cid, sistema, contenido, schema)
                if isinstance(r, dict) and r.get("respuesta") is not None and r.get("accion") in ("preguntar", "editar", "nada"):
                    r["_nota"] = f"🧠 Lo pensé con Claude Code en {self.compus.get(cid, {}).get('nombre', 'tu compu')} (0 ¢)."
                    return r
                nota = "Claude Code contestó algo raro"
            except Exception as exc:  # noqa: BLE001
                nota = str(exc)[:160]
        if self.demo:
            r = self._cerebro_demo(p, "", self.clips(p))
        else:
            from agentes import claude as ia
            r = ia.json_estructurado(sistema, contenido, schema, tarea="sala", effort="medium", que="editor de la sala")
        if nota:
            r["_nota"] = f"(Claude Code de tu compu no pudo: {nota}. Usé la IA del servidor.)"
        return r

    def _pensar_en_compu(self, p: dict, cid: str, sistema: str, contenido: list, schema: dict) -> dict:
        carpeta = SALIDA / p["id"] / "pensar"
        shutil.rmtree(carpeta, ignore_errors=True)
        carpeta.mkdir(parents=True)
        instrucciones, entradas = armar_instrucciones(sistema, contenido, carpeta)
        r = self.crear({"tipo": "pensar", "origen": "sala", "etiqueta": f"{p['nombre']} · pensar", "entradas": entradas,
                        "salida": str(carpeta), "compu": cid,
                        "parametros": {"instrucciones": instrucciones, "schema": schema, "minutos": 8}})
        if "error" in r:
            raise RuntimeError(r["error"])
        tid, inicio = r["id"], time.time()
        try:
            while True:
                time.sleep(1.5)
                t = self.ver(tid)
                if t["estado"] == "listo":
                    return (self.trabajos.get(tid, {}).get("resultado") or {}).get("json") or {}
                if t["estado"] in ("error", "cancelado"):
                    raise RuntimeError(t.get("error") or "se canceló")
                if t["estado"] == "en_cola" and time.time() - inicio > 90:
                    raise RuntimeError("tu compu estaba ocupada")
                if time.time() - inicio > 10 * 60:
                    raise RuntimeError("tardó demasiado")
        finally:
            self.cancelar(tid)
            shutil.rmtree(carpeta, ignore_errors=True)

    def _buscar_musica(self, p: dict, consulta: str, quien: str) -> None:
        """Busca música libre (Openverse) y te enseña 3 opciones en el chat para escucharlas."""
        try:
            if self.demo:
                opciones = [{"n": i, "titulo": f"Pista de prueba {i}", "autor": "Demo", "licencia": "cc0", "version": "", "url": "",
                             "pagina": "", "segundos": 60, "fuente": "demo", "id": f"demo{i}", "credito": ""} for i in (1, 2, 3)]
            else:
                import musica_libre
                total = sum(x.get("segundos") or 0 for x in self.clips(p))
                opciones = musica_libre.buscar(consulta, total)
        except Exception as exc:  # noqa: BLE001
            return self._decir(p, quien, f"🎵 No pude buscar música ahorita ({str(exc)[:80]}).")
        if not opciones:
            return self._decir(p, quien, f"🎵 No encontré música libre para «{consulta}». Dime otro estilo.")
        p["musica_opciones"] = opciones
        self._decir(p, quien, f"🎵 Encontré estas pistas libres para «{consulta}» (se pueden usar con monetización). "
                              "Escúchalas y dime «usa la 2» si prefieres otra:", musica=opciones)

    def _bajar_opcion(self, p: dict, n: int) -> tuple[str, str, dict]:
        opciones = p.get("musica_opciones") or []
        o = next((x for x in opciones if x["n"] == n), opciones[0] if opciones else None)
        if not o:
            raise RuntimeError("no hay opciones de música")
        carpeta = SALIDA / p["id"] / "musica"
        if self.demo:
            import subprocess
            carpeta.mkdir(parents=True, exist_ok=True)
            nombre = f"pista-demo-{o['n']}.mp3"
            if not (carpeta / nombre).exists():
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency={200 + 60 * o['n']}:duration=40",
                                "-c:a", "libmp3lame", str(carpeta / nombre)], check=True)
        else:
            import musica_libre
            nombre = musica_libre.descargar(o, carpeta)
        with self.lock:
            if o.get("credito"):
                p.setdefault("creditos", [])
                if o["credito"] not in p["creditos"]:
                    p["creditos"].append(o["credito"])
        return nombre, str(carpeta / nombre), o

    def lanzar_edicion(self, p: dict, plan: dict, extra_musica: list | None = None, contexto: str = "") -> None:
        n = len(p["versiones"]) + 1
        servidor = SALIDA / p["id"] / "clips"
        entradas = [str(f) for f in sorted(servidor.iterdir())] if servidor.exists() else []
        usados = {c["archivo"] for c in plan["clips"]}
        entradas = [e for e in entradas if Path(e).name in usados] + list(extra_musica or [])
        (SALIDA / p["id"]).mkdir(parents=True, exist_ok=True)
        r = self.crear({"tipo": "libre", "origen": "sala", "etiqueta": f"{p['nombre']} · v{n}", "entradas": entradas,
                        "salida": str(SALIDA / p["id"]), "compu": p.get("compu") or None,
                        "local": {"carpeta": p["carpeta"]},
                        "parametros": {"plan": plan, "version": n, "proyecto": p["id"], "carpeta": p["carpeta"],
                                       "ruta": p.get("ruta", ""), "musica_entradas": [Path(m).name for m in extra_musica or []],
                                       "revisar": True, "contexto": contexto[:8000]}})
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
            revision = (t.get("resultado") or {}).get("revision") or {}
            if revision.get("plan"):  # lo revisó y lo corrigió: la versión es la corregida
                v["plan"] = revision["plan"]
            with self.lock:
                p["versiones"].append(v)
                p.update(estado="listo", trabajo=None)
                self._tocar()
            if p.get("compu"):  # lo que subiste al servidor ya quedó en la carpeta de tu compu: se libera espacio
                shutil.rmtree(SALIDA / p["id"] / "clips", ignore_errors=True)
            p["plan"] = v["plan"]
            nota = ""
            if revision.get("problemas"):
                nota = "\n🔍 Antes de mandártelo lo revisé y corregí:\n" + "\n".join(f"• {x}" for x in revision["problemas"][:6])
            elif "problemas" in revision and not revision.get("error") and t.get("parametros", {}).get("revisar"):
                nota = "\n🔍 Lo revisé antes de mandártelo y quedó bien." if revision.get("revisado") else ""
            self._decir(p, quien, f"¡Listo la versión {v['n']}! ({v['segundos']} s). También quedó en tu compu, en la carpeta "
                                  f"Ediciones del proyecto. ¿Le cambio algo?{nota}", version=v["n"])
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
        base = {"formato": formato or "vertical", "clips": [{"archivo": x["nombre"], "desde": 0, "hasta": 0, "velocidad": 1,
                                                              "texto": "", "posicion_texto": "arriba", "encima": {"archivo": "", "desde": 0},
                                                              "transicion": "corte"} for x in clips],
                "quitar_silencios": True, "quitar_repetidas": True, "quitar_muletillas": True, "cortes_dinamicos": False,
                "zoom_suave": True, "efectos_sonido": "sin efectos" not in t, "al_ritmo": True, "saltar_malas": True,
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
                    "formato": "", "plan": base, "cambios": [], "no_puedo": "", "buscar_musica": "", "estructura": []}
        if not clips:
            return {"respuesta": "Pásame los clips a la carpeta y me avisas. (demo)", "accion": "nada", "formato": formato, "plan": base,
                    "cambios": [], "no_puedo": "", "buscar_musica": "", "estructura": []}
        pide_musica = "música" in t or "musica" in t
        m = re.search(r"usa la (?:música |musica )?(\d)", t)
        if pide_musica or m:
            base["musica"] = {"archivo": f"opcion:{m.group(1) if m else 1}", "volumen": 0.15}
        return {"respuesta": f"Va, lo armo {formato} con {len(clips)} clips. (demo)", "accion": "editar", "formato": formato, "plan": base,
                "cambios": ["Quité silencios y partes movidas", "Subtítulos " + base["subtitulos"]["tamano"]], "no_puedo": "",
                "buscar_musica": "upbeat travel" if pide_musica and not m else "",
                "estructura": [f"Gancho: {clips[0]['nombre']}", "Desarrollo: el resto en orden", "Cierre: el último clip"]}
