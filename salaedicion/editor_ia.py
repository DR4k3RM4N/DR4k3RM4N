"""Editor IA: Claude Code edita con las manos libres en la carpeta del proyecto, en tu compu.

- Desde la oficina: la sala manda un trabajo "claude_libre" con tu mensaje → `editar()` corre Claude Code sin ventana
  (con memoria del proyecto: --continue) → sube la versión que dejó en Ediciones.
- Directo en tu compu: doble clic en «Abrir editor IA.bat» dentro de la carpeta del proyecto → la misma plática.

Todo lo que el editor necesita saber (manual, herramientas, reglas) va en _editor/CLAUDE.md, que se regenera cada vez."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent


def python_exe() -> str:
    """El Python de la sala con ventana de consola (compu.py corre con pythonw, sin ventana)."""
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe" and (exe.parent / "python.exe").exists():
        exe = exe.parent / "python.exe"
    return str(exe)


def _ruta(p: Path | str) -> str:
    return str(p).replace("\\", "/")


def guia(carpeta: Path, nombre: str, formato: str, musica: Path, motion_listo: bool) -> str:
    from manual_edicion import MANUAL
    py, h = _ruta(python_exe()), _ruta(AQUI / "herramientas.py")
    t = f'"{py}" "{h}"'
    return f"""# Editor de video de Miguel — proyecto «{nombre}»

Eres el editor de video profesional de Miguel (creador mexicano: canal "Apps que sí pagan" y TikTok Shop México).
Trabajas en SU compu, en esta carpeta. Hablas español de México, casual y directo ("va", "jefe"); respuestas cortas.
Tu trabajo es entregar videos que se vean hechos por un editor con mucho oficio, no clips pegados.

## Dónde está todo
- Clips originales: `{_ruta(carpeta)}` (la carpeta de arriba, `..`). **Nunca los borres, muevas ni modifiques.**
- Tu mesa de trabajo: esta carpeta `_editor` (cortes, props, vistas, notas). Aquí sí puedes crear y borrar.
- Entregas: `{_ruta(carpeta / "Ediciones")}/{nombre} vN.mp4` (N = siguiente número libre, salvo que te digan cuál).
- Música de Miguel: `{_ruta(musica)}` (úsala solo si la pide o si le queda al video; nada con derechos de terceros).
- Formato: {formato or "pregúntalo si no se deduce (vertical 1080x1920 para TikTok/Reels/Shorts; horizontal 1920x1080 para YouTube)"}.
- Tu memoria del proyecto: `notas.md` (léela al empezar; al terminar apunta qué hiciste, qué le gustó y qué no).

## Herramientas (córrelas con Bash, desde esta carpeta)
- `{t} ficha` → qué dice cada clip con tiempos, calidad (movido/borroso/oscuro) y hoja de cuadros en `vistas/`.
  **Mira con Read TODAS las hojas** antes de decidir.
- `{t} cuadros CLIP DESDE HASTA 8` → cuadros de un tramo, para comparar tomas repetidas y elegir la mejor de verdad
  (mirada a cámara, energía, foco, que no se trabe).
- `{t} transcribir ARCHIVO` → palabras con tiempos en `ARCHIVO.palabras.json` (para subtítulos con estilo).
- `{t} armar plan.json base.mp4` → el motor de cortes de la sala (quita silencios y muletillas, zoom suave, música que
  baja cuando hablas, loudnorm…). Formato del plan: el de la sala (`clips` con archivo/desde/hasta/velocidad/encima…,
  `quitar_silencios`, `quitar_muletillas`, `zoom_suave`, `musica`…). Para motion graphics deja `subtitulos.activar=false`
  y pon los subtítulos con estilo en Remotion. También puedes cortar tú con ffmpeg si necesitas algo que esto no hace.
- `{t} codificar` → opciones de ffmpeg para esta compu (NVENC si hay tarjeta).
- `{t} motion props.json final.mp4` → motion graphics (Remotion) encima del video base. {"" if motion_listo else "**Ahorita Remotion no está instalado en esta compu: entrega sin motion graphics y avísale.**"}
- `{t} revisar VIDEO` → cuadros del video terminado + lo que se oye, para revisarlo antes de entregar.

