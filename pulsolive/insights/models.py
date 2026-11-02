import secrets

from django.conf import settings
from django.db import models

from accounts.models import Organization
from lives.models import Brand


def _share_token():
    return secrets.token_urlsafe(18)


class Report(models.Model):
    PERIOD_CHOICES = [("daily", "Diario"), ("weekly", "Semanal"), ("monthly", "Mensual")]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="reports")
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, null=True, blank=True, related_name="reports")
    period = models.CharField(max_length=10, choices=PERIOD_CHOICES)
    start = models.DateField()
    end = models.DateField()  # inclusivo
    data = models.JSONField(default=dict)
    ai_summary = models.JSONField(default=dict, blank=True)
    share_token = models.CharField(max_length=40, unique=True, default=_share_token)
    shared = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start", "-created_at"]

    def __str__(self):
        scope = self.brand.name if self.brand else "Todas las marcas"
        return f"Reporte {self.get_period_display().lower()} · {scope} · {self.start:%d/%m/%Y}"


class Experiment(models.Model):
    """Prueba A/B: comparar dos formas de hacer el live."""

    STATUS_CHOICES = [("running", "En curso"), ("done", "Terminada")]
    METRIC_CHOICES = [
        ("gmv_per_hour", "Ventas por hora"),
        ("conversion_rate", "Conversión"),
        ("orders", "Pedidos"),
        ("avg_watch_seconds", "Tiempo de visualización"),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="experiments")
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name="experiments")
    name = models.CharField("nombre", max_length=150)
    hypothesis = models.TextField("hipótesis", blank=True)
    variant_a = models.CharField("variante A", max_length=150)
    variant_b = models.CharField("variante B", max_length=150)
    metric = models.CharField("métrica principal", max_length=30, choices=METRIC_CHOICES, default="gmv_per_hour")
    target_lives_per_variant = models.PositiveIntegerField("lives por variante", default=4)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="running")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class AIRun(models.Model):
    """Registro de cada llamada a la IA (para límites del plan y costos)."""

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="ai_runs")
    kind = models.CharField(max_length=30)
    model = models.CharField(max_length=60, blank=True)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    ok = models.BooleanField(default=True)
    counted = models.BooleanField(default=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
