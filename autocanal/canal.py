"""Automatización del canal: de la idea al video publicado.

Uso rápido:
    python canal.py ideas                      # sugiere apps para investigar
    python canal.py crear com.ejemplo.app      # investiga, escribe, narra, edita (todo local)
    python canal.py publicar com.ejemplo.app   # sube blog a WordPress y video a YouTube
    python canal.py automatico --n 2           # ideas + crear las 2 mejores (sin publicar)
    python canal.py demo                       # prueba la edición sin APIs ni internet
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from agentes import config

ETAPAS = ["recolectar", "investigar", "guion", "voz", "miniatura", "video", "blog"]


def _leer(p: Path):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _guardar(p: Path, datos) -> None:
    p.write_text(json.dumps(datos, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _clips(app_id: str) -> list[str]:
    carpeta = config.ENTRADA / app_id
    if not carpeta.exists():
        return []
    return [str(p) for p in sorted(carpeta.iterdir()) if p.suffix.lower() in (".mp4", ".mov", ".mkv", ".webm")]


def _slug(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-")[:60] or "app"


def _rehacer(etapa: str, desde: str | None) -> bool:
    """True si la etapa va en o después de --desde (se rehace aunque ya exista)."""
    return desde is not None and ETAPAS.index(etapa) >= ETAPAS.index(desde)


def crear(app_id: str, con_web: bool = True, minutos: int = 6, voz: str | None = None,
          desde: str | None = None) -> Path:
    from agentes import blog, editor, graficos, guionista, investigador, voz as voz_mod

    carpeta = config.SALIDA / app_id
    carpeta.mkdir(parents=True, exist_ok=True)
    clips = _clips(app_id)
    print(f"\n▶ {app_id}  ({len(clips)} clip(s) tuyos en entrada/{app_id}/)")

    print("1/7 Recolectando datos de Play Store")
    if (carpeta / "ficha.json").exists() and not _rehacer("recolectar", desde):
        datos = {"ficha": _leer(carpeta / "ficha.json"), "resenas": _leer(carpeta / "resenas.json"),
                 "imagenes": _leer(carpeta / "imagenes.json")}
    else:
        datos = investigador.recolectar(app_id, carpeta)
    ficha, imagenes = datos["ficha"], datos["imagenes"]

    print("2/7 Investigando (expediente de evidencia)")
    expediente = _leer(carpeta / "expediente.json")
    if expediente is None or _rehacer("investigar", desde):
        expediente = investigador.analizar(datos, carpeta, con_web=con_web)
    print(f"    veredicto: {expediente['veredicto']}")

    print("3/7 Escribiendo guion")
    guion = _leer(carpeta / "guion.json")
    if guion is None or _rehacer("guion", desde):
        info_clips = [{"indice": i, "archivo": Path(c).name} for i, c in enumerate(clips, 1)]
        guion = guionista.escribir(ficha, expediente, info_clips, minutos)
        _guardar(carpeta / "guion.json", guion)

    print("4/7 Narrando")
    if _rehacer("voz", desde):
        for f in (carpeta / "audio").glob("*.mp3"):
            f.unlink()
    escenas = voz_mod.narrar(guion["escenas"], carpeta, voz)
    _guardar(carpeta / "guion.json", guion)

    print("5/7 Miniatura")
    caps = imagenes.get("capturas") or []
    mini = graficos.miniatura(guion["texto_miniatura"], guion["sello_miniatura"], imagenes.get("icono"),
                              caps[0] if caps else None, carpeta / "miniatura.jpg")

    print("6/7 Editando video")
    ctx = {"ficha": ficha, "expediente": expediente, "imagenes": imagenes}
    video = editor.editar(escenas, ctx, carpeta, clips)

    print("7/7 Escribiendo entrada del blog")
    entrada = _leer(carpeta / "blog.json")
    if entrada is None or _rehacer("blog", desde):
        entrada = blog.escribir(ficha, expediente, len(caps))
        _guardar(carpeta / "blog.json", entrada)
    (carpeta / "blog_preview.html").write_text(
        f"<meta charset='utf-8'><h1>{entrada['titulo']}</h1>{entrada['html']}", encoding="utf-8")

    _reporte(carpeta, ficha, expediente, guion, entrada, video, mini)
    print(f"\n✔ Listo. Revisa {carpeta / 'REVISAR.md'} antes de publicar.")
    return carpeta


def _reporte(carpeta, ficha, exp, guion, entrada, video, mini) -> None:
    dur = sum(e.get("duracion", 0) for e in guion["escenas"])
    l = [f"# Revisión: {ficha['title']}", "",
         f"- Video: `{video.name}` ({dur / 60:.1f} min) · Miniatura: `{mini.name}` · Blog: `blog_preview.html`",
         f"- **Veredicto:** {exp['veredicto']}", f"- {exp['resumen']}", "",
         "## Antes de publicar, comprueba tú mismo", *[f"- [ ] {p}" for p in exp["pendiente_de_probar"]],
         "- [ ] Cada afirmación del guion está respaldada abajo", "",
         "## Señales y evidencia"]
    for s in exp["senales"]:
        l.append(f"- **[{s['gravedad']}] {s['senal']}** — {s['evidencia']} _(fuente: {s['fuente']})_")
    l += ["", "## Fuentes web", *[f"- [{f['titulo']}]({f['url']})" for f in exp.get("fuentes_web", [])], "",
          "## Títulos propuestos", *[f"{i}. {t}" for i, t in enumerate(guion["titulos"], 1)], "",
          f"## Blog: {entrada['titulo']}", entrada["meta_descripcion"], "",
          "## Guion"]
    for i, e in enumerate(guion["escenas"], 1):
        l.append(f"{i}. _[{e['visual']} {e.get('indice', '')} {e.get('texto', '')}]_ {e['narracion']}")
    (carpeta / "REVISAR.md").write_text("\n".join(l), encoding="utf-8")


def publicar(app_id: str, titulo_n: int = 1) -> None:
    from agentes import blog, buscador, youtube

    carpeta = config.SALIDA / app_id
    guion, entrada = _leer(carpeta / "guion.json"), _leer(carpeta / "blog.json")
    imagenes = _leer(carpeta / "imagenes.json")
    if not (guion and entrada and (carpeta / "video.mp4").exists()):
        sys.exit(f"Primero ejecuta: python canal.py crear {app_id}")
    pub = _leer(carpeta / "publicado.json") or {}

    if "blog" not in pub:
        print("Subiendo entrada a WordPress…")
        wp = blog.WordPress()
        pub["blog"] = wp.publicar(entrada, imagenes, str(carpeta / "miniatura.jpg"), _slug(entrada["slug"]))
        _guardar(carpeta / "publicado.json", pub)
        print(f"  · {pub['blog']['link']} ({pub['blog']['estado']})")

    if "youtube" not in pub:
        print("Subiendo video a YouTube…")
        desc = guion["descripcion"].replace("{{BLOG_URL}}", pub["blog"]["link"])
        if pub["blog"]["link"] not in desc:
            desc += f"\n\nAnálisis completo: {pub['blog']['link']}"
        sintetico = config.env("VOZ_MOTOR", "edge") != "propia"
        pub["youtube"] = youtube.subir(carpeta / "video.mp4", carpeta / "miniatura.jpg",
                                       guion["titulos"][titulo_n - 1], desc, guion["etiquetas"], sintetico)
        _guardar(carpeta / "publicado.json", pub)
        print(f"  · {pub['youtube']}")

    if not pub.get("video_en_blog"):
        blog.WordPress().insertar_video(pub["blog"]["id"], pub["youtube"])
        pub["video_en_blog"] = True
        _guardar(carpeta / "publicado.json", pub)
    buscador.marcar_hecha(app_id)
    print("✔ Publicado.")


def demo() -> None:
    """Genera un video de prueba con datos inventados, sin APIs: verifica que ffmpeg y Pillow funcionan."""
    from PIL import Image, ImageDraw

    from agentes import editor, graficos, voz

    carpeta = config.SALIDA / "_demo"
    img = carpeta / "img"
    img.mkdir(parents=True, exist_ok=True)
    icono = Image.new("RGB", (512, 512), (255, 196, 0))
    ImageDraw.Draw(icono).text((150, 170), "$$", font=graficos.fuente(180), fill=(0, 120, 0))
    icono.save(img / "icono.png")
    caps = []
    for i in range(1, 4):
        c = Image.new("RGB", (1080, 2340), (30 + i * 40, 60, 120))
        d = ImageDraw.Draw(c)
        d.text((120, 900), f"GANA $500\nAL DÍA #{i}", font=graficos.fuente(130), fill=(255, 255, 255))
        c.save(img / f"captura_{i}.png")
        caps.append(str(img / f"captura_{i}.png"))
    imagenes = {"icono": str(img / "icono.png"), "portada": None, "capturas": caps}
    expediente = {"veredicto": "senales_de_alerta", "resenas_citadas": [
        {"usuario": "Laura M.", "estrellas": 1, "fecha": "2026-10-01", "likes": 312,
         "texto": "Llegué a los 50 dólares y al querer retirar me pidió ver 200 anuncios más. Nunca pagó."}]}
    escenas = [
        {"narracion": "Esta app promete quinientos pesos al día solo por jugar. ¿Será cierto?", "visual": "titulo", "indice": 0, "texto": "¿Paga de verdad?"},
        {"narracion": "Así se ve por dentro. Todo son monedas y premios gigantes.", "visual": "captura", "indice": 1, "texto": ""},
        {"narracion": "Pero mira lo que dicen los usuarios.", "visual": "resena", "indice": 0, "texto": ""},
        {"narracion": "El pago mínimo es de cincuenta dólares.", "visual": "dato", "indice": 0, "texto": "Pago mínimo: 50 USD"},
        {"narracion": "Mi veredicto: no pierdas tu tiempo.", "visual": "veredicto", "indice": 0, "texto": "No pierdas tu tiempo"},
    ]
    escenas = voz.narrar(escenas, carpeta, "silencio")
    graficos.miniatura("¿Te paga?", "NO PAGA", imagenes["icono"], caps[0], carpeta / "miniatura.jpg")
    video = editor.editar(escenas, {"ficha": {"title": "Demo"}, "expediente": expediente, "imagenes": imagenes},
                          carpeta, [])
    print(f"✔ Demo lista: {video} y {carpeta / 'miniatura.jpg'}")


def main() -> None:
    p = argparse.ArgumentParser(description="Automatización del canal de apps")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("ideas"); s.add_argument("--n", type=int, default=5)
    s = sub.add_parser("crear"); s.add_argument("app_id")
    s.add_argument("--sin-web", action="store_true", help="no buscar en internet (más barato)")
    s.add_argument("--minutos", type=int, default=6)
    s.add_argument("--voz", choices=["edge", "elevenlabs", "silencio"])
    s.add_argument("--desde", choices=ETAPAS, help="rehacer desde esta etapa")
    s = sub.add_parser("publicar"); s.add_argument("app_id")
    s.add_argument("--titulo", type=int, default=1, help="cuál de los 3 títulos usar")
    s = sub.add_parser("automatico"); s.add_argument("--n", type=int, default=1)
    s.add_argument("--publicar", action="store_true", help="publicar sin revisión humana (no recomendado)")
    sub.add_parser("demo")
    a = p.parse_args()

    if a.cmd == "ideas":
        from agentes import buscador
        for i, c in enumerate(buscador.ideas(a.n), 1):
            print(f"{i}. [{c['potencial_vistas']}] {c['titulo']}  →  python canal.py crear {c['app_id']}\n   {c['por_que']}")
    elif a.cmd == "crear":
        crear(a.app_id, not a.sin_web, a.minutos, a.voz, a.desde)
    elif a.cmd == "publicar":
        publicar(a.app_id, a.titulo)
    elif a.cmd == "automatico":
        from agentes import buscador
        for c in buscador.ideas(a.n):
            try:
                crear(c["app_id"])
                if a.publicar:
                    publicar(c["app_id"])
            except Exception as exc:  # noqa: BLE001 — una app fallida no detiene las demás
                print(f"✖ {c['app_id']}: {exc}")
    elif a.cmd == "demo":
        demo()


if __name__ == "__main__":
    main()
