"""🎬 Claude edita los videos de YouTube de la oficina en tu compu (trabajo "edu_ia").

La oficina manda el paquete de siempre (audios por escena con tiempos de palabras, imágenes, grabaciones, guion,
estilo, mascota). Aquí:
1. se arma `materiales.md` (qué dura cada escena, qué se dice, qué imágenes y clips hay) y un `edu.json` borrador;
2. Claude Code (tu plan) dirige la edición: escribe `edu.json` con el kit Edu de Remotion (texto cinético, celular,
   chat, datos, comparativas, sellos, mascota, zooms, sacudidas, efectos de sonido…), renderiza, revisa y corrige;
3. si algo falla, se edita con la plantilla de siempre para que el video nunca se quede sin hacer.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent

GUIA = """# Eres el editor de video de YouTube de Miguel — «{titulo}»

Canal: **{canal}**. Público: México, gente que quiere cuidar o ganar dinero desde el celular. Tu trabajo: que este
video se vea hecho por un editor de YouTube de primer nivel (estilo de los canales grandes de explicación y
alertas), NO por una plantilla: ritmo, sorpresa visual cada pocos segundos, todo lo que se dice se VE.
Hablas español de México. Trabajas en esta carpeta (tu mesa). Usa tu criterio de director.

## Lo que tienes
- `materiales.md`: cada escena con su duración EXACTA (la de su narración), lo que se dice, el momento (gancho,
  desarrollo, regancho, cierre), lo que el guionista sugirió que se viera, y la lista de imágenes, grabaciones,
  mascota, efectos de sonido y música disponibles. **Léelo completo primero.**
- `edu.json`: un borrador que ya trae cada escena con su audio, duración y palabras. **No cambies `audio`,
  `duracion` ni `palabras`** (son la voz: si los mueves se desfasa). Tú decides `fondo`, `capas`, `transicion`,
  `sfx` y los ajustes generales.
- Las imágenes y grabaciones: míralas con Read antes de usarlas (img/, clips/; para clips usa
  `{t} cuadros clips/ARCHIVO 0 30 6` y mira la hoja).

## Herramientas (con Bash, desde esta carpeta)
- `{t} edu edu.json prueba.mp4 DESDE HASTA` → renderiza solo un tramo (segundos) para revisar rápido.
- `{t} edu edu.json video_final.mp4` → el video completo (tarda varios minutos; hazlo UNA vez al final).
- `{t} revisar ARCHIVO.mp4` → hoja de cuadros + lo que se oye; mírala con Read.

## El kit (edu.json) — todo en segundos; `desde`/`hasta` de las capas son RELATIVOS al inicio de su escena
```json
{{"acento": "{acento}", "acento2": "#22c55e", "peligro": "#ef4444", "barra": true,
 "subtitulos": {{"activar": true, "estilo": "pop", "y": 0.86, "porGrupo": 3}},
 "musica": {{"archivo": "estilo/musica.mp3", "volumen": 0.07}},
 "escenas": [{{"audio": "...", "duracion": 4.2, "palabras": [...], "transicion": "destello",
   "fondo": {{"tipo": "imagen", "archivo": "img/captura_1.png", "movimiento": "acercar", "ajuste": "contener", "oscurecer": 0.3}},
   "capas": [{{"tipo": "texto", "desde": 0.2, "texto": "TE PROMETE $500", "estilo": "golpe", "y": 0.4}}],
   "sfx": [{{"archivo": "estilo/sfx/whoosh.mp3", "desde": 0, "volumen": 0.5}}]}}]}}
```
Fondos (`fondo.tipo`): `imagen` (`movimiento`: acercar|alejar|izquierda|derecha|fijo; `ajuste: "contener"` para
capturas verticales: se ven completas sobre su propia imagen desenfocada; `desenfocar: true` para usarla de ambiente;
`oscurecer` 0-0.8), `video` (grabación; `desde` = segundo del clip; elige un tramo que dure lo que la escena),
`degradado` (`color`, `color2`), `color`.
Capas (`tipo`) y sus campos:
- `texto` {{texto, estilo: pop|golpe|maquina, x, y, tamano, color}} — texto cinético (palabras que entran). Cifras y
  la última palabra salen del color de acento. Máx. ~7 palabras.
