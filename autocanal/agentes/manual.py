"""📘 Manual del canal: la "skill" que leen todos los agentes antes de trabajar.

Es texto (Markdown) en estilo/manual.md: cómo es el gancho, cuánto dura cada parte, cómo hablan las voces, qué se
ve y qué suena, cómo son las miniaturas y los títulos. Se escribe solo a partir de los videos que te gustan
(Claude ve sus cuadros y escucha lo que dicen) y de lo que ya aprendieron Dani, Edu y Rosa; lo puedes leer y
corregir en la pestaña Estilo y bajarlo como skill para usarlo también en tus chats de Claude.
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

from . import claude, config, estilo

ARCHIVO = estilo.DIR / "manual.md"
LIMITE = 9000  # caracteres que se le pasan a cada agente (cabe de sobra y no encarece)

DEFECTO = f"""# Manual del canal «{config.CANAL_NOMBRE}»

## Canal y público
- Canal de YouTube en español de México. Público: gente que quiere ganar dinero con su celular o saber si una app
  es real, y también temas de tecnología y videojuegos cuando el jefe los pide.
- Promesa del canal: "lo probé / lo investigué por ti, con pruebas". Honesto, directo, nada de humo.

## Gancho (lo más importante)
- La primera frase se escribe palabra por palabra y se dice en menos de 4 segundos (≈10 palabras).
- Empieza a media acción, con la promesa contra la realidad o el dato más fuerte. Nunca "hola, bienvenidos".
- En pantalla, al mismo tiempo: texto grande de 2 a 5 palabras y algo que se mueve.

## Estructura y duración
- 150 palabras por minuto de video. Escenas de 4 a 20 segundos.
- Cada ~60 segundos, un re-gancho: una frase que deja con ganas de lo que sigue ("y espérate a ver lo que pasó
  cuando quise retirar…").
- Cierre: veredicto u opinión clara, una pregunta para comentarios y suscribirse. Sin despedidas largas.

## Cómo se escribe (guion en tabla)
- Cada escena tiene: lo que se dice · lo que se ve · lo que suena.
- Cada frase debe poder ilustrarse; si una frase no tiene imagen, se reescribe.
- Frases cortas, de compa a compa, números como se dicen. Sin emojis ni símbolos en lo que se lee.

## Voces
- Voz principal: el narrador, seguro y cercano.
- Segunda voz (opcional): pregunta o reacciona en frases cortas ("¿neta?", "¿y sí pagó?") para que no suene a
  robot leyendo. Sin pausas largas.

## Lo que se ve
- Nunca una imagen quieta más de 3 segundos: zoom, cortes, textos que entran con la voz.
- Motion graphics en las palabras clave: cifras que cuentan, sellos (NO PAGA, OJO), textos que saltan.
- Subtítulos karaoke. Si hay mascota del canal, aparece en cada escena.

## Lo que suena
- Música de fondo baja. Un efecto en cada cambio de escena y en cada motion graphic.

## Miniaturas y títulos
- Miniatura: 2 a 4 palabras enormes, icono o imagen grande, alto contraste, legible en chiquito.
- Títulos: curiosos y honestos, máximo 70 caracteres; nada de clickbait falso.

## Nunca
- Inventar datos, reseñas o pruebas. Decir "estafa" sin evidencia fuerte.
- Empezar lento, repetir ideas, dejar segundos muertos.
"""


def leer() -> str:
    try:
        texto = ARCHIVO.read_text(encoding="utf-8").strip()
        return texto or DEFECTO
    except OSError:
        return DEFECTO


def guardar(texto: str) -> None:
    estilo.DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVO.write_text(texto.strip()[:20000] + "\n", encoding="utf-8")


def para_agente() -> str:
    """El manual tal cual, listo para pegarse en las instrucciones de un agente."""
    return ("MANUAL DEL CANAL (síguelo siempre; manda sobre cualquier regla general que contradiga):\n"
            + leer()[:LIMITE])


def como_skill() -> str:
    """El manual con el formato de una skill de Claude (SKILL.md), para usarlo también en tus chats."""
    nombre = re.sub(r"[^a-z0-9]+", "-", config.CANAL_NOMBRE.lower()).strip("-") or "mi-canal"
    return (f'---\nname: "manual-{nombre}"\n'
            f'description: "Cómo se hacen los videos del canal {config.CANAL_NOMBRE}: gancho, estructura, voces, '
            'visuales, sonido, miniaturas y títulos. Úsala cuando pidan un video, guion, miniatura o título para el canal."\n'
            "---\n\n" + leer())


# ---------- que Claude lo escriba ----------
SCHEMA = {
    "type": "object",
    "properties": {
        "manual": {"type": "string", "description": "El manual completo en Markdown, con las mismas secciones"},
        "cambios": {"type": "array", "items": {"type": "string"}, "description": "Qué cambió respecto al anterior, en frases cortas"},
    },
    "required": ["manual", "cambios"],
    "additionalProperties": False,
}

SISTEMA = """Eres un productor de YouTube con 30 años de experiencia (guion, edición, motion graphics, miniaturas).
Escribes el MANUAL de un canal: el documento que leen todos los agentes de IA que hacen sus videos (investigador,
guionista, locutores, editor, diseñadora de miniaturas, redactora). Debe ser concreto y medible: segundos,
palabras, colores en hex, frases de ejemplo. Nada genérico.

Mantén las secciones del manual actual (Canal y público, Gancho, Estructura y duración, Cómo se escribe, Voces,
Lo que se ve, Lo que suena, Miniaturas y títulos, Nunca). Mejóralo con lo que te muestran los videos de referencia
y lo que el jefe ha pedido; respeta sus gustos por encima de todo. Lo que la oficina no puede hacer (grabar en
la calle, actuar) no lo pongas como regla. Las reglas de honestidad (no inventar, no acusar sin evidencia) se
quedan siempre."""


def _transcribir(video: Path, segundos: int = 150) -> str:
    """Lo que se dice en el video de referencia (Whisper local, gratis). Vacío si no está instalado."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return ""
    with tempfile.TemporaryDirectory() as tmp:
        audio = Path(tmp) / "a.wav"
        r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-t", str(segundos), "-i", str(video), "-vn",
                            "-ac", "1", "-ar", "16000", str(audio)], check=False)
        if r.returncode or not audio.exists():
            return ""
        try:
            modelo = WhisperModel(config.env("WHISPER_MODELO", "small"), device="cpu", compute_type="int8")
            partes, _ = modelo.transcribe(str(audio), language="es", vad_filter=True)
            return " ".join(f"[{p.start:.0f}s] {p.text.strip()}" for p in partes)[:6000]
        except Exception as exc:  # noqa: BLE001 — sin transcripción el manual sale igual (solo con lo visual)
            print(f"  · no pude transcribir la referencia: {exc}", flush=True)
            return ""


