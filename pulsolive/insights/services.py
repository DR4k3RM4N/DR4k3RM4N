"""Une la base de datos con el motor de análisis."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from django.utils import timezone

from lives.models import LiveSession
from lives.services import lives_queryset, minutes_and_events, rows_for

from . import engine
from .models import Report


def aware(d: date) -> datetime:
    return timezone.make_aware(datetime.combine(d, time.min), timezone.get_current_timezone())


def period_range(period: str, anchor: date) -> tuple[date, date]:
    """Rango [inicio, fin] inclusivo para el periodo que contiene `anchor`."""
    if period == "daily":
        return anchor, anchor
    if period == "weekly":
        start = anchor - timedelta(days=anchor.weekday())
        return start, start + timedelta(days=6)
    start = anchor.replace(day=1)
    nxt = (start + timedelta(days=32)).replace(day=1)
    return start, nxt - timedelta(days=1)


def previous_range(period: str, start: date) -> tuple[date, date]:
    return period_range(period, start - timedelta(days=1))


def event_effects_for(lives) -> tuple[list[dict], dict]:
    per_live = []
    per_live_moments = {}
    for live in lives:
        minutes, events = minutes_and_events(live)
        if not minutes:
            continue
        m = engine.moments_for_live(minutes, events)
        per_live.append(m["event_impacts"])
        per_live_moments[live.id] = m
    return engine.event_effects(per_live), per_live_moments


def run_analysis(org, brand=None, start: date | None = None, end: date | None = None,
                 metric: str = "gmv_per_hour") -> dict:
    qs = lives_queryset(org, brand, aware(start) if start else None,
                        aware(end + timedelta(days=1)) if end else None)
    rows = rows_for(qs)
    df = engine.build_frame(rows)
    factors = engine.factor_analysis(df, metric) if not df.empty else []
    lives = list(qs.prefetch_related("minutes", "events"))
    events, _ = event_effects_for(lives)
    hosts = engine.host_scorecards(df)
    recs = engine.recommendations(df, factors, events, hosts, metric)
    return {
        "df": df,
        "rows": rows,
        "kpis": engine.kpis(df),
        "factors": factors,
        "events": events,
        "hosts": hosts,
        "recommendations": recs,
        "heatmap": engine.heatmap(df, metric) if not df.empty else None,
        "funnel": engine.funnel(df) if not df.empty else None,
        "best_slots": engine.best_slots(df, metric),
        "metric": metric,
        "metric_label": engine.METRICS.get(metric, metric),
    }


def _top_lives(rows, n=5):
    ranked = sorted(rows, key=lambda r: r["gmv"], reverse=True)[:n]
    return [{"id": r["id"], "brand": r["brand"], "host": r["host"], "started_at": r["started_at"].isoformat(),
             "gmv": r["gmv"], "orders": r["orders"], "duration_minutes": r["duration_minutes"],
             "gmv_per_hour": r["gmv"] / max(r["duration_minutes"], 1) * 60} for r in ranked]


def build_report_data(org, brand, period: str, start: date, end: date) -> dict:
    current = run_analysis(org, brand, start, end)
    prev_start, prev_end = previous_range(period, start)
    prev_rows = rows_for(lives_queryset(org, brand, aware(prev_start), aware(prev_end + timedelta(days=1))))
    prev_kpis = engine.kpis(engine.build_frame(prev_rows))
    # Para los patrones usamos más historia que solo el periodo (más confiable)
    history_start = start - timedelta(days=90)
    history = run_analysis(org, brand, history_start, end)
    data = {
        "period": period,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "previous": {"start": prev_start.isoformat(), "end": prev_end.isoformat()},
        "kpis": engine.compare_kpis(current["kpis"], prev_kpis),
        "top_lives": _top_lives(current["rows"]),
        "period_factors": [f.as_dict() for f in current["factors"][:6]],
        "history_factors": [f.as_dict() for f in history["factors"][:8]],
        "history_lives": int(history["kpis"]["lives"]),
        "events": history["events"][:8],
        "hosts": [{k: v for k, v in h.items()} for h in current["hosts"]],
        "recommendations": [r.as_dict() for r in history["recommendations"][:8]],
        "best_slots": history["best_slots"],
        "calendar": engine.weekly_calendar(history["df"], datetime.combine(end + timedelta(days=1), time.min))
        if not history["df"].empty else [],
    }
    if brand and brand.monthly_gmv_goal and period == "monthly":
        goal = float(brand.monthly_gmv_goal)
        data["goal"] = {"target": goal, "progress": current["kpis"]["gmv"] / goal if goal else None}
    return data


def generate_report(org, brand, period: str, anchor: date, user=None) -> Report:
    start, end = period_range(period, anchor)
    data = build_report_data(org, brand, period, start, end)
    report, _ = Report.objects.update_or_create(
        organization=org, brand=brand, period=period, start=start,
        defaults={"end": end, "data": data, "created_by": user, "ai_summary": {}},
    )
    return report


def live_detail_analysis(live: LiveSession) -> dict:
    minutes, events = minutes_and_events(live)
    moments = engine.moments_for_live(minutes, events) if minutes else None
    # Comparación contra lives similares de la misma marca
    peers = rows_for(lives_queryset(live.organization, live.brand).exclude(pk=live.pk)[:200])
    peer_df = engine.build_frame(peers)
    comparison = {}
    if not peer_df.empty:
        for key in ("gmv_per_hour", "conversion_rate", "avg_watch_seconds", "aov"):
            avg = float(peer_df[key].mean()) if key in peer_df else 0
            mine = getattr(live, key, None)
            mine = float(mine) if mine is not None else 0
            comparison[key] = {"value": mine, "avg": avg, "delta": (mine / avg - 1) if avg else None}
        rank = int((peer_df["gmv_per_hour"] > live.gmv_per_hour).sum()) + 1
        comparison["rank"] = {"position": rank, "of": len(peer_df) + 1}
    from lives.services import live_to_row

    funnel = engine.live_funnel(live_to_row(live), peer_df) if live.impressions else None
    weakest = None
    if funnel:
        gaps = [f for f in funnel if f["delta"] is not None]
        if gaps:
            w = min(gaps, key=lambda f: f["delta"])
            weakest = w if w["delta"] < -0.15 else None
    return {"minutes": minutes, "events": events, "moments": moments, "comparison": comparison,
            "funnel": funnel, "funnel_weakest": weakest}
