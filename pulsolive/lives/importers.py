"""Importación de archivos exportados de TikTok Shop / LIVE Center.

TikTok cambia los nombres de columnas según idioma y versión, así que en vez
de exigir un formato fijo reconocemos muchos alias (español e inglés) y
normalizamos formatos de dinero, duración y fecha.
"""
from __future__ import annotations

import io
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

import pandas as pd
from django.utils import timezone


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


SESSION_ALIASES = {
    "external_id": ["id del live", "live id", "room id", "id de transmision", "id"],
    "title": ["titulo", "title", "nombre del live", "live name", "nombre"],
    "started_at": ["hora de inicio", "fecha de inicio", "inicio", "start time", "live start time", "launched time",
                   "fecha y hora", "fecha", "date", "start"],
    "ended_at": ["hora de fin", "hora de finalizacion", "fin", "end time", "live end time"],
    "duration_minutes": ["duracion", "duracion min", "duracion del live", "duration", "live duration",
                         "duracion minutos", "minutos"],
    "gmv": ["gmv", "ventas", "ventas mxn", "gmv mxn", "ingresos", "revenue", "gross merchandise value",
            "monto de ventas", "valor bruto de mercancia", "gmv total", "live gmv"],
    "orders": ["pedidos", "orders", "sku orders", "ordenes", "pedidos de sku", "pedidos pagados", "paid orders"],
    "units_sold": ["piezas vendidas", "units sold", "articulos vendidos", "unidades vendidas", "items sold"],
    "viewers": ["espectadores", "viewers", "vistas", "views", "visualizaciones", "espectadores unicos",
                "unique viewers", "total viewers", "vistas del live"],
    "peak_viewers": ["pico de espectadores", "peak viewers", "max viewers", "espectadores simultaneos maximos",
                     "maximo de espectadores", "pcu"],
    "avg_watch_seconds": ["tiempo promedio de visualizacion", "tiempo medio de visualizacion",
                          "avg watch time", "average view duration", "average watch time",
                          "duracion media de visualizacion", "tiempo promedio"],
    "new_followers": ["nuevos seguidores", "new followers", "seguidores nuevos", "seguidores ganados"],
    "likes": ["likes", "me gusta"],
    "comments": ["comentarios", "comments"],
    "shares": ["compartidos", "shares", "veces compartido"],
    "product_clicks": ["clics en producto", "clics de producto", "product clicks", "clics en productos",
                       "product click"],
    "host": ["host", "presentador", "presentadora", "anfitrion", "anfitriona", "creador", "creator"],
    "promo_type": ["promocion", "promo", "tipo de promocion"],
    "script_type": ["guion", "script", "tipo de guion"],
    "main_product": ["producto", "producto principal", "main product", "product"],
    "product_category": ["categoria", "categoria de producto", "category"],
    "notes": ["notas", "notes", "comentarios internos"],
}

MINUTE_ALIASES = {
    "minute": ["minuto", "minute", "min", "tiempo", "time", "timestamp", "hora"],
    "viewers": ["espectadores", "viewers", "espectadores en linea", "online viewers", "concurrent viewers"],
    "orders": ["pedidos", "orders", "ordenes"],
    "gmv": ["gmv", "ventas", "revenue", "ingresos"],
    "comments": ["comentarios", "comments"],
}

PROMO_ALIASES = {
    "none": ["", "ninguna", "sin promocion", "no", "none"],
    "discount": ["descuento", "discount", "rebaja"],
    "flash_sale": ["flash", "flash sale", "oferta relampago", "relampago"],
    "bundle": ["paquete", "bundle", "2x1", "combo", "3x2"],
    "gift": ["regalo", "gift", "obsequio"],
    "free_shipping": ["envio gratis", "free shipping"],
    "coupon": ["cupon", "coupon", "codigo"],
    "giveaway": ["sorteo", "giveaway", "dinamica"],
}

SCRIPT_ALIASES = {
    "demo": ["demo", "demostracion"],
    "tutorial": ["tutorial", "paso a paso"],
    "storytelling": ["historia", "storytelling", "testimonio"],
    "qna": ["preguntas", "qna", "q a", "preguntas y respuestas"],
    "unboxing": ["unboxing"],
    "before_after": ["antes y despues", "before after"],
    "haul": ["haul"],
}


def _match_choice(value: str, aliases: dict, default: str) -> str:
    v = norm(value)
    for code, names in aliases.items():
        if v == code or v in names or any(n and n in v for n in names):
            return code
    return default


