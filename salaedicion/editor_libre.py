"""El editor de cada compu de la sala de edición: hace un video a partir de un "plan de edición".

El plan lo escribe el editor (Claude Haiku) según lo que le pides en el chat del proyecto; aquí solo se ejecuta,
con ffmpeg y la tarjeta de video de tu compu. Lo que sabe hacer:
cortar y ordenar clips, quitar silencios y tomas repetidas, velocidad, acercamientos cada ~2 s, brillo/contraste/
saturación, textos en pantalla, subtítulos karaoke con tu voz, música de tu carpeta Musica, vertical u horizontal y
duración objetivo.
"""
from __future__ import annotations

import difflib
import shutil
import subprocess
from pathlib import Path

import cris  # reusa: escuchar (Whisper), duración, audio, ffmpeg y el formato de subtítulos

RESOLUCION = {"vertical": (1080, 1920), "horizontal": (1920, 1080)}
analizar = None  # lo pone compu.py: analizar(clip) → {"frases", "calidad"} (partes movidas/borrosas/oscuras)

PLAN_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["formato", "clips", "quitar_silencios", "quitar_repetidas", "quitar_muletillas", "cortes_dinamicos",
                 "zoom_suave", "efectos_sonido", "al_ritmo", "saltar_malas", "estabilizar",
                 "audio_original", "reducir_ruido", "subtitulos", "textos", "color", "musica", "duracion_objetivo"],
    "properties": {
        "formato": {"type": "string", "enum": ["vertical", "horizontal"]},
        "clips": {"type": "array", "description": "en el orden del video; solo archivos de la lista",
                  "items": {"type": "object", "additionalProperties": False,
                            "required": ["archivo", "desde", "hasta", "velocidad", "texto", "posicion_texto", "encima", "transicion"],
                            "properties": {"archivo": {"type": "string", "description": "el clip de este pedazo (su audio es el que se oye)"},
                                           "desde": {"type": "number", "description": "segundo de inicio (0 = desde el principio)"},
                                           "hasta": {"type": "number", "description": "segundo final (0 = hasta el final)"},
                                           "velocidad": {"type": "number", "description": "1 normal, 0.5 lento, 2 rápido"},
                                           "texto": {"type": "string", "description": "texto corto en pantalla durante este pedazo (o vacío)"},
                                           "posicion_texto": {"type": "string", "enum": ["arriba", "centro", "abajo"]},
                                           "encima": {"type": "object", "additionalProperties": False, "required": ["archivo", "desde"],
                                                      "description": "toma de apoyo (b-roll): se VE este otro clip mientras se OYE el de arriba; vacío = sin",
                                                      "properties": {"archivo": {"type": "string"}, "desde": {"type": "number"}}},
                                           "transicion": {"type": "string", "enum": ["corte", "fundido"],
                                                          "description": "cómo entra este pedazo (corte seco casi siempre; fundido para cambios de lugar/tiempo)"}}}},
        "quitar_silencios": {"type": "boolean"},
        "quitar_repetidas": {"type": "boolean", "description": "si dijo lo mismo dos veces, deja la última"},
        "cortes_dinamicos": {"type": "boolean", "description": "acercamientos cada ~2 s en tomas largas"},
        "quitar_muletillas": {"type": "boolean", "description": "cortar 'eh', 'mmm', 'este…' palabra por palabra"},
        "zoom_suave": {"type": "boolean", "description": "zoom lento que entra/sale en cada toma (se ve más profesional que los brincos)"},
        "efectos_sonido": {"type": "boolean", "description": "whoosh en los fundidos y pop cuando aparece un texto"},
        "al_ritmo": {"type": "boolean", "description": "en las tomas sin voz, cortar al ritmo de la música"},
        "saltar_malas": {"type": "boolean", "description": "saltarse solo las partes movidas, borrosas u oscuras"},
        "estabilizar": {"type": "boolean", "description": "estabilizar tomas con la cámara temblando"},
        "audio_original": {"type": "string", "enum": ["normal", "solo_voz", "silenciar"],
                           "description": "normal = todo; solo_voz = solo donde hablas (el resto calla y queda la música); silenciar = sin audio de los clips"},
        "reducir_ruido": {"type": "boolean", "description": "quitar ruido de fondo (viento, aire, zumbido)"},
        "subtitulos": {"type": "object", "additionalProperties": False,
                       "required": ["activar", "tamano", "posicion", "mayusculas", "color_resaltado"],
                       "properties": {"activar": {"type": "boolean"}, "tamano": {"type": "string", "enum": ["normal", "grande"]},
                                      "posicion": {"type": "string", "enum": ["abajo", "centro"]}, "mayusculas": {"type": "boolean"},
                                      "color_resaltado": {"type": "string", "description": "#RRGGBB de la palabra que se dice"}}},
        "textos": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                              "required": ["texto", "desde", "hasta", "posicion"],
                                              "properties": {"texto": {"type": "string"}, "desde": {"type": "number"},
                                                             "hasta": {"type": "number", "description": "0 = hasta el final"},
                                                             "posicion": {"type": "string", "enum": ["arriba", "centro", "abajo"]}}}},
        "color": {"type": "object", "additionalProperties": False, "required": ["brillo", "contraste", "saturacion"],
                  "properties": {"brillo": {"type": "number", "description": "-0.2 a 0.2 (0 = igual)"},
                                 "contraste": {"type": "number", "description": "0.8 a 1.3 (1 = igual)"},
                                 "saturacion": {"type": "number", "description": "0 a 2 (1 = igual, 0 = blanco y negro)"}}},
        "musica": {"type": "object", "additionalProperties": False, "required": ["archivo", "volumen"],
                   "properties": {"archivo": {"type": "string", "description": "de la carpeta Musica, o vacío para sin música"},
                                  "volumen": {"type": "number", "description": "0.05 a 0.4 (bajito debajo de la voz)"}}},
        "duracion_objetivo": {"type": "number", "description": "segundos máximos (0 = sin límite)"},
    },
}


