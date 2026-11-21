"""📱 La prueba propia: alguien usó la app de verdad y la grabó (tú con tu cel, o el robot con el Android viejo).

- `grabaciones(app_id)`: las grabaciones del proyecto (las que subiste y las que hizo el robot).
- `analizar(...)`: Claude ve los cuadros de la grabación y saca cómo funciona, qué promete, el pago mínimo, qué
  pasó al querer retirar, cuántos anuncios salen y DE QUÉ APPS son (esas se vuelven ideas nuevas), y los mejores
  momentos para el video (el guion los usa con su segundo exacto).
- `pedir_al_celular(...)`: si una de tus compus tiene el Android conectado, le pide que instale la app, la use y la
  grabe (trabajo "probar_app" de la sala de edición). Si no hay cel conectado, no espera nada.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import time
from pathlib import Path

import requests

from . import claude, config, estilo

VIDEO_EXT = (".mp4", ".mov", ".mkv", ".webm")
SALA_URL = config.env("SALA_URL", "http://127.0.0.1:8767").rstrip("/")


def carpeta_robot(app_id: str) -> Path:
    return config.SALIDA / app_id / "prueba_robot"


def grabaciones(app_id: str) -> list[Path]:
    """Tus grabaciones (entrada/<id>/) y las del robot (salida/<id>/prueba_robot/)."""
    lugares = [config.ENTRADA / app_id, config.ENTRADA / app_id.split("~")[0], carpeta_robot(app_id)]
    vistas, salida = set(), []
    for c in lugares:
        if c.exists():
            for p in sorted(c.iterdir()):
                if p.suffix.lower() in VIDEO_EXT and p.resolve() not in vistas and not p.name.endswith(".subiendo"):
                    vistas.add(p.resolve())
                    salida.append(p)
    return salida


def _duracion(p: Path) -> float:
    try:
        return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                                    capture_output=True, text=True, timeout=60).stdout.strip() or 0)
    except (subprocess.SubprocessError, ValueError):
        return 0.0


SCHEMA = {
    "type": "object",
    "properties": {
        "resumen": {"type": "string", "description": "Qué se ve en la prueba, en 2-3 frases"},
        "como_funciona": {"type": "string", "description": "Qué te pide hacer la app para 'ganar'"},
        "promesa": {"type": "string", "description": "Qué promete pagar, tal como se ve en pantalla (vacío si no se ve)"},
        "pago_minimo": {"type": "string", "description": "El mínimo para retirar si se ve (vacío si no)"},
        "intento_de_retiro": {"type": "string", "description": "Qué pasó al intentar retirar; vacío si no se intentó"},
        "anuncios": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "grabacion": {"type": "integer", "description": "Número de grabación (empieza en 1)"},
                "segundo": {"type": "number"},
                "app_anunciada": {"type": "string", "description": "Nombre de la app o producto del anuncio, tal como se lee; vacío si no se lee"},
                "parece_de_dinero": {"type": "boolean", "description": "¿El anuncio promete ganar dinero?"},
            },
            "required": ["grabacion", "segundo", "app_anunciada", "parece_de_dinero"],
            "additionalProperties": False,
        }},
        "momentos": {"type": "array", "description": "Los mejores momentos para mostrar en el video (máx. 12)", "items": {
            "type": "object",
            "properties": {
                "grabacion": {"type": "integer"},
                "segundo": {"type": "number"},
                "que_se_ve": {"type": "string"},
            },
            "required": ["grabacion", "segundo", "que_se_ve"],
            "additionalProperties": False,
        }},
        "senales": {"type": "array", "items": {"type": "string"}, "description": "Señales de alerta que SE VEN en la prueba"},
    },
    "required": ["resumen", "como_funciona", "promesa", "pago_minimo", "intento_de_retiro", "anuncios", "momentos", "senales"],
    "additionalProperties": False,
}

SISTEMA = """Eres el investigador de un canal de YouTube que prueba apps que prometen pagar dinero. Te paso cuadros de
grabaciones de pantalla de alguien usando la app de verdad (con el segundo de cada cuadro) y, si hay, sus notas.
Describe SOLO lo que se ve: no inventes cifras ni pantallas. Los anuncios se reconocen por botones de cerrar (X),
"Instalar", "Anuncio"/"Ad", contadores o pantallas de otra app; anota de qué app o producto es cada uno si se lee.
Los momentos son los que mejor muestran la app para el video (promesas, saldo, intento de retiro, anuncios)."""


def analizar(app_id: str, carpeta: Path, nombre: str = "") -> dict | None:
    """Ve las grabaciones y guarda prueba.json (si no cambiaron, usa lo que ya había)."""
    clips = grabaciones(app_id)
    if not clips:
        return None
    firma = hashlib.sha1(json.dumps([[p.name, p.stat().st_size] for p in clips]).encode()).hexdigest()[:12]
    archivo = carpeta / "prueba.json"
    if archivo.exists():
        try:
            guardado = json.loads(archivo.read_text(encoding="utf-8"))
            if guardado.get("firma") == firma:
                return guardado
        except (json.JSONDecodeError, OSError):
            pass
    notas = []
    for n in sorted(carpeta_robot(app_id).glob("*.json")) if carpeta_robot(app_id).exists() else []:
        try:
            notas.append(json.loads(n.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            pass
    duraciones = [_duracion(p) for p in clips]
    total = sum(duraciones) or 1
    cuadros_max = 40
    contenido = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, (p, dur) in enumerate(zip(clips, duraciones), 1):
            n = max(4, round(cuadros_max * dur / total))
            for k in range(n):
                t = dur * (k + 0.5) / n
                img = Path(tmp) / f"g{i}_{k}.jpg"
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(p), "-frames:v", "1",
                                "-vf", "scale='if(gt(iw,ih),640,-2)':'if(gt(iw,ih),-2,640)'", str(img)], check=False)
                if img.exists():
                    contenido += [{"type": "text", "text": f"Grabación {i}, segundo {t:.0f}:"}, estilo.imagen_bloque(img, 640)]
    if not contenido:
        return None
    contenido.append({"type": "text", "text": (
        f"App probada: {nombre or app_id}. Grabaciones: " + ", ".join(f"{i}) {d:.0f} s" for i, d in enumerate(duraciones, 1))
        + (f"\n\nNOTAS DE QUIEN LA PROBÓ:\n{json.dumps(notas, ensure_ascii=False)[:4000]}" if notas else "")
        + "\n\nDescribe la prueba.")})
    r = claude.json_estructurado(SISTEMA, contenido, SCHEMA, tarea="prueba", que="ver la grabación de la prueba")
    minutos = total / 60
    r["anuncios_por_minuto"] = round(len(r["anuncios"]) / max(minutos, 0.5), 1)
    r["minutos_probados"] = round(minutos, 1)
    r["grabaciones"] = [{"indice": i, "archivo": p.name, "segundos": round(d, 1)} for i, (p, d) in enumerate(zip(clips, duraciones), 1)]
    r["por_robot"] = bool(notas)
    r["firma"] = firma
    archivo.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    return r


def apps_anunciadas(prueba: dict | None) -> list[str]:
    """Las apps de dinero que salieron en anuncios (para que Paola las proponga)."""
    if not prueba:
        return []
    nombres = [a["app_anunciada"].strip() for a in prueba.get("anuncios", [])
               if a.get("parece_de_dinero") and len(a.get("app_anunciada", "").strip()) >= 3]
    return list(dict.fromkeys(nombres))[:5]


# ---------- el robot: tu Android viejo en tu compu ----------
OFICINA_LOCAL = "http://127.0.0.1:8787"  # lo pone oficina.py al arrancar (su puerto)
ULTIMO_ERROR = {"texto": ""}  # por qué falló la última prueba en el cel (para decírtelo)


def celular_disponible() -> bool:
    try:
        return bool(requests.get(f"{SALA_URL}/interno/disponible", params={"tipo": "probar_app"}, timeout=3).json().get("compus"))
    except (requests.RequestException, ValueError):
        return False


def pedir_al_celular(app_id: str, nombre: str, paquete: str, minutos: int = 8, avance=None,
                     ya_instalada: bool = False) -> bool:
    """Le pide a tu compu con el Android conectado que pruebe la app. Regresa True si dejó grabación."""
    ULTIMO_ERROR["texto"] = ""
    if not celular_disponible():
        ULTIMO_ERROR["texto"] = "no hay ninguna compu con el cel listo en la sala"
        return False
    destino = carpeta_robot(app_id)
    destino.mkdir(parents=True, exist_ok=True)
    try:
        r = requests.post(f"{SALA_URL}/interno/trabajo", timeout=10, json={
            "tipo": "probar_app", "origen": "youtube", "etiqueta": f"Probar {nombre}"[:80], "salida": str(destino),
            "clasificar": f"{OFICINA_LOCAL}/interno/robot/{app_id}",  # el cerebro del robot (paso a paso)
            "parametros": {"nombre": nombre, "paquete": paquete, "minutos": minutos, "ya_instalada": ya_instalada}}).json()
        tid = r.get("id")
    except (requests.RequestException, ValueError):
        return False
    if not tid:
        return False
    limite = time.time() + (minutos + 50) * 60  # puede esperar su turno (un solo cel) + instalar + probar + subir
    while time.time() < limite:
        time.sleep(5)
        try:
            e = requests.get(f"{SALA_URL}/interno/trabajo/{tid}", timeout=5).json()
        except (requests.RequestException, ValueError):
            continue
        if e.get("estado") == "listo":
            return any(p.suffix.lower() in VIDEO_EXT for p in destino.iterdir())
        if e.get("estado") in ("error", "cancelado"):
            print(f"  · el celular no pudo probarla: {e.get('error')}", flush=True)
            ULTIMO_ERROR["texto"] = str(e.get("error") or "")[:300]
            return False
        if avance and e.get("paso"):
            avance(f"📱 {e['paso']}", 0.1 + 0.8 * float(e.get("avance") or 0))
    try:
        requests.post(f"{SALA_URL}/interno/cancelar/{tid}", json={}, timeout=5)
    except requests.RequestException:
        pass
    print("  · el celular tardó demasiado; sigo sin su prueba", flush=True)
    return False
