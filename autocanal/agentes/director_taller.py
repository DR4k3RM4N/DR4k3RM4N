"""🛠️ El taller del director: cuando encuentra un error del PROGRAMA, lo arregla él mismo.

Cómo (todo en el servidor, con tu plan de Claude):
1. Copia limpia del código en `.taller/` (nunca toca la carpeta que está corriendo).
2. Claude Code (Opus) hace el arreglo ahí, con reglas: cambio mínimo, sin claves, sin tocar el despliegue.
3. El programa (no la IA) revisa el cambio: tamaño, que no traiga claves, que compile y que la oficina arranque en
   modo demo y conteste.
4. Lo sube a GitHub a tu rama; el servidor se actualiza solo en ~1-2 min. Si la versión nueva no arranca,
   `autoactualizar.sh` regresa sola a la anterior y el director te avisa.
Necesita `GITHUB_TOKEN_DIRECTOR` en el .env (asistente: oficina.py --configurar-github). Sin él, solo diagnostica.
"""
from __future__ import annotations

import base64
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

from . import claude, config, director

REPO = config.BASE.parent
TALLER = REPO / ".taller"
_candado = threading.Lock()

ESQ_ARREGLO = {"type": "object", "additionalProperties": False,
               "required": ["hecho", "resumen", "mensaje_commit", "riesgo", "explicacion"],
               "properties": {
                   "hecho": {"type": "boolean", "description": "true si hiciste y compilaste el arreglo"},
                   "resumen": {"type": "string", "description": "para Miguel, 1-2 líneas sin tecnicismos: qué va a notar"},
                   "mensaje_commit": {"type": "string", "description": "título del commit en español (qué va a notar Miguel)"},
                   "riesgo": {"type": "string", "enum": ["bajo", "medio", "alto"]},
                   "explicacion": {"type": "string", "description": "qué cambiaste y por qué (técnico, breve); o por qué no se pudo"}}}

PROHIBIDO = re.compile(r"^(autocanal/despliegue/|\.github/|\.gitignore$|.*\.env)|(^|/)(\.env|.*token.*\.json|client_secret.*)$")
SECRETO = re.compile(r"sk-ant-|ghp_|github_pat_|AIza[0-9A-Za-z_-]{20}|xox[bp]-|-----BEGIN [A-Z ]*PRIVATE KEY|EAA[A-Za-z0-9]{30}|"
                     r"[A-Za-z0-9._%+-]+@(gmail|hotmail|outlook|yahoo)\.com|\b\d{9}:[A-Za-z0-9_-]{35}\b")


def token() -> str:
    return config.env("GITHUB_TOKEN_DIRECTOR")


def listo() -> bool:
    """¿Puede programar? (token de GitHub y plan de Claude conectados)."""
    return bool(token() and claude.claude_cli() and claude.suscripcion_lista() and not config.env("AUTOCANAL_DEMO"))


def _git(*args, cwd: Path = TALLER, env: dict | None = None, timeout: int = 180) -> str:
    p = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=timeout, env=env)
    if p.returncode:
        raise RuntimeError(f"git {args[0]}: {(p.stderr or p.stdout).strip()[-300:]}")
    return p.stdout.strip()


def _origen() -> tuple[str, str]:
    """(URL https del repo, rama) — los mismos que usa el servidor para actualizarse."""
    url = _git("remote", "get-url", "origin", cwd=REPO)
    m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", url)
    rama = _git("rev-parse", "--abbrev-ref", "HEAD", cwd=REPO)
    return (f"https://github.com/{m.group(1)}.git" if m else url), rama


def _env_git() -> dict:
    """El token va en una variable de git (no en la línea de comando ni en la IA)."""
    clave = base64.b64encode(f"x-access-token:{token()}".encode()).decode()
    return {**_env_base(), "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader",
            "GIT_CONFIG_VALUE_0": f"AUTHORIZATION: basic {clave}", "GIT_TERMINAL_PROMPT": "0"}


