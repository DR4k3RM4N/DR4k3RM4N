import json
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from django import forms
from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import feature_required, org_required
from accounts.plans import (F_AI_REPORTS, F_EXPERIMENTS, F_HOST_SCORECARDS, F_PLAYBOOKS, F_SHARE_LINKS,
                            F_WHITE_LABEL)
from lives.models import Brand, LiveSession
from lives.services import data_coverage, lives_queryset, rows_for

from . import ai, engine
from .models import Experiment, Report
from .services import generate_report, run_analysis


def _brand_from_request(request):
    bid = request.GET.get("marca") or request.POST.get("marca")
    if bid:
        return get_object_or_404(Brand, pk=bid, organization=request.org)
    return None


def _parse_date(value, default):
    try:
        return date.fromisoformat(value) if value else default
    except ValueError:
        return default


def _range_from_request(request, default_days=30, coverage=None):
    """Rango pedido en la URL; si no hay, el periodo donde sí hay datos (no "los últimos días desde hoy")."""
    today = timezone.localdate()
    end_default = min(coverage["last"], today) if coverage else today
    span = max(default_days, 90) if coverage else default_days
    start_default = end_default - timedelta(days=span - 1)
    if coverage:
        start_default = max(start_default, coverage["first"])
    end = _parse_date(request.GET.get("hasta"), end_default)
    start = _parse_date(request.GET.get("desde"), start_default)
    if start > end:
        start, end = end, start
    return start, end


MONTH_NAMES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
               "octubre", "noviembre", "diciembre"]


def _calendar(coverage, start, end, months_max=4):
    """Meses con cada día marcado: con live, con tendencia de videos, sin datos; y si está en el rango elegido."""
    if not coverage:
        return None
    last = max(coverage["last"], end)
    first_month = max(coverage["first"].replace(day=1), (last.replace(day=1) - timedelta(days=31 * (months_max - 1))).replace(day=1))
    months, m = [], first_month
    while m <= last:
        nxt = (m + timedelta(days=32)).replace(day=1)
        weeks, week = [], [None] * m.weekday()
        d = m
        while d < nxt:
            live = coverage["live_days"].get(d)
            views = coverage["trend_days"].get(d)
            state = "live" if live else "trend" if views is not None else "none"
            week.append({"day": d.day, "date": d, "state": state, "in_range": start <= d <= end,
                         "title": d.strftime("%d/%m") + (f" · {live['n']} live(s), ${live['gmv']:,.0f}" if live else "")
                         + (f" · {views:,} vistas de videos" if views is not None else "")
                         + ("" if live or views is not None else " · sin datos")})
            if len(week) == 7:
                weeks.append(week)
                week = []
            d += timedelta(days=1)
        if week:
            weeks.append(week + [None] * (7 - len(week)))
        months.append({"name": f"{MONTH_NAMES[m.month - 1]} {m.year}", "weeks": weeks})
        m = nxt
    return {"months": months, "first": coverage["first"], "last": coverage["last"],
            "lives_days": len(coverage["live_days"]), "trend_days": len(coverage["trend_days"])}


def _with_bars(rows, key):
    """Añade `bar` (0-100): el ancho de la fila como proporción del valor más alto."""
    top = max((max(r[key], 0) for r in rows), default=0) or 1
    return [{**r, "bar": max(4, round(max(r[key], 0) / top * 100))} for r in rows]


def _video_finding(result):
    """Una frase sobre si los días con videos fuertes venden más en el live."""
    f = next((x for x in result["factors"] if x.key == "video_day"), None)
    if not f:
        return None
    strong = next((lv for lv in f.levels if lv.level.startswith("Día con")), None)
    if not strong:
        return None
    sure = {"alta": "", "media": " (confianza media)", "baja": " (todavía con pocos lives, confianza baja)"}[strong.confidence]
    if abs(strong.lift) < 0.05:
        return f"Los días con videos fuertes, tus lives venden casi igual que los demás días{sure}."
    word = "más" if strong.lift > 0 else "menos"
    return f"Los días con videos fuertes, tus lives venden {abs(strong.lift) * 100:.0f}% {word} por hora{sure}."


