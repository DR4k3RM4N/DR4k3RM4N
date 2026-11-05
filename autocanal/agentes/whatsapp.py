"""WhatsApp (API oficial de Meta, WhatsApp Cloud API): avisos del equipo y chat con el jefe.

- Enviar: texto libre si el jefe escribió en las últimas 24 h; si no, una plantilla aprobada por Meta
  (WhatsApp exige plantilla para iniciar conversación).
- Recibir: Meta llama a /whatsapp/webhook con cada mensaje; se verifica la firma con el App Secret.
"""
from __future__ import annotations

import hashlib
import hmac
import re

import requests

from . import config

TOKEN = config.env("WHATSAPP_TOKEN")
PHONE_ID = config.env("WHATSAPP_PHONE_ID")
JEFE = re.sub(r"\D", "", config.env("WHATSAPP_JEFE"))          # tu número con lada, ej. 5216641234567
VERIFY_TOKEN = config.env("WHATSAPP_VERIFY_TOKEN")
APP_SECRET = config.env("WHATSAPP_APP_SECRET")
PLANTILLA = config.env("WHATSAPP_PLANTILLA", "novedad_oficina")
IDIOMA = config.env("WHATSAPP_IDIOMA", "es_MX")
VERSION = config.env("WHATSAPP_API_VERSION", "v24.0")
NIVEL = config.env("WHATSAPP_NIVEL", "importante")              # importante | todo


class ErrorWhatsApp(Exception):
    pass


def activo() -> bool:
    return bool(TOKEN and PHONE_ID and JEFE)


def es_el_jefe(numero: str) -> bool:
    """Compara los últimos 10 dígitos (en México WhatsApp a veces agrega un 1 después del 52)."""
    n = re.sub(r"\D", "", numero or "")
    return bool(JEFE) and n[-10:] == JEFE[-10:]


def _post(cuerpo: dict) -> dict:
    r = requests.post(f"https://graph.facebook.com/{VERSION}/{PHONE_ID}/messages",
                      headers={"Authorization": f"Bearer {TOKEN}"}, json=cuerpo, timeout=30)
    datos = r.json() if r.content else {}
    if r.status_code >= 400:
        err = datos.get("error", {})
        raise ErrorWhatsApp(f"{r.status_code}: {err.get('message', r.text[:200])} (código {err.get('code')})")
    return datos


def enviar_texto(para: str, texto: str) -> dict:
    return _post({"messaging_product": "whatsapp", "to": para, "type": "text",
                  "text": {"body": texto[:4000], "preview_url": True}})


def enviar_plantilla(para: str, texto: str) -> dict:
    # Las variables de plantilla no aceptan saltos de línea ni muchos espacios seguidos.
    limpio = re.sub(r"\s*\n+\s*", " · ", texto)
    limpio = re.sub(r"\s{4,}", "   ", limpio).strip()[:900]
    return _post({"messaging_product": "whatsapp", "to": para, "type": "template",
                  "template": {"name": PLANTILLA, "language": {"code": IDIOMA},
                               "components": [{"type": "body", "parameters": [{"type": "text", "text": limpio}]}]}})


def firma_valida(cuerpo: bytes, cabecera: str) -> bool:
    if not APP_SECRET:
        return False
    esperado = hmac.new(APP_SECRET.encode(), cuerpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={esperado}", cabecera or "")


def mensajes_entrantes(datos: dict) -> list[dict]:
    """Saca los mensajes de texto (y botones) del aviso que manda Meta."""
    salida = []
    for entrada in datos.get("entry", []):
        for cambio in entrada.get("changes", []):
            valor = cambio.get("value", {})
            for m in valor.get("messages", []) or []:
                texto = (m.get("text") or {}).get("body") or (m.get("button") or {}).get("text") \
                    or ((m.get("interactive") or {}).get("button_reply") or {}).get("title") or ""
                salida.append({"id": m.get("id"), "de": m.get("from"), "texto": texto.strip(), "tipo": m.get("type")})
    return salida
