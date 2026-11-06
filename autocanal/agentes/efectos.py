"""Motion graphics de Edu: decide escena por escena qué efecto va y en qué palabra, y los dibuja.

Edu (un editor con 30 años de experiencia en videos de alto impacto) lee el guion y arma un plan:
"en la palabra 'quinientos' sale un contador de $0 a $500 con sonido de caja", "en 'estafa' cae un sello
rojo con un golpe de zoom"… El código sabe dibujar cada efecto con Pillow y ffmpeg; Edu solo elige.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw

from . import claude, config, estilo, graficos, voz

FPS = 30
W, H = 1920, 1080
TIPOS = ["texto_pop", "contador", "sello", "cintillo", "golpe_zoom", "sacudida", "flash", "marco_alerta"]
DIBUJADOS = {"texto_pop", "contador", "sello", "cintillo"}  # los que se dibujan encima del video
SONIDO = {"texto_pop": "pop", "contador": "caja", "sello": "golpe", "cintillo": "whoosh", "golpe_zoom": "golpe",
          "sacudida": "golpe", "flash": "click", "marco_alerta": "alerta"}
MAXIMO = {"nada": 0, "poco": 1, "normal": 2, "mucho": 3}  # efectos por escena según la intensidad

SCHEMA_PLAN = {
    "type": "object",
    "properties": {
        "plan": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "escena": {"type": "integer"},
                "efectos": {"type": "array", "items": {
                    "type": "object",
                    "properties": {
                        "tipo": {"type": "string", "enum": TIPOS},
                        "palabra": {"type": "string", "description": "Palabra EXACTA de la narración de esa escena en la que entra el efecto"},
                        "texto": {"type": "string", "description": "Lo que se ve (texto_pop ≤4 palabras, contador = la cifra como '$500' o '50 USD', sello 1-2 palabras, cintillo ≤6 palabras). Vacío en los demás"},
                        "sonido": {"type": "boolean"},
                    },
                    "required": ["tipo", "palabra", "texto", "sonido"],
                    "additionalProperties": False,
                }},
            },
            "required": ["escena", "efectos"],
            "additionalProperties": False,
        }},
    },
    "required": ["plan"],
    "additionalProperties": False,
}

SISTEMA = """Eres Edu, editor de video y motion graphics con 30 años de experiencia en contenido de alto impacto
para YouTube (canales de reseñas, finanzas y "¿esta app paga o es estafa?"). Sabes que la retención se gana
con ritmo: cada idea importante se refuerza en pantalla justo en la palabra que la dice, y nada se repite tanto
que canse. Usas el motion graphics para ENFATIZAR, no para adornar.

Efectos que puedes usar (el código los dibuja; tú eliges cuál y en qué palabra):
- texto_pop: palabra o frase corta que salta en grande (≤4 palabras, en MAYÚSCULAS si es un golpe emocional).
- contador: una cifra que cuenta desde cero ("$500", "50 USD", "10,000 descargas"). SOLO para cifras dichas.
- sello: sello que cae como estampa: "ESTAFA", "NO PAGA", "OJO", "FALSO", "SÍ PAGA", "REAL", "CUIDADO".
- cintillo: franja tipo noticiero arriba con un dato o advertencia (≤6 palabras).
- golpe_zoom: acercamiento rápido para remarcar una frase fuerte.
- sacudida: la imagen tiembla (sorpresa, enojo, "¡no lo puedo creer!").
- flash: destello blanco para cortar o revelar algo.
- marco_alerta: borde rojo parpadeante (peligro, quejas, dinero perdido).

Reglas de oficio:
- La escena 1 es el gancho: lleva el efecto más fuerte del video.
- "palabra" debe ser una palabra que aparezca TAL CUAL en la narración de esa escena (la del momento exacto).
- No pongas el mismo efecto en dos escenas seguidas, y combina uno visual (golpe_zoom, sacudida, flash) con
  uno dibujado (texto_pop, contador, sello, cintillo) cuando la escena lo merezca.