## Motion graphics (props.json, junto a base.mp4)
```json
{{"fondo": "base.mp4", "duracion": 0, "acento": "#FFD23F",
 "elementos": [
  {{"tipo": "titulo",   "desde": 0,   "hasta": 2.5, "texto": "ESTO CAMBIÓ MI COCINA", "y": 0.18}},
  {{"tipo": "etiqueta", "desde": 3,   "hasta": 6,   "texto": "Se carga en 2 horas", "icono": "⚡", "x": 0.5, "y": 0.42}},
  {{"tipo": "precio",   "desde": 6,   "hasta": 9,   "texto": "$299", "antes": "$499", "y": 0.3}},
  {{"tipo": "circulo",  "desde": 7,   "hasta": 9,   "x": 0.5, "y": 0.6, "tamano": 1}},
  {{"tipo": "flecha",   "desde": 7,   "hasta": 9,   "x": 0.5, "y": 0.6, "angulo": 200}},
  {{"tipo": "contador", "desde": 2,   "hasta": 5,   "texto": "{{n}} vendidos", "hastaNumero": 1500}},
  {{"tipo": "emoji",    "desde": 4,   "hasta": 5.5, "texto": "🔥", "x": 0.8, "y": 0.3}},
  {{"tipo": "link",     "desde": 12,  "hasta": 15,  "texto": "🛒 Link aquí"}}],
 "subtitulos": {{"palabras": [...las de base.palabras.json...], "estilo": "pop", "y": 0.72,
                "resaltado": "#FFD23F", "porGrupo": 3, "emojis": {{"dinero": "💰"}}}}}}
```
- `duracion: 0` = la del video base. x/y van de 0 a 1. `angulo` de la flecha = de dónde viene (0 izquierda, 90 arriba).
- Estilos de subtítulos: `pop` (la palabra salta), `karaoke` (se va pintando), `caja` (cajita de color).
- Zonas seguras en vertical: nada importante a la derecha de x=0.85 (botones de TikTok) ni abajo de y=0.82 (texto
  del post), salvo el botón de link. Título arriba (y≈0.15-0.2), subtítulos en y≈0.7, nunca tapes la cara ni el producto.
- Producto (TikTok Shop): círculo/flecha al producto cuando lo menciona, etiquetas con beneficios (1 a la vez, 2-3 s),
  precio solo si Miguel lo dice o te lo da (NUNCA lo inventes), "Link aquí" al final.
- Menos es más: 1 elemento a la vez además de los subtítulos; que cada uno aparezca justo cuando se dice.

## Cómo trabajas
1. Lee `notas.md` y la petición. Si es solo una pregunta, contéstala sin editar.
2. `ficha` y mira todas las hojas. Si repitió algo, compara las tomas con `cuadros` y escoge la mejor (no la primera).
3. Escribe en `plan.md` la historia: gancho (0-3 s), desarrollo, cierre — con clip y segundos exactos y por qué.
4. Corta (`armar` o ffmpeg) → `base.mp4`. Transcribe `base.mp4` → subtítulos. Arma `props.json` → `motion`.
5. `revisar` el resultado, míralo con Read y corrige lo que esté mal (máximo 2 vueltas). Checa: primeros 3 s, tomas
   movidas, texto encimado o con faltas, palabras cortadas, silencios, final que se alarga.
6. Copia a `../Ediciones/{nombre} vN.mp4`. Actualiza `notas.md`.
7. Si te lo pidieron desde la oficina, escribe `resultado.json`:
   `{{"respuesta": "lo que le dices a Miguel", "video": "Ediciones/{nombre} vN.mp4" (o "" si no editaste), "cambios": ["…"]}}`

Correcciones: cambia SOLO lo que pidió, sobre la última versión (está en tus notas y archivos). Nada inventado: datos,
precios y nombres solo si Miguel los dijo o vienen en los clips.

