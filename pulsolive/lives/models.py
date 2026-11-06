from decimal import Decimal

from django.db import models
from django.utils import timezone

from accounts.models import Organization


class Brand(models.Model):
    """Una marca / cuenta de TikTok cuyos lives se analizan."""

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="brands")
    name = models.CharField("nombre", max_length=120)
    tiktok_handle = models.CharField("usuario de TikTok", max_length=80, blank=True)
    category = models.CharField("categoría", max_length=80, blank=True, help_text="Ej. belleza, moda, hogar")
    monthly_gmv_goal = models.DecimalField("meta mensual de ventas", max_digits=12, decimal_places=2, null=True, blank=True)
    archived = models.BooleanField("archivada", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "marca"

    def __str__(self):
        return self.name


class Host(models.Model):
    GENDER_CHOICES = [
        ("female", "Mujer"),
        ("male", "Hombre"),
        ("nonbinary", "No binario"),
        ("unspecified", "Prefiere no decir"),
    ]
    STYLE_CHOICES = [
        ("energetic", "Energético / vendedor"),
        ("expert", "Experto / técnico"),
        ("friendly", "Cercano / amigable"),
        ("funny", "Divertido / entretenimiento"),
        ("calm", "Tranquilo / aspiracional"),
    ]
    EXPERIENCE_CHOICES = [
        ("new", "Nuevo (< 20 lives)"),
        ("mid", "Intermedio (20–100)"),
        ("senior", "Experimentado (100+)"),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="hosts")
    name = models.CharField("nombre", max_length=120)
    handle = models.CharField("usuario", max_length=80, blank=True)
    gender = models.CharField("género", max_length=20, choices=GENDER_CHOICES, default="unspecified")
    style = models.CharField("estilo", max_length=20, choices=STYLE_CHOICES, blank=True)
    experience = models.CharField("experiencia", max_length=20, choices=EXPERIENCE_CHOICES, blank=True)
    active = models.BooleanField("activo", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Tag(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="tags")
    name = models.CharField(max_length=60)

    class Meta:
        unique_together = ("organization", "name")
        ordering = ["name"]

    def __str__(self):
        return self.name


PROMO_CHOICES = [
    ("unknown", "Sin registrar"),
    ("none", "Sin promoción"),
    ("discount", "Descuento directo"),
    ("flash_sale", "Flash sale / oferta relámpago"),
    ("bundle", "Paquete / 2x1"),
    ("gift", "Regalo con compra"),
    ("free_shipping", "Envío gratis"),
    ("coupon", "Cupón"),
    ("giveaway", "Sorteo / dinámica"),
]

SCRIPT_CHOICES = [
    ("demo", "Demostración del producto"),
    ("tutorial", "Tutorial / paso a paso"),
    ("storytelling", "Historia / testimonio"),
    ("qna", "Preguntas y respuestas"),
    ("unboxing", "Unboxing"),
    ("before_after", "Antes y después"),
    ("haul", "Haul / muchos productos"),
    ("other", "Otro"),
]

FORMAT_CHOICES = [
    ("solo", "Un host"),
    ("duo", "Dos hosts"),
    ("guest", "Con invitado / creador"),
]

SETTING_CHOICES = [
    ("studio", "Estudio / set"),
    ("home", "Casa"),
    ("store", "Tienda / bodega"),
    ("outdoor", "Exterior"),
]


class LiveSession(models.Model):
    SOURCE_CHOICES = [("manual", "Manual"), ("csv", "Archivo"), ("api", "TikTok API"), ("demo", "Demo")]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="lives")
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name="lives")
    host = models.ForeignKey(Host, on_delete=models.SET_NULL, null=True, blank=True, related_name="lives")
    title = models.CharField("título", max_length=200, blank=True)
    started_at = models.DateTimeField("inicio")
    duration_minutes = models.PositiveIntegerField("duración (min)", default=60)

    # Métricas (de TikTok Shop / LIVE Center)
    gmv = models.DecimalField("ventas (GMV)", max_digits=12, decimal_places=2, default=Decimal("0"))
    orders = models.PositiveIntegerField("pedidos", default=0)
    units_sold = models.PositiveIntegerField("piezas vendidas", default=0)
    viewers = models.PositiveIntegerField("espectadores", default=0)
    peak_viewers = models.PositiveIntegerField("pico de espectadores", default=0)
    avg_watch_seconds = models.PositiveIntegerField("tiempo promedio de visualización (s)", default=0)
    new_followers = models.PositiveIntegerField("nuevos seguidores", default=0)
    likes = models.PositiveIntegerField("likes", default=0)
    comments = models.PositiveIntegerField("comentarios", default=0)
    shares = models.PositiveIntegerField("compartidos", default=0)
    product_clicks = models.PositiveIntegerField("clics en producto", default=0)
    impressions = models.PositiveIntegerField("impresiones del live", default=0,
                                              help_text="Cuántas veces apareció el live en el feed")
    product_impressions = models.PositiveIntegerField("impresiones de producto", default=0)
    customers = models.PositiveIntegerField("clientes", default=0)

    # Lo que hizo el equipo (etiquetado)
    promo_type = models.CharField("promoción", max_length=20, choices=PROMO_CHOICES, default="none")
    script_type = models.CharField("tipo de guion", max_length=20, choices=SCRIPT_CHOICES, blank=True)
    format = models.CharField("formato", max_length=20, choices=FORMAT_CHOICES, default="solo")
    setting = models.CharField("escenario", max_length=20, choices=SETTING_CHOICES, blank=True)
    main_product = models.CharField("producto principal", max_length=150, blank=True)
    product_category = models.CharField("categoría de producto", max_length=80, blank=True)
    avg_price = models.DecimalField("precio promedio", max_digits=10, decimal_places=2, null=True, blank=True)
    tags = models.ManyToManyField(Tag, blank=True, related_name="lives")
    notes = models.TextField("notas", blank=True)

    experiment = models.ForeignKey(
        "insights.Experiment", on_delete=models.SET_NULL, null=True, blank=True, related_name="lives"
    )
    experiment_variant = models.CharField(max_length=1, choices=[("A", "A"), ("B", "B")], blank=True)

    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default="manual")
    external_id = models.CharField(max_length=120, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-started_at"]
        indexes = [models.Index(fields=["organization", "started_at"])]

    def __str__(self):
        return self.title or f"{self.brand} · {timezone.localtime(self.started_at):%d/%m %H:%M}"

    # --- Métricas derivadas ---------------------------------------------
    @property
    def hours(self) -> float:
        return max(self.duration_minutes, 1) / 60

    @property
    def gmv_per_hour(self) -> float:
        return float(self.gmv) / self.hours

    @property
    def conversion_rate(self) -> float:
        return self.orders / self.viewers if self.viewers else 0.0

    @property
    def aov(self) -> float:
        return float(self.gmv) / self.orders if self.orders else 0.0

    @property
    def click_rate(self) -> float:
        return self.product_clicks / self.viewers if self.viewers else 0.0

    # --- Embudo: lo vieron → entraron → dieron clic al producto → compraron ---
    @property
    def entry_rate(self):
        return self.viewers / self.impressions if self.impressions else None

    @property
    def product_ctr(self):
        return self.product_clicks / self.viewers if self.viewers else None

    @property
    def click_to_order(self):
        return self.orders / self.product_clicks if self.product_clicks else None

    @property
    def is_tagged(self) -> bool:
        return bool(self.host_id and self.script_type)


class LiveMinute(models.Model):
    """Serie minuto a minuto (opcional) para ver qué pasó en cada momento."""

    live = models.ForeignKey(LiveSession, on_delete=models.CASCADE, related_name="minutes")
    minute = models.PositiveIntegerField()
    viewers = models.PositiveIntegerField(default=0)
    orders = models.PositiveIntegerField(default=0)
    gmv = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    comments = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("live", "minute")
        ordering = ["minute"]


EVENT_CHOICES = [
    ("product_demo", "Demostró el producto"),
    ("price_reveal", "Reveló el precio"),
    ("discount", "Anunció descuento"),
    ("flash_sale", "Lanzó oferta relámpago"),
    ("scarcity", "Escasez (últimas piezas)"),
    ("urgency", "Urgencia (tiempo limitado)"),
    ("cta_cart", "Pidió dar clic al carrito"),
    ("giveaway", "Sorteo / dinámica"),
    ("qna", "Respondió preguntas"),
    ("shoutout", "Saludó a gente por su nombre"),
    ("testimonial", "Testimonio / reseña"),
    ("bundle", "Ofreció paquete / 2x1"),
    ("free_shipping", "Mencionó envío gratis"),
    ("product_switch", "Cambió de producto"),
    ("guest", "Entró un invitado"),
    ("before_after", "Mostró antes y después"),
    ("other", "Otro"),
]
EVENT_LABELS = dict(EVENT_CHOICES)


class LiveEvent(models.Model):
    """Algo que pasó en el live en un minuto concreto."""

    SOURCE_CHOICES = [("manual", "Manual"), ("ai", "IA"), ("keywords", "Palabras clave")]

    live = models.ForeignKey(LiveSession, on_delete=models.CASCADE, related_name="events")
    minute = models.PositiveIntegerField("minuto")
    kind = models.CharField("tipo", max_length=20, choices=EVENT_CHOICES)
    description = models.CharField("descripción", max_length=300, blank=True)
    quote = models.TextField("frase del host", blank=True)
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default="manual")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["minute"]

    def __str__(self):
        return f"min {self.minute}: {self.get_kind_display()}"


