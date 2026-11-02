"""Crea una cuenta demo con 6 meses de lives realistas.

Los datos tienen patrones "escondidos" (horario, host, promoción, guion,
momentos que disparan ventas) para que el análisis los descubra. Sirve para
probar el producto y para hacer demos de venta.

    python manage.py seed_demo            # crea/actualiza demo@pulsolive.app / demo12345
    python manage.py seed_demo --reset    # borra la cuenta demo y la vuelve a crear
"""
import math
import random
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Membership, Organization
from insights.services import generate_report
from lives.importers import parse_transcript
from lives.models import Brand, Host, LiveEvent, LiveMinute, LiveSession, Tag, Transcript

DEMO_EMAIL = "demo@pulsolive.app"
DEMO_PASSWORD = "demo12345"

BRANDS = [
    {"name": "Glow Lab", "category": "Belleza", "handle": "@glowlab.mx", "base": 9000, "price": 289,
     "products": ["Sérum vitamina C", "Protector solar FPS 50", "Kit rutina noche", "Bálsamo labial"]},
    {"name": "Casa Viva", "category": "Hogar", "handle": "@casaviva", "base": 7000, "price": 459,
     "products": ["Organizadores de cocina", "Freidora de aire", "Set de toallas", "Lámpara LED"]},
    {"name": "Urbana", "category": "Moda", "handle": "@urbana.store", "base": 6000, "price": 349,
     "products": ["Jeans wide leg", "Tenis blancos", "Bolsa tote", "Sudadera oversize"]},
]

HOSTS = [
    # nombre, género, estilo, experiencia, efecto ventas, efecto retención, efecto conversión
    ("Ana Ruiz", "female", "energetic", "senior", 1.30, 1.10, 1.20),
    ("Luis Ortega", "male", "expert", "mid", 1.05, 1.00, 1.05),
    ("Sofi Méndez", "female", "friendly", "new", 0.82, 0.70, 0.95),
    ("Diego Paz", "male", "funny", "mid", 0.95, 1.25, 0.75),
    ("Vale Ríos", "nonbinary", "calm", "senior", 1.12, 1.05, 1.08),
]

HOUR_EFFECT = {9: 0.6, 11: 0.75, 13: 0.8, 16: 0.95, 18: 1.05, 20: 1.45, 21: 1.35, 23: 0.9}
WEEKDAY_EFFECT = [0.9, 0.92, 0.95, 1.12, 1.15, 0.98, 1.08]
PROMO_EFFECT = {"none": 1.0, "discount": 1.1, "flash_sale": 1.38, "bundle": 1.2, "gift": 1.08,
                "free_shipping": 1.12, "coupon": 1.04, "giveaway": 0.97}
SCRIPT_EFFECT = {"demo": 1.25, "tutorial": 1.12, "storytelling": 1.0, "qna": 0.95, "unboxing": 1.0,
                 "before_after": 1.22, "haul": 0.88}

SAMPLE_TRANSCRIPT = """[00:00:20] ¡Hola, hola! Bienvenidas a Glow Lab, hoy tenemos algo muy especial para su piel.
[00:01:30] Saludos a Mariana y a Coco que siempre están aquí, gracias por seguirnos.
[00:03:10] Miren la textura de este sérum de vitamina C, les muestro cómo se absorbe en segundos.
[00:06:45] Yo lo uso todas las mañanas y a mí me funcionó para las manchas, esta es mi piel sin filtro.
[00:09:00] El precio normal es 389, pero hoy está a solo 289 pesos.
[00:12:00] Den clic en el carrito naranja, ahí abajo, el producto número uno.
[00:15:30] Me preguntan si sirve para piel grasa: buena pregunta, sí, es ligero y no deja brillo.
[00:20:00] ¡Oferta relámpago! Solo por los próximos 10 minutos el kit completo con 30% de descuento.
[00:22:00] Quedan solo 40 piezas, se están acabando, ya se vendieron 60.
[00:27:00] Vamos a cambiar al protector solar, este es para todos los días.
[00:31:00] Les enseño el antes y después de una clienta que lo usó tres semanas.
[00:35:00] Envío gratis en compras de más de 299, aprovechen.
[00:40:00] Últimas piezas del kit, ya casi no hay, solo en este live.
[00:44:00] Gracias por estar aquí, mañana regresamos a las 8 de la noche."""