def _env_base() -> dict:
    """Entorno sin ninguna clave de la oficina (el .env se carga en el proceso; aquí no pasa nada de eso)."""
    return {k: os.environ[k] for k in ("PATH", "LANG", "LC_ALL", "TZ") if k in os.environ} | {"HOME": tempfile.gettempdir()}


def _env_ia() -> dict:
    casa = config.BASE / ".claude_casa"
    casa.mkdir(exist_ok=True)
    return _env_base() | {"HOME": str(casa), "CLAUDE_CODE_OAUTH_TOKEN": config.env("CLAUDE_CODE_OAUTH_TOKEN"),
                          "DISABLE_AUTOUPDATER": "1", "DISABLE_TELEMETRY": "1"}


def _preparar() -> None:
    url, rama = _origen()
    if not (TALLER / ".git").exists():
        _git("clone", "-q", "--branch", rama, url, str(TALLER), cwd=REPO, timeout=600)
    _git("fetch", "-q", "origin", rama, timeout=300)
    _git("reset", "-q", "--hard", f"origin/{rama}")
    _git("clean", "-q", "-fdx")
    _git("config", "user.name", "Director de producción")
    _git("config", "user.email", "director@oficina.invalid")


def _sistema() -> str:
    return (
        "Eres un programador senior arreglando un error en el sistema de oficinas de IA de Miguel (Python con la "
        "biblioteca estándar en autocanal/ y salaedicion/, páginas HTML/JS sin frameworks en autocanal/oficina/). "
        "Estás en una COPIA del código: cámbiala con Edit/Write.\n\nREGLAS (no las rompas):\n"
        "- Cambio MÍNIMO que arregle la causa real. No refactorices ni cambies cosas que no tienen que ver.\n"
        "- Lee solo lo necesario. CONTEXTO.md es enorme: usa Grep para encontrar la sección del tema y lee solo esa.\n"
        "- Nunca pongas claves, tokens, correos ni datos personales (el repo es público). No toques autocanal/despliegue/ "
        "ni .github/. No agregues dependencias nuevas.\n"
        "- Mantén el estilo: comentarios y textos en español de México, nombres en español.\n"
        "- Que lo que ya está guardado siga funcionando (estados viejos en JSON, casos ya hechos).\n"
        "- Compila cada .py que cambies con `python3 -m py_compile archivo` y cada .js con `node --check archivo`.\n"
        "- Agrega una línea corta en CONTEXTO.md, en la sección del tema, explicando el arreglo.\n"
        "- Si no estás seguro de la causa o el arreglo es grande o peligroso, NO lo hagas: hecho=false y explica.\n"
        "- riesgo «alto» = toca el flujo de publicar/borrar en YouTube, dinero, o muchos archivos: Miguel lo aprueba antes."
    )


def _agente(falla: str, pedido: str) -> dict:
    p = subprocess.run(
        [claude.claude_cli(), "-p", "--output-format", "json", "--model", config.env("SUSCRIPCION_MODELO_DIRECTOR", "opus"),
         "--effort", "high", "--json-schema", json.dumps(ESQ_ARREGLO), "--system-prompt", _sistema(), "--max-turns", "80",
         "--tools", "Read,Grep,Glob,Edit,Write,Bash",
         "--allowedTools", "Read", "Grep", "Glob", "Edit", "Write", "Bash(python3 -m py_compile:*)", "Bash(node --check:*)",
         "Bash(git diff:*)", "Bash(git status)", "Bash(git log:*)",
         "--disallowedTools", "Read(//**/.env)", "Read(//**/.env.*)", "Read(//**/.claude_casa/**)", "Read(//**/*token*)",
         "Read(//**/client_secret*)", "Read(//**/llaves_ssh/**)", "WebFetch", "WebSearch", "NotebookEdit",
         "--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence", "--setting-sources", "", "--",
         f"FALLA DIAGNOSTICADA POR EL DIRECTOR:\n{falla}\n\nLO QUE PIDIÓ MIGUEL: {pedido or '(lo encontró el director)'}\n\n"
         "Arréglalo en esta copia del código."],
        capture_output=True, text=True, cwd=str(TALLER), env=_env_ia(), timeout=2700)
    try:
        r = json.loads(p.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError) as exc:
        raise RuntimeError(f"el programador no contestó bien: {(p.stderr or p.stdout)[-200:]}") from exc
    if r.get("is_error") or not r.get("structured_output"):
        detalle = str(r.get("result") or r.get("subtype") or "")[-200:]
        if any(x in detalle.lower() for x in claude.LIMITE_PALABRAS):
            raise RuntimeError("se acabó el límite de tu plan de Claude; lo intento cuando vuelva")
        raise RuntimeError(f"el programador no terminó ({detalle})")
    return r["structured_output"]


