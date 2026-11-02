import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import billing
from .decorators import org_required
from .forms import (AcceptInvitationForm, InvitationForm, OnboardingForm, OrganizationSettingsForm,
                    SignupForm)
from .models import Invitation, Membership, Organization
from .plans import PLANS, TRIAL_DAYS

log = logging.getLogger(__name__)


# Momentos de un live de ejemplo (los mismos patrones que la cuenta demo) para el tablero de la portada.
LANDING_MOMENTS = [
    ("Demostró el producto", 3, "0.7", "1.8", "+170%", "up", "Miren cómo se absorbe en segundos.", "La demo al abrir el live engancha a quien acaba de entrar."),
    ("Pidió dar clic al carrito", 12, "2.0", "1.6", "−20%", "down", "Den clic en el carrito naranja.", "Pedir el clic antes de mostrar el precio no funcionó."),
    ("Reveló el precio", 16, "1.0", "1.6", "+60%", "up", "Normal 389, hoy a solo 289.", "Precio ancla y precio del live, juntos."),
    ("Lanzó oferta relámpago", 20, "1.2", "2.6", "+117%", "up", "Solo por los próximos 10 minutos.", "El pico más alto del live: repítelo cada 15 a 20 minutos."),
    ("Escasez: últimas piezas", 51, "0.6", "1.4", "+133%", "up", "Quedan solo 40 piezas.", "Funciona cuando la cifra es real y se actualiza."),
    ("Cambió de producto", 85, "0.4", "0.0", "−100%", "down", "Vamos a cambiar al protector solar.", "Se fue un tercio de la audiencia; haz la transición más corta."),
    ("Respondió preguntas", 95, "0.4", "1.6", "+300%", "up", "¿Sirve para piel grasa? Sí, es ligero.", "Resolver la objeción en voz alta destrabó pedidos."),
    ("Testimonio de clienta", 158, "1.8", "1.0", "−44%", "down", "A mí me funcionó para las manchas.", "Muy largo para este momento del live."),
    ("Saludó por nombre", 193, "1.6", "1.0", "−38%", "down", "Saludos a Mariana y a Coco.", "Retiene, pero no vende: úsalo entre ofertas."),
]

LANDING_FAQS = [
    ("¿De dónde salen los datos?", "Del archivo que exportas de TikTok Shop Seller Center o LIVE Center, en CSV o Excel, en español o en inglés. Para el minuto a minuto subes la serie de pedidos y espectadores; para los momentos, la transcripción o los subtítulos del live. El plan Enterprise se conecta directo a la API de TikTok Shop."),
    ("¿Cuántos lives necesito para ver resultados?", "Con 10 lives ya ves tendencias; con 20 a 30 lives etiquetados por marca, los patrones son confiables. PulsoLive te dice el nivel de confianza de cada conclusión y te avisa cuando todavía hay pocos datos."),
    ("¿El análisis dice qué causó las ventas?", "Muestra qué se asocia con vender más y separa cada factor de los demás, por ejemplo al host del horario en que le toca transmitir. Para confirmar una causa, crea una prueba A/B y PulsoLive te dice cuál opción ganó."),
    ("¿Puedo compartir los reportes con mis marcas?", "Sí. En el plan Agencia los reportes llevan tu logo y tus colores, se imprimen en PDF y cada uno tiene un link para compartir. También puedes invitar a la marca con acceso de solo lectura."),
    ("¿Qué pasa al terminar la prueba?", "Eliges un plan o tu cuenta queda en pausa con tus datos guardados. La prueba no pide tarjeta."),
]