- `titulo_seccion` {{texto: "#3", titulo: "Te piden tus contactos"}} — cortinilla para cambiar de bloque.
- `dato` {{numero, prefijo, sufijo, decimales, texto: "etiqueta"}} — contador grande que sube hasta la cifra.
- `celular` {{archivo: imagen o video, numero: segundo del video, x, angulo, tamano}} — la app dentro de un celular.
- `chat` {{nombre, mensajes: [{{"de": "ellos"|"yo", "texto"}}], x, tamano}} — chat tipo WhatsApp que se va escribiendo.
- `resena` {{usuario, estrellas, texto}} — reseña que se escribe sola (texto COPIADO tal cual de los materiales).
- `lista` {{titulo, textos: [..], estilo: numeros|check|x}} — puntos que entran uno por uno.
- `comparativa` {{izquierda: {{titulo, puntos}}, derecha: {{titulo, puntos}}}} — promesa vs realidad (verde vs rojo).
- `alerta` {{texto}} — alerta roja con el borde de la pantalla latiendo.
- `sello` {{texto, x, y, angulo, color}} — sello que cae de golpe ("ESTAFA", "NO PAGA", "CUIDADO").
- `imagen` {{archivo, lado: izquierda|derecha, tamano}} — foto/captura en tarjeta que entra de lado.
- `mascota` {{archivo, lado, texto (globo opcional), tamano}} — la mascota reacciona (usa la expresión que va).
- `emoji` {{texto, x, y}}, `flecha` {{x, y, angulo}}, `circulo` {{x, y}} — señalar algo en pantalla.
- `cintillo` {{titulo, texto}} — rótulo abajo a la izquierda (fuente, dato, nombre de la app).
- Efectos de cámara: `zoom_golpe` {{desde, hasta, tamano: 0.15-0.3}}, `sacudida` {{desde, hasta}}, `destello` {{desde}}.
Transiciones de escena: corte | zoom | barrido | destello | deslizar.

## Cómo dirige un editor de primer nivel (síguelo)
- **Gancho (primeros 5-8 s)**: lo más fuerte de todo el video. Texto `golpe` con la promesa o la amenaza, `zoom_golpe`
  en la palabra clave, sonido, mascota reaccionando. Nada de logos ni presentaciones.
- **Algo cambia en pantalla cada 2-4 segundos** (capa nueva, zoom, cambio de fondo, efecto): es lo que retiene.
  Pero **una idea a la vez**: máximo 2 capas grandes al mismo tiempo; deja aire.
- **Lo que se dice, se ve**: cifra → `dato`; mensajes o amenazas → `chat`; lo que dice la gente → `resena`;
  promesa contra realidad → `comparativa`; pasos o señales → `lista`; la app → `celular` con su captura o grabación;
  peligro → `alerta`/`sello`. Usa los tiempos de `palabras` para que cada capa entre JUSTO cuando se dice.
- **Regancho** (momento "regancho"): cortinilla `titulo_seccion` o un `zoom_golpe` + sonido.
- **La grabación de la prueba (si hay) es oro**: úsala como fondo `video` en las escenas que la narran, con el tramo
  que corresponde (en materiales viene qué se ve en cada segundo). Señala lo importante con `circulo`/`flecha`.
- **Variedad**: no repitas el mismo tipo de capa dos escenas seguidas; alterna fondos (imagen, video, degradado).
- **Sonido**: whoosh en transiciones, un golpe en sellos y zooms (los que haya en estilo/sfx). Música bajita (0.05-0.09).
- **Cierre**: conclusión clara (`sello` o `lista`), y la mascota despidiéndose.
- **Nada inventado**: textos, cifras, nombres y reseñas solo si están en materiales. Si no hay dato, no lo pongas.
- Colores del canal: acento {acento}. Respeta lo que diga «Dirección del canal» abajo.

## Dirección del canal (manual, correcciones del jefe y lo que dicen sus números)
{direccion}

## Cómo trabajas (máximo ~60 min contando el render; cuida el plan de Claude de Miguel)
1. Lee `materiales.md`. Mira con Read las imágenes que vas a usar (no hace falta ver todas si son muchas).
2. Escribe `plan.md`: en una línea por escena, qué se ve y por qué (ritmo del video completo).
3. Llena `edu.json` (fondo, capas, transicion, sfx de cada escena; subtítulos y música).
4. Renderiza el gancho (`edu edu.json prueba.mp4 0 15`) y `revisar prueba.mp4`: míralo con Read y corrige lo que esté
   encimado, ilegible, vacío o feo. Haz lo mismo con un tramo de en medio si dudas.
