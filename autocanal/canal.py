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
from pathlib import Path

from agentes import config

# Qué necesita cada etapa para empezar. Las que no dependen entre sí corren al mismo tiempo
# en la oficina (por ejemplo, el blog se escribe mientras se hace el guion).
DEPENDE = {
    "investigar": [],
    "guion": ["investigar"],
    "blog": ["investigar"],
    "voz": ["guion"],
    "miniatura": ["guion"],
    "video": ["voz"],
}
ETAPAS = ["investigar", "guion", "voz", "miniatura", "video", "blog"]  # orden si se hace de una en una


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


def afectadas(desde: str | None) -> set[str]:
    """Etapas que hay que rehacer si se pide rehacer desde `desde` (ella y todo lo que depende de ella)."""
    if desde is None:
        return set()
    if desde == "recolectar":
        desde = "investigar"
    salida, pendientes = set(), [desde]
    while pendientes:
        e = pendientes.pop()
        if e not in salida:
            salida.add(e)
            pendientes += [k for k, deps in DEPENDE.items() if e in deps]
    return salida


class Produccion:
    """Todo lo que se va armando de un video. Cada método es una etapa (un agente)."""

    def __init__(self, app_id: str, con_web: bool = True, minutos: int = 6, voz: str | None = None,
                 desde: str | None = None, notas: str = ""):
        self.app_id, self.con_web, self.minutos, self.voz, self.notas = app_id, con_web, minutos, voz, notas
        self.rehacer = afectadas(desde)
        self.carpeta = config.SALIDA / app_id
        self.carpeta.mkdir(parents=True, exist_ok=True)
        self.clips = _clips(app_id)
        self.ficha = self.imagenes = self.expediente = self.guion = self.entrada = None
        self.video = self.mini = None

    def investigar(self) -> None:
        from agentes import investigador

        c = self.carpeta
        if (c / "ficha.json").exists() and "investigar" not in self.rehacer:
            datos = {"ficha": _leer(c / "ficha.json"), "resenas": _leer(c / "resenas.json"),
                     "imagenes": _leer(c / "imagenes.json")}
        else:
            print("  · recolectando datos de Play Store")
            datos = investigador.recolectar(self.app_id, c)
        self.ficha, self.imagenes = datos["ficha"], datos["imagenes"]
        self.expediente = _leer(c / "expediente.json")
        if self.expediente is None or "investigar" in self.rehacer:
            self.expediente = investigador.analizar(datos, c, con_web=self.con_web)
        print(f"    veredicto: {self.expediente['veredicto']}")

    def guionizar(self) -> None:
        from agentes import guionista

        self.guion = _leer(self.carpeta / "guion.json")
        if self.guion is None or "guion" in self.rehacer:
            info = [{"indice": i, "archivo": Path(x).name} for i, x in enumerate(self.clips, 1)]
            self.guion = guionista.escribir(self.ficha, self.expediente, info, self.minutos, self.notas)
            _guardar(self.carpeta / "guion.json", self.guion)

    def narrar(self) -> None:
        from agentes import voz as voz_mod

        if "voz" in self.rehacer:
            for f in (self.carpeta / "audio").glob("*.mp3"):
                f.unlink()
        voz_mod.narrar(self.guion["escenas"], self.carpeta, self.voz)
        _guardar(self.carpeta / "guion.json", self.guion)

    def miniatura(self) -> None:
        from agentes import graficos

        caps = self.imagenes.get("capturas") or []
        self.mini = graficos.miniatura(self.guion["texto_miniatura"], self.guion["sello_miniatura"],
                                       self.imagenes.get("icono"), caps[0] if caps else None,
                                       self.carpeta / "miniatura.jpg")

    def editar(self) -> None:
        from agentes import editor

        ctx = {"ficha": self.ficha, "expediente": self.expediente, "imagenes": self.imagenes}
        self.video = editor.editar(self.guion["escenas"], ctx, self.carpeta, self.clips)

    def redactar(self) -> None:
        from agentes import blog

        self.entrada = _leer(self.carpeta / "blog.json")
        if self.entrada is None or "blog" in self.rehacer:
            self.entrada = blog.escribir(self.ficha, self.expediente, len(self.imagenes.get("capturas") or []))
            _guardar(self.carpeta / "blog.json", self.entrada)
        (self.carpeta / "blog_preview.html").write_text(
            f"<meta charset='utf-8'><h1>{self.entrada['titulo']}</h1>{self.entrada['html']}", encoding="utf-8")

    def cargar(self, nombre: str) -> None:
        """Toma lo que ya se hizo antes en esa etapa, sin rehacerlo (para reintentos y cambios)."""
        c = self.carpeta
        if nombre == "investigar":
            self.ficha, self.imagenes = _leer(c / "ficha.json"), _leer(c / "imagenes.json")
            self.expediente = _leer(c / "expediente.json")
        elif nombre == "guion":
            self.guion = _leer(c / "guion.json")
        elif nombre == "miniatura":
            self.mini = c / "miniatura.jpg"
        elif nombre == "video":
            self.video = c / "video.mp4"
        elif nombre == "blog":
            self.entrada = _leer(c / "blog.json")
        faltan = {"investigar": self.expediente, "guion": self.guion, "blog": self.entrada}.get(nombre, True)
        if faltan is None:
            raise RuntimeError(f"No encontré lo que ya se había hecho en la etapa '{nombre}'.")

    def etapa(self, nombre: str) -> None:
        {"investigar": self.investigar, "guion": self.guionizar, "voz": self.narrar,
         "miniatura": self.miniatura, "video": self.editar, "blog": self.redactar}[nombre]()

    def cerrar(self) -> Path:
        _reporte(self.carpeta, self.ficha, self.expediente, self.guion, self.entrada, self.video, self.mini)
        return self.carpeta