def map_columns(columns, aliases: dict) -> dict:
    """Devuelve {campo: nombre_de_columna_original}."""
    normalized = {norm(c): c for c in columns}
    mapping = {}
    for fieldname, names in aliases.items():
        for name in names:
            if name in normalized:
                mapping[fieldname] = normalized[name]
                break
        else:
            # Coincidencia parcial: "GMV (MXN)" -> "gmv mxn" contiene "gmv"
            for ncol, original in normalized.items():
                if any(ncol.startswith(n + " ") for n in names if len(n) > 3) and original not in mapping.values():
                    mapping[fieldname] = original
                    break
    return mapping


def parse_money(value) -> Decimal:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return Decimal("0")
    if isinstance(value, (int, float)):
        return Decimal(str(round(value, 2)))
    s = re.sub(r"[^\d,.\-]", "", str(value))
    if not s:
        return Decimal("0")
    if "," in s and "." in s:
        s = s.replace(",", "") if s.rfind(".") > s.rfind(",") else s.replace(".", "").replace(",", ".")
    elif "," in s:
        parts = s.split(",")
        s = s.replace(",", "") if len(parts[-1]) == 3 else s.replace(",", ".")
    try:
        return Decimal(s).quantize(Decimal("0.01"))
    except InvalidOperation:
        return Decimal("0")


def parse_int(value) -> int:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 0
    if isinstance(value, (int, float)):
        return int(round(value))
    s = str(value).strip().lower()
    mult = 1
    if s.endswith("k"):
        mult, s = 1000, s[:-1]
    elif s.endswith("m"):
        mult, s = 1_000_000, s[:-1]
    s = re.sub(r"[^\d.]", "", s.replace(",", ""))
    try:
        return int(float(s) * mult) if s else 0
    except ValueError:
        return 0