class Command(BaseCommand):
    help = "Crea una cuenta demo con datos realistas de lives de TikTok."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true")
        parser.add_argument("--days", type=int, default=180)
        parser.add_argument("--seed", type=int, default=7)

    @transaction.atomic
    def handle(self, *args, **opts):
        rng = random.Random(opts["seed"])
        User = get_user_model()
        user, created = User.objects.get_or_create(username=DEMO_EMAIL, defaults={"email": DEMO_EMAIL,
                                                                                  "first_name": "Demo"})
        if created:
            user.set_password(DEMO_PASSWORD)
            user.save()
        org = Organization.objects.filter(memberships__user=user, name="Agencia Demo").first()
        if org and opts["reset"]:
            org.delete()
            org = None
        if org:
            self.stdout.write("La cuenta demo ya existe (usa --reset para recrearla).")
            return
        org = Organization.objects.create(name="Agencia Demo", kind=Organization.KIND_AGENCY,
                                          plan_code="agency", subscription_status=Organization.STATUS_ACTIVE,
                                          report_footer="Reporte preparado por Agencia Demo")
        Membership.objects.create(user=user, organization=org, role=Membership.ROLE_OWNER)

        hosts = {}
        for name, gender, style, exp, *_ in HOSTS:
            hosts[name] = Host.objects.create(organization=org, name=name, gender=gender, style=style,
                                              experience=exp, handle="@" + name.split()[0].lower())
        tag_new_set = Tag.objects.create(organization=org, name="set nuevo")
        tag_guest = Tag.objects.create(organization=org, name="invitada")

        now = timezone.localtime()
        start_day = (now - timedelta(days=opts["days"])).date()
        total = 0
        lives_with_minutes = []
        for b in BRANDS:
            brand = Brand.objects.create(organization=org, name=b["name"], category=b["category"],
                                         tiktok_handle=b["handle"],
                                         monthly_gmv_goal=Decimal(b["base"] * 22))
            host_pool = list(HOSTS)
            for day_offset in range(opts["days"]):
                day = start_day + timedelta(days=day_offset)
                if rng.random() > 0.62:  # ~4-5 lives por semana por marca
                    continue
                hour = rng.choices(list(HOUR_EFFECT), weights=[1, 2, 2, 2, 3, 5, 4, 1])[0]
                started = timezone.make_aware(datetime.combine(day, time(hour, rng.choice([0, 0, 30]))))
                if started > now - timedelta(hours=3):
                    continue
                hname, gender, style, exp, h_sales, h_watch, h_conv = rng.choice(host_pool)
                promo = rng.choices(list(PROMO_EFFECT), weights=[5, 4, 3, 2, 1, 2, 1, 1])[0]
                script = rng.choices(list(SCRIPT_EFFECT), weights=[4, 2, 2, 2, 1, 2, 1])[0]
                duration = rng.choice([45, 60, 90, 120, 120, 150, 180, 240])
                fmt = rng.choices(["solo", "duo", "guest"], weights=[6, 2, 1])[0]
                setting = rng.choices(["studio", "home", "store"], weights=[5, 3, 1])[0]

                # Rendimiento por hora con efectos combinados
                dur_effect = 1.0 if duration <= 180 else 0.8
                if duration < 60:
                    dur_effect = 0.85
                cat_bonus = 1.2 if (hname == "Luis Ortega" and b["category"] == "Hogar") else 1.0
                before_after_bonus = 1.1 if (script == "before_after" and b["category"] == "Belleza") else 1.0
                fmt_effect = {"solo": 1.0, "duo": 1.08, "guest": 1.15}[fmt]
                growth = 1 + 0.25 * day_offset / opts["days"]  # la cuenta crece con el tiempo
                rate = (b["base"] * HOUR_EFFECT[hour] * WEEKDAY_EFFECT[day.weekday()] * PROMO_EFFECT[promo]
                        * SCRIPT_EFFECT[script] * h_sales * dur_effect * cat_bonus * before_after_bonus
                        * fmt_effect * growth * rng.lognormvariate(0, 0.28))
                gmv = rate * duration / 60
                price = b["price"] * rng.uniform(0.85, 1.25) * (1.25 if promo == "bundle" else 1.0)
                orders = max(0, int(gmv / price))
                conv = 0.018 * h_conv * PROMO_EFFECT[promo] ** 0.5 * rng.lognormvariate(0, 0.2)
                viewers = max(orders * 3, int(orders / conv)) if orders else rng.randint(200, 900)
                avg_watch = int(70 * h_watch * (1.1 if script in ("demo", "before_after") else 1.0)
                                * rng.lognormvariate(0, 0.15))

                live = LiveSession.objects.create(
                    organization=org, brand=brand, host=hosts[hname],
                    title=f"{b['name']} · {rng.choice(b['products'])}",
                    started_at=started, duration_minutes=duration,
                    gmv=Decimal(str(round(gmv, 2))), orders=orders, units_sold=int(orders * rng.uniform(1.05, 1.4)),
                    viewers=viewers, peak_viewers=int(viewers * rng.uniform(0.05, 0.12)),
                    avg_watch_seconds=avg_watch, new_followers=int(viewers * rng.uniform(0.01, 0.03)),
                    likes=int(viewers * rng.uniform(1.5, 4)), comments=int(viewers * rng.uniform(0.08, 0.2)),
                    shares=int(viewers * rng.uniform(0.003, 0.01)),
                    product_clicks=int(viewers * rng.uniform(0.12, 0.25)),
                    promo_type=promo, script_type=script, format=fmt, setting=setting,
                    main_product=rng.choice(b["products"]), product_category=b["category"],
                    avg_price=Decimal(str(round(price, 2))), source="demo",
                )
                if fmt == "guest":
                    live.tags.add(tag_guest)
                if day_offset > opts["days"] - 45 and setting == "studio":
                    live.tags.add(tag_new_set)
                # Algunos lives sin etiquetar, como en la vida real
                if rng.random() < 0.06:
                    live.script_type = ""
                    live.save(update_fields=["script_type"])
                if day_offset > opts["days"] - 50 and rng.random() < 0.7:
                    lives_with_minutes.append(live)
                total += 1

        for live in lives_with_minutes:
            self._minutes_and_events(live, rng)

        # Transcripción de ejemplo en el mejor live reciente de Glow Lab
        glow_live = (LiveSession.objects.filter(organization=org, brand__name="Glow Lab", minutes__isnull=False)
                     .order_by("-gmv").first())
        if glow_live:
            Transcript.objects.create(live=glow_live, raw_text=SAMPLE_TRANSCRIPT,
                                      segments=parse_transcript(SAMPLE_TRANSCRIPT))

        today = timezone.localdate()
        for brand in org.brands.all():
            generate_report(org, brand, "weekly", today - timedelta(days=7), user)
            generate_report(org, brand, "monthly", today.replace(day=1) - timedelta(days=1), user)
        generate_report(org, None, "weekly", today - timedelta(days=7), user)

        self.stdout.write(self.style.SUCCESS(
            f"Cuenta demo lista: {total} lives, {len(lives_with_minutes)} con minuto a minuto.\n"
            f"Entra con {DEMO_EMAIL} / {DEMO_PASSWORD}"))

    def _minutes_and_events(self, live, rng):
        """Simula la curva minuto a minuto con momentos que mueven las ventas."""
        duration = live.duration_minutes
        effects = {"flash_sale": 3.2, "scarcity": 2.2, "cta_cart": 1.7, "price_reveal": 1.6, "product_demo": 1.4,
                   "giveaway": 0.9, "shoutout": 1.0, "qna": 1.1, "product_switch": 0.6, "testimonial": 1.3}
        kinds = list(effects)
        events = []
        m = rng.randint(2, 6)
        while m < duration - 3:
            kind = rng.choices(kinds, weights=[2, 2, 3, 2, 3, 1, 2, 2, 2, 2])[0]
            if kind == "flash_sale" and live.promo_type != "flash_sale" and rng.random() < 0.6:
                kind = "cta_cart"
            events.append((m, kind))
            m += rng.randint(6, 14)
        base_orders = max(live.orders / max(duration, 1), 0.05)
        peak = max(live.peak_viewers, 50)
        boost = [1.0] * (duration + 1)
        viewer_mult = [1.0] * (duration + 1)
        for minute, kind in events:
            for k in range(minute, min(duration, minute + 5)):
                decay = 1 - (k - minute) / 5
                boost[k] *= 1 + (effects[kind] - 1) * decay
            if kind == "product_switch":
                for k in range(minute, min(duration, minute + 6)):
                    viewer_mult[k] *= 0.65
            if kind == "giveaway":
                for k in range(minute, min(duration, minute + 6)):
                    viewer_mult[k] *= 1.35
        rows = []
        for minute in range(duration):
            ramp = min(1.0, 0.35 + minute / 12)
            fade = 1.0 if minute < duration - 10 else 0.75
            viewers = int(peak * ramp * fade * viewer_mult[minute] * rng.uniform(0.85, 1.1))
            lam = base_orders * boost[minute] * ramp
            orders = self._poisson(lam, rng)
            rows.append(LiveMinute(live=live, minute=minute, viewers=viewers, orders=orders,
                                   gmv=Decimal(str(round(orders * float(live.avg_price or 300), 2))),
                                   comments=int(viewers * rng.uniform(0.02, 0.08))))
        LiveMinute.objects.bulk_create(rows)
        LiveEvent.objects.bulk_create([LiveEvent(live=live, minute=minute, kind=kind, source="manual")
                                       for minute, kind in events])

    @staticmethod
    def _poisson(lam, rng):
        if lam <= 0:
            return 0
        if lam > 30:
            return max(0, int(rng.gauss(lam, math.sqrt(lam))))
        L, k, p = math.exp(-lam), 0, 1.0
        while True:
            p *= rng.random()
            if p <= L:
                return k
            k += 1