def crear(app_id: str, con_web: bool = True, minutos: int = 6, voz: str | None = None,
          desde: str | None = None, notas: str = "") -> Path:
    """Hace el video completo, una etapa tras otra (desde la terminal)."""
    p = Produccion(app_id, con_web, minutos, voz, desde, notas)
    print(f"\n▶ {app_id}  ({len(p.clips)} clip(s) tuyos en entrada/{app_id}/)")
    for i, etapa in enumerate(ETAPAS, 1):
        print(f"{i}/{len(ETAPAS)} {etapa}")
        p.etapa(etapa)
    p.cerrar()
    print(f"\n✔ Listo. Revisa {p.carpeta / 'REVISAR.md'} antes de publicar.")
    return p.carpeta


def _reporte(carpeta, ficha, exp, guion, entrada, video, mini) -> None:
    dur = sum(e.get("duracion", 0) for e in guion["escenas"])
    l = [f"# Revisión: {ficha['title']}", "",
         f"- Video: `{video.name}` ({dur / 60:.1f} min) · Miniatura: `{mini.name}` · Blog: `blog_preview.html`",
         f"- **Veredicto:** {exp['veredicto']}", f"- {exp['resumen']}",
         f"- Búsqueda en internet: {exp.get('investigacion_web', 'hecha')}", "",
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


def publicar(app_id: str, titulo_n: int = 1) -> dict:
    from agentes import blog, buscador, youtube

    carpeta = config.SALIDA / app_id
    guion, entrada = _leer(carpeta / "guion.json"), _leer(carpeta / "blog.json")
    imagenes = _leer(carpeta / "imagenes.json")
    if not (guion and entrada and (carpeta / "video.mp4").exists()):
        raise RuntimeError(f"Falta el video o el blog. Primero ejecuta: python canal.py crear {app_id}")
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
    return pub


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
    s.add_argument("--desde", choices=ETAPAS, help="rehacer esta etapa y las que dependen de ella")
    s = sub.add_parser("publicar"); s.add_argument("app_id")
    s.add_argument("--titulo", type=int, default=1, help="cuál de los 3 títulos usar")
    s = sub.add_parser("automatico"); s.add_argument("--n", type=int, default=1)
    s.add_argument("--publicar", action="store_true", help="publicar sin revisión humana (no recomendado)")
    sub.add_parser("demo")
    s = sub.add_parser("autorizar-youtube", help="da permiso a tu canal (crea youtube_token.json)")
    s.add_argument("--puerto", type=int, default=0, help="en un servidor usa 8090 con un túnel SSH")
    s.add_argument("--sin-navegador", action="store_true", help="solo muestra el enlace (para servidores)")
    a = p.parse_args()

    if a.cmd == "ideas":
        from agentes import buscador
        for i, c in enumerate(buscador.ideas(a.n), 1):
            print(f"{i}. [{c['potencial_vistas']}] {c['titulo']}  →  python canal.py crear {c['app_id']}\n"
                  f"   Video: {c['angulo']}\n   {c['por_que']}")
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
    elif a.cmd == "autorizar-youtube":
        from agentes import youtube
        canal_info = youtube._servicio(a.puerto, not a.sin_navegador).channels().list(part="snippet", mine=True).execute()
        nombre = (canal_info.get("items") or [{}])[0].get("snippet", {}).get("title", "?")
        print(f"✔ Listo, autorizado el canal: {nombre}. Se creó youtube_token.json")


if __name__ == "__main__":
    main()