def escribir(preferencias: list[str] | None = None, url: str = "") -> dict:
    """Escribe (o mejora) el manual con: los videos que te gustan, lo aprendido y tus preferencias."""
    if url:
        estilo.bajar_referencia(url)
    datos = estilo.cargar()
    contenido = []
    video = estilo.archivo("referencia")
    if video:
        import json as _json

        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                    str(video)], capture_output=True, text=True).stdout.strip() or 0)
        analizar = min(dur, 150.0)
        with tempfile.TemporaryDirectory() as tmp:
            for k in range(10):
                t = analizar * (k + 0.5) / 10
                p = Path(tmp) / f"c{k}.jpg"
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v",
                                "1", "-vf", "scale=640:-2", str(p)], check=False)
                if p.exists():
                    contenido += [{"type": "text", "text": f"Video de referencia, segundo {t:.0f}:"}, estilo.imagen_bloque(p, 640)]
        dicho = _transcribir(video)
        if dicho:
            palabras = len(re.sub(r"\[\d+s\]", "", dicho).split())
            contenido.append({"type": "text", "text": (
                f"LO QUE SE DICE en el video de referencia (primeros {analizar:.0f} s, {palabras} palabras ≈ "
                f"{palabras / max(analizar, 1) * 60:.0f} por minuto):\n{dicho}")})
        if datos.get("edicion"):
            contenido.append({"type": "text", "text": "LO QUE EDU MIDIÓ DE SU EDICIÓN:\n"
                              + _json.dumps(datos["edicion"], ensure_ascii=False)})
    import json as _json

    for clave, nombre in (("miniaturas", "ESTILO DE MINIATURAS QUE APRENDIÓ DANI"), ("blog", "ESTILO DEL BLOG QUE APRENDIÓ ROSA")):
        if datos.get(clave):
            contenido.append({"type": "text", "text": f"{nombre}:\n{_json.dumps(datos[clave], ensure_ascii=False)[:2500]}"})
    if preferencias:
        contenido.append({"type": "text", "text": "LO QUE EL JEFE HA PEDIDO O DICHO (respétalo):\n"
                          + "\n".join(f"- {p}" for p in preferencias[-30:])})
    contenido.append({"type": "text", "text": f"MANUAL ACTUAL:\n{leer()}\n\nEscribe el manual mejorado."})
    r = claude.json_estructurado(SISTEMA, contenido, SCHEMA, tarea="estilo", que="escribir el manual del canal")
    texto = r["manual"].strip()
    if len(texto) < 400:
        raise claude.ErrorIA("El manual salió demasiado corto; no lo cambié.")
    anterior = ARCHIVO.with_name("manual_anterior.md")
    if ARCHIVO.exists():
        anterior.write_text(ARCHIVO.read_text(encoding="utf-8"), encoding="utf-8")
    guardar(texto)
    return {"cambios": r.get("cambios", [])[:8], "largo": len(texto)}
