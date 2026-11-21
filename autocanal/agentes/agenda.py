"""📅 Gestor de horarios: reparte los videos en el día para que nunca salgan dos juntos.

Reglas (pestaña Estilo; por defecto):
- Ventana: de 8:00 a 21:00 (hora de IDEAS_ZONA, México).
- Entre dos videos de investigación: 3 horas. Si alguno de los dos es de grabación de pantalla: 1 hora.
- Nunca dos videos a la misma hora, ni dos de la misma app el mismo día.
- Máximo de videos por día (AGENDA_MAX_DIA, 5): la API de YouTube regala 10,000 unidades al día y cada video
  subido gasta 1,600.
La agenda se arma con lo que ya está programado (salida/*/publicado.json → programado_utc).
"""
from __future__ import annotations

import datetime as dt
import json
from zoneinfo import ZoneInfo

from . import config, estilo

UTC = dt.timezone.utc


def zona() -> ZoneInfo:
    return ZoneInfo(config.env("IDEAS_ZONA", "America/Mexico_City"))


def reglas() -> dict:
    a = estilo.cargar()["ajustes"]
    return {"activa": bool(a.get("agenda", True)), "inicio": int(a.get("agenda_inicio", 8)),
            "fin": int(a.get("agenda_fin", 21)), "sep_investigacion": float(a.get("sep_investigacion", 3)),
            "sep_grabacion": float(a.get("sep_grabacion", 1)),
            "max_dia": int(config.env("AGENDA_MAX_DIA", "5") or 5)}


def ocupados(sin: str = "", canal: str | None = None) -> list[dict]:
    """Lo que ya está programado o publicado en los últimos días (de todos los proyectos)."""
    salida = []
    limite = dt.datetime.now(UTC) - dt.timedelta(days=2)
    for f in config.SALIDA.glob("*/publicado.json"):
        if f.parent.name == sin:
            continue
        try:
            pub = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        cuando = pub.get("programado_utc")
        if not cuando or pub.get("desprogramado"):
            continue
        if canal and (pub.get("canal") or "principal") != canal:  # cada canal tiene su propia agenda
            continue
        t = dt.datetime.strptime(cuando, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        if t >= limite:
            salida.append({"t": t, "tipo": pub.get("tipo_video", "investigacion"), "app": f.parent.name.split("~")[0],
                           "canal": pub.get("canal") or "principal",
                           "proyecto": f.parent.name, "titulo": pub.get("titulo", "")})
    return sorted(salida, key=lambda x: x["t"])


def tipo_de(app_id: str) -> str:
    """'grabacion' si el video lleva prueba grabada (tuya o del robot); si no, 'investigacion'."""
    prueba = config.SALIDA / app_id / "prueba.json"
    return "grabacion" if prueba.exists() else "investigacion"


def siguiente(app_id: str, tipo: str, desde: dt.datetime | None = None, canal: str | None = None) -> dt.datetime:
    """El primer horario libre que cumple las reglas (en UTC)."""
    r = reglas()
    z = zona()
    ahora = (desde or dt.datetime.now(UTC)).astimezone(z)
    otros = ocupados(sin=app_id, canal=canal or "principal")
    app = app_id.split("~")[0]
    inicio = ahora + dt.timedelta(minutes=50)  # YouTube necesita margen para programar
    hora = inicio.replace(minute=0, second=0, microsecond=0) + (dt.timedelta(hours=1) if inicio.minute else dt.timedelta())
    for _ in range(24 * 30):  # hasta 30 días
        if r["inicio"] <= hora.hour <= r["fin"]:
            dia = hora.date()
            del_dia = [o for o in otros if o["t"].astimezone(z).date() == dia]
            libre = len(del_dia) < r["max_dia"] and not any(o["app"] == app for o in del_dia)
            for o in otros:
                if not libre:
                    break
                separacion = r["sep_investigacion"] if tipo == o["tipo"] == "investigacion" else r["sep_grabacion"]
                if abs((hora - o["t"].astimezone(z)).total_seconds()) < separacion * 3600 - 1:
                    libre = False
            if libre:
                return hora.astimezone(UTC)
        hora += dt.timedelta(hours=1)
    raise RuntimeError("No encontré horario libre en los próximos 30 días.")


def texto(t: dt.datetime) -> str:
    z = zona()
    local = t.astimezone(z)
    hoy = dt.datetime.now(z).date()
    dia = "hoy" if local.date() == hoy else "mañana" if local.date() == hoy + dt.timedelta(days=1) \
        else f"el {local:%d/%m}"
    hora = local.strftime("%I:%M %p").lstrip("0").lower().replace("am", "a. m.").replace("pm", "p. m.")
    return f"{dia} a las {hora}"


def proximos() -> list[dict]:
    """Para la pestaña Agenda: lo que viene (y lo de hoy que ya salió)."""
    z = zona()
    hoy = dt.datetime.now(z).replace(hour=0, minute=0, second=0, microsecond=0)
    return [{"proyecto": o["proyecto"], "titulo": o["titulo"], "tipo": o["tipo"], "cuando": texto(o["t"]), "canal": o["canal"],
             "t": o["t"].timestamp(), "ya_salio": o["t"] <= dt.datetime.now(UTC)}
            for o in ocupados() if o["t"].astimezone(z) >= hoy]