def landing(request):
    if request.user.is_authenticated and request.org:
        return redirect("insights:dashboard")
    moments = [dict(zip(("label", "minute", "before", "after", "change", "state", "quote", "note"), m))
               for m in LANDING_MOMENTS]
    # Intensidad del mapa de calor de ejemplo (7 días × 24 h): más fuerte en la noche y en jueves y viernes.
    heat_cells = []
    for day in range(7):
        for hour in range(24):
            v = {9: .35, 11: .45, 13: .5, 16: .6, 18: .7, 20: 1, 21: .9, 23: .55}.get(hour, 0)
            v *= {3: 1, 4: 1, 6: .9}.get(day, .75)
            heat_cells.append(f"{max(v, .08):.2f}")
    palette = ["#e11d74", "#131416", "#b0145a", "#131416", "#e11d74", "#45474a", "#e11d74", "#131416", "#b0145a"]
    heights = [100, 72, 88, 64, 94, 80, 68, 92, 76]
    letters = list(zip("PULSOLIVE", heights, palette))
    return render(request, "accounts/landing.html", {
        "plans": PLANS, "priced": [PLANS[c] for c in ("creator", "pro", "agency")], "trial_days": TRIAL_DAYS,
        "moments": moments, "heat_cells": heat_cells, "faqs": LANDING_FAQS, "letters": letters,
    })




PRICING_FAQS = [
    ("¿Qué es un análisis con IA?", "Cada resumen ejecutivo de un reporte o análisis de transcripción hecho con IA. El análisis estadístico, las recomendaciones automáticas y los reportes son ilimitados en todos los planes."),
    ("¿Puedo cambiar de plan?", "Sí, cuando quieras, desde Plan y pagos. El cambio se prorratea en tu siguiente cobro."),
    ("¿Cobran en pesos?", "Sí. Los precios son mensuales, en pesos mexicanos y con IVA incluido. Si pagas el año, son 10 meses: 2 meses gratis."),
]


def pricing(request):
    return render(request, "accounts/pricing.html", {
        "plans": PLANS, "priced": [PLANS[c] for c in ("creator", "pro", "agency")], "trial_days": TRIAL_DAYS,
        "faqs": PRICING_FAQS + LANDING_FAQS[:1] + LANDING_FAQS[-1:],
    })


@transaction.atomic
def signup(request):
    if request.user.is_authenticated:
        return redirect("insights:dashboard")
    form = SignupForm(request.POST or None, initial={"org_kind": request.GET.get("tipo", "agency")})
    if request.method == "POST" and form.is_valid():
        user = form.save()
        org = Organization.objects.create(name=form.cleaned_data["org_name"], kind=form.cleaned_data["org_kind"])
        Membership.objects.create(user=user, organization=org, role=Membership.ROLE_OWNER)
        login(request, user)
        messages.success(request, f"¡Listo! Tienes {TRIAL_DAYS} días de prueba con todo el plan Pro.")
        return redirect("lives:brand_list")
    return render(request, "accounts/signup.html", {"form": form, "trial_days": TRIAL_DAYS})


@login_required
def onboarding(request):
    if request.org:
        return redirect("insights:dashboard")
    form = OnboardingForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        org = form.save()
        Membership.objects.create(user=request.user, organization=org, role=Membership.ROLE_OWNER)
        return redirect("lives:brand_list")
    return render(request, "accounts/onboarding.html", {"form": form})


@login_required
def switch_org(request, org_id):
    membership = get_object_or_404(Membership, user=request.user, organization_id=org_id)
    request.session["org_id"] = membership.organization_id
    return redirect("insights:dashboard")


@org_required(manage=True, active=False)
def org_settings(request):
    form = OrganizationSettingsForm(request.POST or None, request.FILES or None, instance=request.org)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Guardado.")
        return redirect("accounts:settings")
    return render(request, "accounts/settings.html", {"form": form})


@org_required(active=False)
def team(request):
    org = request.org
    form = InvitationForm(request.POST or None)
    if request.method == "POST":
        if not request.membership.can_manage:
            messages.error(request, "Solo administradores pueden invitar.")
        elif not org.can_add_user():
            messages.error(request, f"Tu plan {org.plan.name} permite {org.plan.max_users} usuario(s). Sube de plan para invitar más.")
        elif form.is_valid():
            inv = form.save(commit=False)
            inv.organization = org
            inv.invited_by = request.user
            inv.save()
            link = request.build_absolute_uri(reverse("accounts:accept_invitation", args=[inv.token]))
            messages.success(request, f"Invitación creada. Comparte este link con {inv.email}: {link}")
            return redirect("accounts:team")
    return render(request, "accounts/team.html", {
        "form": form,
        "members": org.memberships.select_related("user").order_by("created_at"),
        "invitations": org.invitations.filter(accepted_at__isnull=True),
    })