class Transcript(models.Model):
    live = models.OneToOneField(LiveSession, on_delete=models.CASCADE, related_name="transcript")
    raw_text = models.TextField()
    segments = models.JSONField(default=list)  # [{"start": seg, "end": seg, "text": str}]
    summary = models.TextField(blank=True)
    analysis = models.JSONField(default=dict, blank=True)
    analyzed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ImportBatch(models.Model):
    KIND_CHOICES = [("sessions", "Resumen de lives"), ("minutes", "Minuto a minuto"), ("trends", "Tendencias diarias")]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="imports")
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name="imports")
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default="sessions")
    filename = models.CharField(max_length=200)
    created = models.PositiveIntegerField(default=0)
    updated = models.PositiveIntegerField(default=0)
    skipped = models.PositiveIntegerField(default=0)
    errors = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class AccountDay(models.Model):
    """Tendencia diaria de la cuenta (videos): el archivo de Análisis → Tendencias de TikTok."""

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="account_days")
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name="days")
    date = models.DateField()
    video_views = models.PositiveIntegerField(default=0)
    profile_views = models.PositiveIntegerField(default=0)
    likes = models.PositiveIntegerField(default=0)
    comments = models.PositiveIntegerField(default=0)
    shares = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("brand", "date")
        ordering = ["date"]