BASE_PLAN = {"formato": "vertical", "clips": [], "quitar_silencios": True, "quitar_repetidas": True, "quitar_muletillas": True,
             "cortes_dinamicos": False, "zoom_suave": True, "efectos_sonido": False, "al_ritmo": False, "saltar_malas": True,
             "estabilizar": False, "audio_original": "normal", "reducir_ruido": False,
             "subtitulos": {"activar": True, "tamano": "grande", "posicion": "abajo", "mayusculas": True, "color_resaltado": "#FFD23F"},
             "textos": [], "color": {"brillo": 0, "contraste": 1, "saturacion": 1}, "musica": {"archivo": "", "volumen": 0.15},
             "duracion_objetivo": 0}


def normalizar_plan(plan: dict, nombres: set[str] | None = None) -> dict:
    """Un plan que no viene de la API (Claude Code en tu compu) puede venir chueco: se rellena y se limpia aquí."""
    if not isinstance(plan, dict):
        return {}
    limpio = {k: plan.get(k, v) for k, v in BASE_PLAN.items()}
    for k in ("subtitulos", "color", "musica"):
        limpio[k] = {**BASE_PLAN[k], **(plan.get(k) if isinstance(plan.get(k), dict) else {})}
    if limpio["formato"] not in RESOLUCION:
        limpio["formato"] = "vertical"
    if limpio["audio_original"] not in ("normal", "solo_voz", "silenciar"):
        limpio["audio_original"] = "normal"
    clips = []
    for c in plan.get("clips") if isinstance(plan.get("clips"), list) else []:
        if not isinstance(c, dict) or (nombres is not None and Path(str(c.get("archivo", ""))).name not in nombres):
            continue
        encima = c.get("encima") if isinstance(c.get("encima"), dict) else {}
        num = lambda v, d: v if isinstance(v, (int, float)) else d  # noqa: E731
        clips.append({"archivo": Path(str(c.get("archivo", ""))).name, "desde": num(c.get("desde"), 0),
                      "hasta": num(c.get("hasta"), 0), "velocidad": num(c.get("velocidad"), 1), "texto": str(c.get("texto") or "")[:80],
                      "posicion_texto": c.get("posicion_texto") if c.get("posicion_texto") in ("arriba", "centro", "abajo") else "arriba",
                      "encima": {"archivo": Path(str(encima.get("archivo") or "")).name if encima.get("archivo") else "",
                                 "desde": num(encima.get("desde"), 0)},
                      "transicion": "fundido" if c.get("transicion") == "fundido" else "corte"})
    limpio["clips"] = clips
    limpio["textos"] = [t for t in (plan.get("textos") if isinstance(plan.get("textos"), list) else [])
                        if isinstance(t, dict) and t.get("texto")][:20]
    return limpio


