"""📱 El robot probador: tu Android viejo conectado por USB a esta compu.

La oficina manda un trabajo "probar_app". Esta compu:
1. empieza a grabar la pantalla del cel (adb screenrecord, en trozos de ~3 min);
2. le da el cel a Claude Code (tu plan) con las reglas de CLAUDE.md y los comandos de cel.py: instala la app de
   Play Store, la usa como una persona, ve los anuncios y anota de qué apps son, busca el pago mínimo y el retiro;
3. para la grabación, la junta, desinstala la app y sube prueba.mp4 + notas.json a la oficina.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

import cel

AQUI = Path(__file__).resolve().parent
SIN_VENTANA = 0x08000000 if os.name == "nt" else 0

REGLAS = """# Eres el probador de apps del canal "Apps que sí pagan"

Manejas un celular Android de PRUEBAS por cable con `./cel` (lee `./cel` sin argumentos si dudas). La pantalla se
está grabando: lo que hagas sale en un video de YouTube. Trabaja como una persona curiosa que quiere saber si la app
de verdad paga.

## Tu misión
1. Instala la app: `./cel instalada PAQUETE`; si no está, `./cel tienda PAQUETE` (o `./cel buscar_tienda "nombre"` si
   no hay paquete), toca "Instalar" y espera (`./cel esperar 10` y revisa con `./cel pantalla`) hasta que diga "Abrir".
2. Ábrela (`./cel abrir PAQUETE`) y úsala unos {minutos} minutos: haz lo que te pida para "ganar" (ver videos, jugar,
   girar ruletas, encuestas sencillas), recoge recompensas y ve los anuncios cuando te los ofrezca: los anuncios son
   lo que más nos importa.
3. CADA anuncio que salga: toma pantalla, lee de qué app o producto es y anótalo: `./cel anuncio "Nombre" "qué promete"`.
   - Si el anuncio es de OTRA app que promete ganar dinero (pagos, PayPal, retiros, "gana jugando", encuestas
     pagadas, recompensas en efectivo): **pícale** al anuncio o a su botón (Instalar / Descargar / Más
     información) para ver qué app es. Cuando abra Play Store o una página, toma pantalla y guárdala con
     `./cel guardar_deseo "Nombre" "lo que promete"`. NO la instales ni descargues nada: regresa con `./cel atras`
     (las veces que haga falta) o `./cel abrir PAQUETE` y sigue probando la app de hoy.
   - Si no es de dinero, solo ciérralo (busca la X o "Cerrar", a veces hay que esperar unos segundos) o `./cel atras`.
4. Anota con `./cel nota "…"` lo importante: cuánto saldo llevas, cuánto promete pagar, cada cuánto sale un anuncio.
5. Al final busca la sección de retiro/cobrar/canjear: anota el pago mínimo y qué te pide para retirar
   (`./cel nota "Retiro: mínimo 50 USD, pide…"`). NO completes un retiro.
6. Termina con `./cel terminar "resumen de lo que viste en 3-5 frases"`.

## Reglas de seguridad (no se negocian)
- NUNCA escribas datos reales: ni nombres, ni correos, ni teléfonos, ni datos bancarios o de PayPal. Si un paso los
  exige, anótalo (`./cel nota "Pide número de teléfono para seguir"`) y no sigas por ahí.
- NUNCA pagues, compres ni aceptes suscripciones o pruebas gratis.
- NUNCA pidas un préstamo ni un crédito, ni llenes solicitudes. En apps de préstamos solo revisa qué permisos pide
  (anótalos), qué promete y sus condiciones, y termina: muchas son montadeudas que extorsionan con tus contactos.
- Permisos: niega contactos, SMS, llamadas, ubicación y archivos. Acepta solo notificaciones si no hay otra forma.
- NUNCA instales nada fuera de Play Store (APKs, "descarga aquí"), ni instales las apps de los anuncios: solo se
  guardan en la lista de deseos con `./cel guardar_deseo` y se regresa.
- Si pide iniciar sesión con Google o Facebook, busca "invitado"/"saltar"; si no hay, anótalo y termina.
- Si aparece un captcha, verificación con tu cara o algo que no puedes hacer, anótalo y termina.
- Mira cada `pantalla.png` con Read antes de tocar. No toques a ciegas.
- Tiempo: unos {minutos} minutos usando la app. No te quedes atorado: si algo no avanza en 3 intentos, haz otra cosa.