{MANUAL}
"""


def preparar(carpeta: Path, nombre: str, formato: str, musica: Path, claude: str, motion_listo: bool) -> Path:
    """Crea/actualiza _editor con su CLAUDE.md y el acceso «Abrir editor IA» en la carpeta del proyecto."""
    mesa = carpeta / "_editor"
    mesa.mkdir(parents=True, exist_ok=True)
    (mesa / "CLAUDE.md").write_text(guia(carpeta, nombre, formato, musica, motion_listo), encoding="utf-8")
    if not (mesa / "notas.md").exists():
        (mesa / "notas.md").write_text(f"# Notas del proyecto «{nombre}»\n\n(Aún no hay versiones.)\n", encoding="utf-8")
    (carpeta / "Ediciones").mkdir(exist_ok=True)
    if os.name == "nt" and claude:
        bat = ("@echo off\r\nchcp 65001 >nul\r\ntitle Editor IA - %~nx0\r\n"
               "cd /d \"%~dp0_editor\"\r\n"
               "echo 1> .con_platica\r\n"
               f"set SALA_EDITOR_DIR=%~dp0_editor\r\n"
               f"\"{claude}\" --continue --add-dir \"%~dp0.\" --permission-mode acceptEdits "
               f"|| \"{claude}\" --add-dir \"%~dp0.\" --permission-mode acceptEdits\r\n")
        (carpeta / "Abrir editor IA.bat").write_text(bat, encoding="utf-8")
    return mesa


DESCRIPCION = {"Read": "Viendo", "Write": "Escribiendo", "Edit": "Ajustando", "Glob": "Buscando", "Grep": "Buscando"}


def _paso(uso: dict) -> str:
    """Una frase corta de lo que está haciendo, para el monitor de la oficina."""
    nombre, entrada = uso.get("name", ""), uso.get("input") or {}
    if nombre == "Bash":
        cmd = str(entrada.get("command", ""))
        for clave, texto in (("ficha", "Viendo todos tus clips"), ("cuadros", "Comparando tomas"),
                             ("transcribir", "Escuchando"), ("armar", "Cortando"), ("motion", "Haciendo motion graphics"),
                             ("revisar", "Revisando el video"), ("ffmpeg", "Editando con ffmpeg")):
            if clave in cmd:
                return texto
        return str(entrada.get("description") or "Trabajando")[:60]
    archivo = Path(str(entrada.get("file_path") or entrada.get("pattern") or "")).name
    return f"{DESCRIPCION.get(nombre, nombre)} {archivo}".strip()[:60]


def correr(mesa: Path, claude: str, prompt: str, avance, minutos: int = 60) -> dict:
    """Corre Claude Code en la mesa del proyecto (continuando su plática) y regresa el evento final."""
    carpeta = mesa.parent
    base = [claude, "-p", prompt, "--output-format", "stream-json", "--verbose", "--add-dir", str(carpeta),
            "--permission-mode", "acceptEdits", "--allowedTools", "Bash,Read,Write,Edit,Glob,Grep"]
    if os.environ.get("SALA_MODELO_CLAUDE"):
        base += ["--model", os.environ["SALA_MODELO_CLAUDE"]]
    entorno = {**os.environ, "SALA_EDITOR_DIR": str(mesa)}
    final: dict = {}
    for intento in (["--continue"], []):  # con memoria; si no hay plática anterior, una nueva
        if intento and not (mesa / ".con_platica").exists():
            continue
        proc = subprocess.Popen([*base[:2], *intento, *base[2:]], cwd=mesa, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, encoding="utf-8", errors="replace", env=entorno)
        inicio = time.time()
        reloj = threading.Timer(minutos * 60, proc.kill)
        reloj.start()
        try:
            for linea in proc.stdout:
                try:
                    ev = json.loads(linea)
                except ValueError:
                    continue
                if ev.get("type") == "assistant":
                    for b in (ev.get("message") or {}).get("content") or []:
                        if b.get("type") == "tool_use":
                            avance(_paso(b), min(0.9, 0.05 + (time.time() - inicio) / (25 * 60)))
                elif ev.get("type") == "result":
                    final = ev
            proc.wait()
        except BaseException:
            proc.kill()
            raise
        finally:
            reloj.cancel()
        if final and not (final.get("is_error") and intento and "conversation" in str(final.get("result", "")).lower()):
            break
    if not final:
        raise RuntimeError(f"Claude Code se cerró sin terminar ({(proc.stderr.read() or '')[-200:]})")
    (mesa / ".con_platica").write_text("1", encoding="utf-8")
    if final.get("is_error") or final.get("subtype") not in (None, "success"):
        motivo = str(final.get("result") or final.get("subtype") or "falló")
        if "limit" in motivo.lower():
            motivo = "llegaste al límite de tu plan de Claude por ahora; intenta en un rato"
        elif "login" in motivo.lower() or "api key" in motivo.lower():
            motivo = "Claude Code no tiene la sesión abierta en esta compu"
        elif final.get("subtype") == "error_max_turns":
            motivo = "se le acabaron los pasos antes de terminar; dile «sigue»"
        raise RuntimeError(f"Claude Code: {motivo}"[:240])
    return final