- Los sellos negativos solo si la evidencia lo dice; el veredicto final merece sello.
- Deja algunas escenas tranquilas: el contraste también es ritmo.
- "sonido" en true casi siempre; en false si la escena ya está muy cargada."""


def _norm(p: str) -> str:
    p = unicodedata.normalize("NFD", p.lower())
    return re.sub(r"[^a-z0-9ñ$]", "", "".join(c for c in p if unicodedata.category(c) != "Mn"))


def palabras(esc: dict) -> list[dict]:
    """[{t, d, w}] en segundos desde que empieza la escena. Usa los tiempos reales de la voz si los hay;
    si no (ElevenLabs, pruebas), los reparte según el largo de cada palabra."""
    if esc.get("audio"):
        f = voz.tiempos(esc["audio"])
        if f.exists():
            try:
                lista = json.loads(f.read_text(encoding="utf-8"))
                if lista:
                    return lista
            except (json.JSONDecodeError, OSError):
                pass
    texto = voz.limpiar(esc.get("narracion", "")).split()
    if not texto:
        return []
    dur = float(esc.get("duracion") or 1)
    pesos = [len(w) + 2 for w in texto]
    total, t, salida = sum(pesos), 0.08 * dur, []
    util = dur * 0.9
    for w, p in zip(texto, pesos):
        d = util * p / total
        salida.append({"t": round(t, 3), "d": round(d * 0.9, 3), "w": w})
        t += d
    return salida


def momento(efecto: dict, pals: list[dict], dur: float) -> float:
    """Segundo (dentro de la escena) en que entra el efecto: cuando se dice su palabra."""
    buscada = _norm(efecto.get("palabra", ""))
    if buscada:
        for p in pals:
            if _norm(p["w"]) == buscada:
                return p["t"]
        for p in pals:  # "500" vs "$500", "estafa" vs "estafadores"
            n = _norm(p["w"])
            if n and (buscada in n or n in buscada) and min(len(n), len(buscada)) >= 3:
                return p["t"]
    return round(dur * 0.3, 3)


# ---------- el plan ----------
def _validar(plan: list, escenas: list[dict], maximo: int) -> list[list[dict]]:
    por_escena = [[] for _ in escenas]
    for item in plan or []:
        i = int(item.get("escena") or 0) - 1
        if not 0 <= i < len(escenas):
            continue
        for e in item.get("efectos") or []:
            if e.get("tipo") not in TIPOS or len(por_escena[i]) >= maximo:
                continue
            texto = re.sub(r"\s+", " ", str(e.get("texto") or "")).strip()[:40]
            if e["tipo"] in DIBUJADOS and not texto:
                continue
            if e["tipo"] == "contador" and not re.search(r"\d", texto):
                e = {**e, "tipo": "texto_pop"}  # sin cifra no hay qué contar
            por_escena[i].append({"tipo": e["tipo"], "palabra": str(e.get("palabra") or "")[:40], "texto": texto,
                                  "sonido": bool(e.get("sonido", True))})
    return por_escena


def planear(escenas: list[dict], carpeta: Path) -> list[list[dict]]:
    """Plan de motion graphics por escena (se guarda: si el guion no cambia no se vuelve a pedir)."""
    ajustes = estilo.cargar()["ajustes"]
    intensidad = ajustes.get("motion", "normal")
    maximo = MAXIMO.get(intensidad, 2)
    if not maximo or not escenas:
        return [[] for _ in escenas]
    edicion = estilo.cargar().get("edicion") or {}
    firma = hashlib.sha1(json.dumps([[e.get("narracion"), e.get("visual"), e.get("texto")] for e in escenas]
                                    + [intensidad, edicion.get("descripcion")], ensure_ascii=False).encode()).hexdigest()[:12]
    archivo = carpeta / "plan_edicion.json"
    if archivo.exists():
        try:
            guardado = json.loads(archivo.read_text(encoding="utf-8"))
            if guardado.get("firma") == firma:
                return guardado["efectos"]
        except (json.JSONDecodeError, KeyError):
            pass
    lineas = [f"Escena {i} ({e.get('duracion', 0):.1f} s, visual: {e.get('visual')}"
              + (f", texto en pantalla: «{e['texto']}»" if e.get("texto") else "") + f"): {e.get('narracion', '')}"
              for i, e in enumerate(escenas, 1)]
    referencia = ""
    if edicion:
        referencia = (f"\n\nEstilo de edición que le gusta al creador (de su video de referencia): {edicion.get('descripcion', '')}"
                      f" Ritmo ≈{edicion.get('cortes_por_minuto', '?')} cortes por minuto."
                      + (f" Efectos que se ven en la referencia: {', '.join(edicion.get('efectos') or [])}." if edicion.get("efectos") else ""))
    pedido = (f"Intensidad pedida: {intensidad} (máximo {maximo} efecto(s) por escena).{referencia}\n\n"
              "Guion:\n" + "\n".join(lineas) + "\n\nArma el plan de motion graphics, escena por escena.")
    try:
        r = claude.json_estructurado(SISTEMA, pedido, SCHEMA_PLAN, tarea="edicion", que="plan de motion graphics")
        efectos = _validar(r.get("plan"), escenas, maximo)
    except Exception as exc:  # noqa: BLE001 — sin plan el video sale igual, solo sin efectos
        print(f"  · no pude armar el plan de efectos ({exc}); el video sale sin motion graphics", flush=True)
        return [[] for _ in escenas]
    archivo.write_text(json.dumps({"firma": firma, "efectos": efectos}, ensure_ascii=False, indent=1), encoding="utf-8")
    return efectos


# ---------- sonidos (se generan una vez, sin archivos con derechos) ----------
SONIDOS = {
    "pop": "aevalsrc='0.6*sin(2*PI*(520+900*t)*t)*exp(-28*t)':d=0.18",
    "caja": "aevalsrc='0.45*(sin(2*PI*1320*t)+0.7*sin(2*PI*1980*t))*exp(-6*t)':d=0.8",
    "golpe": "aevalsrc='0.9*sin(2*PI*(95-55*t)*t)*exp(-7*t)':d=0.6",
    "whoosh": "anoisesrc=d=0.5:c=pink:a=0.5,bandpass=f=1400:w=1200,afade=t=in:d=0.25,afade=t=out:st=0.25:d=0.25",
    "click": "anoisesrc=d=0.07:c=white:a=0.6,afade=t=out:d=0.07",
    "alerta": "aevalsrc='0.35*sin(2*PI*if(lt(mod(t\\,0.3)\\,0.15)\\,880\\,660)*t)':d=0.6",
}


def sonido(nombre: str) -> Path:
    carpeta = config.BASE / "estilo" / "sfx"
    carpeta.mkdir(parents=True, exist_ok=True)
    propio = carpeta / f"{nombre}_propio.mp3"  # si algún día subes los tuyos
    if propio.exists():
        return propio
    ruta = carpeta / f"{nombre}.wav"
    if not ruta.exists():
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", SONIDOS[nombre],
                        "-ar", "44100", "-ac", "1", str(ruta)], check=True)
    return ruta


# ---------- dibujos (cuadros PNG transparentes) ----------
def _texto_img(texto: str, tam: int, color, borde=(0, 0, 0), grosor: int = 10) -> Image.Image:
    f = graficos.fuente(tam)
    caja = ImageDraw.Draw(Image.new("RGBA", (1, 1))).textbbox((0, 0), texto, font=f, stroke_width=grosor)
    img = Image.new("RGBA", (caja[2] - caja[0] + 20, caja[3] - caja[1] + 20), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((10 - caja[0], 10 - caja[1]), texto, font=f, fill=color, stroke_width=grosor,
                             stroke_fill=borde)
    if img.width > W - 120:
        img = img.resize((W - 120, int(img.height * (W - 120) / img.width)), Image.LANCZOS)
    return img


def _cuadro(pieza: Image.Image, escala: float, centro: tuple[int, int], angulo: float = 0,
            oscuro: int = 0) -> Image.Image:
    """Un cuadro de 1920x1080 transparente con la pieza. `oscuro` (0-255) oscurece el video detrás para que
    el texto se lea encima de cualquier cosa."""
    lienzo = Image.new("RGBA", (W, H), (0, 0, 0, oscuro))
    p = pieza.resize((max(1, int(pieza.width * escala)), max(1, int(pieza.height * escala))), Image.LANCZOS)
    if angulo:
        p = p.rotate(angulo, expand=True, resample=Image.BICUBIC)
    lienzo.alpha_composite(p, (int(centro[0] - p.width / 2), int(centro[1] - p.height / 2)))
    return lienzo


POP = [0.45, 0.8, 1.12, 1.18, 1.08, 1.0]
GOLPE_SELLO = [2.2, 1.7, 1.25, 0.94, 1.03, 1.0]


def _dibujar(efecto: dict, carpeta: Path, nombre: str, colores: dict) -> tuple[str, float, float]:
    """Guarda los cuadros de la animación; devuelve (patrón de archivos, segundos quieto, segundos de animación)."""
    tipo, texto = efecto["tipo"], efecto["texto"]
    cuadros: list[Image.Image] = []
    if tipo == "texto_pop":
        pieza = _texto_img(texto, 130, colores["acento"])
        cuadros = [_cuadro(pieza, s, (W // 2, 420), oscuro=min(120, 30 * (k + 1))) for k, s in enumerate(POP)]
        quieto = 1.2
    elif tipo == "contador":
        m = re.search(r"\d[\d,\.]*", texto)
        num_txt = m.group(0)
        decimales = len(num_txt.split(".")[1]) if "." in num_txt and len(num_txt.split(".")[-1]) <= 2 else 0
        valor = float(num_txt.replace(",", "")) if decimales else float(num_txt.replace(",", "").replace(".", ""))
        antes, despues = texto[:m.start()], texto[m.end():]
        n = 20
        for k in range(n + 1):
            x = 1 - (1 - k / n) ** 3  # frena al final
            v = valor * x
            cifra = f"{v:,.{decimales}f}" if decimales else f"{int(round(v)):,}"
            escala = 1.0 + (0.12 if k == n else 0)
            cuadros.append(_cuadro(_texto_img(f"{antes}{cifra}{despues}", 170, colores["numero"]), escala, (W // 2, 420),
                                   oscuro=min(130, 26 * (k + 1))))
        cuadros.append(_cuadro(_texto_img(texto, 170, colores["numero"]), 1.0, (W // 2, 420), oscuro=130))
        quieto = 1.3
    elif tipo == "sello":
        color = graficos.COLOR_SELLO.get(texto.upper(), (34, 197, 94) if re.search(r"S[IÍ]\b|REAL", texto.upper()) else graficos.ROJO)
        t = _texto_img(texto.upper(), 110, color + (255,), borde=(255, 255, 255), grosor=4)
        pieza = Image.new("RGBA", (t.width + 70, t.height + 50), (0, 0, 0, 0))
        d = ImageDraw.Draw(pieza)
        d.rounded_rectangle((6, 6, pieza.width - 6, pieza.height - 6), radius=22, outline=color + (255,), width=12,
                            fill=(255, 255, 255, 215))
        pieza.alpha_composite(t, (35, 25))
        cuadros = [_cuadro(pieza, s, (W - 420, 250), angulo=-12) for s in GOLPE_SELLO]
        quieto = 1.6
    elif tipo == "cintillo":
        t = _texto_img(texto.upper(), 62, (255, 255, 255, 255), grosor=0)
        pieza = Image.new("RGBA", (t.width + 120, t.height + 36), colores["franja"] + (240,))
        ImageDraw.Draw(pieza).rectangle((0, 0, 22, pieza.height), fill=(255, 255, 255, 255))
        pieza.alpha_composite(t, (70, 18))
        for k in range(8):
            x = 1 - (1 - (k + 1) / 8) ** 3
            lienzo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            lienzo.alpha_composite(pieza, (int(-pieza.width + (pieza.width + 60) * x), 70))
            cuadros.append(lienzo)
        quieto = 2.2
    else:
        raise ValueError(tipo)
    for k, c in enumerate(cuadros):
        c.save(carpeta / f"{nombre}_{k:03d}.png", optimize=False, compress_level=1)
    return str(carpeta / f"{nombre}_%03d.png"), quieto, len(cuadros) / FPS


def colores() -> dict:
    spec = {**graficos.ESTILO_DEFECTO, **(estilo.cargar().get("miniaturas") or {})}
    acento = graficos._rgb(spec.get("color_acento"), graficos.AMARILLO)
    return {"acento": acento + (255,), "numero": graficos.AMARILLO + (255,), "franja": graficos.ROJO}


# ---------- aplicar a una escena ----------
def aplicar(base: Path, efectos: list[dict], pals: list[dict], dur: float, total: float, destino: Path,
            trabajo: Path, i: int) -> None:
    """Toma el video de una escena ya armado y le pone encima los efectos del plan, con sus sonidos."""
    carpeta = trabajo / "fx"
    carpeta.mkdir(parents=True, exist_ok=True)
    pal = colores()
    entradas = ["-i", str(base)]
    filtros, actual = [], "[0:v]"
    momentos = [(e, min(max(momento(e, pals, dur), 0.0), max(dur - 0.4, 0.0))) for e in efectos]

    # 1) movimientos de cámara (zoom de golpe y sacudidas) en una sola pasada
    golpes = [t for e, t in momentos if e["tipo"] == "golpe_zoom"]
    sacudidas = [t for e, t in momentos if e["tipo"] == "sacudida"]
    if golpes or sacudidas:
        T = "(in/30)"
        z = "1" + "".join(f"+0.16*exp(-7*({T}-{t:.2f}))*gte({T},{t:.2f})" for t in golpes)
        z += "".join(f"+0.06*between({T},{t:.2f},{t + 0.5:.2f})" for t in sacudidas)
        sx = "".join(f"+22*sin({T}*80)*between({T},{t:.2f},{t + 0.5:.2f})" for t in sacudidas)
        sy = "".join(f"+14*cos({T}*67)*between({T},{t:.2f},{t + 0.5:.2f})" for t in sacudidas)
        filtros.append(f"{actual}zoompan=z='{z}':x='iw/2-(iw/zoom/2){sx}':y='ih/2-(ih/zoom/2){sy}'"
                       f":d=1:s={W}x{H}:fps={FPS},setsar=1[cam]")
        actual = "[cam]"
    # 2) destellos y bordes de alerta
    cajas = []
    for e, t in momentos:
        if e["tipo"] == "flash":
            cajas.append(f"drawbox=x=0:y=0:w=iw:h=ih:color=white@0.75:t=fill:enable='between(t,{t:.2f},{t + 0.07:.2f})'")
            cajas.append(f"drawbox=x=0:y=0:w=iw:h=ih:color=white@0.3:t=fill:enable='between(t,{t + 0.07:.2f},{t + 0.15:.2f})'")
        elif e["tipo"] == "marco_alerta":
            cajas.append(f"drawbox=x=0:y=0:w=iw:h=ih:color=0xFF3B30@0.95:t=24"
                         f":enable='between(t,{t:.2f},{t + 1.8:.2f})*lt(mod(t-{t:.2f},0.4),0.26)'")
    if cajas:
        filtros.append(f"{actual}{','.join(cajas)}[cajas]")
        actual = "[cajas]"
    # 3) lo dibujado (textos, contador, sello, cintillo)
    for k, (e, t) in enumerate(momentos):
        if e["tipo"] not in DIBUJADOS:
            continue
        patron, quieto, anim = _dibujar(e, carpeta, f"e{i:02d}_{k}", pal)
        quieto = max(0.4, min(quieto, total - t - anim - 0.1))
        entradas += ["-framerate", str(FPS), "-i", patron]
        n = entradas.count("-i") - 1
        filtros.append(f"[{n}:v]format=rgba,tpad=stop_mode=clone:stop_duration={quieto:.2f},"
                       f"fade=t=out:st={anim + quieto - 0.18:.2f}:d=0.18:alpha=1,setpts=PTS+{t:.2f}/TB[o{k}]")
        filtros.append(f"{actual}[o{k}]overlay=0:0:eof_action=pass[v{k}]")
        actual = f"[v{k}]"
    # 4) sonidos en el momento exacto
    mezcla = ["[0:a]"]
    for k, (e, t) in enumerate(momentos):
        if not e.get("sonido"):
            continue
        entradas += ["-i", str(sonido(SONIDO[e["tipo"]]))]
        n = entradas.count("-i") - 1
        ms = int(t * 1000)
        filtros.append(f"[{n}:a]aformat=sample_rates=44100:channel_layouts=stereo,volume=0.55,adelay={ms}:all=1[s{k}]")
        mezcla.append(f"[s{k}]")
    if len(mezcla) > 1:
        filtros.append("".join(mezcla) + f"amix=inputs={len(mezcla)}:duration=first:normalize=0[a]")
        audio = "[a]"
    else:
        audio = "0:a"
    if actual == "[0:v]":
        filtros.append("[0:v]null[vfin]")
        actual = "[vfin]"
    script = trabajo / f"fx_{i:02d}.txt"
    script.write_text(";\n".join(filtros), encoding="utf-8")
    from .editor import AUDIO, RAPIDO, _ff
    _ff(*entradas, "-filter_complex_script", str(script), "-map", actual, "-map", audio, "-t", f"{total:.3f}",
        *RAPIDO, *AUDIO, str(destino))
    for f in carpeta.glob(f"e{i:02d}_*.png"):
        f.unlink()