## La app de hoy
- Nombre: {nombre}
- Paquete de Play Store: {paquete}
"""


def instalar_adb() -> str:
    """Si no hay adb, lo instala con winget (Google Platform Tools). Regresa la ruta o vacío."""
    if cel.adb_ruta():
        return cel.adb_ruta()
    if os.name == "nt" and shutil.which("winget"):
        subprocess.run(["winget", "install", "--id", "Google.PlatformTools", "-e", "--silent",
                        "--accept-package-agreements", "--accept-source-agreements"],
                       capture_output=True, timeout=600, creationflags=SIN_VENTANA)
    return cel.adb_ruta()


def celular() -> dict:
    """{'serie', 'modelo'} si hay un Android conectado y autorizado; {} si no (o {'pendiente': True} si falta autorizar)."""
    ruta = cel.adb_ruta()
    if not ruta:
        return {}
    try:
        salida = subprocess.run([ruta, "devices", "-l"], capture_output=True, text=True, timeout=15,
                                creationflags=SIN_VENTANA).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    for linea in salida.splitlines()[1:]:
        partes = linea.split()
        if len(partes) >= 2 and partes[1] == "device":
            modelo = next((p.split(":", 1)[1] for p in partes if p.startswith("model:")), "Android")
            return {"serie": partes[0], "modelo": modelo.replace("_", " ")}
        if len(partes) >= 2 and partes[1] == "unauthorized":
            return {"pendiente": True}
    return {}


class Grabadora:
    """Graba la pantalla del cel en trozos (Android corta cada 3 min) hasta que se le pida parar."""

    def __init__(self):
        self.parar = threading.Event()
        self.trozos: list[str] = []
        self.hilo = threading.Thread(target=self._grabar, daemon=True)

    def _grabar(self) -> None:
        n = 0
        while not self.parar.is_set():
            n += 1
            archivo = f"/sdcard/autocanal_prueba_{n:02d}.mp4"
            self.trozos.append(archivo)
            try:
                subprocess.run([cel.adb_ruta(), "shell", "screenrecord", "--time-limit", "170", "--bit-rate", "6000000",
                                archivo], capture_output=True, timeout=200, creationflags=SIN_VENTANA)
            except subprocess.TimeoutExpired:
                pass

    def empezar(self) -> None:
        self.hilo.start()

    def terminar(self, destino: Path) -> Path | None:
        self.parar.set()
        cel.adb("shell", "pkill", "-INT", "screenrecord")  # que cierre bien el último trozo
        self.hilo.join(timeout=20)
        time.sleep(2)
        locales = []
        for i, remoto in enumerate(self.trozos):
            local = destino.parent / f"trozo_{i:02d}.mp4"
            subprocess.run([cel.adb_ruta(), "pull", remoto, str(local)], capture_output=True, timeout=300,
                           creationflags=SIN_VENTANA)
            cel.adb("shell", "rm", "-f", remoto)
            if local.exists() and local.stat().st_size > 10_000:
                locales.append(local)
        if not locales:
            return None
        lista = destino.parent / "trozos.txt"
        lista.write_text("".join(f"file '{p.as_posix()}'\n" for p in locales), encoding="utf-8")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lista),
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", "-an",
                        str(destino)], capture_output=True, timeout=1800, creationflags=SIN_VENTANA)
        return destino if destino.exists() else None


def probar(of, t: dict, temporal: Path, avance, claude: str, log) -> None:
    par, tid = t["parametros"], t["id"]
    nombre, paquete = str(par.get("nombre") or "la app")[:80], str(par.get("paquete") or "")[:150]
    minutos = max(3, min(20, int(par.get("minutos") or 8)))
    if not celular().get("serie"):
        raise RuntimeError("No hay un Android conectado y autorizado en esta compu.")
    mesa = temporal / "mesa"
    mesa.mkdir(parents=True, exist_ok=True)
    (mesa / "CLAUDE.md").write_text(REGLAS.format(nombre=nombre, paquete=paquete or "(no tiene: búscala por nombre)",
                                                  minutos=minutos), encoding="utf-8")
    # ./cel para Claude Code (en Windows usa Git Bash): llama a cel.py con este mismo Python
    import sys
    (mesa / "cel").write_text(f'#!/bin/sh\nexec "{Path(sys.executable).as_posix()}" "{(AQUI / "cel.py").as_posix()}" "$@"\n',
                              encoding="utf-8", newline="\n")
    os.chmod(mesa / "cel", 0o755)
    # el cel despierto y sin bloquearse mientras está conectado
    cel.adb("shell", "svc", "power", "stayon", "usb")
    cel.adb("shell", "input", "keyevent", "224")  # prender pantalla
    cel.adb("shell", "wm", "dismiss-keyguard")
    cel.adb("shell", "input", "keyevent", "3")
    avance(f"Empiezo a grabar el cel y a probar {nombre}", 0.03)
    grabadora = Grabadora()
    grabadora.empezar()
    time.sleep(1.5)
    (mesa / "notas.json").write_text(json.dumps({"inicio": time.time(), "anuncios": [], "pasos": [], "resumen": "",
                                                 "terminado": False, "app": nombre, "paquete": paquete},
                                                ensure_ascii=False), encoding="utf-8")
    prompt = (f"Prueba la app «{nombre}» en el celular siguiendo CLAUDE.md al pie de la letra. "
              "Empieza con ./cel pantalla. Termina siempre con ./cel terminar.")
    cmd = [claude, "-p", prompt, "--output-format", "json", "--max-turns", "250",
           "--allowedTools", "Bash(./cel:*)", "Bash(./cel *)", "Read",
           "--model", os.environ.get("ROBOT_MODELO_CLAUDE", "sonnet")]
    inicio = time.time()
    proceso = subprocess.Popen(cmd, cwd=mesa, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                               encoding="utf-8", errors="replace", creationflags=SIN_VENTANA)
    limite = inicio + (minutos + 12) * 60
    try:
        while proceso.poll() is None:
            time.sleep(4)
            transcurrido = (time.time() - inicio) / 60
            prog = (mesa / "progreso.txt").read_text(encoding="utf-8") if (mesa / "progreso.txt").exists() else "Probando"
            avance(f"{prog} ({transcurrido:.0f} min)", min(0.85, 0.05 + 0.8 * transcurrido / (minutos + 4)))
            if time.time() > limite:
                proceso.kill()
                log("El robot se pasó del tiempo: corto la prueba con lo que lleva.")
                break
    except InterruptedError:
        proceso.kill()
        grabadora.terminar(temporal / "cancelado.mp4")
        raise
    salida = proceso.stdout.read() if proceso.stdout else ""
    try:
        info = json.loads(salida.strip().splitlines()[-1]) if salida.strip() else {}
    except ValueError:
        info = {}
    avance("Juntando la grabación", 0.88)
    video = grabadora.terminar(temporal / "prueba.mp4")
    if paquete:  # que el cel de pruebas no se llene de apps (y de anuncios)
        cel.adb("shell", "pm", "uninstall", paquete)
    cel.adb("shell", "input", "keyevent", "3")
    notas = json.loads((mesa / "notas.json").read_text(encoding="utf-8"))
    notas["segundos"] = round(time.time() - notas.get("inicio", inicio))
    if info.get("is_error"):
        notas["problema"] = str(info.get("result") or "")[:300]
    (temporal / "notas.json").write_text(json.dumps(notas, ensure_ascii=False, indent=1), encoding="utf-8")
    if not video:
        raise RuntimeError("No se pudo sacar la grabación del cel. " + str(notas.get("problema", ""))[:150])
    avance("Subiendo la prueba a la oficina", 0.92)
    of.subir(tid, video)
    of.subir(tid, temporal / "notas.json")
    of.post(f"terminar/{tid}", {"ok": True, "resultado": {
        "video": video.name, "anuncios": len(notas.get("anuncios", [])), "deseos": notas.get("deseos", [])[:20],
        "resumen": notas.get("resumen", "")[:500],
        "uso": {"pasos": info.get("num_turns"), "usd": info.get("total_cost_usd")}}})
    log(f"Robot: probé «{nombre}» ({len(notas.get('anuncios', []))} anuncios) en {round((time.time() - inicio) / 60)} min.")