@org_required(manage=True, active=False)
@require_POST
def remove_member(request, membership_id):
    m = get_object_or_404(Membership, pk=membership_id, organization=request.org)
    if m.role == Membership.ROLE_OWNER:
        messages.error(request, "No se puede quitar al dueño de la cuenta.")
    else:
        m.delete()
        messages.success(request, "Usuario quitado.")
    return redirect("accounts:team")


@transaction.atomic
def accept_invitation(request, token):
    inv = get_object_or_404(Invitation, token=token, accepted_at__isnull=True)
    if request.user.is_authenticated:
        Membership.objects.get_or_create(user=request.user, organization=inv.organization,
                                         defaults={"role": inv.role})
        inv.accepted_at = timezone.now()
        inv.save()
        request.session["org_id"] = inv.organization_id
        return redirect("insights:dashboard")
    form = AcceptInvitationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        from django.contrib.auth import get_user_model

        User = get_user_model()
        if User.objects.filter(username=inv.email.lower()).exists():
            messages.info(request, "Ya tienes cuenta: entra y vuelve a abrir el link de invitación.")
            return redirect(reverse("accounts:login") + f"?next={request.path}")
        user = form.save(commit=False)
        user.username = inv.email.lower()
        user.email = inv.email.lower()
        user.save()
        Membership.objects.create(user=user, organization=inv.organization, role=inv.role)
        inv.accepted_at = timezone.now()
        inv.save()
        login(request, user)
        return redirect("insights:dashboard")
    return render(request, "accounts/accept_invitation.html", {"form": form, "invitation": inv})


@org_required(active=False)
def billing_view(request):
    org = request.org
    if request.GET.get("ok"):
        messages.success(request, "¡Gracias! Tu suscripción se está activando.")
    return render(request, "accounts/billing.html", {
        "plans": PLANS,
        "stripe_enabled": billing.stripe_enabled(),
        "usage": [
            ("Marcas", org.brands.filter(archived=False).count(), org.plan.max_brands),
            ("Usuarios", org.memberships.count(), org.plan.max_users),
            ("Análisis con IA este mes", org.ai_runs_this_month(), org.plan.ai_runs_per_month),
        ],
    })


@org_required(manage=True, active=False)
@require_POST
def choose_plan(request, plan_code):
    org = request.org
    if plan_code not in PLANS or plan_code == "enterprise":
        return HttpResponseBadRequest("Plan no válido")
    if billing.stripe_enabled():
        try:
            return redirect(billing.create_checkout_url(org, plan_code, request.user.email))
        except Exception:  # noqa: BLE001 — mostramos error amable y registramos
            log.exception("Error creando checkout de Stripe")
            messages.error(request, "No pudimos abrir el pago. Intenta de nuevo o escríbenos.")
            return redirect("accounts:billing")
    # Modo demo (sin Stripe): se activa directo
    org.plan_code = plan_code
    org.subscription_status = Organization.STATUS_ACTIVE
    org.save()
    messages.success(request, f"Plan {PLANS[plan_code].name} activado (modo demo, sin cobro).")
    return redirect("accounts:billing")


@org_required(manage=True, active=False)
@require_POST
def billing_portal(request):
    if not (billing.stripe_enabled() and request.org.stripe_customer_id):
        messages.info(request, "Aún no tienes una suscripción de pago.")
        return redirect("accounts:billing")
    return redirect(billing.create_portal_url(request.org))


@csrf_exempt
@require_POST
def stripe_webhook(request):
    if not settings.STRIPE_WEBHOOK_SECRET:
        return HttpResponse(status=404)
    try:
        billing.handle_webhook(request.body, request.META.get("HTTP_STRIPE_SIGNATURE", ""))
    except Exception:  # noqa: BLE001 — firma inválida o payload raro
        log.exception("Webhook de Stripe rechazado")
        return HttpResponse(status=400)
    return HttpResponse(status=200)
