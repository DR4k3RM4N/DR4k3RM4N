import csv
import json

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import feature_required, org_required
from accounts.plans import F_TRANSCRIPTS
from insights import ai
from insights.services import live_detail_analysis

from .forms import (BrandForm, HostForm, ImportForm, LiveEventForm, LiveSessionForm, MinuteImportForm,
                    QuickTagForm, TranscriptForm)
from .importers import keyword_events, parse_transcript
from .models import EVENT_LABELS, Brand, Host, LiveEvent, LiveSession, Transcript
from .services import import_minutes_file, import_sessions_file


# --- Marcas -----------------------------------------------------------------

@org_required
def brand_list(request):
    org = request.org
    form = BrandForm(request.POST or None)
    if request.method == "POST":
        if not request.membership.can_edit:
            messages.error(request, "Tu rol es de solo lectura.")
        elif not org.can_add_brand():
            messages.error(request, f"Tu plan {org.plan.name} permite {org.plan.max_brands} marca(s). Sube de plan para agregar más.")
        elif form.is_valid():
            brand = form.save(commit=False)
            brand.organization = org
            brand.save()
            messages.success(request, f"Marca «{brand.name}» creada. Ahora importa sus lives.")
            return redirect("lives:import")
    brands = (org.brands.filter(archived=False)
              .annotate(n_lives=Count("lives"), total_gmv=Sum("lives__gmv")).order_by("name"))
    return render(request, "lives/brand_list.html", {"brands": brands, "form": form,
                                                     "has_hosts": org.hosts.exists()})


@org_required(edit=True)
def brand_edit(request, pk):
    brand = get_object_or_404(Brand, pk=pk, organization=request.org)
    form = BrandForm(request.POST or None, instance=brand)
    if request.method == "POST":
        if "archive" in request.POST:
            brand.archived = True
            brand.save()
            messages.success(request, "Marca archivada.")
            return redirect("lives:brand_list")
        if form.is_valid():
            form.save()
            messages.success(request, "Guardado.")
            return redirect("lives:brand_list")
    return render(request, "lives/form_page.html", {"form": form, "title": f"Editar {brand.name}",
                                                    "archive": True})


# --- Hosts ------------------------------------------------------------------

@org_required
def host_list(request):
    org = request.org
    form = HostForm(request.POST or None)
    if request.method == "POST" and request.membership.can_edit and form.is_valid():
        host = form.save(commit=False)
        host.organization = org
        host.save()
        messages.success(request, f"Host «{host.name}» agregado.")
        return redirect("lives:host_list")
    hosts = org.hosts.annotate(n_lives=Count("lives"), total_gmv=Sum("lives__gmv")).order_by("-active", "name")
    return render(request, "lives/host_list.html", {"hosts": hosts, "form": form})


@org_required(edit=True)
def host_edit(request, pk):
    host = get_object_or_404(Host, pk=pk, organization=request.org)
    form = HostForm(request.POST or None, instance=host)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Guardado.")
        return redirect("lives:host_list")
    return render(request, "lives/form_page.html", {"form": form, "title": f"Editar {host.name}"})


# --- Lives ------------------------------------------------------------------

@org_required
def live_list(request):
    org = request.org
    qs = LiveSession.objects.filter(organization=org).select_related("brand", "host")
    brand_id = request.GET.get("marca")
    host_id = request.GET.get("host")
    q = request.GET.get("q", "").strip()
    if brand_id:
        qs = qs.filter(brand_id=brand_id)
    if host_id:
        qs = qs.filter(host_id=host_id)
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(main_product__icontains=q) | Q(notes__icontains=q))
    if request.GET.get("sin_etiquetar"):
        qs = qs.filter(Q(host__isnull=True) | Q(script_type=""))
    order = request.GET.get("orden", "-started_at")
    if order in ("-started_at", "started_at", "-gmv", "gmv", "-orders"):
        qs = qs.order_by(order)
    page = Paginator(qs, 30).get_page(request.GET.get("p"))
    untagged = LiveSession.objects.filter(organization=org).filter(Q(host__isnull=True) | Q(script_type="")).count()
    return render(request, "lives/live_list.html", {
        "page": page, "brands": org.brands.filter(archived=False), "hosts": org.hosts.all(),
        "untagged": untagged,
    })


@org_required(edit=True)
def live_create(request):
    form = LiveSessionForm(request.POST or None, org=request.org,
                           initial={"started_at": timezone.localtime().replace(minute=0, second=0, microsecond=0)})
    if request.method == "POST" and form.is_valid():
        live = form.save()
        messages.success(request, "Live guardado.")
        return redirect("lives:live_detail", pk=live.pk)
    return render(request, "lives/form_page.html", {"form": form, "title": "Registrar live"})


