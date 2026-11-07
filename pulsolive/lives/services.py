from django.db import transaction
from django.utils import timezone

from .importers import is_trend_table, parse_minutes, parse_sessions, parse_trends, read_table
from .models import EVENT_LABELS, AccountDay, Host, ImportBatch, LiveMinute, LiveSession


def live_to_row(live: LiveSession) -> dict:
    """Convierte un live a dict plano para el motor de análisis."""
    host = live.host
    return {
        "id": live.id,
        "brand": live.brand.name if live.brand_id else "",
        "started_at": timezone.localtime(live.started_at).replace(tzinfo=None),
        "duration_minutes": live.duration_minutes,
        "gmv": float(live.gmv),
        "orders": live.orders,
        "units_sold": live.units_sold,
        "viewers": live.viewers,
        "peak_viewers": live.peak_viewers,
        "avg_watch_seconds": live.avg_watch_seconds,
        "new_followers": live.new_followers,
        "likes": live.likes,
        "comments": live.comments,
        "shares": live.shares,
        "product_clicks": live.product_clicks,
        "impressions": live.impressions,
        "product_impressions": live.product_impressions,
        "customers": live.customers,
        "video_views_day": getattr(live, "_video_views_day", 0),
        "host": host.name if host else "",
        "host_gender": host.get_gender_display() if host and host.gender != "unspecified" else "",
        "host_style": host.get_style_display() if host and host.style else "",
        "host_experience": host.get_experience_display() if host and host.experience else "",
        "promo_type": "" if live.promo_type == "unknown" else live.get_promo_type_display(),
        "script_type": live.get_script_type_display() if live.script_type else "",
        "format": live.get_format_display(),
        "setting": live.get_setting_display() if live.setting else "",
        "product_category": live.product_category,
        "tags": [t.name for t in live.tags.all()],
        "has_minutes": getattr(live, "_has_minutes", False),
    }


def lives_queryset(org, brand=None, start=None, end=None):
    qs = (LiveSession.objects.filter(organization=org)
          .select_related("host", "brand").prefetch_related("tags"))
    if brand is not None:
        qs = qs.filter(brand=brand)
    if start is not None:
        qs = qs.filter(started_at__gte=start)
    if end is not None:
        qs = qs.filter(started_at__lt=end)
    return qs


def rows_for(qs):
    lives = list(qs)
    with_minutes = set(LiveMinute.objects.filter(live__in=lives).values_list("live_id", flat=True).distinct())
    days = {}
    if lives:
        dates = [timezone.localtime(l.started_at).date() for l in lives]
        for d in AccountDay.objects.filter(brand_id__in={l.brand_id for l in lives},
                                           date__gte=min(dates), date__lte=max(dates)):
            days[(d.brand_id, d.date)] = d.video_views
    rows = []
    for live in lives:
        live._has_minutes = live.id in with_minutes
        live._video_views_day = days.get((live.brand_id, timezone.localtime(live.started_at).date()), 0)
        rows.append(live_to_row(live))
    return rows


def minutes_and_events(live: LiveSession):
    minutes = [{"minute": m.minute, "orders": m.orders, "viewers": m.viewers, "gmv": float(m.gmv)}
               for m in live.minutes.all()]
    events = [{"minute": e.minute, "kind": e.kind, "label": EVENT_LABELS.get(e.kind, e.kind),
               "description": e.description, "quote": e.quote, "source": e.source}
              for e in live.events.all()]
    return minutes, events


def _get_or_create_host(org, name, cache):
    if not name:
        return None
    key = name.lower()
    if key not in cache:
        host = Host.objects.filter(organization=org, name__iexact=name).first()
        cache[key] = host or Host.objects.create(organization=org, name=name)
    return cache[key]


