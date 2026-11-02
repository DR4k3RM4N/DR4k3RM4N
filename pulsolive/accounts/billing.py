"""Cobro de suscripciones con Stripe.

Flujo: Checkout (Stripe aloja el formulario de pago) → webhook actualiza el
plan de la organización → el cliente administra su suscripción en el
Customer Portal de Stripe.

Sin llaves de Stripe la app funciona en "modo demo": el cambio de plan se
aplica directo, útil para desarrollo y demos de venta.
"""
import json
from datetime import datetime, timezone as dt_tz

import stripe
from django.conf import settings
from django.urls import reverse

from .models import Organization


def stripe_enabled() -> bool:
    return bool(settings.STRIPE_SECRET_KEY)


def _stripe():
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def create_checkout_url(org: Organization, plan_code: str, user_email: str) -> str:
    price = settings.STRIPE_PRICE_IDS.get(plan_code)
    if not price:
        raise ValueError(f"No hay precio de Stripe configurado para el plan {plan_code}")
    s = _stripe()
    params = {
        "mode": "subscription",
        "line_items": [{"price": price, "quantity": 1}],
        "success_url": settings.SITE_URL + reverse("accounts:billing") + "?ok=1",
        "cancel_url": settings.SITE_URL + reverse("accounts:billing"),
        "client_reference_id": str(org.pk),
        "metadata": {"org_id": str(org.pk), "plan": plan_code},
        "subscription_data": {"metadata": {"org_id": str(org.pk), "plan": plan_code}},
        "allow_promotion_codes": True,
        "locale": "es",
    }
    if org.stripe_customer_id:
        params["customer"] = org.stripe_customer_id
    else:
        params["customer_email"] = user_email
    session = s.checkout.Session.create(**params)
    return session.url


def create_portal_url(org: Organization) -> str:
    s = _stripe()
    session = s.billing_portal.Session.create(
        customer=org.stripe_customer_id, return_url=settings.SITE_URL + reverse("accounts:billing")
    )
    return session.url


STATUS_MAP = {
    "active": Organization.STATUS_ACTIVE,
    "trialing": Organization.STATUS_ACTIVE,
    "past_due": Organization.STATUS_PAST_DUE,
    "unpaid": Organization.STATUS_PAST_DUE,
    "canceled": Organization.STATUS_CANCELED,
    "incomplete_expired": Organization.STATUS_CANCELED,
}


def _plan_from_price(price_id: str) -> str | None:
    for code, pid in settings.STRIPE_PRICE_IDS.items():
        if pid and pid == price_id:
            return code
    return None


def handle_webhook(payload: bytes, signature: str) -> str:
    s = _stripe()
    # construct_event valida la firma; luego trabajamos con JSON plano.
    s.Webhook.construct_event(payload, signature, settings.STRIPE_WEBHOOK_SECRET)
    event = json.loads(payload)
    obj = event["data"]["object"]
    etype = event["type"]

    if etype == "checkout.session.completed":
        org = Organization.objects.filter(pk=obj.get("client_reference_id")).first()
        if org:
            org.stripe_customer_id = obj.get("customer") or org.stripe_customer_id
            org.stripe_subscription_id = obj.get("subscription") or org.stripe_subscription_id
            org.plan_code = (obj.get("metadata") or {}).get("plan", org.plan_code)
            org.subscription_status = Organization.STATUS_ACTIVE
            org.save()
    elif etype in ("customer.subscription.updated", "customer.subscription.created",
                   "customer.subscription.deleted"):
        org = (Organization.objects.filter(stripe_subscription_id=obj["id"]).first()
               or Organization.objects.filter(pk=(obj.get("metadata") or {}).get("org_id")).first())
        if org:
            org.stripe_subscription_id = obj["id"]
            org.stripe_customer_id = obj.get("customer") or org.stripe_customer_id
            status = "canceled" if etype.endswith("deleted") else obj.get("status")
            org.subscription_status = STATUS_MAP.get(status, org.subscription_status)
            items = (obj.get("items") or {}).get("data") or []
            if items:
                plan = _plan_from_price(items[0]["price"]["id"])
                if plan:
                    org.plan_code = plan
                period_end = items[0].get("current_period_end")
            else:
                period_end = obj.get("current_period_end")
            if period_end:
                org.current_period_end = datetime.fromtimestamp(period_end, tz=dt_tz.utc)
            org.save()
    return etype
