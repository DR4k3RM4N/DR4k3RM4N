"""📱 Las manos del robot: Claude Code maneja tu Android viejo por el cable USB con estos comandos.

  ./cel pantalla                 foto de la pantalla (pantalla.png) + lista numerada de botones y textos
  ./cel tocar 3                  toca el elemento 3 de la última lista
  ./cel tocar 540 1200           toca en esas coordenadas
  ./cel tocar_texto "Instalar"   toca el primer elemento que diga eso
  ./cel escribir "hola"          escribe (solo letras sin acento y números)
  ./cel deslizar abajo           arriba | abajo | izquierda | derecha
  ./cel atras | inicio
  ./cel esperar 5                espera segundos (máx. 60)
  ./cel tienda com.app.id        abre la app en Play Store
  ./cel buscar_tienda "nombre"   busca en Play Store
  ./cel abrir com.app.id         abre la app instalada
  ./cel instalada com.app.id     ¿ya está instalada?
  ./cel anuncio "App anunciada" "lo que promete"   anota un anuncio que salió (con el segundo de la grabación)
  ./cel nota "lo que pasó"       anota algo importante (saldo, pago mínimo, retiro…)
  ./cel guardar_deseo "Nombre" "lo que promete"   después de picarle a un anuncio de dinero: ve qué app abrió
                                 (Play Store o página) y la guarda en la lista de deseos para probarla otro día
  ./cel terminar "resumen"       termina la prueba

Corre en la carpeta de la prueba (notas.json, pantalla.png, elementos.json). Necesita `adb` y el cel con
depuración USB autorizada.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

AQUI = Path.cwd()
NOTAS = AQUI / "notas.json"


def adb_ruta() -> str:
    candidatos = [os.environ.get("ADB", ""), shutil.which("adb") or ""]
    local = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    if local.exists():
        candidatos += [str(p) for p in local.glob("Google.PlatformTools*/platform-tools/adb.exe")]
    candidatos += [str(Path.home() / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb"))]
    return next((c for c in candidatos if c and Path(c).is_file()), "")


def adb(*args: str, binario: bool = False, timeout: int = 40):
    r = subprocess.run([adb_ruta(), *args], capture_output=True, timeout=timeout,
                       creationflags=0x08000000 if os.name == "nt" else 0)  # sin ventana de CMD
    return r.stdout if binario else r.stdout.decode("utf-8", "replace")


def _notas() -> dict:
    try:
        return json.loads(NOTAS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"inicio": time.time(), "anuncios": [], "pasos": [], "resumen": "", "terminado": False}


def _guardar(n: dict) -> None:
    NOTAS.write_text(json.dumps(n, ensure_ascii=False, indent=1), encoding="utf-8")


def _segundo() -> float:
    """Segundo de la grabación (la compu empieza a grabar justo antes de darle el cel a Claude)."""
    return round(time.time() - _notas().get("inicio", time.time()), 1)


def _progreso(texto: str) -> None:
    (AQUI / "progreso.txt").write_text(texto[:120], encoding="utf-8")


def pantalla() -> None:
    crudo = adb("exec-out", "screencap", "-p", binario=True)
    if not crudo.startswith(b"\x89PNG"):
        print("No pude tomar la pantalla. ¿El cel está conectado y desbloqueado?")
        return
    destino = AQUI / "pantalla.png"
    destino.write_bytes(crudo)
    try:  # más chica: se ve igual y gasta menos de tu plan
        from PIL import Image
        img = Image.open(destino)
        if img.height > 1280:
            img.resize((int(img.width * 1280 / img.height), 1280)).save(destino)
    except Exception:  # noqa: BLE001
        pass
    adb("shell", "uiautomator", "dump", "/sdcard/autocanal_ui.xml")
    xml = adb("exec-out", "cat", "/sdcard/autocanal_ui.xml")
    elementos = []
    try:
        for nodo in ET.fromstring(xml[xml.find("<"):]).iter("node"):
            texto = (nodo.get("text") or nodo.get("content-desc") or "").strip()
            clic = nodo.get("clickable") == "true"
            if not texto and not clic:
                continue
            m = re.findall(r"\d+", nodo.get("bounds") or "")
            if len(m) != 4:
                continue
            x1, y1, x2, y2 = map(int, m)
            if x2 - x1 < 8 or y2 - y1 < 8:
                continue
            elementos.append({"texto": texto[:60], "clic": clic, "x": (x1 + x2) // 2, "y": (y1 + y2) // 2,
                              "tipo": (nodo.get("class") or "").rsplit(".", 1)[-1]})
    except ET.ParseError:
        pass
    (AQUI / "elementos.json").write_text(json.dumps(elementos, ensure_ascii=False), encoding="utf-8")
    print(f"Pantalla guardada en pantalla.png (míralo con Read). Segundo de la grabación: {_segundo()}")
    for i, e in enumerate(elementos[:80]):
        print(f"[{i}] {'🔘' if e['clic'] else '  '} {e['texto'] or '(sin texto)'} — {e['tipo']} en ({e['x']},{e['y']})")
    if not elementos:
        print("(No hay lista de elementos: puede ser un anuncio o un juego. Usa las coordenadas de la imagen.)")


def tocar(args: list[str]) -> None:
    if len(args) == 1:
        elementos = json.loads((AQUI / "elementos.json").read_text(encoding="utf-8"))
        e = elementos[int(args[0])]
        x, y = e["x"], e["y"]
    else:
        x, y = int(args[0]), int(args[1])
    adb("shell", "input", "tap", str(x), str(y))
    print(f"Toqué ({x},{y}).")


def tocar_texto(texto: str) -> None:
    pantalla_ok = (AQUI / "elementos.json").exists()
    elementos = json.loads((AQUI / "elementos.json").read_text(encoding="utf-8")) if pantalla_ok else []
    buscado = texto.lower()
    e = next((e for e in elementos if e["texto"].lower() == buscado), None) or \
        next((e for e in elementos if buscado in e["texto"].lower()), None)
    if not e:
        print(f"No encontré «{texto}» en la última pantalla. Toma otra con ./cel pantalla.")
        return
    adb("shell", "input", "tap", str(e["x"]), str(e["y"]))
    print(f"Toqué «{e['texto']}».")


def deslizar(direccion: str) -> None:
    tam = re.findall(r"(\d+)x(\d+)", adb("shell", "wm", "size"))
    w, h = map(int, tam[-1]) if tam else (1080, 1920)
    cx, cy = w // 2, h // 2
    mov = {"abajo": (cx, int(h * .75), cx, int(h * .25)), "arriba": (cx, int(h * .25), cx, int(h * .75)),
           "izquierda": (int(w * .8), cy, int(w * .2), cy), "derecha": (int(w * .2), cy, int(w * .8), cy)}
    a = mov.get(direccion, mov["abajo"])
    adb("shell", "input", "swipe", *map(str, a), "300")
    print(f"Deslicé {direccion}.")


def app_en_pantalla(probando: str = "") -> dict:
    """¿Qué abrió el anuncio? El paquete si es Play Store, o la dirección si es una página.
    `dumpsys` lista primero lo más reciente; se ignora la app que estamos probando (también estuvo en Play Store)."""
    actividad = adb("shell", "dumpsys", "activity", "activities")
    paquetes = [p for p in re.findall(r"details\?id=([A-Za-z][\w.]+)", actividad) if p != probando]
    salida = {"paquete": paquetes[0] if paquetes else ""}
    if not salida["paquete"]:
        url = next((u for u in re.findall(r"dat=(https?://[^\s}]+)", actividad) if "google.com/store" not in u), "")
        if url:
            salida["url"] = url[:300]
    foco = re.search(r"(?:mResumedActivity|topResumedActivity|ResumedActivity).*?\s([\w.]+)/", actividad)
    salida["en_pantalla"] = foco.group(1) if foco else ""
    return salida


def guardar_deseo(nombre: str, promesa: str) -> None:
    n = _notas()
    info = app_en_pantalla(n.get("paquete", ""))
    paquete = info.get("paquete", "")
    deseo = {"segundo": _segundo(), "nombre": nombre[:80], "promesa": promesa[:200], "paquete": paquete,
             "url": info.get("url", ""), "abrio": info.get("en_pantalla", "")}
    n.setdefault("deseos", [])
    if any((paquete and d.get("paquete") == paquete) or d.get("nombre", "").lower() == nombre.lower() for d in n["deseos"]):
        print("Esa ya estaba en la lista de deseos. Regresa a la app (./cel atras).")
        return
    n["deseos"].append(deseo)
    _guardar(n)
    _progreso(f"⭐ A la lista de deseos: {nombre[:40]}")
    print(f"⭐ Guardé «{nombre}» en la lista de deseos" + (f" (Play Store: {paquete})" if paquete else
          f" (página: {info['url'][:60]})" if info.get("url") else " (sin paquete: la buscamos por nombre)")
          + ". NO la instales: regresa a la app con ./cel atras (las veces que haga falta) o ./cel abrir PAQUETE.")


def main() -> None:
    if not adb_ruta():
        print("No encontré adb en esta compu.")
        sys.exit(1)
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "pantalla":
        pantalla()
    elif cmd == "tocar":
        tocar(args)
    elif cmd == "tocar_texto":
        tocar_texto(" ".join(args))
    elif cmd == "escribir":
        texto = re.sub(r"[^A-Za-z0-9@._\- ]", "", " ".join(args))[:80].replace(" ", "%s")
        adb("shell", "input", "text", texto)
        print("Escribí.")
    elif cmd == "deslizar":
        deslizar(args[0] if args else "abajo")
    elif cmd == "atras":
        adb("shell", "input", "keyevent", "4")
        print("Atrás.")
    elif cmd == "inicio":
        adb("shell", "input", "keyevent", "3")
        print("Inicio.")
    elif cmd == "esperar":
        s = min(60, max(1, int(float(args[0])) if args else 3))
        time.sleep(s)
        print(f"Esperé {s} s.")
    elif cmd == "tienda":
        adb("shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", f"market://details?id={args[0]}")
        _progreso("Abriendo Play Store")
        print("Abrí la app en Play Store. Toma pantalla.")
    elif cmd == "buscar_tienda":
        q = " ".join(args).replace(" ", "+")
        adb("shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", f"market://search?q={q}&c=apps")
        print("Busqué en Play Store. Toma pantalla.")
    elif cmd == "abrir":
        adb("shell", "monkey", "-p", args[0], "-c", "android.intent.category.LAUNCHER", "1")
        _progreso("Usando la app")
        print("Abrí la app. Toma pantalla.")
    elif cmd == "instalada":
        print("sí" if f"package:{args[0]}" in adb("shell", "pm", "list", "packages", args[0]).split() else "no")
    elif cmd == "anuncio":
        n = _notas()
        n["anuncios"].append({"segundo": _segundo(), "app": (args[0] if args else "")[:80],
                              "nota": " ".join(args[1:])[:200]})
        _guardar(n)
        _progreso(f"Anuncio #{len(n['anuncios'])}: {(args[0] if args else '')[:40]}")
        print(f"Anoté el anuncio #{len(n['anuncios'])}.")
    elif cmd == "nota":
        n = _notas()
        n["pasos"].append({"segundo": _segundo(), "nota": " ".join(args)[:300]})
        _guardar(n)
        _progreso(" ".join(args)[:80])
        print("Anotado.")
    elif cmd == "guardar_deseo":
        guardar_deseo(args[0] if args else "", " ".join(args[1:]))
    elif cmd == "terminar":
        n = _notas()
        n.update(resumen=" ".join(args)[:1500], terminado=True, fin=time.time())
        _guardar(n)
        print("Prueba terminada. Ya no hagas nada más.")
    else:
        print(f"No conozco «{cmd}».\n{__doc__}")


if __name__ == "__main__":
    main()