@transaction.atomic
def import_trends_table(org, brand, df, filename):
    parsed = parse_trends(df)
    batch = ImportBatch(organization=org, brand=brand, kind="trends", filename=filename[:200])
    for row in parsed.rows:
        _, created = AccountDay.objects.update_or_create(
            organization=org, brand=brand, date=row["date"],
            defaults={k: row[k] for k in ("video_views", "profile_views", "likes", "comments", "shares")})
        if created:
            batch.created += 1
        else:
            batch.updated += 1
    batch.skipped = len(parsed.errors)
    batch.errors = parsed.errors[:50]
    batch.save()
    return batch, parsed


@transaction.atomic
def import_sessions_file(org, brand, uploaded_file, default_host=None):
    """Importa el archivo de lives, o el de tendencias diarias si eso es lo que se subió."""
    df = read_table(uploaded_file)
    if is_trend_table(df):
        return import_trends_table(org, brand, df, uploaded_file.name)
    parsed = parse_sessions(df)
    batch = ImportBatch(organization=org, brand=brand, kind="sessions", filename=uploaded_file.name[:200])
    if parsed.missing_required:
        batch.errors = [f"No encontramos la columna de {m}. Columnas del archivo: {', '.join(df.columns)}"
                        for m in parsed.missing_required]
        batch.save()
        return batch, parsed
    hosts = {}
    for row in parsed.rows:
        data = dict(row.data)
        host = _get_or_create_host(org, row.host_name, hosts) or default_host
        existing = None
        if data["external_id"]:
            existing = LiveSession.objects.filter(organization=org, brand=brand, external_id=data["external_id"]).first()
        if existing is None:
            existing = LiveSession.objects.filter(organization=org, brand=brand, started_at=data["started_at"]).first()
        if existing:
            for k, v in data.items():
                # No pisar el etiquetado manual con valores vacíos del archivo
                if v in ("", None) and k in ("title", "main_product", "product_category", "notes"):
                    continue
                setattr(existing, k, v)
            if host and not existing.host_id:
                existing.host = host
            existing.save()
            batch.updated += 1
        else:
            LiveSession.objects.create(organization=org, brand=brand, host=host, source="csv", **data)
            batch.created += 1
    batch.skipped = len(parsed.errors)
    batch.errors = parsed.errors[:50]
    batch.save()
    return batch, parsed


@transaction.atomic
def import_minutes_file(live: LiveSession, uploaded_file):
    df = read_table(uploaded_file)
    parsed = parse_minutes(df, live_start=live.started_at)
    batch = ImportBatch(organization=live.organization, brand=live.brand, kind="minutes",
                        filename=uploaded_file.name[:200])
    if parsed.missing_required:
        batch.errors = [f"No encontramos la columna de {m}." for m in parsed.missing_required]
        batch.save()
        return batch, parsed
    live.minutes.all().delete()
    seen = set()
    objs = []
    for r in parsed.rows:
        if r["minute"] in seen:
            continue
        seen.add(r["minute"])
        objs.append(LiveMinute(live=live, **r))
    LiveMinute.objects.bulk_create(objs)
    batch.created = len(objs)
    batch.skipped = len(parsed.errors)
    batch.errors = parsed.errors[:50]
    batch.save()
    return batch, parsed


def data_coverage(org, brand=None):
    """Días con lives y con tendencia de videos, para el calendario de datos y el rango por defecto."""
    from collections import defaultdict

    lives = LiveSession.objects.filter(organization=org)
    days = AccountDay.objects.filter(organization=org)
    if brand is not None:
        lives, days = lives.filter(brand=brand), days.filter(brand=brand)
    live_days = defaultdict(lambda: {"n": 0, "gmv": 0.0})
    for started, gmv in lives.values_list("started_at", "gmv"):
        d = timezone.localtime(started).date()
        live_days[d]["n"] += 1
        live_days[d]["gmv"] += float(gmv)
    trend_days = {d: v for d, v in days.values_list("date", "video_views")}
    all_days = set(live_days) | set(trend_days)
    if not all_days:
        return None
    return {"live_days": dict(live_days), "trend_days": trend_days,
            "first": min(all_days), "last": max(all_days),
            "first_live": min(live_days) if live_days else None, "last_live": max(live_days) if live_days else None}
