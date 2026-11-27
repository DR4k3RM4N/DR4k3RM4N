"""🖥️ Edu en tus compus: los videos de YouTube se editan en las compus de la sala de edición (más rápido y varios a la
vez); el servidor edita uno a la vez si no hay compu prendida.

Servidor: `editar_en_sala(...)` arma un paquete (audios, tiempos de palabras, imágenes, grabaciones, tu estilo y el
plan de efectos ya hecho), lo deja en la fila de la sala como trabajo "edu" y espera el video.
Compu: `python -m agentes.edicion_remota <carpeta>` (lo llama salaedicion/compu.py) arma el mismo video con el mismo
editor y deja video.mp4 en la carpeta.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

from . import config

SALA_URL = config.env("SALA_URL", "http://127.0.0.1:8767").rstrip("/")
ESTILO_ARCHIVOS = ("estilo.json", "fondo_relleno", "mascota.png", "musica.mp3", "whoosh.mp3", "intro.mp4", "outro.mp4",
                   "fuente_negrita.ttf", "cara.png")


def compus_libres(tipo: str = "edu") -> int:
    import requests
    try:
        return int(requests.get(f"{SALA_URL}/interno/disponible", params={"tipo": tipo}, timeout=3).json().get("compus") or 0)
    except (requests.RequestException, ValueError):
        return 0


SOLO_GRABACION_EDICION = """FORMATO 100% GRABACIÓN DEL CEL (lo más importante de este video):
- El protagonista es la grabación de pantalla de principio a fin. Cada escena lleva de fondo la grabación
  (`fondo.tipo: "video"`, `archivo` = la grabación, `desde` = el segundo que dice el guion, `ajuste: "contener"`,
  `movimiento: "fijo"` o un `acercar` muy suave): se ve completa, al centro, sobre su versión desenfocada.
- NADA de fondos degradados, imágenes externas, chats inventados ni comparativas que tapen el cel. Las capas solo
  ayudan a entender lo que se ve y van a los lados: `circulo`/`flecha` a lo que se toca o al saldo, `cintillo` con lo
  que pasa ("Me pide ver 30 anuncios"), `dato` chiquito para cifras (pago mínimo, saldo), `sello` al final con el
  veredicto. 1 capa a la vez, breve.