def _revisar_cambio() -> list[str]:
    """Lo revisa el programa, no la IA: qué archivos, cuánto, sin claves, compila."""
    _git("add", "-A")
    archivos = [x for x in _git("diff", "--cached", "--name-only").splitlines() if x]
    if not archivos:
        raise RuntimeError("no cambió nada")
    malos = [a for a in archivos if PROHIBIDO.search(a)]
    if malos:
        raise RuntimeError(f"tocó archivos que no debe: {', '.join(malos)}")
    lineas = sum(int(a) + int(b) for a, b, *_ in (l.split("\t") for l in _git("diff", "--cached", "--numstat").splitlines())
                 if a.isdigit() and b.isdigit())
    if len(archivos) > 12 or lineas > 700:
        raise RuntimeError(f"el cambio es muy grande ({len(archivos)} archivos, {lineas} líneas): mejor que lo vea Claude Code")
    agregado = "\n".join(l for l in _git("diff", "--cached", "-U0").splitlines() if l.startswith("+"))
    if SECRETO.search(agregado):
        raise RuntimeError("el cambio parece traer una clave o un correo: no lo subo")
    for a in archivos:
        f = TALLER / a
        if a.endswith(".py") and f.exists():
            p = subprocess.run([sys.executable, "-m", "py_compile", str(f)], capture_output=True, text=True, env=_env_base())
            if p.returncode:
                raise RuntimeError(f"{a} no compila: {p.stderr.strip()[-200:]}")
        if a.endswith(".js") and f.exists() and subprocess.run(["which", "node"], capture_output=True).returncode == 0:
            p = subprocess.run(["node", "--check", str(f)], capture_output=True, text=True, env=_env_base())
            if p.returncode:
                raise RuntimeError(f"{a} tiene un error de JavaScript: {p.stderr.strip()[-200:]}")
    return archivos