@org_required
def dashboard(request):
    org = request.org
    brand = _brand_from_request(request)
    coverage = data_coverage(org, brand)
    start, end = _range_from_request(request, 30, coverage)
    days = (end - start).days + 1
    prev_start, prev_end = start - timedelta(days=days), start - timedelta(days=1)

    current = run_analysis(org, brand, start, end)
    prev_rows = rows_for(lives_queryset(org, brand,
                                        timezone.make_aware(datetime.combine(prev_start, time.min)),
                                        timezone.make_aware(datetime.combine(prev_end + timedelta(days=1), time.min))))
    k = engine.compare_kpis(current["kpis"], engine.kpis(engine.build_frame(prev_rows)))

    # Serie diaria
    per_day = defaultdict(float)
    for r in current["rows"]:
        per_day[r["started_at"].date()] += r["gmv"]
    labels, values, video_views = [], [], []
    trend = coverage["trend_days"] if coverage else {}
    for i in range(days):
        d = start + timedelta(days=i)
        labels.append(d.strftime("%d/%m"))
        values.append(round(per_day.get(d, 0.0), 2))
        video_views.append(trend.get(d))

    # Patrones con 90 días de historia (más confiable que 30)
    history = run_analysis(org, brand, end - timedelta(days=89), end) if current["kpis"]["lives"] < 40 else current

    has_lives = LiveSession.objects.filter(organization=org).exists()
    top_lives = sorted(current["rows"], key=lambda r: r["gmv"], reverse=True)[:5]
    return render(request, "insights/dashboard.html", {
        "brand": brand, "brands": org.brands.filter(archived=False), "start": start, "end": end,
        "kpis": k,
        "calendar": _calendar(coverage, start, end),
        "video_finding": _video_finding(history),
        "chart": {"labels": labels, "values": values,
                  "videos": video_views if any(v is not None for v in video_views) else None,
                  "best": max(range(len(values)), key=values.__getitem__) if any(values) else None},
        "recommendations": history["recommendations"][:6],
        "best_slots": history["best_slots"][:3],
        "funnel": current["funnel"],
        "events": _with_bars(history["events"][:5], "median_uplift"),
        "top_lives": top_lives,
        "has_lives": has_lives,
        "has_brands": org.brands.exists(),
        "has_hosts": org.hosts.exists(),
        "untagged": LiveSession.objects.filter(organization=org, script_type="").count(),
    })


@org_required
def analysis(request):
    org = request.org
    brand = _brand_from_request(request)
    coverage = data_coverage(org, brand)
    start, end = _range_from_request(request, 90, coverage)
    metric = request.GET.get("metrica", "gmv_per_hour")
    if metric not in engine.METRICS:
        metric = "gmv_per_hour"
    result = run_analysis(org, brand, start, end, metric)
    heat = result["heatmap"]
    return render(request, "insights/analysis.html", {
        "brand": brand, "brands": org.brands.filter(archived=False), "start": start, "end": end,
        "metric": metric, "metrics": engine.METRICS, "result": result,
        "factors": result["factors"],
        "heat_json": json.dumps(heat) if heat else "",
        "calendar": _calendar(coverage, start, end),
    })


@org_required
@feature_required(F_HOST_SCORECARDS)
def host_ranking(request):
    org = request.org
    brand = _brand_from_request(request)
    start, end = _range_from_request(request, 90)
    result = run_analysis(org, brand, start, end)
    return render(request, "insights/hosts.html", {
        "brand": brand, "brands": org.brands.filter(archived=False), "start": start, "end": end,
        "cards": result["hosts"], "team": result["kpis"],
    })


@org_required
@feature_required(F_PLAYBOOKS)
def playbook(request):
    org = request.org
    brands = org.brands.filter(archived=False)
    brand = _brand_from_request(request) or brands.first()
    if brand is None:
        return redirect("lives:brand_list")
    end = timezone.localdate()
    start = end - timedelta(days=180)
    result = run_analysis(org, brand, start, end)
    pb = engine.playbook(result["df"], result["factors"], result["events"])
    top_lives = LiveSession.objects.filter(pk__in=pb["top_live_ids"]).select_related("host")[:6]
    calendar = engine.weekly_calendar(result["df"], datetime.combine(end + timedelta(days=1), time.min)) \
        if not result["df"].empty else []
    return render(request, "insights/playbook.html", {
        "brand": brand, "brands": brands, "pb": pb, "result": result, "top_lives": top_lives,
        "calendar": calendar,
    })


# --- Reportes ---------------------------------------------------------------