def parse_duration_seconds(value, assume_unit="minutes") -> int:
    """Acepta '1h 23m', '01:23:45', '83', '83 min', '4980s', '1m 20s'."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 0
    if isinstance(value, (int, float)):
        return int(value * 60) if assume_unit == "minutes" else int(value)
    if isinstance(value, timedelta):
        return int(value.total_seconds())
    s = str(value).strip().lower()
    if re.fullmatch(r"\d{1,3}:\d{2}(:\d{2})?", s):
        parts = [int(p) for p in s.split(":")]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        # mm:ss para tiempos de visualización, hh:mm para duraciones
        return parts[0] * 60 + parts[1] if assume_unit == "seconds" else parts[0] * 3600 + parts[1] * 60
    total, found = 0, False
    for amount, unit in re.findall(r"(\d+(?:\.\d+)?)\s*(h|hr|hrs|hora|horas|m|min|mins|minutos|s|seg|segundos|sec)\b", s):
        found = True
        amount = float(amount)
        if unit.startswith("h"):
            total += amount * 3600
        elif unit.startswith("m"):
            total += amount * 60
        else:
            total += amount
    if found:
        return int(total)
    num = re.sub(r"[^\d.]", "", s)
    if not num:
        return 0
    return int(float(num) * 60) if assume_unit == "minutes" else int(float(num))


def parse_datetime(value) -> datetime | None:
    if value is None or (isinstance(value, float) and pd.isna(value)) or str(value).strip() == "":
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        s = str(value).strip()
        dt = None
        for dayfirst in (False, True) if re.match(r"\d{4}-", s) else (True, False):
            try:
                dt = pd.to_datetime(s, dayfirst=dayfirst).to_pydatetime()
                break
            except (ValueError, TypeError):
                continue
        if dt is None:
            return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def read_table(uploaded_file) -> pd.DataFrame:
    name = (getattr(uploaded_file, "name", "") or "").lower()
    raw = uploaded_file.read()
    if name.endswith((".xlsx", ".xls")):
        df = pd.read_excel(io.BytesIO(raw))
    else:
        text = None
        for enc in ("utf-8-sig", "latin-1"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        sep = ";" if text.count(";") > text.count(",") else ","
        df = pd.read_csv(io.StringIO(text), sep=sep, dtype=str, keep_default_na=False)
    df = df.dropna(how="all")
    df.columns = [str(c).strip() for c in df.columns]
    return df


@dataclass
class ParsedSession:
    row_number: int
    data: dict
    host_name: str = ""


@dataclass
class ParseResult:
    rows: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    mapping: dict = field(default_factory=dict)
    missing_required: list = field(default_factory=list)


def parse_sessions(df: pd.DataFrame) -> ParseResult:
    result = ParseResult()
    mapping = map_columns(df.columns, SESSION_ALIASES)
    result.mapping = mapping
    if "started_at" not in mapping:
        result.missing_required.append("fecha / hora de inicio")
    if "gmv" not in mapping and "orders" not in mapping:
        result.missing_required.append("ventas (GMV) o pedidos")
    if result.missing_required:
        return result

    def get(row, key):
        col = mapping.get(key)
        return row[col] if col is not None else None

    for i, row in df.iterrows():
        n = int(i) + 2  # número de fila como en Excel (con encabezado)
        started = parse_datetime(get(row, "started_at"))
        if not started:
            result.errors.append(f"Fila {n}: no se entendió la fecha de inicio «{get(row, 'started_at')}».")
            continue
        duration_min = 0
        if "duration_minutes" in mapping:
            duration_min = round(parse_duration_seconds(get(row, "duration_minutes"), "minutes") / 60)
        if not duration_min and "ended_at" in mapping:
            ended = parse_datetime(get(row, "ended_at"))
            if ended and ended > started:
                duration_min = round((ended - started).total_seconds() / 60)
        data = {
            "started_at": started,
            "duration_minutes": max(duration_min or 60, 1),
            "gmv": parse_money(get(row, "gmv")),
            "orders": parse_int(get(row, "orders")),
            "units_sold": parse_int(get(row, "units_sold")),
            "viewers": parse_int(get(row, "viewers")),
            "peak_viewers": parse_int(get(row, "peak_viewers")),
            "avg_watch_seconds": parse_duration_seconds(get(row, "avg_watch_seconds"), "seconds"),
            "new_followers": parse_int(get(row, "new_followers")),
            "likes": parse_int(get(row, "likes")),
            "comments": parse_int(get(row, "comments")),
            "shares": parse_int(get(row, "shares")),
            "product_clicks": parse_int(get(row, "product_clicks")),
            "title": str(get(row, "title") or "")[:200],
            "external_id": str(get(row, "external_id") or "")[:120],
            "main_product": str(get(row, "main_product") or "")[:150],
            "product_category": str(get(row, "product_category") or "")[:80],
            "notes": str(get(row, "notes") or ""),
        }
        if "promo_type" in mapping:
            data["promo_type"] = _match_choice(get(row, "promo_type"), PROMO_ALIASES, "none")
        if "script_type" in mapping:
            data["script_type"] = _match_choice(get(row, "script_type"), SCRIPT_ALIASES, "other")
        result.rows.append(ParsedSession(row_number=n, data=data, host_name=str(get(row, "host") or "").strip()))
    return result


def parse_minutes(df: pd.DataFrame, live_start: datetime | None = None) -> ParseResult:
    result = ParseResult()
    mapping = map_columns(df.columns, MINUTE_ALIASES)
    result.mapping = mapping
    if "minute" not in mapping:
        result.missing_required.append("minuto / tiempo")
        return result
    first_dt = None
    for i, row in df.iterrows():
        raw = row[mapping["minute"]]
        minute = None
        s = str(raw).strip()
        if re.fullmatch(r"\d+(\.\d+)?", s):
            minute = int(float(s))
        elif re.fullmatch(r"\d{1,2}:\d{2}(:\d{2})?", s):
            parts = [int(p) for p in s.split(":")]
            minute = parts[0] * 60 + parts[1] if len(parts) == 3 else parts[0]
        else:
            dt = parse_datetime(s)
            if dt:
                base = live_start or first_dt or dt
                first_dt = first_dt or dt
                minute = int((dt - base).total_seconds() // 60)
        if minute is None or minute < 0:
            result.errors.append(f"Fila {int(i) + 2}: tiempo no válido «{raw}».")
            continue
        result.rows.append({
            "minute": minute,
            "viewers": parse_int(row[mapping["viewers"]]) if "viewers" in mapping else 0,
            "orders": parse_int(row[mapping["orders"]]) if "orders" in mapping else 0,
            "gmv": parse_money(row[mapping["gmv"]]) if "gmv" in mapping else Decimal("0"),
            "comments": parse_int(row[mapping["comments"]]) if "comments" in mapping else 0,
        })
    return result


# ---------------------------------------------------------------------------
# Transcripciones
# ---------------------------------------------------------------------------

_TS = r"(\d{1,2}:)?\d{1,2}:\d{2}(?:[.,]\d{1,3})?"


def _ts_to_seconds(ts: str) -> float:
    ts = ts.replace(",", ".")
    parts = ts.split(":")
    secs = float(parts[-1])
    mins = int(parts[-2]) if len(parts) >= 2 else 0
    hrs = int(parts[-3]) if len(parts) >= 3 else 0
    return hrs * 3600 + mins * 60 + secs


def parse_transcript(text: str) -> list[dict]:
    """Soporta SRT, WebVTT y texto con marcas de tiempo tipo "[00:12:30] hola".

    Si no hay marcas de tiempo, reparte el texto en bloques de ~1 minuto
    suponiendo 150 palabras por minuto (aproximación).
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    segments = []
    cue = re.compile(rf"({_TS})\s*-->\s*({_TS})")
    blocks = re.split(r"\n\s*\n", text)
    if cue.search(text):
        for block in blocks:
            lines = [ln for ln in block.strip().split("\n") if ln.strip()]
            for idx, ln in enumerate(lines):
                m = cue.search(ln)
                if m:
                    body = " ".join(l.strip() for l in lines[idx + 1:])
                    body = re.sub(r"<[^>]+>", "", body).strip()
                    if body:
                        segments.append({"start": _ts_to_seconds(m.group(1)), "end": _ts_to_seconds(m.group(3)),
                                         "text": body})
                    break
        return segments

    stamp = re.compile(rf"^\s*\[?({_TS})\]?\s*[-–:]?\s*(.*)$")
    for line in text.split("\n"):
        m = stamp.match(line)
        if m and m.group(3).strip():
            segments.append({"start": _ts_to_seconds(m.group(1)), "end": None, "text": m.group(3).strip()})
        elif segments and line.strip():
            segments[-1]["text"] += " " + line.strip()
    if segments:
        for a, b in zip(segments, segments[1:]):
            a["end"] = b["start"]
        segments[-1]["end"] = segments[-1]["start"] + 30
        return segments

    words = text.split()
    for i in range(0, len(words), 150):
        segments.append({"start": i / 150 * 60, "end": (i + 150) / 150 * 60, "text": " ".join(words[i:i + 150])})
    return segments


