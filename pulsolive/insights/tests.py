import io
import random
from datetime import datetime, timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Membership, Organization
from lives.importers import (keyword_events, map_columns, parse_duration_seconds, parse_money, parse_sessions,
                             parse_transcript, read_table, SESSION_ALIASES)
from lives.models import Brand, Host, LiveSession, Transcript

from . import engine
from .models import Report


class EngineTests(TestCase):
    def _rows(self, n=120, seed=1):
        rng = random.Random(seed)
        rows = []
        base = datetime(2026, 6, 1, 10)
        for i in range(n):
            hour = rng.choice([10, 13, 20, 21])
            promo = rng.choice(["Sin promoción", "Flash sale"])
            host = rng.choice(["Ana", "Beto", "Caro"])
            rate = 10000 * (1.5 if hour >= 19 else 1.0) * (1.3 if promo == "Flash sale" else 1.0)
            rate *= {"Ana": 1.25, "Beto": 1.0, "Caro": 0.8}[host] * rng.lognormvariate(0, 0.15)
            rows.append({
                "id": i, "brand": "X", "started_at": (base + timedelta(days=i // 2)).replace(hour=hour),
                "duration_minutes": 120, "gmv": rate * 2, "orders": int(rate / 150), "units_sold": 0,
                "viewers": 5000, "peak_viewers": 300, "avg_watch_seconds": 60, "new_followers": 10,
                "product_clicks": 600, "host": host, "host_gender": "", "host_style": "", "host_experience": "",
                "promo_type": promo, "script_type": "Demo", "format": "Un host", "setting": "",
                "product_category": "", "tags": [], "has_minutes": False,
            })
        return rows

    def test_factor_analysis_finds_planted_effects(self):
        df = engine.build_frame(self._rows())
        factors = {f.key: f for f in engine.factor_analysis(df)}
        self.assertEqual(factors["daypart"].best.level, "Noche (19–22 h)")
        self.assertEqual(factors["promo_type"].best.level, "Flash sale")
        self.assertEqual(factors["host"].best.level, "Ana")
        self.assertEqual(factors["host"].worst.level, "Caro")
        self.assertEqual(factors["daypart"].best.confidence, "alta")
        # Efecto ajustado del host cercano al real (+25% vs. promedio de hosts)
        self.assertGreater(factors["host"].best.adjusted_lift, 0.1)

    def test_small_samples_are_low_confidence(self):
        df = engine.build_frame(self._rows(n=4))
        for f in engine.factor_analysis(df):
            for lv in f.levels:
                if lv.n < engine.MIN_N:
                    self.assertEqual(lv.confidence, "baja")

    def test_recommendations_warn_on_few_lives(self):
        df = engine.build_frame(self._rows(n=6))
        recs = engine.recommendations(df, engine.factor_analysis(df), [], [], "gmv_per_hour")
        self.assertEqual(recs[0].kind, "datos")

    def test_welch(self):
        self.assertLess(engine.welch_p_value([10, 11, 12, 10, 11, 12], [1, 2, 1, 2, 1, 2]), 0.001)
        self.assertGreater(engine.welch_p_value([1, 2, 3, 2], [2, 1, 3, 2]), 0.5)
        self.assertIsNone(engine.welch_p_value([1], [2, 3]))

    def test_moments_detects_spike_after_event(self):
        minutes = [{"minute": m, "orders": 1, "viewers": 100, "gmv": 100} for m in range(40)]
        for m in range(20, 24):
            minutes[m]["orders"] = 9
        events = [{"minute": 20, "kind": "flash_sale", "label": "Flash"}]
        res = engine.moments_for_live(minutes, events)
        self.assertTrue(any(s["minute"] == 20 and s["cause"] for s in res["spikes"]))
        self.assertGreater(res["event_impacts"][0]["uplift"], 3)

    def test_experiment_evaluation(self):
        res = engine.evaluate_experiment([100, 110, 105, 98], [150, 160, 155, 149], target=4)
        self.assertEqual(res["winner"], "B")
        res = engine.evaluate_experiment([100], [150], target=4)
        self.assertIsNone(res["winner"])
        self.assertIn("Faltan", res["status"])


class ImporterTests(TestCase):
    def test_parse_money(self):
        self.assertEqual(parse_money("$12,345.67"), Decimal("12345.67"))
        self.assertEqual(parse_money("MX$ 1.234,50"), Decimal("1234.50"))
        self.assertEqual(parse_money("1,234"), Decimal("1234"))
        self.assertEqual(parse_money(""), Decimal("0"))

    def test_parse_duration(self):
        self.assertEqual(parse_duration_seconds("1h 23m"), 4980)
        self.assertEqual(parse_duration_seconds("01:30:00"), 5400)
        self.assertEqual(parse_duration_seconds("90"), 5400)
        self.assertEqual(parse_duration_seconds("1m 20s", "seconds"), 80)
        self.assertEqual(parse_duration_seconds("01:20", "seconds"), 80)

    def test_column_aliases_spanish_and_english(self):
        m = map_columns(["Hora de inicio", "GMV (MXN)", "Pedidos de SKU", "Espectadores", "Duración"], SESSION_ALIASES)
        self.assertEqual(m["started_at"], "Hora de inicio")
        self.assertEqual(m["gmv"], "GMV (MXN)")
        self.assertEqual(m["orders"], "Pedidos de SKU")
        m = map_columns(["Start Time", "Revenue", "Orders", "Viewers"], SESSION_ALIASES)
        self.assertEqual(set(m), {"started_at", "gmv", "orders", "viewers"})

    def test_parse_sessions_csv(self):
        csv = ("Hora de inicio;Duración;GMV;Pedidos;Espectadores;Tiempo promedio de visualización;Promoción;Guion\n"
               "29/10/2026 20:00;2h;$18,450.50;142;6,230;1m 25s;flash sale;demo\n"
               "fecha mala;1h;100;1;10;30;;\n")
        f = SimpleUploadedFile("lives.csv", csv.encode("utf-8"))
        res = parse_sessions(read_table(f))
        self.assertEqual(len(res.rows), 1)
        self.assertEqual(len(res.errors), 1)
        row = res.rows[0].data
        self.assertEqual(row["duration_minutes"], 120)
        self.assertEqual(row["gmv"], Decimal("18450.50"))
        self.assertEqual(row["viewers"], 6230)
        self.assertEqual(row["avg_watch_seconds"], 85)
        self.assertEqual(row["promo_type"], "flash_sale")
        self.assertEqual(row["script_type"], "demo")
        self.assertEqual(timezone.localtime(row["started_at"]).day, 29)

    def test_transcripts(self):
        srt = "1\n00:00:01,000 --> 00:00:04,000\nHola a todos\n\n2\n00:05:00,000 --> 00:05:03,000\nQuedan solo 10 piezas\n"
        segs = parse_transcript(srt)
        self.assertEqual(len(segs), 2)
        self.assertEqual(segs[1]["start"], 300)
        segs = parse_transcript("[00:10:00] ¡Oferta relámpago! solo por los próximos 5 minutos\n[00:12:00] den clic al carrito")
        kinds = {e["kind"] for e in keyword_events(segs)}
        self.assertIn("flash_sale", kinds)
        self.assertIn("cta_cart", kinds)


class AppFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", days=60, stdout=io.StringIO())
        cls.user = get_user_model().objects.get(username="demo@pulsolive.app")
        cls.org = Organization.objects.get(name="Agencia Demo")

    def setUp(self):
        self.client.force_login(self.user)

    def test_all_pages_render(self):
        live = LiveSession.objects.filter(organization=self.org, minutes__isnull=False).first()
        brand = Brand.objects.filter(organization=self.org).first()
        report = Report.objects.filter(organization=self.org).first()
        urls = [
            reverse("insights:dashboard"), reverse("insights:dashboard") + f"?marca={brand.pk}",
            reverse("insights:analysis"), reverse("insights:analysis") + "?metrica=conversion_rate",
            reverse("insights:hosts"), reverse("insights:playbook"), reverse("insights:report_list"),
            reverse("insights:report_detail", args=[report.pk]), reverse("insights:experiment_list"),
            reverse("lives:live_list"), reverse("lives:live_detail", args=[live.pk]),
            reverse("lives:live_edit", args=[live.pk]), reverse("lives:live_create"),
            reverse("lives:brand_list"), reverse("lives:host_list"), reverse("lives:import"),
            reverse("accounts:billing"), reverse("accounts:team"), reverse("accounts:settings"),
            reverse("lives:import_template"),
        ]
        for url in urls:
            with self.subTest(url=url):
                r = self.client.get(url)
                self.assertEqual(r.status_code, 200, url)

    def test_public_pages(self):
        self.client.logout()
        for name in ("accounts:landing", "accounts:pricing", "accounts:signup", "accounts:login"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_signup_creates_trial_org(self):
        self.client.logout()
        r = self.client.post(reverse("accounts:signup"), {
            "first_name": "Miguel", "email": "m@agencia.mx", "org_name": "Mi Agencia", "org_kind": "agency",
            "password1": "Sup3rSegura!2026", "password2": "Sup3rSegura!2026"})
        self.assertEqual(r.status_code, 302)
        org = Organization.objects.get(name="Mi Agencia")
        self.assertEqual(org.subscription_status, "trialing")
        self.assertTrue(org.is_active)
        self.assertEqual(org.trial_days_left, 13)

    def test_import_flow(self):
        brand = Brand.objects.filter(organization=self.org).first()
        csv = ("ID del live,Hora de inicio,Duración,GMV,Pedidos,Espectadores,Host\n"
               "abc1,2026-10-20 20:07,90,5000,40,2000,Nuevo Host\n"
               "abc2,2026-10-21 13:07,60,1200,10,900,\n")
        f = SimpleUploadedFile("lives.csv", csv.encode())
        r = self.client.post(reverse("lives:import"), {"brand": brand.pk, "file": f})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(LiveSession.objects.filter(external_id="abc1", host__name="Nuevo Host").exists())
        # Reimportar actualiza, no duplica
        f = SimpleUploadedFile("lives.csv", csv.replace("5000", "5500").encode())
        self.client.post(reverse("lives:import"), {"brand": brand.pk, "file": f})
        self.assertEqual(LiveSession.objects.filter(external_id="abc1").count(), 1)
        self.assertEqual(LiveSession.objects.get(external_id="abc1").gmv, Decimal("5500"))

    def test_generate_report_and_share(self):
        r = self.client.post(reverse("insights:report_list"),
                             {"period": "monthly", "anchor": timezone.localdate().isoformat(), "brand": ""})
        self.assertEqual(r.status_code, 302)
        report = Report.objects.filter(organization=self.org, period="monthly", brand=None).latest("created_at")
        public_url = reverse("insights:report_public", args=[report.share_token])
        self.client.logout()
        self.assertEqual(self.client.get(public_url).status_code, 404)
        report.shared = True
        report.save()
        self.assertEqual(self.client.get(public_url).status_code, 200)

    def test_transcript_keywords_analysis(self):
        live = Transcript.objects.filter(live__organization=self.org).first().live
        r = self.client.post(reverse("lives:transcript_analyze", args=[live.pk]), {"mode": "keywords"})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(live.events.filter(source="keywords").exists())

    def test_ai_report_uses_claude_when_configured(self):
        report = Report.objects.filter(organization=self.org).first()
        fake = {"headline": "Las noches venden", "summary": "s", "what_worked": ["a"], "what_to_fix": ["b"],
                "next_actions": [{"action": "x", "why": "y", "how_to_measure": "z"}],
                "experiment_idea": {"name": "n", "variant_a": "a", "variant_b": "b", "hypothesis": "h"},
                "data_caveats": ""}
        with self.settings(ANTHROPIC_API_KEY="test"), mock.patch("insights.ai._call_json", return_value=fake):
            r = self.client.post(reverse("insights:report_ai", args=[report.pk]))
        self.assertEqual(r.status_code, 302)
        report.refresh_from_db()
        self.assertEqual(report.ai_summary["headline"], "Las noches venden")
        page = self.client.get(reverse("insights:report_detail", args=[report.pk]))
        self.assertContains(page, "Las noches venden")

    def test_plan_gating(self):
        self.org.plan_code = "creator"
        self.org.save()
        r = self.client.get(reverse("insights:hosts"))
        self.assertRedirects(r, reverse("accounts:billing"))
        live = LiveSession.objects.filter(organization=self.org).first()
        r = self.client.post(reverse("lives:transcript_upload", args=[live.pk]), {"text": "[00:01] hola"})
        self.assertRedirects(r, reverse("accounts:billing"))

    def test_expired_trial_redirects_to_billing(self):
        self.org.subscription_status = "trialing"
        self.org.trial_ends_at = timezone.now() - timedelta(days=1)
        self.org.save()
        self.assertRedirects(self.client.get(reverse("insights:dashboard")), reverse("accounts:billing"))
        # Modo demo: elegir plan lo activa
        self.client.post(reverse("accounts:choose_plan", args=["pro"]))
        self.org.refresh_from_db()
        self.assertEqual(self.org.plan_code, "pro")
        self.assertEqual(self.client.get(reverse("insights:dashboard")).status_code, 200)

    def test_tenant_isolation(self):
        other_user = get_user_model().objects.create_user("otro@x.mx", "otro@x.mx", "pass12345!")
        other = Organization.objects.create(name="Otra agencia")
        Membership.objects.create(user=other_user, organization=other, role="owner")
        self.client.force_login(other_user)
        live = LiveSession.objects.filter(organization=self.org).first()
        self.assertEqual(self.client.get(reverse("lives:live_detail", args=[live.pk])).status_code, 404)
        report = Report.objects.filter(organization=self.org).first()
        self.assertEqual(self.client.get(reverse("insights:report_detail", args=[report.pk])).status_code, 404)
        r = self.client.get(reverse("lives:live_list"))
        self.assertNotContains(r, "Glow Lab")

    def test_viewer_cannot_edit(self):
        viewer = get_user_model().objects.create_user("cliente@marca.mx", "cliente@marca.mx", "pass12345!")
        Membership.objects.create(user=viewer, organization=self.org, role="viewer")
        self.client.force_login(viewer)
        live = LiveSession.objects.filter(organization=self.org).first()
        self.assertEqual(self.client.get(reverse("lives:live_edit", args=[live.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("lives:live_detail", args=[live.pk])).status_code, 200)

    def test_brand_limit(self):
        self.org.plan_code = "creator"
        self.org.save()
        before = Brand.objects.filter(organization=self.org).count()
        self.client.post(reverse("lives:brand_list"), {"name": "Otra marca"})
        self.assertEqual(Brand.objects.filter(organization=self.org).count(), before)

    def test_experiment_flow(self):
        brand = Brand.objects.filter(organization=self.org).first()
        r = self.client.post(reverse("insights:experiment_list"), {
            "brand": brand.pk, "name": "Flash vs 2x1", "variant_a": "Flash", "variant_b": "2x1",
            "metric": "gmv_per_hour", "target_lives_per_variant": 2})
        self.assertEqual(r.status_code, 302)
        exp = self.org.experiments.get()
        lives = list(LiveSession.objects.filter(brand=brand)[:4])
        for live, variant in zip(lives, "AABB"):
            live.experiment, live.experiment_variant = exp, variant
            live.save()
        r = self.client.get(reverse("insights:experiment_detail", args=[exp.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["ev"]["n_a"], 2)


class TikTokExportFormatTests(TestCase):
    """Formatos reales de TikTok: Excel de LIVE con título y fila vacía antes del encabezado, y CSV de tendencias."""

    def _xlsx(self):
        import openpyxl

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["2026-09-01 ~ 2026-10-25"])
        ws.append([])
        ws.append(["Room ID", "Room Title", "Start Time", "End Time", "Duration", "Attributed GMV",
                   "Attributed items sold", "Attributed orders", "Customers", "Views", "Impressions",
                   "Avg. viewing duration", "Product Impressions", "Product clicks", "New followers", "Likes"])
        ws.append(["111", "FLASH SALE SOLO HOY!!", "2026-10-05 16:01:06", "2026-10-05 20:03:39", "4h02m",
                   "$1,494.10", "3", "2", "2", "1472", "17031", "61.95", "3366", "93", "8", "3304"])
        ws.append(["222", "Super promos!!", "2026-10-06 13:00:00", "2026-10-06 13:07:00", "0h07m",
                   "$0.00", "0", "0", "0", "1", "12", "0", "0", "0", "0", "0"])
        buf = io.BytesIO()
        wb.save(buf)
        # TikTok declara mal el tamaño de la hoja; el lector no debe depender de eso.
        return SimpleUploadedFile("Creator-Live-Performance.xlsx", buf.getvalue())

    def test_live_export_with_title_rows(self):
        res = parse_sessions(read_table(self._xlsx()))
        self.assertEqual(res.missing_required, [])
        self.assertEqual(len(res.rows), 2)
        a = res.rows[0].data
        self.assertEqual(a["external_id"], "111")
        self.assertEqual(a["duration_minutes"], 242)
        self.assertEqual(a["gmv"], Decimal("1494.10"))
        self.assertEqual((a["orders"], a["customers"], a["viewers"], a["impressions"]), (2, 2, 1472, 17031))
        self.assertEqual((a["product_impressions"], a["product_clicks"], a["avg_watch_seconds"]), (3366, 93, 61))
        self.assertEqual(a["promo_type"], "flash_sale")
        # Un título genérico no dice la mecánica de la promoción
        self.assertEqual(res.rows[1].data["promo_type"], "unknown")
        self.assertEqual(res.rows[1].data["duration_minutes"], 7)

    def test_trend_csv_spanish_dates_without_year(self):
        from datetime import date

        from lives.importers import is_trend_table, parse_trends

        csv = ('"Date","Video Views","Profile Views","Likes","Comments","Shares"\n'
               '"24 de septiembre","180412","205","555","3","28"\n"5 de noviembre","14","1","0","0","0"\n')
        df = read_table(SimpleUploadedFile("trends.csv", csv.encode()))
        self.assertTrue(is_trend_table(df))
        res = parse_trends(df, today=date(2026, 11, 6))
        self.assertEqual(res.rows[0]["date"], date(2026, 9, 24))
        self.assertEqual(res.rows[0]["video_views"], 180412)
        # Una fecha "futura" sin año es del año pasado
        res = parse_trends(df, today=date(2026, 3, 1))
        self.assertEqual(res.rows[1]["date"], date(2025, 11, 5))

    def test_import_flow_detects_both_files(self):
        from lives.models import AccountDay

        user = get_user_model().objects.create_user("a@b.mx", "a@b.mx", "pass12345!")
        org = Organization.objects.create(name="Afiliado", plan_code="agency", subscription_status="active")
        Membership.objects.create(user=user, organization=org, role="owner")
        brand = Brand.objects.create(organization=org, name="Cuenta afiliada")
        self.client.force_login(user)
        self.client.post(reverse("lives:import"), {"brand": brand.pk, "file": self._xlsx()})
        self.assertEqual(LiveSession.objects.filter(brand=brand).count(), 2)
        csv = '"Date","Video Views","Profile Views","Likes","Comments","Shares"\n"5 de octubre","900","1","0","0","0"\n'
        self.client.post(reverse("lives:import"), {"brand": brand.pk, "file": SimpleUploadedFile("t.csv", csv.encode())})
        self.assertEqual(AccountDay.objects.filter(brand=brand).count(), 1)
        live = LiveSession.objects.get(external_id="111")
        page = self.client.get(reverse("lives:live_detail", args=[live.pk]))
        self.assertContains(page, "Embudo de este live")
        self.assertContains(self.client.get(reverse("insights:dashboard") + "?desde=2026-10-01&hasta=2026-10-31"),
                            "Embudo del periodo")