class ReportForm(forms.Form):
    period = forms.ChoiceField(label="Periodo", choices=Report.PERIOD_CHOICES)
    anchor = forms.DateField(label="Fecha dentro del periodo", widget=forms.DateInput(attrs={"type": "date"}))
    brand = forms.ModelChoiceField(label="Marca", queryset=Brand.objects.none(), required=False,
                                   empty_label="Todas las marcas")

    def __init__(self, *args, org=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["brand"].queryset = Brand.objects.filter(organization=org, archived=False)


@org_required
def report_list(request):
    org = request.org
    form = ReportForm(request.POST or None, org=org,
                      initial={"period": "weekly", "anchor": timezone.localdate() - timedelta(days=7)})
    if request.method == "POST" and request.membership.can_edit and form.is_valid():
        report = generate_report(org, form.cleaned_data["brand"], form.cleaned_data["period"],
                                 form.cleaned_data["anchor"], request.user)
        return redirect("insights:report_detail", pk=report.pk)
    reports = org.reports.select_related("brand")[:50]
    return render(request, "insights/report_list.html", {"form": form, "reports": reports})


def _report_context(report, request=None, public=False):
    org = report.organization
    return {
        "report": report, "d": report.data, "public": public,
        "white_label": org.has_feature(F_WHITE_LABEL),
        "report_org": org,
        "can_ai": org.has_feature(F_AI_REPORTS) and ai.ai_enabled() and not public,
        "can_share": org.has_feature(F_SHARE_LINKS) and not public,
        "share_url": request.build_absolute_uri(f"/r/{report.share_token}/") if request else "",
    }


@org_required
def report_detail(request, pk):
    report = get_object_or_404(Report.objects.select_related("brand"), pk=pk, organization=request.org)
    return render(request, "insights/report_detail.html", _report_context(report, request))


@org_required(edit=True)
@feature_required(F_AI_REPORTS)
@require_POST
def report_ai(request, pk):
    report = get_object_or_404(Report, pk=pk, organization=request.org)
    try:
        report.ai_summary = ai.summarize_report(report)
        report.save(update_fields=["ai_summary"])
        messages.success(request, "Resumen con IA listo.")
    except ai.AIUnavailable as exc:
        messages.error(request, str(exc))
    return redirect("insights:report_detail", pk=pk)


@org_required(edit=True)
@require_POST
def report_regenerate(request, pk):
    report = get_object_or_404(Report, pk=pk, organization=request.org)
    report = generate_report(request.org, report.brand, report.period, report.start, request.user)
    messages.success(request, "Reporte actualizado con los datos más recientes.")
    return redirect("insights:report_detail", pk=report.pk)


@org_required(edit=True)
@feature_required(F_SHARE_LINKS)
@require_POST
def report_share(request, pk):
    report = get_object_or_404(Report, pk=pk, organization=request.org)
    report.shared = not report.shared
    report.save(update_fields=["shared"])
    messages.success(request, "Link activado." if report.shared else "Link desactivado.")
    return redirect("insights:report_detail", pk=pk)


def report_public(request, token):
    report = get_object_or_404(Report.objects.select_related("brand", "organization"), share_token=token)
    if not report.shared or not report.organization.is_active:
        raise Http404
    return render(request, "insights/report_detail.html", _report_context(report, None, public=True))


# --- Experimentos ----------------------------------------------------------

class ExperimentForm(forms.ModelForm):
    class Meta:
        model = Experiment
        fields = ("brand", "name", "hypothesis", "variant_a", "variant_b", "metric", "target_lives_per_variant")
        widgets = {"hypothesis": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, org=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["brand"].queryset = Brand.objects.filter(organization=org, archived=False)


@org_required
@feature_required(F_EXPERIMENTS)
def experiment_list(request):
    org = request.org
    form = ExperimentForm(request.POST or None, org=org, initial={
        "name": request.GET.get("nombre", ""), "variant_a": request.GET.get("a", ""),
        "variant_b": request.GET.get("b", ""), "hypothesis": request.GET.get("hipotesis", ""),
    })
    if request.method == "POST" and request.membership.can_edit and form.is_valid():
        exp = form.save(commit=False)
        exp.organization = org
        exp.save()
        messages.success(request, "Prueba creada. Al registrar o editar cada live, márcalo como variante A o B.")
        return redirect("insights:experiment_detail", pk=exp.pk)
    return render(request, "insights/experiment_list.html", {
        "form": form, "experiments": org.experiments.select_related("brand"),
    })


@org_required
@feature_required(F_EXPERIMENTS)
def experiment_detail(request, pk):
    exp = get_object_or_404(Experiment.objects.select_related("brand"), pk=pk, organization=request.org)
    if request.method == "POST" and request.membership.can_edit:
        if "assign" in request.POST:
            live = get_object_or_404(LiveSession, pk=request.POST.get("live"), organization=request.org,
                                     brand=exp.brand)
            variant = request.POST.get("variant")
            if variant in ("A", "B"):
                live.experiment, live.experiment_variant = exp, variant
            else:
                live.experiment, live.experiment_variant = None, ""
            live.save(update_fields=["experiment", "experiment_variant"])
        elif "finish" in request.POST:
            exp.status = "done" if exp.status == "running" else "running"
            exp.save(update_fields=["status"])
        return redirect("insights:experiment_detail", pk=pk)
    lives = list(exp.lives.select_related("host").order_by("started_at"))

    def metric_of(live):
        return float(getattr(live, exp.metric))

    a = [metric_of(lv) for lv in lives if lv.experiment_variant == "A"]
    b = [metric_of(lv) for lv in lives if lv.experiment_variant == "B"]
    evaluation = engine.evaluate_experiment(a, b, exp.target_lives_per_variant)
    candidates = (LiveSession.objects.filter(organization=request.org, brand=exp.brand, experiment__isnull=True,
                                             started_at__gte=exp.created_at - timedelta(days=3))
                  .order_by("-started_at")[:20])
    return render(request, "insights/experiment_detail.html", {
        "exp": exp, "lives": lives, "ev": evaluation, "candidates": candidates,
        "metric_label": dict(Experiment.METRIC_CHOICES)[exp.metric],
    })