@org_required(edit=True)
def live_edit(request, pk):
    live = get_object_or_404(LiveSession, pk=pk, organization=request.org)
    if request.method != "POST":
        live.started_at = timezone.localtime(live.started_at)
    form = LiveSessionForm(request.POST or None, instance=live, org=request.org)
    if request.method == "POST":
        if "delete" in request.POST:
            live.delete()
            messages.success(request, "Live eliminado.")
            return redirect("lives:live_list")
        if form.is_valid():
            form.save()
            messages.success(request, "Guardado.")
            return redirect("lives:live_detail", pk=live.pk)
    return render(request, "lives/form_page.html", {"form": form, "title": "Editar live", "delete": True})


@org_required
def live_detail(request, pk):
    live = get_object_or_404(LiveSession.objects.select_related("brand", "host"), pk=pk, organization=request.org)
    analysis = live_detail_analysis(live)
    transcript = getattr(live, "transcript", None)
    chart = None
    if analysis["minutes"]:
        chart = {
            "labels": [m["minute"] for m in analysis["minutes"]],
            "orders": [m["orders"] for m in analysis["minutes"]],
            "viewers": [m["viewers"] for m in analysis["minutes"]],
            "events": [{"minute": e["minute"], "label": e["label"]} for e in analysis["events"]],
        }
    return render(request, "lives/live_detail.html", {
        "live": live,
        "analysis": analysis,
        "chart_json": json.dumps(chart) if chart else "",
        "event_form": LiveEventForm(),
        "minute_form": MinuteImportForm(),
        "transcript_form": TranscriptForm(),
        "transcript": transcript,
        "can_transcripts": request.org.has_feature(F_TRANSCRIPTS),
        "ai_enabled": ai.ai_enabled(),
    })


@org_required(edit=True)
@require_POST
def event_add(request, pk):
    live = get_object_or_404(LiveSession, pk=pk, organization=request.org)
    form = LiveEventForm(request.POST)
    if form.is_valid():
        ev = form.save(commit=False)
        ev.live = live
        ev.source = "manual"
        ev.save()
        messages.success(request, "Momento agregado.")
    else:
        messages.error(request, "Revisa el minuto y el tipo de momento.")
    return redirect("lives:live_detail", pk=pk)


@org_required(edit=True)
@require_POST
def event_delete(request, pk, event_id):
    ev = get_object_or_404(LiveEvent, pk=event_id, live_id=pk, live__organization=request.org)
    ev.delete()
    return redirect("lives:live_detail", pk=pk)


@org_required(edit=True)
@require_POST
def minutes_upload(request, pk):
    live = get_object_or_404(LiveSession, pk=pk, organization=request.org)
    form = MinuteImportForm(request.POST, request.FILES)
    if form.is_valid():
        try:
            batch, _ = import_minutes_file(live, form.cleaned_data["file"])
        except Exception as exc:  # noqa: BLE001 — archivo corrupto / formato raro
            messages.error(request, f"No pudimos leer el archivo: {exc}")
            return redirect("lives:live_detail", pk=pk)
        if batch.created:
            messages.success(request, f"{batch.created} minutos importados.")
        for e in batch.errors[:5]:
            messages.warning(request, e)
    return redirect("lives:live_detail", pk=pk)


@org_required(edit=True)
@feature_required(F_TRANSCRIPTS)
@require_POST
def transcript_upload(request, pk):
    live = get_object_or_404(LiveSession, pk=pk, organization=request.org)
    form = TranscriptForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, "Sube un archivo o pega el texto de la transcripción.")
        return redirect("lives:live_detail", pk=pk)
    if form.cleaned_data.get("file"):
        raw = form.cleaned_data["file"].read()
        text = raw.decode("utf-8-sig", errors="replace")
    else:
        text = form.cleaned_data["text"]
    segments = parse_transcript(text)
    Transcript.objects.update_or_create(live=live, defaults={"raw_text": text, "segments": segments,
                                                             "analysis": {}, "summary": "", "analyzed_at": None})
    messages.success(request, f"Transcripción guardada ({len(segments)} fragmentos). Ahora analízala.")
    return redirect("lives:live_detail", pk=pk)


