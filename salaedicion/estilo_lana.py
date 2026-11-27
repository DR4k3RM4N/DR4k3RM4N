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


def armar(mesa: Path, m: dict, borrador: dict) -> dict:
    """Llena fondo, capas, transición y sonidos de cada escena del borrador (las voces y duraciones no se tocan)."""
    whoosh, golpe, pop = _sonido(mesa, "whoosh"), _sonido(mesa, "golpe", "impact", "boom"), _sonido(mesa, "pop", "click")
    escenas_guion = m.get("escenas") or []
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

        # 1) el centro: grabación en el cel, captura en el cel o el chat oscuro con el mensaje citado
        citas = [c.strip() for c in CITA.findall(narr)]
        clip = _clip(mesa, e) if visual == "grabacion" else None
        img = _imagen(mesa, e, k) if visual in ("captura", "imagen", "resena", "dato") else None
        if clip:
            capas.append({"tipo": "celular", "desde": 0, "archivo": clip, "numero": float(e.get("desde") or 0), "x": 0.5, "tamano": 0.95})
            centro = "cel"
        elif citas:
            texto_cita = " ".join(citas)
            resaltar = next((w for w in RESALTAR if w in _sin_acentos(texto_cita)), None)
            if resaltar:  # la palabra tal cual aparece en el mensaje (con acentos)
                pos = _sin_acentos(texto_cita).find(resaltar)
                resaltar = texto_cita[pos:pos + len(resaltar)]
            capas.append({"tipo": "chat", "estilo": "oscuro", "desde": 0.15, "nombre": "Número desconocido",
                          "mensajes": [{"de": "ellos", "texto": c} for c in citas[:4]], "resaltar": resaltar, "x": 0.5})
            centro = "chat"
        elif img:
            capas.append({"tipo": "celular", "desde": 0.1, "archivo": img, "x": 0.5, "tamano": 0.95})
            centro = "cel"

        # 2) el título recortado (rótulo del guion): arriba si no hay nada al centro; a un lado si lo hay
        rotulo = _rotulo(e)
        lado_titulo = 0.21 if k % 2 == 0 else 0.79
        if rotulo and visual == "dato" and centro:  # el dato va en notita amarilla junto al cel
            capas.append({"tipo": "nota", "desde": 0.4, "texto": rotulo, "x": lado_titulo, "y": 0.32, "tamano": 0.9,
                          "angulo": 4 if lado_titulo > 0.5 else -4})
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
