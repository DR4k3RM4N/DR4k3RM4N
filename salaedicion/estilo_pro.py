"""🎬 Director automático «Pro»: edita como un editor de YouTube de primer nivel SIN gastar el plan de Claude.

Arma el `edu.json` con código, siguiendo las reglas que ya usa el canal:
- Gancho fuerte (texto de golpe, zoom en la palabra clave, la mascota reacciona) y nada de presentaciones.
- La grabación (o la captura) es la protagonista: completa al centro sobre su versión desenfocada; las capas van a los
  lados para no taparla, y nunca más de 2 a la vez.
- Lo que se dice, se ve, JUSTO cuando se dice (con los tiempos de cada palabra): cifras → contador; reseñas → la
  reseña real que se escribe sola; la app → su ficha; pago/retiro/anuncios → las palabras dichas en grande.
- Algo cambia cada 2–4 segundos (capa nueva, zoom, sacudida) y nunca el mismo recurso dos escenas seguidas.
- Regancho con cortinilla; cierre con el veredicto del expediente en sello y las señales reales en lista.
- Sonido en cada golpe y transición; música bajita; subtítulos con la palabra que se dice resaltada.
- Nada inventado: todo texto sale del guion (narración/rótulo), del expediente (reseñas, señales, veredicto) o de la
  ficha de la app.
Claude solo escribió el guion; aquí trabajan el procesador y la tarjeta de tu compu.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from estilo_lana import (CIFRA_RE, _clip, _imagen, _inicios_de_frase, _mascota, _recorta, _rotulo, _sin_acentos,
                         _sonido)

RESENA_RE = re.compile(r"rese[ñn]a|comentari|opini|usuarios? (dic|cuent|report|se quej)|la gente (dic|cuent|se quej)", re.I)
FUERTE_RE = re.compile(r"retir|pag[oóau]|cobr|anunci|m[ií]nimo|gan[aoé]|dinero|pesos|monedas|puntos|fraud|estaf|nunca|"
                       r"jam[aá]s|gratis|\d", re.I)
PELIGRO_RE = re.compile(r"fraud|estaf|amenaz|extors|robo|enga[ñn]|trampa", re.I)
EMOJI = [(re.compile(r"^likes?\b|me ?gusta", re.I), "👍"), (re.compile(r"whatsapp|mensaje|chat", re.I), "💬"),
         (re.compile(r"pesos|dinero|pag[oa]n?\b|ganar|deposit", re.I), "💸"), (re.compile(r"banco|tarjeta|transferen", re.I), "🏦"),
         (re.compile(r"grupo|telegram", re.I), "👥"), (re.compile(r"amenaz|miedo|peligr", re.I), "⚠️"),
         (re.compile(r"conf[ií]e|anzuelo|trampa", re.I), "🪤"), (re.compile(r"llam|tel[eé]fono|cel\b", re.I), "📱"),
         (re.compile(r"anunci", re.I), "📺"), (re.compile(r"horas|minutos", re.I), "⏳")]
CITA_RE = re.compile(r"[«“\"]([^»”\"]{6,90})[»”\"]")
SELLO = {"estafa_comprobada": ("ESTAFA", "#ef4444"), "senales_de_alerta": ("CUIDADO", "#f59e0b"),
         "paga_pero_no_vale_la_pena": ("NO VALE LA PENA", "#f59e0b"), "legitima": ("SÍ PAGA", "#22c55e"),
         "no_concluyente": ("OJO", "#f59e0b")}


def _info(mesa: Path, m: dict) -> dict:
    ctx = m.get("ctx") or {}
    ficha, exp = ctx.get("ficha") or {}, ctx.get("expediente") or {}
    if not isinstance(exp, dict) or not exp:
        try:
            exp = json.loads(m.get("datos") or "{}")
        except ValueError:
            exp = {}
    resenas = [{"usuario": str(r.get("usuario") or r.get("fuente") or "Usuario")[:26], "estrellas": r.get("estrellas") or 0,
                "texto": _recorta(str(r.get("texto") or ""), 150)} for r in exp.get("resenas_citadas") or []
               if isinstance(r, dict) and r.get("texto")]
    return {"nombre": (ficha.get("title") or "")[:40], "resenas": resenas, "n": 0,
            "senales": [str(x.get("senal"))[:60] for x in exp.get("senales") or [] if isinstance(x, dict) and x.get("senal")],
            "veredicto": exp.get("veredicto") or "", "tema": exp.get("tipo") == "tema"}


def _numero(txt: str) -> dict | None:
    """«$1,500» → contador de 0 a 1500 con «$»; «30 %» → con «%»; «5 llamadas» → 5 y la etiqueta «llamadas»."""
    m = re.match(r"(\$?)\s?([\d.,]+)\s?(%|mil|millones)?\s*(.*)", txt.strip())
    if not m:
        return None
    crudo = m.group(2).replace(",", "")
    try:
        valor = float(crudo.rstrip("."))
    except ValueError:
        return None
    dec = len(crudo.rstrip(".").split(".")[1]) if "." in crudo.rstrip(".") else 0  # «$0.30» se ve $0.30
    sufijo = {"%": "%", "mil": " mil", "millones": " millones"}.get(m.group(3) or "", "")
    return {"numero": valor, "prefijo": m.group(1), "sufijo": sufijo, "decimales": dec, "texto": m.group(4)[:24]}


class Lados:
    """Qué lado de la pantalla está ocupado y hasta cuándo (para no encimar capas ni tapar la grabación)."""

    def __init__(self):
        self.tramos = {"izq": [], "der": []}

    def esta_libre(self, lado: str, desde: float, hasta: float) -> bool:
        return all(hasta <= a or desde >= b for a, b in self.tramos[lado])

    def libre(self, desde: float, preferido: str, hasta: float | None = None) -> str | None:
        hasta = desde + 0.5 if hasta is None else hasta
        for lado in (preferido, "der" if preferido == "izq" else "izq"):
            if self.esta_libre(lado, desde, hasta):
                return lado
        return None

    def ocupar(self, lado: str, hasta: float, desde: float = 0.0) -> None:
        self.tramos[lado].append((desde, hasta))

    def vaciar(self) -> None:
        self.tramos = {"izq": [], "der": []}


def armar(mesa: Path, m: dict, borrador: dict) -> dict:
    info = _info(mesa, m)
    whoosh, golpe, pop = _sonido(mesa, "whoosh"), _sonido(mesa, "golpe", "impact", "boom"), _sonido(mesa, "pop", "click")
    caja = _sonido(mesa, "caja", "cash", "coin")
    escenas_guion = m.get("escenas") or []
    solo_grabacion = bool(m.get("solo_grabacion"))
    ultimo_recurso, sellos, alerta_usada = "", 0, False
    for k, esc in enumerate(borrador["escenas"]):
        e = escenas_guion[k] if k < len(escenas_guion) else {}
        dur = float(esc["duracion"])
        palabras = esc.get("palabras") or []
        narr = e.get("narracion") or ""
        momento = e.get("momento") or "desarrollo"
        visual = e.get("visual") or ""
        rotulo = _rotulo(e)
        capas, sfx, lados = [], [], Lados()
        pref = "izq" if k % 2 == 0 else "der"
        X = {"izq": 0.17, "der": 0.83}

        # 1) el fondo: la grabación o la captura completa al centro (la protagonista); si no hay, degradado del canal
        clip = _clip(mesa, e) if (visual == "grabacion" or solo_grabacion) else None
        img = None if clip else _imagen(mesa, e, k) if visual in ("captura", "imagen", "resena", "dato") else None
        if clip:
            esc["fondo"] = {"tipo": "video", "archivo": clip, "desde": float(e.get("desde") or 0), "ajuste": "contener",
                            "movimiento": "fijo" if k % 3 else "acercar"}
        elif img:
            esc["fondo"] = {"tipo": "imagen", "archivo": img, "ajuste": "contener", "movimiento": ("acercar", "izquierda", "alejar")[k % 3]}
        else:
            esc["fondo"] = {"tipo": "degradado", "color": "#0f172a", "color2": borrador.get("acento") or "#FFD23F"}
        hay_centro = bool(clip or img)
        if img:  # la captura va DENTRO de un cel a la derecha; lo que se dice, a la izquierda (más espacio)
            esc["fondo"] = {"tipo": "imagen", "archivo": img, "desenfocar": True, "oscurecer": 0.55}
            capas.append({"tipo": "celular", "archivo": img, "x": 0.7, "angulo": 3 if k % 2 else -3, "desde": 0.1})
            lados.ocupar("der", dur + 1, 0)
            X = {"izq": 0.3, "der": 0.83}

        def poner(capa: dict, desde: float, largo: float, lado_pref: str | None = None) -> bool:
            """Pone una capa a un lado libre (o al centro si no hay grabación). False si no cabe sin encimarse."""
            desde = round(max(0.0, min(desde, dur - 0.8)), 2)
            hasta = round(min(dur, desde + largo), 2)
            if hay_centro:
                lado = lados.libre(desde, lado_pref or pref, hasta + 0.3)
                if not lado:  # ¿cabe más cortito, antes de lo que ya sigue en ese lado? (mínimo 1.8 s)
                    for ld in (lado_pref or pref, "der" if (lado_pref or pref) == "izq" else "izq"):
                        sig = min((a_ for a_, b_ in lados.tramos[ld] if a_ > desde), default=None)
                        if sig and sig - 0.3 - desde >= 1.8 and lados.esta_libre(ld, desde, sig - 0.3):
                            lado, hasta = ld, round(sig - 0.3, 2)
                            break
                if not lado:
                    return False
                capa.setdefault("x", X[lado])
                lados.ocupar(lado, hasta + 0.3, desde)
            else:
                if not lados.esta_libre("izq", desde, hasta + 0.3):
                    return False
                lados.ocupar("izq", hasta + 0.3, desde)
                lados.ocupar("der", hasta + 0.3, desde)
            capas.append({**capa, "desde": desde, "hasta": hasta})
            return True

        # 2) gancho: texto de golpe con el rótulo + zoom en la palabra fuerte + mascota que reacciona
        fuerte = next((p for p in palabras if p["t"] > 0.4 and FUERTE_RE.search(p["w"])), None)
        if momento == "gancho":
            texto = rotulo or " ".join(p["w"] for p in palabras[:4])
            poner({"tipo": "texto", "estilo": "impacto" if hay_centro else "golpe", "texto": texto.upper(),
                   "y": 0.36, "tamano": 0.75 if hay_centro else 1}, 0.15, min(dur, 3.6))
            if golpe:
                sfx.append({"archivo": golpe, "desde": 0.15, "volumen": 0.5})
        if fuerte and fuerte["t"] < dur - 0.6:
            capas.append({"tipo": "zoom_golpe", "desde": round(fuerte["t"], 2), "hasta": round(fuerte["t"] + 0.7, 2),
                          "tamano": 0.16 if momento == "gancho" else 0.1})
            if golpe and momento != "gancho":
                sfx.append({"archivo": golpe, "desde": round(fuerte["t"], 2), "volumen": 0.35})

        # 3) lo que se dice, se ve: reseña real / cifra / ficha / palabras de pago, cuando se dicen
        usado = ""
        mres = RESENA_RE.search(narr)
        if info["resenas"] and (visual == "resena" or mres) and ultimo_recurso != "resena":
            r = info["resenas"][(e.get("indice") if visual == "resena" and isinstance(e.get("indice"), int) else info["n"]) % len(info["resenas"])]
            info["n"] += 1
            t = next((p["t"] for p in palabras if RESENA_RE.search(p["w"])), 0.4)
            if poner({"tipo": "resena", "usuario": r["usuario"], "estrellas": r["estrellas"], "texto": r["texto"], "y": 0.42},
                     t, min(7.0, dur - t)):
                usado = "resena"
                if pop:
                    sfx.append({"archivo": pop, "desde": round(t, 2), "volumen": 0.4})
        for cifra in [x.group(1).strip().rstrip(".,") for x in CIFRA_RE.finditer(narr)][:2]:
            n = _numero(cifra)
            t = next((p["t"] for p in palabras if cifra.split()[0].strip("$").rstrip(".,%") in p["w"]), None)
            if n and t is not None and poner({"tipo": "dato", **n, "y": 0.4, "tamano": 0.45 if hay_centro else 0.8}, t, 3.2):
                usado = usado or "dato"
                if caja:
                    sfx.append({"archivo": caja, "desde": round(t, 2), "volumen": 0.45})
        # lo que alguien dice entre comillas, en grande y citado, justo cuando se dice
        for cita in CITA_RE.findall(narr)[:1]:
            primera = cita.split()[0].lower().strip(".,")
            t = next((p["t"] for p in palabras if p["w"].lower().strip("«“\".,") == primera), 0.5)
            if poner({"tipo": "texto", "estilo": "pop", "texto": f"«{cita.upper()}»", "y": 0.4, "tamano": 0.75 if hay_centro else 0.9},
                     t, min(3.5, dur - t)):
                usado = usado or "cita"
        if usado in ("", "cita") and momento == "desarrollo" and rotulo and ultimo_recurso != "cintillo":
            titulo = info["nombre"].upper() if info["nombre"] and len(info["nombre"]) <= 18 and not info["tema"] else "OJO"
            if poner({"tipo": "cintillo", "titulo": titulo, "texto": rotulo}, 0.35, min(4.0, dur - 0.4), "izq"):
                usado = "cintillo"
        # sin nada concreto: el rótulo del guion en grande (frase completa, nunca pedazos)
        if not usado and momento == "desarrollo" and rotulo and ultimo_recurso != "rotulo":
            if poner({"tipo": "texto", "estilo": "impacto" if hay_centro else "golpe", "texto": rotulo.upper(), "y": 0.36,
                      "tamano": 0.6 if hay_centro else 0.9}, fuerte["t"] if fuerte else 0.4, 3.0):
                usado = "rotulo"
        # un emoji que ilustra la palabra justo cuando se dice (👍 likes, 💬 WhatsApp, 💸 dinero…)
        vistos = set()
        for p in palabras:
            emo = next((em for rx, em in EMOJI if rx.search(p["w"].strip("«».,¿?¡!"))), None)
            if emo and emo not in vistos and len(vistos) < 2 and p["t"] < dur - 1:
                vistos.add(emo)
                capas.append({"tipo": "emoji", "texto": emo, "x": 0.88 if not img else 0.5, "y": 0.14 + (0.2 * (len(vistos) - 1) if not img else 0),
                              "desde": round(p["t"], 2), "hasta": round(min(dur, p["t"] + 2.2), 2)})
                if pop:
                    sfx.append({"archivo": pop, "desde": round(p["t"], 2), "volumen": 0.3})
        if PELIGRO_RE.search(narr) and momento == "desarrollo" and not alerta_usada and info["veredicto"] in ("estafa_comprobada", "senales_de_alerta"):
            t = next((p["t"] for p in palabras if PELIGRO_RE.search(p["w"])), 0.5)
            capas.append({"tipo": "alerta", "desde": round(t, 2), "hasta": round(min(dur, t + 2.2), 2), "texto": "¡CUIDADO!"})
            alerta_usada = True
        ultimo_recurso = usado or ultimo_recurso

        # 4) ritmo: en cada frase nueva algo se mueve (zoom suave o sacudida), sin pisar lo anterior
        ultimo = fuerte["t"] if fuerte else 0.0
        for i, t in enumerate(_inicios_de_frase(palabras)[1:]):
            if t - ultimo < 2.6 or t > dur - 1.0:
                continue
            ultimo = t
            capas.append({"tipo": "zoom_golpe", "desde": t, "hasta": t + 0.6, "tamano": 0.06} if i % 2 == 0
                         else {"tipo": "sacudida", "desde": t, "hasta": t + 0.3, "tamano": 0.4})

        # 5) regancho: cortinilla; cierre: veredicto en sello + señales reales en lista
        if momento == "regancho" and rotulo:
            capas.append({"tipo": "titulo_seccion", "desde": 0.05, "hasta": round(min(dur - 0.3, 2.4), 2), "titulo": rotulo, "texto": "⚠️"})
        if momento == "cierre":  # el cierre se adueña de la pantalla: grabación oscurecida, veredicto y señales reales
            esc["fondo"]["oscurecer"] = 0.6
            capas = [c for c in capas if c["tipo"] not in ("resena", "dato", "cintillo", "texto", "emoji")]
            sello = SELLO.get(info["veredicto"])
            if sello and sellos == 0:
                capas.append({"tipo": "sello", "texto": sello[0], "color": sello[1], "x": 0.5, "y": 0.22, "angulo": -6,
                              "tamano": 0.85, "desde": 0.5, "hasta": dur})
                sellos += 1
                if golpe:
                    sfx.append({"archivo": golpe, "desde": 0.5, "volumen": 0.6})
            if info["senales"] and info["veredicto"] != "legitima":
                capas.append({"tipo": "lista", "titulo": "", "textos": info["senales"][:3], "estilo": "x", "y": 0.58,
                              "desde": 1.2, "hasta": dur})
            lados.vaciar()

        # 6) la mascota: gancho, reganchos, cierre y de vez en cuando (en un lado libre)
        cara, globo = None, ""
        if momento == "gancho":
            cara, globo = _mascota(mesa, "sorprendido", "asustado"), ""
        elif momento == "cierre":
            cara, globo = _mascota(mesa, "feliz", "guinando"), ""
        elif momento == "regancho" or k % 5 == 3:
            cara = _mascota(mesa, "pensando", "sorprendido", "normal")
        if cara and dur > 2.2:
            t = round(min(dur * 0.4, 2.0), 2)
            lado = ("derecha" if lados.esta_libre("der", t, t + 3.5) else "izquierda" if lados.esta_libre("izq", t, t + 3.5)
                    else None)
            if lado:
                capas.append({"tipo": "mascota", "desde": t, "hasta": round(min(dur, t + 3.5), 2), "archivo": cara,
                              "lado": lado, "texto": globo, "tamano": 0.55})

        transicion = "destello" if momento == "gancho" else "barrido" if momento == "regancho" else ("zoom", "deslizar", "corte", "zoom")[k % 4]
        if whoosh and transicion != "corte" and k:
            sfx.append({"archivo": whoosh, "desde": 0, "volumen": 0.35})
        esc.update(capas=capas, sfx=sfx, transicion=transicion)
    borrador.update(barra=True, subtitulos={"activar": True, "estilo": "karaoke", "y": 0.88, "porGrupo": 3,
                                            "resaltado": borrador.get("acento") or "#FFD23F"})
    if borrador.get("musica"):
        borrador["musica"]["volumen"] = 0.07
    return borrador
