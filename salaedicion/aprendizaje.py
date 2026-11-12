"""Cómo aprenden los editores de la sala: un cuaderno de estilo compartido por todos.

- Reglas: lo que Miguel quiere en general ("títulos de máximo 4 palabras"). Las escriben los editores cuando una
  corrección o una calificación dice algo de su gusto (no solo de ese video). Si una regla se repite, sube su peso.
- Notas: lo que Miguel escriba a mano en «📒 Estilo».
- Calificaciones: 👍/👎 por versión con su porqué; el siguiente editor que trabaje las convierte en reglas.
- Recetas: el plan/props de los videos con 👍. El editor arranca de una receta del mismo tipo en lugar de empezar de cero
  (menos vueltas = menos uso de tu plan de Claude).
Todo esto viaja con cada trabajo; aprender no gasta llamadas extra (va dentro de la misma edición)."""
from __future__ import annotations

import difflib
import json
import re
import threading
import time
import uuid

MAX_REGLAS = 40
MAX_RECETAS = 8


def _norm(t: str) -> str:
    return re.sub(r"[^\wáéíóúñü ]+", " ", (t or "").lower()).strip()


class Aprendizaje:
    estilo: dict

    def cargar_estilo(self, datos: dict) -> None:
        self.estilo = {"reglas": [], "notas": "", "recetas": [], "calificaciones": [], **(datos.get("estilo") or {})}

    # ---------- aprender ----------
    def aprender(self, reglas: list, origen: str) -> list[str]:
        """Agrega reglas nuevas (o refuerza las que ya estaban). Regresa las que de verdad son nuevas."""
        nuevas = []
        with self.lock:
            for texto in reglas or []:
                texto = " ".join(str(texto).split())[:200]
                if len(texto) < 6:
                    continue
                igual = next((r for r in self.estilo["reglas"]
                              if difflib.SequenceMatcher(None, _norm(r["texto"]), _norm(texto)).ratio() > 0.78), None)
                if igual:
                    igual.update(veces=igual.get("veces", 1) + 1, texto=texto, t=time.time())
                else:
                    self.estilo["reglas"].append({"id": uuid.uuid4().hex[:8], "texto": texto, "origen": origen[:80],
                                                  "veces": 1, "t": time.time()})
                    nuevas.append(texto)
            demasiadas = len(self.estilo["reglas"]) > MAX_REGLAS
            self._tocar()
        if demasiadas:
            threading.Thread(target=self._consolidar, daemon=True).start()
        return nuevas

    def _consolidar(self) -> None:
        """Si el cuaderno crece mucho, Haiku lo resume (fracción de centavo); sin clave, se quedan las más pesadas."""
        with self.lock:
            reglas = sorted(self.estilo["reglas"], key=lambda r: (-r.get("veces", 1), -r["t"]))
        juntas = None
        if not self.demo:
            try:
                from agentes import claude as ia
                r = ia.json_estructurado(
                    "Ordenas el cuaderno de estilo de un editor de video. Junta reglas repetidas o parecidas, quita las que "
                    "se contradicen dejando la más reciente, y deja máximo 25 reglas cortas, concretas y accionables, en "
                    "español de México. No inventes reglas nuevas.",
                    "\n".join(f"- (×{x.get('veces', 1)}, {time.strftime('%Y-%m-%d', time.localtime(x['t']))}) {x['texto']}"
                              for x in reglas),
                    {"type": "object", "additionalProperties": False, "required": ["reglas"],
                     "properties": {"reglas": {"type": "array", "items": {"type": "string"}}}},
                    tarea="sala_aprender", effort="low", que="ordenar el estilo de la sala")
                juntas = [str(x)[:200] for x in r.get("reglas") or [] if str(x).strip()][:25]
            except Exception:  # noqa: BLE001 — sin clave o sin saldo: se recorta y ya
                juntas = None
        with self.lock:
            if juntas:
                self.estilo["reglas"] = [{"id": uuid.uuid4().hex[:8], "texto": t, "origen": "resumen", "veces": 2,
                                          "t": time.time()} for t in juntas]
            else:
                self.estilo["reglas"] = reglas[:MAX_REGLAS - 10]
            self._tocar()

    def calificar(self, pid: str, n: int, voto: str, comentario: str) -> dict:
        p = self.proyectos.get(pid)
        if not p:
            return {"error": "No encontré ese proyecto."}
        v = next((x for x in p["versiones"] if x["n"] == n), None)
        if not v:
            return {"error": "No encontré esa versión."}
        if voto not in ("bien", "mal"):
            return {"error": "Calificación no válida."}
        comentario = " ".join((comentario or "").split())[:400]
        with self.lock:
            v.update(voto=voto, comentario=comentario)
            # se guardan todas (aunque cambies de opinión): cada comentario es algo que aprender
            self.estilo["calificaciones"] = self.estilo["calificaciones"][-29:]
            self.estilo["calificaciones"].append({"id": uuid.uuid4().hex[:8], "proyecto": pid, "nombre": p["nombre"],
                                                  "version": n, "voto": voto, "comentario": comentario, "t": time.time(),
                                                  "procesada": False})
            if voto == "bien" and v.get("receta"):
                self.estilo["recetas"] = [r for r in self.estilo["recetas"] if not (r["proyecto"] == pid and r["version"] == n)]
                self.estilo["recetas"].append({"id": uuid.uuid4().hex[:8], "proyecto": pid, "nombre": p["nombre"], "version": n,
                                               "tipo": v.get("tipo") or "", "descripcion": v.get("descripcion") or "",
                                               "por_que": comentario, **v["receta"], "t": time.time()})
                self.estilo["recetas"] = self.estilo["recetas"][-MAX_RECETAS:]
            elif voto == "mal":
                self.estilo["recetas"] = [r for r in self.estilo["recetas"] if not (r["proyecto"] == pid and r["version"] == n)]
            self._tocar()
        quien = self.editor_id(p["encargado"]) if p.get("encargado") else "sala"
        self._decir(p, quien, ("👍 ¡Gracias! " + ("Lo guardo como receta: así arranco los videos parecidos. " if v.get("receta") else "")
                               if voto == "bien" else "👎 Anotado. ")
                    + ("Lo apunto en mi cuaderno de estilo para no repetirlo." if comentario else ""))
        return {"ok": True}

    def por_aprender(self) -> list[dict]:
        with self.lock:
            return [c for c in self.estilo["calificaciones"] if not c.get("procesada") and c.get("comentario")][-8:]

    def aprendido_de(self, ids: list[str]) -> None:
        with self.lock:
            for c in self.estilo["calificaciones"]:
                if c["id"] in (ids or []):
                    c["procesada"] = True
            self._tocar()

    # ---------- lo que se le pasa a cada editor ----------
    def estilo_texto(self, maximo: int = 4000) -> str:
        with self.lock:
            reglas = sorted(self.estilo["reglas"], key=lambda r: (-r.get("veces", 1), -r["t"]))
            notas = (self.estilo.get("notas") or "").strip()
            califs = self.estilo["calificaciones"][-8:]
        partes = []
        if notas:
            partes.append("Notas de Miguel (mandan sobre todo lo demás):\n" + notas[:1500])
        if reglas:
            partes.append("Lo que ya aprendiste de su gusto (×N = veces que lo ha pedido):\n"
                          + "\n".join(f"- {r['texto']}" + (f" (×{r['veces']})" if r.get("veces", 1) > 1 else "") for r in reglas))
        if califs:
            partes.append("Sus últimas calificaciones:\n" + "\n".join(
                f"- {'👍' if c['voto'] == 'bien' else '👎'} «{c['nombre']}» v{c['version']}" + (f": {c['comentario']}" if c["comentario"] else "")
                for c in califs))
        texto = "\n\n".join(partes)
        return texto[:maximo] if texto else "(Todavía no hay nada aprendido: es de los primeros videos.)"

    def recetas_para(self, cuantas: int = 4) -> list[dict]:
        with self.lock:
            return [dict(r) for r in self.estilo["recetas"][-cuantas:]]

    # ---------- «📒 Estilo» en la oficina ----------
    def ver_estilo(self) -> dict:
        with self.lock:
            return {"notas": self.estilo.get("notas", ""),
                    "reglas": sorted(self.estilo["reglas"], key=lambda r: (-r.get("veces", 1), -r["t"])),
                    "recetas": [{k: r.get(k) for k in ("id", "nombre", "version", "tipo", "descripcion", "por_que", "t")}
                                for r in reversed(self.estilo["recetas"])],
                    "calificaciones": list(reversed(self.estilo["calificaciones"][-15:]))}

    def editar_estilo(self, d: dict) -> dict:
        with self.lock:
            if "notas" in d:
                self.estilo["notas"] = str(d["notas"])[:3000]
            if d.get("agregar"):
                texto = " ".join(str(d["agregar"]).split())[:200]
                if texto:
                    self.estilo["reglas"].append({"id": uuid.uuid4().hex[:8], "texto": texto, "origen": "Miguel",
                                                  "veces": 3, "t": time.time()})
            if d.get("borrar"):
                self.estilo["reglas"] = [r for r in self.estilo["reglas"] if r["id"] != d["borrar"]]
            if d.get("borrar_receta"):
                self.estilo["recetas"] = [r for r in self.estilo["recetas"] if r["id"] != d["borrar_receta"]]
            self._tocar()
        return {"ok": True, **self.ver_estilo()}


def resumen_recetas(recetas: list[dict]) -> str:
    if not recetas:
        return ""
    return "\n".join(f"- recetas/{r['id']}.json: «{r['nombre']}» v{r['version']} ({r.get('tipo') or 'video'})"
                     + (f" — {r['descripcion']}" if r.get("descripcion") else "") + (f" — le gustó: {r['por_que']}" if r.get("por_que") else "")
                     for r in recetas)


def receta_json(r: dict) -> str:
    return json.dumps({k: r.get(k) for k in ("nombre", "tipo", "descripcion", "por_que", "plan", "props")}, ensure_ascii=False, indent=1)
