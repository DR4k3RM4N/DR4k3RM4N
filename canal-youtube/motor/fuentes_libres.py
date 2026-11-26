"""Busca y descarga material con licencia libre (Wikimedia Commons y Pexels).

  python -E -P motor/fuentes_libres.py commons "Tupperware party" --n 15
  python -E -P motor/fuentes_libres.py pexels-video "plastic factory" --n 8
  python -E -P motor/fuentes_libres.py descargar <manifiesto.json> <carpeta_destino>

El manifiesto es una lista de objetos {nombre, url, fuente, licencia, autor, pagina}.
Los créditos se guardan en <carpeta_destino>/creditos.json para la descripción del video.
La clave de Pexels se lee de canal-youtube/.pexels_key (nunca se imprime).
"""
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

UA = "ExpedienteVideoTool/1.0 (video educativo; contacto via Wikimedia)"
RAIZ = Path(__file__).resolve().parent.parent
OK_EXT = {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".webm", ".mov", ".tif", ".tiff"}


def fetch(url, headers=None, timeout=120):
    """Descarga con pausa entre peticiones y reintentos si el servidor pide esperar (429/503)."""
    import time
    h = {"User-Agent": UA}
    h.update(headers or {})
    for intento in range(6):
        time.sleep(2.5)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and intento < 5:
                espera = int(e.headers.get("Retry-After") or 0) or 5 * (intento + 1)
                time.sleep(min(espera, 60))
                continue
            raise


def get_json(url, headers=None):
    return json.loads(fetch(url, headers, 60).decode("utf-8"))


def limpia(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html or "")).strip()


def commons(query, n=15):
    api = "https://commons.wikimedia.org/w/api.php"
    q = urllib.parse.urlencode({
        "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrlimit": n,
        "gsrsearch": query, "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 640,
    })
    d = get_json(f"{api}?{q}")
    out = []
    for p in (d.get("query", {}).get("pages", {}) or {}).values():
        ii = (p.get("imageinfo") or [{}])[0]
        md = ii.get("extmetadata", {})
        out.append(dict(
            titulo=p["title"][5:], url=ii.get("url"), mini=ii.get("thumburl"), mime=ii.get("mime"),
            ancho=ii.get("width"), alto=ii.get("height"), bytes=ii.get("size"),
            licencia=limpia(md.get("LicenseShortName", {}).get("value")),
            autor=limpia(md.get("Artist", {}).get("value"))[:80],
            pagina=ii.get("descriptionurl"), fuente="Wikimedia Commons",
        ))
    return out


def commons_thumbs(titulos, ancho=1920):
    """URL de la miniatura estándar (1920 px) de cada archivo; Wikimedia pide no bajar originales en serie."""
    api = "https://commons.wikimedia.org/w/api.php"
    out = {}
    for i in range(0, len(titulos), 20):
        q = urllib.parse.urlencode({
            "action": "query", "format": "json", "titles": "|".join("File:" + t for t in titulos[i:i + 20]),
            "prop": "imageinfo", "iiprop": "url", "iiurlwidth": ancho,
        })
        d = get_json(f"{api}?{q}")
        for p in d.get("query", {}).get("pages", {}).values():
            ii = (p.get("imageinfo") or [{}])[0]
            out[p["title"][5:]] = ii.get("thumburl") or ii.get("url")
    return out


def commons_video_transcode(titulo, alturas=(1080, 720, 480)):
    """URL de una versión convertida (transcode) del video; Wikimedia limita la descarga de originales."""
    api = "https://commons.wikimedia.org/w/api.php"
    q = urllib.parse.urlencode({"action": "query", "format": "json", "titles": "File:" + titulo,
                                "prop": "videoinfo", "viprop": "derivatives"})
    d = get_json(f"{api}?{q}")
    for p in d.get("query", {}).get("pages", {}).values():
        der = (p.get("videoinfo") or [{}])[0].get("derivatives", [])
        for h in alturas:
            for x in der:
                if x.get("height") == h and "webm" in (x.get("type") or "") and "/transcoded/" in x.get("src", ""):
                    return x["src"]
    return None


def pexels_key():
    f = RAIZ / ".pexels_key"
    if not f.exists():
        raise SystemExit("Falta la clave de Pexels en canal-youtube/.pexels_key")
    return f.read_text(encoding="utf-8").strip()


def pexels_video(query, n=8):
    q = urllib.parse.urlencode({"query": query, "per_page": n, "orientation": "landscape", "size": "medium"})
    d = get_json(f"https://api.pexels.com/videos/search?{q}", {"Authorization": pexels_key()})
    out = []
    for v in d.get("videos", []):
        files = [f for f in v.get("video_files", []) if f.get("width") and f.get("file_type") == "video/mp4"]
        hd = [f for f in files if 1280 <= f["width"] <= 1920] or files
        best = max(hd, key=lambda f: f["width"]) if hd else None
        if not best:
            continue
        out.append(dict(
            titulo=f"pexels-{v['id']}", url=best["link"], mini=v.get("image"), mime="video/mp4",
            ancho=best["width"], alto=best["height"], segundos=v.get("duration"),
            licencia="Licencia de Pexels", autor=(v.get("user") or {}).get("name", ""), pagina=v.get("url"),
            fuente="Pexels",
        ))
    return out


def descargar(manifiesto, destino):
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    items = json.loads(Path(manifiesto).read_text(encoding="utf-8"))
    creditos_f = destino / "creditos.json"
    creditos = json.loads(creditos_f.read_text(encoding="utf-8")) if creditos_f.exists() else {}
    for it in items:
        nombre = re.sub(r"[^a-z0-9._-]+", "-", it["nombre"].lower())
        ext = Path(urllib.parse.urlparse(it["url"]).path).suffix.lower()
        if ext not in OK_EXT:
            print("SALTADO (tipo no permitido):", it["nombre"], ext)
            continue
        if not nombre.endswith(ext):
            nombre += ext
        f = destino / nombre
        if not f.exists():
            f.write_bytes(fetch(it["url"], timeout=300))
        creditos[nombre] = {k: it.get(k) for k in ("fuente", "licencia", "autor", "pagina", "titulo")}
        creditos_f.write_text(json.dumps(creditos, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{nombre}  {f.stat().st_size // 1024} KB", flush=True)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return
    cmd = sys.argv[1]
    n = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 15
    if cmd == "commons":
        r = commons(sys.argv[2], n)
    elif cmd == "pexels-video":
        r = pexels_video(sys.argv[2], n)
    elif cmd == "descargar":
        descargar(sys.argv[2], sys.argv[3])
        return
    else:
        raise SystemExit("Comando desconocido")
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    main()