def _puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _probar_demo() -> None:
    """La oficina de la copia tiene que arrancar en modo demo y contestar (sin claves, sin tocar la sala real)."""
    puerto = _puerto_libre()
    env = _env_base() | {"SALA_URL": "http://127.0.0.1:9", "TIENDA_URL": "http://127.0.0.1:9", "DEMO_SIN_EXTRAS": "1",
                         "PYTHONUNBUFFERED": "1"}
    p = subprocess.Popen([sys.executable, "oficina.py", "--demo", "--puerto", str(puerto), "--sin-navegador"],
                         cwd=str(TALLER / "autocanal"), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        bien, fin = set(), time.time() + 90
        while time.time() < fin and len(bien) < 3:
            if p.poll() is not None:
                raise RuntimeError("la oficina no arrancó: " + (p.stdout.read() or "")[-400:])
            for ruta in ("/", "/api/director", "/api/quienmato"):
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{puerto}{ruta}", timeout=5) as r:
                        if r.status == 200:
                            bien.add(ruta)
                except Exception:  # noqa: BLE001
                    pass
            time.sleep(3)
        if len(bien) < 3:
            raise RuntimeError(f"la oficina en demo no contestó bien (solo {sorted(bien)})")
        time.sleep(10)  # que corran sus hilos un poco
        if p.poll() is not None:
            raise RuntimeError("la oficina se cayó al ratito: " + (p.stdout.read() or "")[-400:])
    finally:
        p.terminate()
        try:
            p.wait(timeout=15)
        except subprocess.TimeoutExpired:
            p.kill()


def _subir() -> str:
    _, rama = _origen()
    env = _env_git()
    _git("fetch", "-q", "origin", rama, env=env, timeout=300)
    try:
        _git("rebase", "-q", f"origin/{rama}", env=env)
    except RuntimeError:
        subprocess.run(["git", "rebase", "--abort"], cwd=str(TALLER), capture_output=True)
        raise RuntimeError("mientras programaba llegó otro cambio que choca con el mío; lo vuelvo a intentar después")
    for i in range(4):
        try:
            _git("push", "-q", "origin", f"HEAD:{rama}", env=env, timeout=300)
            return _git("rev-parse", "HEAD")
        except RuntimeError as exc:
            if i == 3 or "403" in str(exc) or "denied" in str(exc).lower():
                raise RuntimeError(f"GitHub no me dejó subirlo ({str(exc)[-160:]}). Revisa el token: oficina.py --configurar-github")
            time.sleep(5 * 2 ** i)
    raise RuntimeError("no pude subirlo")


def _estado(**campos) -> dict:
    e = director.estado()
    e["taller"] = {**(e.get("taller") or {}), **campos, "mov": time.time()}
    director._guardar(e)
    return e["taller"]


def ocupado() -> bool:
    t = director.estado().get("taller") or {}
    return t.get("estado") in ("programando", "probando", "subiendo") and time.time() - t.get("mov", 0) < 3600


def programar(oficina, falla: str, pedido: str = "", avisar=None) -> None:
    """Hace todo el arreglo (en un hilo). `avisar(texto)` le escribe a Miguel por donde estaba platicando."""
    avisar = avisar or (lambda _t: None)
    if not _candado.acquire(blocking=False):
        avisar("🛠️ Ya estoy programando otro arreglo; este lo hago en cuanto termine.")
        return
    try:
        _estado(estado="programando", falla=falla[:3000], pedido=pedido[:300], inicio=time.time(), error=None, commit=None, resumen="")
        _preparar()
        r = _agente(falla, pedido)
        director._gaste()
        if not r.get("hecho"):
            _estado(estado="no_se_pudo", error=r.get("explicacion", "")[:600])
            avisar("🛠️ Revisé el código y no me atreví a cambiarlo solo: " + r.get("explicacion", "")[:300]
                   + "\nTe dejé el diagnóstico en mi página para que lo vea Claude Code.")
            return
        _estado(estado="probando", resumen=r["resumen"][:400], explicacion=r["explicacion"][:1500], riesgo=r["riesgo"])
        archivos = _revisar_cambio()
        mensaje = (f"{r['mensaje_commit'][:90]}\n\n{r['resumen'][:600]}\n\nArreglo programado y probado por el director de producción "
                   f"(Claude Code) en el servidor.\nArchivos: {', '.join(archivos)}\n\nCo-Authored-By: Claude <noreply@anthropic.com>")
        _git("commit", "-q", "-m", mensaje)
        _probar_demo()
        _git("clean", "-q", "-fdx")
        _git("reset", "-q", "--hard", "HEAD")
        if r["riesgo"] == "alto":
            _estado(estado="esperando_ok", archivos=archivos)
            avisar(f"🛠️ Ya tengo el arreglo listo y probado: {r['resumen'][:300]}\nComo toca algo delicado, necesito tu OK: "
                   "dime «sí, aplica el arreglo» o dale «Aplicar» en mi página.")
            return
        _aplicar(archivos, avisar)
    except Exception as exc:  # noqa: BLE001
        _estado(estado="error", error=str(exc)[:600])
        avisar(f"🛠️ Intenté programar el arreglo pero no salió: {str(exc)[:300]}\nEl diagnóstico se queda en mi página para Claude Code.")
    finally:
        _candado.release()


def _aplicar(archivos: list[str], avisar) -> None:
    _estado(estado="subiendo")
    commit = _subir()
    _estado(estado="subido", commit=commit, archivos=archivos, subido=time.time())
    avisar(f"🛠️ ¡Listo! Lo programé, lo probé y lo subí: {(director.estado().get('taller') or {}).get('resumen', '')[:300]}\n"
           "Se instala solo en 1-2 minutos (si hay un video a medio editar, espera a que termine). Te aviso cuando quede.")


def aplicar_pendiente(oficina, avisar=None) -> str:
    """Miguel dio el OK a un arreglo de riesgo alto."""
    t = director.estado().get("taller") or {}
    if t.get("estado") != "esperando_ok":
        return "no hay ningún arreglo esperando tu OK"
    if not _candado.acquire(blocking=False):
        return "estoy ocupado con otro arreglo"
    try:
        _aplicar(t.get("archivos") or [], avisar or (lambda _t: None))
        return "subí el arreglo; se instala solo en 1-2 min"
    except Exception as exc:  # noqa: BLE001
        _estado(estado="error", error=str(exc)[:600])
        return f"no pude subirlo: {str(exc)[:200]}"
    finally:
        _candado.release()


def revisar_instalacion() -> str | None:
    """Al arrancar: ¿ya quedó instalado lo que subí? ¿o el servidor tuvo que regresar a la versión anterior?"""
    t = director.estado().get("taller") or {}
    try:
        actual = _git("rev-parse", "HEAD", cwd=REPO)
    except Exception:  # noqa: BLE001
        return None
    mala = REPO / ".version_mala"
    if t.get("estado") == "subido" and mala.exists() and mala.read_text().strip() == t.get("commit"):
        _estado(estado="regresado")
        return ("⚠️ Mi arreglo no arrancó bien en el servidor, así que se regresó solo a la versión anterior (todo sigue "
                "como antes). Te dejé el diagnóstico para que lo vea Claude Code.")
    if t.get("estado") == "subido" and t.get("commit"):
        try:
            _git("merge-base", "--is-ancestor", t["commit"], actual, cwd=REPO)
        except RuntimeError:
            return None
        _estado(estado="instalado", instalado=time.time())
        return f"✅ Ya quedó instalado mi arreglo: {t.get('resumen', '')[:300]}"
    return None


def configurar() -> None:
    """Asistente: guarda el token de GitHub del director en el .env (sin mostrarlo) y prueba que pueda subir."""
    import getpass
    url, rama = _origen()
    m = re.search(r"github\.com/(.+?)\.git$", url)
    repo = m.group(1) if m else ""
    print("Configurar el token de GitHub del director (para que suba sus arreglos).")
    print(f"Repositorio: {repo} · rama: {rama}")
    t = getpass.getpass("Pega el token (no se ve al pegarlo): ").strip()
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}", headers={"Authorization": f"Bearer {t}",
                                                                                "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            datos = json.loads(r.read())
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"✖ Ese token no sirve ({exc}). Revisa que lo copiaste completo y que tenga acceso a {repo}.")
    if not (datos.get("permissions") or {}).get("push"):
        raise SystemExit("✖ El token sí entra, pero no puede subir cambios. Dale el permiso «Contents: Read and write».")
    env = config.BASE / ".env"
    texto = env.read_text(encoding="utf-8") if env.exists() else ""
    if re.search(r"^GITHUB_TOKEN_DIRECTOR=", texto, flags=re.M):
        texto = re.sub(r"^GITHUB_TOKEN_DIRECTOR=.*$", lambda _: f"GITHUB_TOKEN_DIRECTOR={t}", texto, flags=re.M)
    else:
        texto = texto.rstrip("\n") + f"\nGITHUB_TOKEN_DIRECTOR={t}\n"
    env.write_text(texto, encoding="utf-8")
    print("✔ Listo: el director ya puede programar sus arreglos. Reinicia la oficina:  sudo systemctl restart oficina")