KEYWORD_EVENTS = [
    ("flash_sale", ["oferta relampago", "flash", "solo por los proximos", "solo por 5 minutos", "solo por 10 minutos"]),
    ("scarcity", ["ultimas piezas", "quedan pocas", "quedan solo", "se estan acabando", "ultimas unidades",
                  "stock limitado", "se agota"]),
    ("urgency", ["solo hoy", "solo en este live", "por tiempo limitado", "se acaba en", "antes de que termine"]),
    ("discount", ["descuento", "% de descuento", "rebaja", "precio especial", "baja de precio"]),
    ("cta_cart", ["carrito", "da clic", "dale clic", "picale", "pica en", "agregalo", "compralo ya", "link"]),
    ("free_shipping", ["envio gratis", "envio gratuito"]),
    ("bundle", ["2x1", "3x2", "paquete", "combo", "lleva dos"]),
    ("giveaway", ["sorteo", "regalamos", "dinamica", "ganador", "ganadora"]),
    ("price_reveal", ["cuesta", "el precio es", "a solo", "por solo", "en solo"]),
    ("product_demo", ["mira como", "te enseno", "les muestro", "asi se ve", "vamos a probar", "miren la textura"]),
    ("testimonial", ["yo lo uso", "a mi me funciono", "resena", "clientas dicen", "testimonio"]),
    ("qna", ["me preguntan", "pregunta de", "respondiendo", "buena pregunta"]),
    ("shoutout", ["bienvenida", "bienvenido", "hola a", "saludos a", "gracias por seguir"]),
    ("before_after", ["antes y despues", "el antes", "el despues"]),
]


def keyword_events(segments: list[dict]) -> list[dict]:
    """Detector simple sin IA: busca frases típicas de venta en vivo."""
    found = []
    last_by_kind = {}
    for seg in segments:
        t = norm(seg["text"])
        minute = int(seg["start"] // 60)
        for kind, phrases in KEYWORD_EVENTS:
            if any(norm(p) in t for p in phrases):
                if minute - last_by_kind.get(kind, -99) < 3:  # evitar duplicados seguidos
                    continue
                last_by_kind[kind] = minute
                found.append({"minute": minute, "kind": kind, "quote": seg["text"][:280], "description": ""})
    return found