def _rango(v: float, a: float, b: float, defecto: float) -> float:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return defecto
    return max(a, min(b, v))


def _trozos_con_voz(pals: list[dict], ini: float, fin: float, gap: float = 0.6) -> list[tuple[float, float, str]]:
    dentro = [p for p in pals if ini <= p["t"] < fin]
    if not dentro:
        return []
    grupos, actual = [], [dentro[0]]
    for p in dentro[1:]:
        if p["t"] - (actual[-1]["t"] + actual[-1]["d"]) > gap:
            grupos.append(actual)
            actual = []
        actual.append(p)
    grupos.append(actual)
    return [(max(ini, g[0]["t"] - 0.12), min(fin, g[-1]["t"] + g[-1]["d"] + 0.25), " ".join(x["w"] for x in g)) for g in grupos]


MULETILLAS = {"eh", "ehh", "eeh", "em", "emm", "mm", "mmm", "hmm", "ah", "ahh", "eem", "ehm", "mmh"}


def _sin_muletillas(pals: list[dict]) -> list[dict]:
    """Quita 'eh', 'mmm'… y el 'este' que se usa para pensar (seguido de pausa o repetido)."""
    limpio = []
    for i, p in enumerate(pals):
        w = cris._norm(p["w"])
        sig = pals[i + 1] if i + 1 < len(pals) else None
        pausa = sig is None or sig["t"] - (p["t"] + p["d"]) > 0.35
        if w in MULETILLAS or (w in ("este", "osea", "o sea") and (pausa or (sig and cris._norm(sig["w"]) == w))):
            continue
        limpio.append(p)
    return limpio


def piezas_del_plan(plan: dict, carpeta: Path, pista: str = "") -> list[dict]:
    piezas = []
    for idx, c in enumerate(plan.get("clips") or []):
        src = carpeta / Path(str(c.get("archivo", ""))).name
        if not src.exists():
            raise cris.ErrorEdicion(f"No encontré el clip «{c.get('archivo')}» en la carpeta del proyecto.")
        dur = cris.duracion(src)
        ini = _rango(c.get("desde"), 0, dur, 0)
        fin = _rango(c.get("hasta"), 0, dur, 0) or dur
        if fin - ini < 0.3:
            ini, fin = 0, dur
        vel = _rango(c.get("velocidad"), 0.5, 2.0, 1.0)
        tramos = [(ini, fin, "")]
        if plan.get("quitar_muletillas") and cris.tiene_audio(src):  # corta en cada muletilla (y en pausas)
            tramos = _trozos_con_voz(_sin_muletillas(cris.transcribir(src, pista)), ini, fin, gap=0.3) or tramos
        elif plan.get("quitar_silencios") and cris.tiene_audio(src):
            tramos = _trozos_con_voz(cris.transcribir(src, pista), ini, fin) or tramos
        if plan.get("saltar_malas") and analizar:
            malas = [(x[0], x[1]) for x in (analizar(src).get("calidad") or []) if x[2] != "bien"]
            buenos = []
            for a, b, texto in tramos:
                cortes = [(a, b)]
                for m0, m1 in malas:
                    nuevos = []
                    for c0, c1 in cortes:
                        if m1 <= c0 or m0 >= c1:
                            nuevos.append((c0, c1))
                        else:
                            if m0 - c0 >= 0.7:
                                nuevos.append((c0, m0))
                            if c1 - m1 >= 0.7:
                                nuevos.append((m1, c1))
                    cortes = nuevos
                buenos += [(c0, c1, texto) for c0, c1 in cortes]
            tramos = buenos or tramos  # si todo el clip está mal, se deja (mejor algo que nada)
        palabras = cris.transcribir(src, pista) if cris.tiene_audio(src) else []
        encima = c.get("encima") or {}
        apoyo = carpeta / Path(str(encima.get("archivo") or "")).name if encima.get("archivo") else None
        apoyo = apoyo if apoyo and apoyo.exists() and apoyo != src else None
        recorrido = 0.0
        for k, (a, b, texto) in enumerate(tramos):
            voz = bool(texto) or any(a <= w["t"] < b for w in palabras)
            piezas.append({"src": src, "ini": a, "dur": b - a, "vel": vel, "texto": texto, "voz": voz, "zoom": 1.0, "bloque": "clip",
                           "idx": idx, "rotulo": str(c.get("texto") or "").strip(), "pos_rotulo": c.get("posicion_texto") or "arriba",
                           "apoyo": apoyo, "apoyo_ini": _rango(encima.get("desde"), 0, 3600, 0) + recorrido,
                           "fundido": k == 0 and c.get("transicion") == "fundido"})
            recorrido += b - a
    if plan.get("quitar_repetidas"):  # si dijo casi lo mismo dos veces, se queda la última
        quedan = []
        for i, p in enumerate(piezas):
            repetida = p["texto"] and any(
                q["texto"] and difflib.SequenceMatcher(None, cris._norm(p["texto"]), cris._norm(q["texto"])).ratio() > 0.62
                for q in piezas[i + 1:])
            if not repetida:
                quedan.append(p)
        piezas = quedan
    if plan.get("cortes_dinamicos"):
        partidas = []
        for p in piezas:
            for j, x in enumerate(cris._partir(p["src"], p["ini"], p["ini"] + p["dur"], "clip")):
                partidas.append({**p, "ini": x["ini"], "dur": x["dur"], "zoom": 1.0 if p.get("apoyo") else x["zoom"],
                                 "apoyo_ini": p.get("apoyo_ini", 0) + (x["ini"] - p["ini"]), "fundido": p.get("fundido") and j == 0})
        piezas = partidas
    return piezas


