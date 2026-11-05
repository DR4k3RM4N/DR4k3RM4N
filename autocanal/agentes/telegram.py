"""Telegram: avisos del equipo y chat con el jefe, gratis.

Usa la Bot API de Telegram con "long polling" (la oficina le pregunta a Telegram si hay mensajes nuevos),
así no hace falta webhook ni abrir nada en el servidor. Solo se obedecen mensajes del chat del jefe.
"""
from __future__ import annotations

import html
import re
import time

import requests

from . import config

TOKEN = config.env("TELEGRAM_TOKEN")
CHAT_ID = config.env("TELEGRAM_CHAT_ID")
API = f"https://api.telegram.org/bot{TOKEN}"

# Botones fijos abajo del chat para lo que más se usa.
TECLADO = {"keyboard": [[{"text": "💡 Pendientes"}, {"text": "📊 ¿Cómo van?"}], [{"text": "🔍 Buscar ideas"}, {"text": "❓ Ayuda"}]],
           "resize_keyboard": True, "is_persistent": True}


class ErrorTelegram(Exception):
    pass


def activo() -> bool:
    return bool(TOKEN and CHAT_ID)


def _llamar(metodo: str, **datos) -> dict:
    try:
        r = requests.post(f"{API}/{metodo}", json=datos, timeout=datos.get("timeout", 0) + 20)
        j = r.json()
    except (requests.RequestException, ValueError) as exc:
        raise ErrorTelegram(str(exc)) from exc
    if not j.get("ok"):
        raise ErrorTelegram(f"{j.get('error_code')}: {j.get('description')}")
    return j["result"]


def a_html(texto: str) -> str:
    """El formato de los avisos usa *negritas*; Telegram las quiere en HTML."""
    seguro = html.escape(texto, quote=False)
    return re.sub(r"\*([^*\n]+)\*", r"<b>\1</b>", seguro)


def enviar(texto: str, botones: list[list[dict]] | None = None, teclado: bool = False, chat_id: str | None = None) -> None:
    trozos = [texto[i:i + 3800] for i in range(0, len(texto), 3800)] or [""]
    for k, trozo in enumerate(trozos):
        datos = {"chat_id": chat_id or CHAT_ID, "text": a_html(trozo), "parse_mode": "HTML",
                 "link_preview_options": {"is_disabled": True}}
        if k == len(trozos) - 1:
            if botones:
                datos["reply_markup"] = {"inline_keyboard": botones}
            elif teclado:
                datos["reply_markup"] = TECLADO
        _llamar("sendMessage", **datos)


def botones_ideas(ideas: list[dict]) -> list[list[dict]]:
    """Un renglón por idea: ✅ para hacerla y ❌ para descartarla."""
    filas = []
    for p in ideas[:10]:
        n = p.get("num")
        titulo = p["titulo"][:22]
        filas.append([{"text": f"✅ {n}. {titulo}", "callback_data": f"sí {n}"},
                      {"text": f"❌ {n}", "callback_data": f"no {n}"}])
    return filas


def escuchar(al_recibir, detener=lambda: False) -> None:
    """Pide mensajes nuevos a Telegram sin parar y llama al_recibir(mensaje) con los del jefe."""
    desplazamiento = None
    try:  # ignorar lo que se escribió mientras la oficina estaba apagada (más de 10 min)
        viejos = _llamar("getUpdates", timeout=0)
        if viejos:
            desplazamiento = viejos[-1]["update_id"] + 1
            for u in viejos:
                m = u.get("message") or {}
                if m and time.time() - m.get("date", 0) < 600:
                    desplazamiento = u["update_id"]
                    break
    except ErrorTelegram:
        pass
    while not detener():
        try:
            datos = {"timeout": 50, "allowed_updates": ["message", "callback_query"]}
            if desplazamiento is not None:
                datos["offset"] = desplazamiento
            for u in _llamar("getUpdates", **datos):
                desplazamiento = u["update_id"] + 1
                if "callback_query" in u:
                    cq = u["callback_query"]
                    try:
                        _llamar("answerCallbackQuery", callback_query_id=cq["id"], text="Va 👍")
                    except ErrorTelegram:
                        pass
                    chat = str((cq.get("message") or {}).get("chat", {}).get("id", ""))
                    if chat == str(CHAT_ID):
                        al_recibir({"id": f"tg-cb-{cq['id']}", "texto": cq.get("data", ""), "tipo": "boton"})
                    continue
                m = u.get("message") or {}
                if str(m.get("chat", {}).get("id", "")) != str(CHAT_ID):
                    continue  # solo el jefe
                al_recibir({"id": f"tg-{m.get('message_id')}", "texto": (m.get("text") or "").strip(),
                            "tipo": "texto" if m.get("text") else "otro"})
        except ErrorTelegram as exc:
            print(f"aviso: Telegram: {exc}", flush=True)
            time.sleep(10 if "409" not in str(exc) else 30)
        except Exception as exc:  # noqa: BLE001 — escuchar nunca debe morir
            print(f"aviso: Telegram: {exc}", flush=True)
            time.sleep(10)
