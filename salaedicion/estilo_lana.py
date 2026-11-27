"""🐑 Estilo «Cuida Tu Lana» (la mezcla C + D que eligió Miguel): chat en pantalla + recortes y plumón.

Arma el `edu.json` de un video SIN Claude (no gasta plan): hoja de papel café de fondo, el cel al centro con la
captura o la grabación (o el chat oscuro cuando la narración cita un mensaje), títulos de letras recortadas,
rayones de plumón rojo, notitas amarillas, zooms de golpe en las palabras clave, sellos y Lanudo como calcomanía.
Algo cambia en pantalla cada pocos segundos. Solo usa lo que viene del guion (narración, rótulo de la escena y
mensajes citados entre comillas): nada inventado.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

ACENTO, PELIGRO = "#FFD60A", "#E63946"
CLAVES = re.compile(r"fraud|estaf|deposit|dep[oó]sit|comisi|anticip|contactos|amenaz|extors|cuidado|nunca|jam[aá]s|"
                    r"robo|rob[aó]|exhib|cobr|pag[aóu]|presta|deuda|link|enlace|c[oó]digo|nip|contraseñ|\d", re.I)
PELIGROSAS = re.compile(r"fraud|estaf|robo|extors|amenaz", re.I)
CITA = re.compile(r"[«“\"]([^»”\"]{6,140})[»”\"]")
RESALTAR = ("deposit", "comisión", "pago", "paga", "anticipo", "contactos", "código", "link", "enlace", "nip",
            "contraseña", "transfer")


def _sin_acentos(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn").lower()


def _sonido(mesa: Path, *nombres: str) -> str | None:
    carpeta = mesa / "estilo" / "sfx"
    for n in nombres:
        for p in sorted(carpeta.glob(f"{n}*")) if carpeta.exists() else []:
            return p.relative_to(mesa).as_posix()
    return None


def _mascota(mesa: Path, *caras: str) -> str | None:
    for c in caras:
        p = mesa / "mascota" / f"{c}.png"
        if p.exists():
            return p.relative_to(mesa).as_posix()
    p = mesa / "estilo" / "mascota.png"
    return p.relative_to(mesa).as_posix() if p.exists() else None


def _imagen(mesa: Path, e: dict, k: int) -> str | None:
    imgs = sorted(p.relative_to(mesa).as_posix() for p in (mesa / "img").glob("captura_*")) if (mesa / "img").exists() else []
    if not imgs:
        return None
    ind = e.get("indice")
    if isinstance(ind, int):
        for cand in (f"img/captura_{ind}", f"img/captura_{ind + 1}"):
            hit = next((x for x in imgs if x.rsplit(".", 1)[0] == cand), None)
            if hit:
                return hit
    return imgs[k % len(imgs)]


def _clip(mesa: Path, e: dict) -> str | None:
    clips = sorted(p.relative_to(mesa).as_posix() for p in (mesa / "clips").glob("clip_*")) if (mesa / "clips").exists() else []
    if not clips:
        return None
    ind = e.get("indice")
    if isinstance(ind, int) and 1 <= ind <= len(clips):
        return clips[ind - 1]
    return clips[0]


def _momento_clave(palabras: list[dict], desde: float = 0.6) -> float | None:
    """Segundo (en la escena) en que se dice la primera palabra fuerte (cifra, fraude, depósito…)."""
    for p in palabras:
        if p["t"] >= desde and CLAVES.search(p["w"]):
            return round(p["t"], 2)
    return None


def _inicios_de_frase(palabras: list[dict]) -> list[float]:
    """Segundos donde empieza cada frase (después de un punto o una pausa)."""
    out, ant = [], None
    for p in palabras:
        if ant is None or re.search(r"[.?!…]$", ant["w"]) or p["t"] - (ant["t"] + ant.get("d", 0.3)) > 0.45:
            out.append(round(p["t"], 2))
        ant = p
    return out


def _rotulo(e: dict) -> str:
    t = (e.get("texto") or "").strip().strip(".")
    return " ".join(t.split()[:5])


RESENA_RE = re.compile(r"rese[ñn]a|comentari|opini|usuarios? (dic|cuent|report|se quej)|la gente (dic|cuent|se quej)|calific", re.I)
APP_RE = re.compile(r"estrellas|calificaci|descarg|play store|tienda|instal", re.I)
CIFRA_RE = re.compile(r"(\$\s?[\d.,]+(?:\s?(?:mil|millones|pesos))?|[\d.,]+\s?%|\d[\d.,]*\s+(?:mil|millones|pesos|días|dias|horas|llamadas|veces|minutos|semanas|meses|años|usuarios|personas|denuncias|quejas))", re.I)
ALERTA_RE = re.compile(r"fraud|estaf|amenaz|extors|exhib|contactos|robo|cuidado|peligr|alerta|deuda|cobr|acos", re.I)


def _info(mesa: Path, m: dict) -> dict:
    """Lo que se sabe de la app/tema: nombre, ícono, estrellas, descargas, reseñas citadas y señales (todo real)."""
    ctx = m.get("ctx") or {}
    ficha, exp = ctx.get("ficha") or {}, ctx.get("expediente") or {}
    if isinstance(exp, str):
        exp = {}
    if not exp and m.get("datos"):
        try:
            exp = __import__("json").loads(m["datos"])
        except ValueError:
            exp = {}
    icono = next((p.relative_to(mesa).as_posix() for p in sorted((mesa / "img").glob("icono*"))), None) if (mesa / "img").exists() else None
    resenas = [{"usuario": str(r.get("usuario") or r.get("fuente") or "Usuario")[:28], "estrellas": r.get("estrellas"),
                "texto": _recorta(str(r.get("texto") or ""))} for r in exp.get("resenas_citadas") or [] if isinstance(r, dict) and r.get("texto")]
    senales = [str(x.get("senal") or "") for x in exp.get("senales") or [] if isinstance(x, dict) and x.get("senal")]
    try:
        estrellas = round(float(ficha.get("score")), 1) if ficha.get("score") else None
    except (TypeError, ValueError):
        estrellas = None
    return {"nombre": (ficha.get("title") or "")[:40] or "App", "icono": icono, "estrellas": estrellas,
            "descargas": str(ficha.get("installs") or "")[:20], "resenas": resenas, "senales": senales,
            "tema": exp.get("tipo") == "tema", "n_resena": 0}


def _recorta(t: str, n: int = 170) -> str:
    """Las reseñas van copiadas tal cual; si son larguísimas, se corta en una palabra y se marca con «…»."""
    t = " ".join(t.split())
    if len(t) <= n:
        return t
    return t[:n].rsplit(" ", 1)[0] + "…"


def _cuando(palabras: list[dict], regex) -> float:
    return next((round(p["t"], 2) for p in palabras if regex.search(p["w"])), 0.3)


def _pantallas(e: dict, narr: str, palabras: list[dict], info: dict, img: str | None, k: int) -> list[dict]:
    """Qué puede mostrar el cel en esta escena, de lo más pegado a lo que se dice a lo más general."""
    ops, rotulo = [], _rotulo(e)
    if info["resenas"] and (e.get("visual") == "resena" or RESENA_RE.search(narr)):
        i = e.get("indice") if e.get("visual") == "resena" and isinstance(e.get("indice"), int) else info["n_resena"]
        lista = [info["resenas"][(i + d) % len(info["resenas"])] for d in range(min(2, len(info["resenas"])))]
        info["n_resena"] = (i + len(lista)) % len(info["resenas"])
        clave = next((w for w in RESALTAR + ("fraude", "estafa", "amenaz", "contactos") if w in _sin_acentos(lista[0]["texto"])), None)
        if clave:  # la palabra completa, tal cual está escrita en la reseña
            pos = _sin_acentos(lista[0]["texto"]).find(clave)
            m_ = re.match(r"[\wáéíóúüñÁÉÍÓÚÜÑ]+", lista[0]["texto"][pos:]) if pos >= 0 else None
            ini = len(re.findall(r"[\wáéíóúüñÁÉÍÓÚÜÑ]*$", lista[0]["texto"][:pos])[0])
            clave = (lista[0]["texto"][pos - ini:pos] + m_.group(0)) if m_ else None
        ops.append({"tipo": "pantalla", "estilo": "resenas", "resenas": lista, "resaltar": clave,
                    "_desde": _cuando(palabras, RESENA_RE) if RESENA_RE.search(narr) else 0.3})
    if img:
        ops.append({"tipo": "celular", "archivo": img, "tamano": 0.95, "_desde": 0.1})
    cifras = [x.group(1).strip().rstrip(".,") for x in CIFRA_RE.finditer(narr)]
    cifra = CIFRA_RE.search(narr)
    if len(cifras) >= 2 and cifras[1] != cifras[0]:  # dos cifras: se ven las dos, cada una cuando se dice
        for n_, c_ in enumerate(cifras[:2]):
            ops.append({"tipo": "pantalla", "estilo": "dato", "texto": c_[:22], "titulo": rotulo if n_ and rotulo and not re.search(r"\d", rotulo) else "",
                        "_desde": _cuando(palabras, re.compile(re.escape(c_.split()[0].strip("$")))), "_cifra": True})
    elif e.get("visual") == "dato" or cifra:
        texto = cifra.group(1).strip().rstrip(".,") if cifra else rotulo
        if texto:
            ops.append({"tipo": "pantalla", "estilo": "dato", "texto": texto[:22],
                        "titulo": rotulo if rotulo and rotulo != texto and not re.search(r"\d", rotulo) else "",
                        "_desde": _cuando(palabras, re.compile(re.escape(texto.split()[0]))) if cifra else 0.3})
    if not info["tema"] and (APP_RE.search(narr) or e.get("momento") == "gancho") and (info["estrellas"] or info["descargas"]):
        ops.append({"tipo": "pantalla", "estilo": "app", "estrellas": info["estrellas"],
                    "texto": f"{info['descargas']} descargas" if info["descargas"] else "", "_desde": _cuando(palabras, APP_RE)})
    if ALERTA_RE.search(narr):
        pal = set(_sin_acentos(narr).split())
        senal = max(info["senales"], key=lambda x: len(pal & set(_sin_acentos(x).split())), default="")
        texto = senal if senal and len(pal & set(_sin_acentos(senal).split())) >= 2 else rotulo
        if texto:
            ops.append({"tipo": "pantalla", "estilo": "alerta", "titulo": "Señal de alerta", "texto": texto[:110],
                        "_desde": _cuando(palabras, ALERTA_RE)})
    if not ops:  # nada concreto: la app (o el tema) con el rótulo de la escena
        if info["tema"]:
            ops.append({"tipo": "pantalla", "estilo": "dato", "texto": (rotulo or info["nombre"])[:22], "titulo": "", "_desde": 0})
        else:
            ops.append({"tipo": "pantalla", "estilo": "app", "estrellas": info["estrellas"],
                        "texto": rotulo or (f"{info['descargas']} descargas" if info["descargas"] else ""), "_desde": 0})
    return ops


def armar(mesa: Path, m: dict, borrador: dict) -> dict:
    """Llena fondo, capas, transición y sonidos de cada escena del borrador (las voces y duraciones no se tocan)."""
    whoosh, golpe, pop = _sonido(mesa, "whoosh"), _sonido(mesa, "golpe", "impact", "boom"), _sonido(mesa, "pop", "click")
    escenas_guion = m.get("escenas") or []
    info = _info(mesa, m)
    prev_pantalla = False
    sellos = 0
    lado_masc = "derecha"
    for k, esc in enumerate(borrador["escenas"]):
        e = escenas_guion[k] if k < len(escenas_guion) else {}
        dur = float(esc["duracion"])
        palabras = esc.get("palabras") or []
        narr = e.get("narracion") or ""
        momento = e.get("momento") or "desarrollo"
        visual = e.get("visual") or ""
        capas, sfx = [], []
        centro = None  # lo que ocupa el centro de la pantalla

        # 1) el centro: SIEMPRE el cel, y lo que muestra va con lo que se dice (reseñas, ficha, dato, alerta, chat…)
        citas = [c.strip() for c in CITA.findall(narr)]
        clip = _clip(mesa, e) if visual == "grabacion" else None
        img = _imagen(mesa, e, k) if visual in ("captura", "imagen") else None
        centro = "cel"
        if clip:
            capas.append({"tipo": "celular", "desde": 0, "archivo": clip, "numero": float(e.get("desde") or 0), "x": 0.5, "tamano": 0.95})
            prev_pantalla = False
        elif citas:
            texto_cita = " ".join(citas)
            resaltar = next((w for w in RESALTAR if w in _sin_acentos(texto_cita)), None)
            if resaltar:  # la palabra tal cual aparece en el mensaje (con acentos)
                pos = _sin_acentos(texto_cita).find(resaltar)
                resaltar = texto_cita[pos:pos + len(resaltar)]
            capas.append({"tipo": "chat", "estilo": "oscuro", "desde": 0.15, "nombre": "Número desconocido",
                          "mensajes": [{"de": "ellos", "texto": c} for c in citas[:4]], "resaltar": resaltar, "x": 0.5})
            prev_pantalla = False
        else:
            opciones = _pantallas(e, narr, palabras, info, img, k)
            cortes = [t for t in _inicios_de_frase(palabras) if dur * 0.35 < t < dur * 0.75]
            dos = [o for o in opciones if o.pop("_cifra", False)]
            if len(dos) == 2 and 0.5 < dos[1]["_desde"] < dur - 1:  # cada cifra entra justo cuando se dice
                partes = [(dos[0], 0.0, dos[1]["_desde"]), (dos[1], dos[1]["_desde"], None)]
            elif len(opciones) > 1 and dur > 9 and cortes:  # escena larga: el cel cambia a la mitad (algo nuevo que ver)
                partes = [(opciones[0], 0.0, cortes[0]), (opciones[1], cortes[0], None)]
            else:
                partes = [(opciones[0], 0.0, None)]
            for n, (op, desde, hasta) in enumerate(partes):
                capa = {**op, "x": 0.5, "desde": round(max(desde, op.pop("_desde", 0) if n == 0 else desde), 2)}
                capa.pop("_desde", None)
                if hasta:
                    capa["hasta"] = round(hasta, 2)
                if capa["tipo"] == "pantalla":
                    capa["fijo"] = prev_pantalla or n > 0  # el cel ya estaba: solo cambia la pantalla
                    capa.update(nombre=info["nombre"], icono=info["icono"])
                capas.append(capa)
                prev_pantalla = capa["tipo"] == "pantalla"
            primero = capas[0]
            if primero["desde"] > 1.0 and not info["tema"] and primero.get("estilo") != "app":  # mientras llega lo que se va a decir, el cel muestra la app
                capas.insert(0, {"tipo": "pantalla", "estilo": "app", "estrellas": info["estrellas"], "x": 0.5, "desde": 0,
                                 "hasta": primero["desde"], "texto": "", "nombre": info["nombre"], "icono": info["icono"],
                                 "fijo": primero.get("fijo", False)})
                primero["fijo"] = True
            else:  # que el cel nunca se quede vacío al empezar la escena
                primero["desde"] = 0.0

        # 2) el título recortado (rótulo del guion): arriba si no hay nada al centro; a un lado si lo hay
        rotulo = _rotulo(e)
        lado_titulo = 0.21 if k % 2 == 0 else 0.79
        if rotulo and momento == "cierre":  # el cierre: la idea en una notita amarilla junto al cel
            capas.append({"tipo": "nota", "desde": 0.4, "texto": rotulo, "x": round(1 - lado_titulo, 2), "y": 0.28, "tamano": 0.8,
                          "angulo": 4 if lado_titulo < 0.5 else -4})
        elif rotulo:
            if centro:
                capas.append({"tipo": "texto", "estilo": "recorte", "desde": 0.2, "texto": rotulo, "x": lado_titulo, "y": 0.3, "tamano": 0.85})
                if k % 2 == 0:
                    capas.append({"tipo": "raya", "desde": 0.9, "x": lado_titulo, "y": 0.47, "tamano": 0.55})
            else:
                capas.append({"tipo": "texto", "estilo": "recorte", "desde": 0.2, "texto": rotulo, "y": 0.36, "tamano": 1.15})
                capas.append({"tipo": "raya", "desde": 0.9, "y": 0.55, "tamano": 1.1})
            if pop:
                sfx.append({"archivo": pop, "desde": 0.2, "volumen": 0.45})

        # 3) la palabra fuerte: zoom de golpe (y sello si es fraude/estafa, máx. 2 en el video)
        clave = _momento_clave(palabras)
        if clave is not None and clave < dur - 0.5:
            capas.append({"tipo": "zoom_golpe", "desde": clave, "hasta": clave + 0.7, "tamano": 0.14})
            dicha = next((p["w"] for p in palabras if round(p["t"], 2) == clave), "")
            if PELIGROSAS.search(dicha) and sellos < 2 and momento != "gancho":
                sellos += 1
                capas.append({"tipo": "sello", "desde": clave, "texto": "FRAUDE" if re.search(r"fraud", dicha, re.I) else "ESTAFA",
                              "x": 0.8 if lado_titulo < 0.5 else 0.2, "y": 0.24, "angulo": -12})
                capas.append({"tipo": "destello", "desde": clave})
            if golpe:
                sfx.append({"archivo": golpe, "desde": clave, "volumen": 0.5})

        # 4) ritmo: en cada frase nueva (cada ~3 s) algo cambia
        ultimo = 0.0
        for i, t in enumerate(_inicios_de_frase(palabras)[1:]):
            if t - ultimo < 2.8 or t > dur - 1.2 or (clave and abs(t - clave) < 1.0):
                continue
            ultimo = t
            if i % 2 == 0:
                capas.append({"tipo": "zoom_golpe", "desde": t, "hasta": t + 0.6, "tamano": 0.08})
            else:
                capas.append({"tipo": "sacudida", "desde": t, "hasta": t + 0.35, "tamano": 0.5})

        # 5) Lanudo como calcomanía: gancho, reganchos, cierre y de vez en cuando
        cara, globo = None, ""
        if momento == "gancho":
            cara, globo = _mascota(mesa, "asustado", "sorprendido"), "¡Aguas!"
        elif momento == "regancho":
            cara, globo = _mascota(mesa, "sorprendido", "pensando"), "¡Ojo aquí!"
        elif momento == "cierre":
            cara, globo = _mascota(mesa, "feliz", "guinando"), "¡Cuida tu lana!"
        elif k % 4 == 2:
            cara = _mascota(mesa, "enojado" if PELIGROSAS.search(narr) else "pensando", "normal")
        if cara and dur > 2:
            lado_masc = "izquierda" if lado_titulo > 0.5 else "derecha"
            capas.append({"tipo": "mascota", "estilo": "estampa", "desde": round(min(dur * 0.35, 2.5), 2), "archivo": cara,
                          "lado": lado_masc, "texto": globo, "tamano": 0.75})
            if pop:
                sfx.append({"archivo": pop, "desde": round(min(dur * 0.35, 2.5), 2), "volumen": 0.4})

        transicion = "destello" if momento == "gancho" else "barrido" if momento == "regancho" else ("deslizar", "zoom", "corte")[k % 3]
        if whoosh and transicion != "corte" and k:
            sfx.append({"archivo": whoosh, "desde": 0, "volumen": 0.4})
        esc.update(fondo={"tipo": "papel"}, capas=capas, sfx=sfx, transicion=transicion)
    borrador.update(acento=ACENTO, peligro=PELIGRO, barra=True,
                    subtitulos={"activar": True, "estilo": "pop", "y": 0.89, "porGrupo": 3, "resaltado": ACENTO})
    if borrador.get("musica"):
        borrador["musica"]["volumen"] = 0.06
    return borrador