def _pulso(musica: Path) -> float:
    """Segundos entre golpes de la música (para cortar al ritmo). 0 si no se puede medir."""
    try:
        import numpy as np
        crudo = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-t", "60", "-i", str(musica), "-ac", "1",
                                "-ar", "11025", "-f", "f32le", "-"], capture_output=True, timeout=60).stdout
        x = np.frombuffer(crudo, dtype=np.float32)
        salto = 512
        if len(x) < salto * 200:
            return 0.0
        energia = np.array([float((x[i:i + 1024] ** 2).sum()) for i in range(0, len(x) - 1024, salto)])
        golpes = np.maximum(0, np.diff(energia))
        golpes -= golpes.mean()
        auto = np.correlate(golpes, golpes, mode="full")[len(golpes) - 1:]
        por_seg = 11025 / salto
        lo, hi = int(por_seg * 60 / 180), int(por_seg * 60 / 70)  # entre 70 y 180 BPM
        lag = lo + int(np.argmax(auto[lo:hi]))
        return round(lag / por_seg, 3)
    except Exception:  # noqa: BLE001
        return 0.0


SFX = {"pop": "aevalsrc='0.6*sin(2*PI*(520+900*t)*t)*exp(-28*t)':d=0.18",
       "whoosh": "anoisesrc=d=0.5:c=pink:a=0.5,bandpass=f=1400:w=1200,afade=t=in:d=0.25,afade=t=out:st=0.25:d=0.25"}


