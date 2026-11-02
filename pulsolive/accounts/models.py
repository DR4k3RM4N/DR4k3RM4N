import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from .plans import TRIAL_DAYS, TRIAL_PLAN, get_plan


class Organization(models.Model):
    """Cuenta que paga: una agencia, una marca o un creador."""

    KIND_AGENCY = "agency"
    KIND_BRAND = "brand"
    KIND_CREATOR = "creator"
    KIND_CHOICES = [
        (KIND_AGENCY, "Agencia"),
        (KIND_BRAND, "Marca"),
        (KIND_CREATOR, "Creador / host"),
    ]

    STATUS_TRIALING = "trialing"
    STATUS_ACTIVE = "active"
    STATUS_PAST_DUE = "past_due"
    STATUS_CANCELED = "canceled"
    STATUS_CHOICES = [
        (STATUS_TRIALING, "En prueba"),
        (STATUS_ACTIVE, "Activa"),
        (STATUS_PAST_DUE, "Pago pendiente"),
        (STATUS_CANCELED, "Cancelada"),
    ]

    name = models.CharField("nombre", max_length=120)
    slug = models.SlugField(unique=True, max_length=140)
    kind = models.CharField("tipo", max_length=20, choices=KIND_CHOICES, default=KIND_AGENCY)

    plan_code = models.CharField(max_length=20, default=TRIAL_PLAN)
    subscription_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_TRIALING)
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    stripe_customer_id = models.CharField(max_length=80, blank=True)
    stripe_subscription_id = models.CharField(max_length=80, blank=True)

    # Marca blanca para reportes (plan Agencia)
    logo = models.ImageField("logo", upload_to="logos/", blank=True)
    brand_color = models.CharField("color principal", max_length=7, default="#e11d74")
    report_footer = models.CharField("pie de reportes", max_length=200, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "organización"
        verbose_name_plural = "organizaciones"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:120] or "org"
            slug, i = base, 2
            while Organization.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, i = f"{base}-{i}", i + 1
            self.slug = slug
        if self.subscription_status == self.STATUS_TRIALING and not self.trial_ends_at:
            self.trial_ends_at = timezone.now() + timedelta(days=TRIAL_DAYS)
        super().save(*args, **kwargs)

    # --- Suscripción ---------------------------------------------------
    @property
    def plan(self):
        return get_plan(self.plan_code)

    @property
    def trial_days_left(self) -> int:
        if self.subscription_status != self.STATUS_TRIALING or not self.trial_ends_at:
            return 0
        return max(0, (self.trial_ends_at - timezone.now()).days)

    @property
    def is_active(self) -> bool:
        if self.subscription_status == self.STATUS_ACTIVE:
            return True
        if self.subscription_status == self.STATUS_TRIALING:
            return bool(self.trial_ends_at and self.trial_ends_at > timezone.now())
        if self.subscription_status == self.STATUS_PAST_DUE:
            # Gracia de 7 días
            return bool(self.current_period_end and self.current_period_end + timedelta(days=7) > timezone.now())
        return False

    def has_feature(self, feature: str) -> bool:
        return self.is_active and self.plan.has(feature)

    def ai_runs_this_month(self) -> int:
        from insights.models import AIRun

        start = timezone.localtime().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return AIRun.objects.filter(organization=self, created_at__gte=start, counted=True).count()

    def ai_runs_left(self) -> int:
        return max(0, self.plan.ai_runs_per_month - self.ai_runs_this_month())

    def can_add_brand(self) -> bool:
        return self.brands.filter(archived=False).count() < self.plan.max_brands

    def can_add_user(self) -> bool:
        pending = self.invitations.filter(accepted_at__isnull=True).count()
        return self.memberships.count() + pending < self.plan.max_users


class Membership(models.Model):
    ROLE_OWNER = "owner"
    ROLE_ADMIN = "admin"
    ROLE_ANALYST = "analyst"
    ROLE_VIEWER = "viewer"
    ROLE_CHOICES = [
        (ROLE_OWNER, "Dueño"),
        (ROLE_ADMIN, "Administrador"),
        (ROLE_ANALYST, "Analista"),
        (ROLE_VIEWER, "Solo lectura"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_ANALYST)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "organization")

    def __str__(self):
        return f"{self.user} @ {self.organization} ({self.role})"

    @property
    def can_edit(self) -> bool:
        return self.role != self.ROLE_VIEWER

    @property
    def can_manage(self) -> bool:
        return self.role in (self.ROLE_OWNER, self.ROLE_ADMIN)


def _token():
    return secrets.token_urlsafe(24)


class Invitation(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="invitations")
    email = models.EmailField()
    role = models.CharField(max_length=20, choices=Membership.ROLE_CHOICES, default=Membership.ROLE_ANALYST)
    token = models.CharField(max_length=64, unique=True, default=_token)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Invitación {self.email} → {self.organization}"
