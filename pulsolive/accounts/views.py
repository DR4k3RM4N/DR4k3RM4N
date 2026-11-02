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


def landing(request):
    if request.user.is_authenticated and request.org:
        return redirect("insights:dashboard")
    return render(request, "accounts/landing.html", {"plans": PLANS, "trial_days": TRIAL_DAYS})


def pricing(request):
    return render(request, "accounts/pricing.html", {"plans": PLANS, "trial_days": TRIAL_DAYS})


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
        "ai_used": org.ai_runs_this_month(),
        "brands_used": org.brands.filter(archived=False).count(),
        "users_used": org.memberships.count(),
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