def _ass(destino: Path, w: int, h: int, palabras: list[dict], plan: dict, total: float) -> None:
    sub = plan.get("subtitulos") or {}
    vertical = h > w
    grande = sub.get("tamano") == "grande"
    tam = (86 if grande else 66) if vertical else (72 if grande else 54)
    margen_der = int(w * 0.15) + 24 if vertical else 80
    margen_v = int(h * (0.42 if sub.get("posicion") == "centro" else 0.24 if vertical else 0.08))
    color = (sub.get("color_resaltado") or "#FFD23F").lstrip("#")
    resaltado = f"&H00{color[4:6]}{color[2:4]}{color[0:2]}&".upper() if len(color) == 6 else "&H003FD2FF&"
    eventos = []
    if sub.get("activar"):
        mayus = bool(sub.get("mayusculas"))
        n = 3 if vertical else 6
        for k in range(0, len(palabras), n):
            grupo = palabras[k:k + n]
            fin_grupo = min(palabras[k + n]["t"] if k + n < len(palabras) else grupo[-1]["t"] + grupo[-1]["d"] + 0.5,
                            grupo[-1]["t"] + grupo[-1]["d"] + 0.5)
            ws = [cris._ass_texto(p["w"].upper() if mayus else p["w"]) for p in grupo]
            for j, p in enumerate(grupo):
                a = grupo[0]["t"] if j == 0 else p["t"]
                b = grupo[j + 1]["t"] if j + 1 < len(grupo) else fin_grupo
                linea = " ".join((f"{{\\c{resaltado}\\fscx115\\fscy115\\t(0,90,\\fscx106\\fscy106)}}{x}{{\\r}}" if q == j else x)
                                 for q, x in enumerate(ws))
                if b > a:
                    eventos.append(f"Dialogue: 0,{cris._ass_tiempo(a)},{cris._ass_tiempo(b)},Karaoke,,0,0,0,,{linea}")
    alinear = {"arriba": 8, "centro": 5, "abajo": 2}
    for t in plan.get("textos") or []:
        a = _rango(t.get("desde"), 0, total, 0)
        b = _rango(t.get("hasta"), 0, total, 0) or total
        if b > a and str(t.get("texto", "")).strip():
            eventos.append(f"Dialogue: 1,{cris._ass_tiempo(a)},{cris._ass_tiempo(b)},Texto,,0,0,0,,"
                           f"{{\\an{alinear.get(t.get('posicion'), 8)}\\fscx70\\fscy70\\t(0,140,\\fscx100\\fscy100)}}"
                           f"{cris._ass_texto(str(t['texto']).upper())}")
    cabeza = (f"[Script Info]\nScriptType: v4.00+\nPlayResX: {w}\nPlayResY: {h}\nWrapStyle: 0\nScaledBorderAndShadow: yes\n\n"
              "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
              "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
              "MarginR, MarginV, Encoding\n"
              f"Style: Texto,{cris.FUENTE},{int(tam * 0.95)},&H00FFFFFF,&H00FFFFFF,&H30000000,&H00000000,-1,0,0,0,100,100,0,0,3,16,0,8,"
              f"60,{margen_der},{int(h * 0.17) if vertical else 60},1\n"
              f"Style: Karaoke,{cris.FUENTE},{tam},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,6,2,2,"
              f"60,{margen_der},{margen_v},1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    destino.write_text(cabeza + "\n".join(eventos) + "\n", encoding="utf-8")


def render(plan: dict, carpeta: Path, destino: Path, musica_dir: Path | None = None, pista: str = "",
           al_avanzar=None, info: dict | None = None) -> float:
    """Hace el video del plan. Deja `destino` y un cuadro limpio (destino.cuadro.jpg). Regresa los segundos.
    Si pasas `info`, ahí deja lo que se dice en el video final y dónde quedó cada pedazo (para revisarlo después)."""
    avance = al_avanzar or (lambda paso, f: None)
    w, h = RESOLUCION.get(plan.get("formato"), RESOLUCION["vertical"])
    avance("Escuchando tus clips", 0.03)
    piezas = piezas_del_plan(plan, carpeta, pista)
    if not piezas:
        raise cris.ErrorEdicion("El plan no tiene clips que usar.")
    color = plan.get("color") or {}
    eq = (f"eq=brightness={_rango(color.get('brillo'), -0.2, 0.2, 0):.3f}:contrast={_rango(color.get('contraste'), 0.8, 1.3, 1):.3f}"
          f":saturation={_rango(color.get('saturacion'), 0, 2, 1):.3f}")
    trabajo = destino.parent / f".edicion_{destino.stem}"
    shutil.rmtree(trabajo, ignore_errors=True)
    trabajo.mkdir(parents=True)
    objetivo = _rango(plan.get("duracion_objetivo"), 0, 3600, 0)
    musica = plan.get("musica") or {}
    pista_musica = (musica_dir / Path(str(musica.get("archivo") or "")).name) if musica_dir and musica.get("archivo") else None
    pista_musica = pista_musica if pista_musica and pista_musica.exists() else None
    if pista_musica and plan.get("al_ritmo"):  # tomas sin voz: duran golpes enteros de la música
        golpe = _pulso(pista_musica)
        if golpe:
            for p in piezas:
                if not p.get("voz") and p["dur"] > golpe:
                    p["dur"] = max(golpe, int(p["dur"] / golpe) * golpe)
    partes, palabras, t0, tramos_txt, sonidos, dichas, pedazos = [], [], 0.0, [], [], [], []
    for k, p in enumerate(piezas):
        if objetivo and t0 >= objetivo:
            break  # ya se llegó a la duración que pediste
        avance(f"Cortando parte {k + 1} de {len(piezas)}", 0.08 + 0.72 * k / len(piezas))
        z, vel = p["zoom"], p["vel"]
        sw, sh = int(w * z) // 2 * 2, int(h * z) // 2 * 2
        estab = "deshake=rx=48:ry=48:edge=mirror," if plan.get("estabilizar") else ""
        fundido = ",fade=t=in:st=0:d=0.3" if p.get("fundido") else ""
        dur = p["dur"] if not objetivo else min(p["dur"], (objetivo - t0) * vel)
        zoom = ""
        if plan.get("zoom_suave") and z == 1.0:  # zoom lento, alternando entrar/salir
            n = max(2, int(dur * cris.FPS))
            expr = f"1+0.07*on/{n}" if k % 2 == 0 else f"1.07-0.07*on/{n}"
            zoom = (f"fps={cris.FPS},zoompan=z='{expr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={w}x{h}:fps={cris.FPS},")
        vf = (f"scale={sw}:{sh}:force_original_aspect_ratio=increase,crop={w}:{h},{estab}{zoom}setsar=1,{eq},"
              f"setpts=PTS/{vel:.3f},fps={cris.FPS},format=yuv420p{fundido}")
        salida = trabajo / f"p{k:03d}.mp4"
        if plan.get("efectos_sonido") and p.get("fundido") and t0 > 0:
            sonidos.append(("whoosh", max(0, t0 - 0.2)))
        modo_audio = plan.get("audio_original") or "normal"
        con_audio = cris.tiene_audio(p["src"]) and modo_audio != "silenciar" and not (modo_audio == "solo_voz" and not p.get("voz"))
        limpieza = "highpass=f=90,lowpass=f=11000,afftdn=nf=-28," if plan.get("reducir_ruido") else ""
        af = f"{limpieza}atempo={vel:.3f},aformat=sample_rates=44100:channel_layouts=stereo" + (",afade=t=in:d=0.2" if p.get("fundido") else "")
        if p.get("apoyo"):  # toma de apoyo: se VE el otro clip y se OYE el tuyo
            entrada_audio = ["-ss", f"{p['ini']:.3f}", "-t", f"{dur:.3f}", "-i", str(p["src"])] if con_audio else \
                ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=r=44100:cl=stereo"]
            cris._ff("-stream_loop", "-1", "-ss", f"{p.get('apoyo_ini', 0):.3f}", "-t", f"{dur:.3f}", "-i", str(p["apoyo"]),
                     *entrada_audio, "-filter_complex", f"[0:v]{vf}[v];[1:a]{af if con_audio else 'anull'}[a]",
                     "-map", "[v]", "-map", "[a]", "-t", f"{dur / vel:.3f}", *cris.RAPIDO, *cris.AUDIO, str(salida))
        elif con_audio:
            cris._ff("-ss", f"{p['ini']:.3f}", "-t", f"{dur:.3f}", "-i", str(p["src"]), "-vf", vf,
                     "-af", af, *cris.RAPIDO, *cris.AUDIO, str(salida))
        else:
            cris._ff("-ss", f"{p['ini']:.3f}", "-t", f"{dur:.3f}", "-i", str(p["src"]), "-f", "lavfi", "-i",
                     "anullsrc=r=44100:cl=stereo", "-vf", vf, "-map", "0:v", "-map", "1:a", "-shortest",
                     *cris.RAPIDO, *cris.AUDIO, str(salida))
        real = cris.duracion(salida)
        con_subs = (plan.get("subtitulos") or {}).get("activar")
        for x in cris.transcribir(p["src"], pista) if (con_subs or info is not None) and cris.tiene_audio(p["src"]) else []:
            if p["ini"] <= x["t"] < p["ini"] + dur:
                (palabras if con_subs else dichas).append({**x, "t": t0 + (x["t"] - p["ini"]) / vel, "d": x["d"] / vel})
        pedazos.append({"desde": round(t0, 2), "hasta": round(t0 + real, 2), "clip": p["src"].name,
                        "del_segundo": round(p["ini"], 2), "plan_clip": p.get("idx", -1) + 1,
                        "apoyo": Path(p["apoyo"]).name if p.get("apoyo") else ""})
        partes.append(salida)
        tramos_txt.append((p.get("idx", -1), t0, t0 + real, p.get("rotulo", ""), p.get("pos_rotulo", "arriba")))
        t0 += real
    (trabajo / "lista.txt").write_text("".join(f"file '{x.name}'\n" for x in partes), encoding="utf-8")
    cris._ff("-f", "concat", "-safe", "0", "-i", str(trabajo / "lista.txt"), "-c", "copy", str(trabajo / "base.mp4"))
    cris._ff("-ss", f"{t0 * 0.45:.2f}", "-i", str(trabajo / "base.mp4"), "-frames:v", "1", "-q:v", "2",
             str(destino.with_name(f"{destino.stem}.cuadro.jpg")))
    avance("Poniendo textos, subtítulos y música", 0.86)
    rotulos = []  # texto de cada pedazo del plan, del inicio al fin de lo que quedó de él
    for idx, a, b, texto, pos in tramos_txt:
        if not texto:
            continue
        if rotulos and rotulos[-1]["idx"] == idx:
            rotulos[-1]["hasta"] = b
        else:
            rotulos.append({"idx": idx, "texto": texto, "desde": a, "hasta": b, "posicion": pos})
    _ass(trabajo / "textos.ass", w, h, palabras, {**plan, "textos": [*(plan.get("textos") or []), *rotulos]}, t0)
    if plan.get("efectos_sonido"):  # "pop" cuando aparece un texto
        sonidos += [("pop", r["desde"]) for r in rotulos]
    sonidos = sorted(sonidos, key=lambda x: x[1])[:25]
    entradas, filtros, mezcla = ["-i", "base.mp4"], ["[0:v]ass=textos.ass[v]"], "[0:a]"
    if pista_musica:
        vol = _rango(musica.get("volumen"), 0.02, 0.6, 0.15)
        entradas += ["-stream_loop", "-1", "-i", str(Path(pista_musica).resolve())]
        # la música baja sola cuando hablas (sidechain) y sube en las partes sin voz
        filtros += ["[0:a]asplit=2[voz][guia]",
                    f"[1:a]volume={vol * 2.2:.3f},afade=t=out:st={max(0, t0 - 1.5):.2f}:d=1.5[m]",
                    "[m][guia]sidechaincompress=threshold=0.02:ratio=12:attack=15:release=400[mbaja]",
                    "[voz][mbaja]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[conmusica]"]
        mezcla = "[conmusica]"
    if sonidos:
        tipos = sorted({n for n, _ in sonidos})
        for n in tipos:
            cris._ff("-f", "lavfi", "-i", SFX[n], "-ar", "44100", "-ac", "2", str(trabajo / f"{n}.wav"))
        base_sfx = entradas.count("-i")
        for n in tipos:
            entradas += ["-i", f"{n}.wav"]
            veces = sum(1 for m, _ in sonidos if m == n)
            filtros.append(f"[{base_sfx + tipos.index(n)}:a]volume=0.55,asplit={veces}" + "".join(f"[{n}{k}]" for k in range(veces)))
        etiquetas, usados = [], {}
        for j, (n, t) in enumerate(sonidos):
            ms, k = int(t * 1000), usados.get(n, 0)
            usados[n] = k + 1
            filtros.append(f"[{n}{k}]adelay={ms}|{ms}[s{j}]")
            etiquetas.append(f"[s{j}]")
        filtros.append(f"{mezcla}{''.join(etiquetas)}amix=inputs={len(etiquetas) + 1}:duration=first:dropout_transition=0:normalize=0[consfx]")
        mezcla = "[consfx]"
    filtros.append(f"{mezcla}loudnorm=I=-14:TP=-1.5:LRA=11[a]")
    args = [*entradas, "-filter_complex", ";".join(filtros), "-map", "[v]", "-map", "[a]"]
    r = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args, *cris.FINAL, *cris.AUDIO,
                        "-t", f"{t0:.3f}", str(destino.resolve())], cwd=trabajo, capture_output=True, text=True)
    if r.returncode:
        raise cris.ErrorEdicion("ffmpeg falló al terminar el video: " + (r.stderr.strip().splitlines() or [""])[-1][:200])
    shutil.rmtree(trabajo, ignore_errors=True)
    if info is not None:
        info.update(palabras=palabras or dichas, pedazos=pedazos, segundos=round(t0, 2))
    return round(t0, 1)