@org_required(edit=True)
@feature_required(F_TRANSCRIPTS)
@require_POST
def transcript_analyze(request, pk):
    live = get_object_or_404(LiveSession.objects.select_related("brand", "host"), pk=pk, organization=request.org)
    transcript = get_object_or_404(Transcript, live=live)
    use_ai = request.POST.get("mode") != "keywords" and ai.ai_enabled()
    if use_ai:
        minutes = [{"minute": m.minute, "orders": m.orders, "viewers": m.viewers} for m in live.minutes.all()]
        try:
            result = ai.analyze_transcript(live, transcript.segments, minutes)
        except ai.AIUnavailable as exc:
            messages.error(request, str(exc))
            return redirect("lives:live_detail", pk=pk)
        events, source = result["events"], "ai"
        transcript.summary = result.get("summary", "")
        transcript.analysis = result
    else:
        events, source = keyword_events(transcript.segments), "keywords"
        transcript.analysis = {"mode": "keywords"}
    live.events.filter(source__in=("ai", "keywords")).delete()
    max_minute = max(live.duration_minutes, 1) + 5
    LiveEvent.objects.bulk_create([
        LiveEvent(live=live, minute=max(0, min(int(e["minute"]), max_minute)), kind=e["kind"],
                  description=(e.get("description") or "")[:300], quote=e.get("quote") or "", source=source)
        for e in events if e.get("kind") in EVENT_LABELS
    ])
    transcript.analyzed_at = timezone.now()
    transcript.save()
    messages.success(request, f"Se detectaron {len(events)} momentos clave"
                              + (" con IA." if use_ai else " por palabras clave."))
    return redirect("lives:live_detail", pk=pk)


@org_required(edit=True)
def quick_tag(request):
    """Etiqueta en fila los lives a los que les falta información."""
    org = request.org
    pending = (LiveSession.objects.filter(organization=org)
               .filter(Q(host__isnull=True) | Q(script_type="")).select_related("brand").order_by("-started_at"))
    live = pending.first()
    if live is None:
        messages.success(request, "¡Todos tus lives están etiquetados!")
        return redirect("insights:analysis")
    form = QuickTagForm(request.POST or None, instance=live, org=org)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("lives:quick_tag")
    return render(request, "lives/quick_tag.html", {"live": live, "form": form, "remaining": pending.count()})


# --- Importación ----------------------------------------------------------------

@org_required(edit=True)
def import_view(request):
    org = request.org
    if not org.brands.filter(archived=False).exists():
        messages.info(request, "Primero crea la marca a la que pertenecen los lives.")
        return redirect("lives:brand_list")
    form = ImportForm(request.POST or None, request.FILES or None, org=org,
                      initial={"brand": request.GET.get("marca")})
    if request.method == "POST" and form.is_valid():
        try:
            batch, parsed = import_sessions_file(org, form.cleaned_data["brand"], form.cleaned_data["file"],
                                                 form.cleaned_data["default_host"])
        except Exception as exc:  # noqa: BLE001
            messages.error(request, f"No pudimos leer el archivo: {exc}")
            return redirect("lives:import")
        if batch.created or batch.updated:
            messages.success(request, f"Importación lista: {batch.created} lives nuevos, {batch.updated} actualizados.")
        for e in batch.errors[:8]:
            messages.warning(request, e)
        return render(request, "lives/import_result.html", {"batch": batch, "parsed": parsed})
    return render(request, "lives/import.html", {"form": form, "history": org.imports.select_related("brand")[:10]})


TEMPLATE_HEADERS = ["ID del live", "Título", "Hora de inicio", "Duración", "GMV", "Pedidos", "Piezas vendidas",
                    "Espectadores", "Pico de espectadores", "Tiempo promedio de visualización",
                    "Nuevos seguidores", "Likes", "Comentarios", "Compartidos", "Clics en producto",
                    "Host", "Promoción", "Guion", "Producto principal"]


def import_template(request):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="plantilla_lives_pulsolive.csv"'
    response.write("﻿")
    w = csv.writer(response)
    w.writerow(TEMPLATE_HEADERS)
    w.writerow(["7301", "Live jueves noche", "2026-10-29 20:00", "2h 0m", "18450.50", "142", "171", "6230",
                "410", "1m 25s", "120", "15400", "890", "45", "1320", "Ana", "flash sale", "demo",
                "Sérum vitamina C"])
    return response


def minute_template(request):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="plantilla_minuto_a_minuto.csv"'
    response.write("﻿")
    w = csv.writer(response)
    w.writerow(["Minuto", "Espectadores", "Pedidos", "GMV", "Comentarios"])
    for m, (v, o) in enumerate([(120, 0), (180, 1), (240, 2), (260, 6), (250, 3)]):
        w.writerow([m, v, o, o * 129, v // 10])
    return response