- Música de fondo bajita (la de estilo/musica.mp3, volumen 0.05-0.07) y pocos efectos de sonido.
- La escena 1 (gancho) puede abrir con `texto` golpe corto encima de la grabación."""


def lugares(tipo: str) -> tuple[int, int]:
    """(compus prendidas que saben hacer ese tipo, lugares libres que tienen ahorita)."""
    import requests
    try:
        j = requests.get(f"{SALA_URL}/interno/disponible", params={"tipo": tipo}, timeout=3).json()
        compus = int(j.get("compus") or 0)
        return compus, int(j.get("libres", compus) or 0)
    except (requests.RequestException, ValueError):
        return 0, 0


def _direccion() -> str:
    """Lo que Claude (el editor de tu compu) debe respetar: manual del canal, tus correcciones y tus números."""
    from . import lecciones, manual
    try:
        return manual.para_agente()[:6000] + lecciones.para("editor", "disenadora")
    except Exception:  # noqa: BLE001
        return ""


def _preparar(escenas: list[dict], ctx: dict, carpeta: Path, clips: list[str]) -> tuple[list[str], dict]:
    """Junta todo en carpeta/remota/envio (dentro de salida/, donde la sala puede leer) con nombres únicos."""
    from . import estilo as estilo_mod
    from . import voz

    envio = carpeta / "remota" / "envio"
    shutil.rmtree(envio, ignore_errors=True)
    envio.mkdir(parents=True)
    mapa, entradas = {}, []

    def poner(origen: str | Path | None, relativa: str) -> str | None:
        if not origen or not Path(origen).exists():
            return None
        nombre = f"f{len(entradas):03d}_{Path(relativa).name}"
        destino = envio / nombre
        try:
            os.link(origen, destino)
        except OSError:
            shutil.copyfile(origen, destino)
        entradas.append(str(destino))
        mapa[nombre] = relativa
        return relativa

    escenas_r = []
    for i, e in enumerate(escenas, 1):
        e2 = dict(e)
        e2["audio"] = poner(e.get("audio"), f"audio/escena_{i:02d}{Path(e.get('audio') or 'a.mp3').suffix}")
        if e.get("audio"):
            poner(voz.tiempos(e["audio"]), f"audio/escena_{i:02d}.palabras.json")
        escenas_r.append(e2)
    img = ctx.get("imagenes") or {}
    imagenes_r = {"icono": poner(img.get("icono"), f"img/icono{Path(img.get('icono') or 'x.png').suffix}"),
                  "portada": None,
                  "capturas": [r for r in (poner(c, f"img/captura_{k}{Path(c).suffix}")
                                           for k, c in enumerate(img.get("capturas") or [], 1)) if r]}
    clips_r = [r for r in (poner(c, f"clips/clip_{k}{Path(c).suffix}") for k, c in enumerate(clips, 1)) if r]
    from . import canales
    for nombre in ESTILO_ARCHIVOS:
        if nombre == "musica.mp3" and (carpeta / "musica.mp3").exists():
            poner(carpeta / "musica.mp3", "estilo/musica.mp3")  # la música libre de este video
        elif nombre != "mascota.png":
            poner(config.ESTILO_DIR / nombre, f"estilo/{nombre}")
    masc = canales.mascota(canales.actual())
    poner(masc, "estilo/mascota.png")  # la del canal del video
    if masc and masc.parent.parent.name == "mascotas":  # mascota con varias caras (Lanudo): todas, para el editor IA
        for cara in sorted(masc.parent.glob("*.png")):
            if not cara.name.startswith("boca_"):
                poner(cara, f"mascota/{cara.name}")
    sfx = config.ESTILO_DIR / "sfx"
    for f in sorted(sfx.glob("*")) if sfx.exists() else []:
        poner(f, f"estilo/sfx/{f.name}")
    poner(carpeta / "plan_edicion.json", "plan_edicion.json")
    exp = ctx.get("expediente") or {}
    info_canal = canales.get(canales.actual())
    try:
        acento = (estilo_mod.cargar().get("miniaturas") or {}).get("color_acento") or "#FFD23F"
    except Exception:  # noqa: BLE001
        acento = "#FFD23F"
    prueba = {}
    try:
        prueba = json.loads((carpeta / "prueba.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    manifiesto = {"escenas": escenas_r, "clips": clips_r, "mapa": mapa,
                  "ctx": {"ficha": {k: (ctx.get("ficha") or {}).get(k) for k in ("title", "score", "installs", "developer")},
                          "expediente": exp, "imagenes": imagenes_r},
                  # 🎬 para el editor IA (Claude en tu compu)
                  "canal_nombre": info_canal.get("nombre"), "acento": acento, "direccion": _direccion(),
                  "datos": json.dumps({k: v for k, v in exp.items() if k not in ("informe_web", "fuentes_web")},
                                      ensure_ascii=False, default=str)[:8000],
                  "prueba": {"momentos": prueba.get("momentos") or []},
                  "solo_grabacion": bool(ctx.get("solo_grabacion"))}
    if canales.get(canales.actual()).get("nicho") == "fraudes":
        manifiesto["estilo_edicion"] = "lana"
    elif estilo_mod.cargar()["ajustes"].get("cerebro_edicion", "auto") == "auto":
        manifiesto["estilo_edicion"] = "pro"  # el director automático Pro (sin Claude)
    if manifiesto["solo_grabacion"]:
        manifiesto["direccion"] = SOLO_GRABACION_EDICION + "\n\n" + manifiesto["direccion"]
    return entradas, manifiesto


def editar_en_sala(escenas: list[dict], ctx: dict, carpeta: Path, clips: list[str], avance=None) -> Path | None:
    """Manda la edición a una compu de la sala. Regresa el video o None (y el servidor la hace)."""
    import requests

    from . import editor, efectos

    from . import estilo as estilo_mod
    # 🎬 si tu compu puede (Claude Code + Remotion) y está prendido en Estilo, la edición la dirige Claude
    from . import canales as canales_mod
    cerebro = estilo_mod.cargar()["ajustes"].get("cerebro_edicion", "auto")
    lana = canales_mod.get(canales_mod.actual()).get("nicho") == "fraudes"
    # 🎬 por defecto edita el director automático (estilo del canal, en tus compus, sin gastar plan); Claude solo si
    # lo eliges en la sala central. Cuida Tu Lana siempre con su estilo (cel + recortes).
    if (lana or cerebro == "auto") and compus_libres("edu_estilo"):
        tipo = "edu_estilo"
    elif cerebro == "claude" and compus_libres("edu_ia"):
        tipo = "edu_ia"
    else:
        tipo = "edu"
    if tipo == "edu" and not compus_libres():
        return None
    efectos.planear(escenas, carpeta)  # el plan de efectos se hace aquí (la compu no tiene tus claves)
    entradas, manifiesto = _preparar(escenas, ctx, carpeta, clips)
    salida = carpeta / "remota" / "salida"
    shutil.rmtree(salida, ignore_errors=True)
    salida.mkdir(parents=True)
    try:
        r = requests.post(f"{SALA_URL}/interno/trabajo", timeout=15, json={
            "tipo": tipo, "origen": "youtube",
            "etiqueta": f"{'🎬 Claude' if tipo == 'edu_ia' else '🐑 Estilo' if tipo == 'edu_estilo' else 'Edu'}: {manifiesto['ctx']['ficha']['title']}"[:80],
            "parametros": {"manifiesto": manifiesto}, "entradas": entradas, "salida": str(salida)}).json()
        tid = r.get("id")
    except (requests.RequestException, ValueError):
        return None
    if not tid:
        print(f"  · la sala no aceptó la edición: {r.get('error')}", flush=True)
        return None
    print("  · la edición va a una compu de la sala" + (" (la dirige Claude)" if tipo == "edu_ia" else ""), flush=True)
    inicio, en_cola_desde, fila_desde = time.time(), time.time(), None
    while time.time() - inicio < 3 * 3600:
        time.sleep(3)
        try:
            e = requests.get(f"{SALA_URL}/interno/trabajo/{tid}", timeout=5).json()
        except (requests.RequestException, ValueError):
            continue
        estado = e.get("estado")
        if estado == "listo":
            video = salida / "video.mp4"
            if video.exists() and video.stat().st_size > 10_000:
                final = carpeta / "video.mp4"
                shutil.move(str(video), final)
                # subtítulos .srt para YouTube (se hacen aquí en un instante)
                ajustes = __import__("agentes.estilo", fromlist=["cargar"]).cargar()["ajustes"]
                grande = ajustes["subtitulos"] == "grande"
                editor.subtitulos(escenas, carpeta / "subtitulos.srt",
                                  int(ajustes.get("palabras_subtitulo") or 0) or (3 if grande else 7),
                                  bool(ajustes.get("mayusculas_subtitulo")))
                shutil.rmtree(carpeta / "remota", ignore_errors=True)
                print(f"  · {e.get('compu') or 'la compu'} lo editó en {round((time.time() - inicio) / 60)} min", flush=True)
                return final
            break
        if estado in ("error", "cancelado"):
            print(f"  · la compu no pudo editarlo ({e.get('error')}); lo edito aquí", flush=True)
            break
        if estado == "en_cola":
            # 🖥️ el video espera su turno en tus compus (son más rápidas), pero sin quedarse atorado:
            # - si no hay NINGUNA compu prendida para esto en 3 min → lo edita el servidor;
            # - si hay lugar libre y en 8 min nadie lo toma (compu trabada o versión vieja) → el servidor;
            # - si están ocupadas, espera hasta 25 min en fila → luego el servidor.
            fila_desde = fila_desde or time.time()
            en_fila = time.time() - fila_desde
            compus, libres = lugares(tipo)
            if not compus:
                if time.time() - en_cola_desde > 180:
                    break
            else:
                en_cola_desde = time.time()
                if (libres and en_fila > 480) or en_fila > 1500:
                    print("  · ninguna compu lo tomó a tiempo; lo edito aquí", flush=True)
                    break
                if avance:
                    avance(f"🖥️ En fila para tu compu ({round(en_fila / 60)} min; si tarda más de 25, lo hago aquí)", 0.02)
            continue
        en_cola_desde, fila_desde = time.time(), None
        if avance:
            avance(f"🖥️ {e.get('compu') or 'Compu'}: {e.get('paso') or 'editando'}", float(e.get("avance") or 0))
    try:
        requests.post(f"{SALA_URL}/interno/cancelar/{tid}", json={}, timeout=5)
    except requests.RequestException:
        pass
    shutil.rmtree(carpeta / "remota", ignore_errors=True)
    return None


# ---------- del lado de la compu ----------
def correr(carpeta: Path) -> Path:
    """Arma el video con el paquete que ya está acomodado en `carpeta` (manifiesto.json + archivos)."""
    from . import editor

    m = json.loads((carpeta / "manifiesto.json").read_text(encoding="utf-8"))
    escenas = []
    for e in m["escenas"]:
        e = dict(e)
        if e.get("audio"):
            e["audio"] = str(carpeta / e["audio"])
        escenas.append(e)
    ctx = m["ctx"]
    img = ctx["imagenes"]
    img["icono"] = str(carpeta / img["icono"]) if img.get("icono") else None
    img["capturas"] = [str(carpeta / c) for c in img.get("capturas") or []]
    clips = [str(carpeta / c) for c in m.get("clips") or []]

    def avisar(paso: str, fraccion: float) -> None:
        print(f"AVANCE {fraccion:.3f} {paso}", flush=True)

    editor.contexto.al_avanzar = avisar
    return editor.editar(escenas, ctx, carpeta, clips)


if __name__ == "__main__":
    video = correr(Path(sys.argv[1]))
    print(f"LISTO {video}", flush=True)