5. Renderiza el video completo a `video_final.mp4` y revísalo una vez (`revisar video_final.mp4`).
6. Escribe `resultado.json`: {{"ok": true, "resumen": "cómo lo editaste en 2 frases"}}.
"""


def _segundos(archivo: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(archivo)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def preparar(mesa: Path, m: dict) -> tuple[str, dict]:
    """materiales.md + edu.json borrador. Regresa (materiales, borrador)."""
    lineas, escenas = [], []
    for i, e in enumerate(m["escenas"], 1):
        audio = e.get("audio")
        dur = round(_segundos(mesa / audio), 3) if audio and (mesa / audio).exists() else 3.0
        palabras = []
        tiempos = mesa / f"audio/escena_{i:02d}.palabras.json"
        if tiempos.exists():
            try:
                palabras = [{"w": p["w"], "t": round(float(p["t"]), 3), "d": round(float(p.get("d") or 0.3), 3)}
                            for p in json.loads(tiempos.read_text(encoding="utf-8"))]
            except (ValueError, KeyError, TypeError):
                palabras = []
        escenas.append({"audio": audio, "duracion": dur, "palabras": palabras, "transicion": "corte",
                        "fondo": {"tipo": "degradado"}, "capas": [], "sfx": []})
        sugerido = f"{e.get('visual', '')}" + (f" «{e.get('texto')}»" if e.get("texto") else "") \
            + (f" (índice {e.get('indice')})" if e.get("indice") else "") + (f", desde {e.get('desde')} s" if e.get("desde") else "")
        lineas.append(f"### Escena {i} — {dur:.1f} s — {e.get('momento', 'desarrollo')}\n"
                      f"Se dice: «{e.get('narracion', '')}»\nEl guionista sugirió: {sugerido} · sonido: {e.get('sonido', '')}\n")
    archivos = sorted(str(p.relative_to(mesa)).replace("\\", "/") for p in mesa.rglob("*")
                      if p.is_file() and p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".gif"))
    imagenes = [a for a in archivos if a.startswith("img/")]
    mascotas = [a for a in archivos if "mascota" in a]
    clips = []
    for p in sorted((mesa / "clips").glob("*")) if (mesa / "clips").exists() else []:
        clips.append(f"{p.relative_to(mesa).as_posix()} ({_segundos(p):.0f} s)")
    sfx = sorted(p.relative_to(mesa).as_posix() for p in (mesa / "estilo").rglob("*")
                 if p.suffix.lower() in (".mp3", ".wav", ".m4a") and "musica" not in p.name) if (mesa / "estilo").exists() else []
    musica = "estilo/musica.mp3" if (mesa / "estilo" / "musica.mp3").exists() else ""
    prueba = m.get("prueba") or {}
    momentos = "\n".join(f"- {x.get('grabacion', 1)}: segundo {x.get('segundo')}: {x.get('que_se_ve')}"
                         for x in prueba.get("momentos") or [])
    texto = (f"# Materiales — «{m['ctx']['ficha'].get('title', '')}»\n\n"
             f"Duración total: {sum(e['duracion'] for e in escenas):.0f} s en {len(escenas)} escenas.\n\n"
             f"## Imágenes ({len(imagenes)})\n" + "\n".join(f"- {a}" for a in imagenes) + "\n\n"
             f"## Grabaciones / clips ({len(clips)})\n" + ("\n".join(f"- {c}" for c in clips) or "(ninguna)") + "\n"
             + (f"\nQué se ve en la grabación:\n{momentos}\n" if momentos else "")
             + f"\n## Mascota\n" + ("\n".join(f"- {a}" for a in mascotas) or "(sin mascota)") + "\n\n"
             f"## Sonidos\n" + ("\n".join(f"- {a}" for a in sfx) or "(ninguno)") + f"\nMúsica: {musica or '(ninguna)'}\n\n"
             "## Escenas\n\n" + "\n".join(lineas))
    if m.get("datos"):
        texto += "\n## Datos del expediente (lo único que puedes afirmar)\n" + str(m["datos"])[:6000] + "\n"
    borrador = {"acento": m.get("acento") or "#FFD23F", "acento2": "#22c55e", "peligro": "#ef4444", "barra": True,
                "subtitulos": {"activar": True, "estilo": "pop", "y": 0.86, "porGrupo": 3},
                "musica": {"archivo": musica, "volumen": 0.07} if musica else None, "escenas": escenas}
    (mesa / "materiales.md").write_text(texto, encoding="utf-8")
    (mesa / "edu.json").write_text(json.dumps(borrador, ensure_ascii=False, indent=1), encoding="utf-8")
    return texto, borrador


def editar(mesa: Path, m: dict, claude: str, avance, log) -> Path | None:
    """Claude edita. Regresa video_final.mp4 si quedó bien; None si no (y se usa la plantilla)."""
    import editor_ia

    _, borrador = preparar(mesa, m)
    total = sum(e["duracion"] for e in borrador["escenas"])
    py = editor_ia._ruta(editor_ia.python_exe())
    herramientas = editor_ia._ruta(AQUI / "herramientas.py")
    (mesa / "CLAUDE.md").write_text(GUIA.format(
        titulo=m["ctx"]["ficha"].get("title", ""), canal=m.get("canal_nombre") or "Apps que sí pagan",
        acento=borrador["acento"], direccion=(m.get("direccion") or "(sin indicaciones extra)")[:8000],
        t=f'"{py}" "{herramientas}"'), encoding="utf-8")
    avance("Claude está dirigiendo la edición", 0.08)
    inicio = time.time()
    try:
        editor_ia.correr(mesa, claude, "Edita este video siguiendo CLAUDE.md. Empieza leyendo materiales.md.",
                         lambda paso, f: avance(f"🎬 Claude: {paso}", 0.08 + 0.8 * min(1, (time.time() - inicio) / 3600)),
                         minutos=90)
    except Exception as exc:  # noqa: BLE001
        log(f"Claude no terminó la edición: {exc}")
    final = mesa / "video_final.mp4"
    if not final.exists():
        return None
    dur = _segundos(final)
    if dur < total * 0.9 or dur > total + 5:  # la voz debe quedar completa
        log(f"El video de Claude dura {dur:.0f} s y la narración {total:.0f} s: uso la plantilla.")
        return None
    return final


def editar_auto(mesa: Path, m: dict, avance, log) -> Path | None:
    """🐑 Edición con estilo fijo (Cuida Tu Lana: chat + recortes) SIN Claude: el edu.json se arma con código y se
    renderiza con el kit Edu. No gasta nada del plan. None si algo falla (y se usa la plantilla)."""
    import estilo_lana

    _, borrador = preparar(mesa, m)
    total = sum(e["duracion"] for e in borrador["escenas"])
    edu = estilo_lana.armar(mesa, m, borrador)
    (mesa / "edu.json").write_text(json.dumps(edu, ensure_ascii=False, indent=1), encoding="utf-8")
    avance("🐑 Armando la edición (chat + recortes)", 0.1)
    entorno = {**__import__("os").environ, "SALA_EDITOR_DIR": str(mesa)}
    proceso = subprocess.Popen([sys.executable, str(AQUI / "herramientas.py"), "edu", "edu.json", "video_final.mp4"],
                               cwd=str(mesa), env=entorno, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                               encoding="utf-8", errors="replace")
    inicio = time.time()
    salida = []
    for linea in proceso.stdout:
        salida = (salida + [linea.strip()])[-20:]
        avance("🎬 Renderizando el video", 0.12 + 0.8 * min(1, (time.time() - inicio) / max(120, total * 4)))
    proceso.wait()
    final = mesa / "video_final.mp4"
    if proceso.returncode or not final.exists():
        log("El render del estilo falló: " + " | ".join(x for x in salida if x)[-400:])
        return None
    dur = _segundos(final)
    if dur < total * 0.9 or dur > total + 5:
        log(f"El video dura {dur:.0f} s y la narración {total:.0f} s: uso la plantilla.")
        return None
    return final


if __name__ == "__main__":  # prueba: python editor_youtube.py CARPETA (con manifiesto.json ya bajado)
    carpeta = Path(sys.argv[1])
    print(preparar(carpeta, json.loads((carpeta / "manifiesto.json").read_text(encoding="utf-8")))[0][:2000])
