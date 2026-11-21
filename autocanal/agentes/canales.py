"""📺 Tus canales de YouTube. La oficina puede trabajar para varios a la vez: cada uno con su permiso (token), su
proyecto de Google (cuota propia), su 📘 manual, su agenda y su tema.

- "principal": el canal de siempre ("Apps que sí pagan"): youtube_token.json y client_secret.json en autocanal/.
- Los demás: canales/<id>/youtube_token.json y canales/<id>/client_secret.json; datos en canales.json.
En cada trabajo, `claude.contexto.canal` dice para qué canal se está trabajando (lo pone la oficina).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import config

ARCHIVO = config.BASE / "canales.json"
PRINCIPAL = "principal"
NICHOS = {
    "apps": "Apps que prometen pagar dinero: ¿pagan o son estafa? (pruebas, reseñas, veredicto)",
    "fraudes": "Alertas de fraude y protege tu dinero en México: montadeudas, estafas que están pegando, alertas de la "
               "Condusef y la Policía Cibernética, qué hacer si ya caíste y dónde denunciar",
    "libre": "Cualquier tema",
}


def _leer() -> dict:
    try:
        return json.loads(ARCHIVO.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def lista() -> list[dict]:
    """[{id, nombre, nicho, blog}] — siempre incluye el principal."""
    datos = _leer()
    principal = {"id": PRINCIPAL, "nombre": config.CANAL_NOMBRE, "nicho": "apps", "blog": True,
                 **(datos.get(PRINCIPAL) or {})}
    otros = [{"id": k, **v} for k, v in datos.items() if k != PRINCIPAL]
    return [principal, *otros]


def get(cid: str | None) -> dict:
    return next((c for c in lista() if c["id"] == (cid or PRINCIPAL)), lista()[0])


def existe(cid: str) -> bool:
    return any(c["id"] == cid for c in lista())


def carpeta(cid: str | None) -> Path:
    return config.BASE if (cid or PRINCIPAL) == PRINCIPAL else config.BASE / "canales" / cid


def token(cid: str | None) -> Path:
    return carpeta(cid) / "youtube_token.json"


def secreto(cid: str | None) -> Path:
    if (cid or PRINCIPAL) == PRINCIPAL:
        return config.BASE / config.env("YT_CLIENT_SECRETS", "client_secret.json")
    return carpeta(cid) / "client_secret.json"


def conectado(cid: str | None) -> bool:
    return token(cid).exists()


def slug(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-")[:30] or "canal"


def guardar(cid: str, **datos) -> None:
    todo = _leer()
    todo[cid] = {**(todo.get(cid) or {}), **{k: v for k, v in datos.items() if v is not None}}
    ARCHIVO.write_text(json.dumps(todo, ensure_ascii=False, indent=2), encoding="utf-8")


MASCOTAS = {"fraudes": "lanudo"}  # el personaje de cada tema (Lanudo, el borrego de «Cuida Tu Lana»)


def mascota(cid: str | None = None, expresion: str = "normal") -> Path | None:
    """La mascota del canal: estilo/mascota_<id>.png si subiste una; si no, la del tema; el principal, la suya."""
    from . import estilo

    cid = cid or actual()
    if cid == PRINCIPAL:
        return estilo.archivo("mascota")
    propia = config.ESTILO_DIR / f"mascota_{cid}.png"
    if propia.exists():
        return propia
    nombre = MASCOTAS.get(get(cid).get("nicho"))
    if nombre:
        ruta = config.ASSETS / "mascotas" / nombre / f"{expresion}.png"
        return ruta if ruta.exists() else config.ASSETS / "mascotas" / nombre / "normal.png"
    return None


def actual() -> str:
    """El canal del trabajo en curso (la oficina lo pone en cada hilo)."""
    from . import claude
    return getattr(claude.contexto, "canal", None) or PRINCIPAL
