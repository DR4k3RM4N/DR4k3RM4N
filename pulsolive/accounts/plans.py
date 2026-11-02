"""Planes de suscripción y sus límites.

Los precios están en MXN (IVA incluido) y se muestran en la página de precios.
Para cobrar con Stripe, crea un Price por plan y pon su id en las variables
STRIPE_PRICE_CREATOR / STRIPE_PRICE_PRO / STRIPE_PRICE_AGENCY.
"""
from dataclasses import dataclass, field

UNLIMITED = 10**9


@dataclass(frozen=True)
class Plan:
    code: str
    name: str
    price_mxn: int  # mensual
    price_usd: int
    tagline: str
    max_brands: int
    max_users: int
    ai_runs_per_month: int  # reportes con IA + análisis de transcripciones
    features: frozenset = field(default_factory=frozenset)
    highlights: tuple = ()
    public: bool = True

    def has(self, feature: str) -> bool:
        return feature in self.features

    @property
    def price_yearly_mxn(self) -> int:
        return self.price_mxn * 10  # 2 meses gratis


F_AI_REPORTS = "ai_reports"
F_TRANSCRIPTS = "transcripts"
F_PLAYBOOKS = "playbooks"
F_EXPERIMENTS = "experiments"
F_WHITE_LABEL = "white_label"
F_HOST_SCORECARDS = "host_scorecards"
F_SHARE_LINKS = "share_links"
F_API = "api"

PLANS = {
    "creator": Plan(
        code="creator",
        name="Creator",
        price_mxn=699,
        price_usd=39,
        tagline="Para creadores y marcas que hacen sus propios lives.",
        max_brands=1,
        max_users=1,
        ai_runs_per_month=10,
        features=frozenset({F_AI_REPORTS, F_PLAYBOOKS}),
        highlights=(
            "1 cuenta / marca",
            "Importación ilimitada de lives",
            "Reportes diario, semanal y mensual",
            "10 análisis con IA al mes",
            "Playbook de lo que funciona",
        ),
    ),
    "pro": Plan(
        code="pro",
        name="Pro",
        price_mxn=2490,
        price_usd=139,
        tagline="Para marcas con varios hosts y equipos chicos.",
        max_brands=5,
        max_users=3,
        ai_runs_per_month=40,
        features=frozenset(
            {F_AI_REPORTS, F_PLAYBOOKS, F_TRANSCRIPTS, F_EXPERIMENTS, F_HOST_SCORECARDS}
        ),
        highlights=(
            "Hasta 5 marcas, 3 usuarios",
            "Análisis de transcripción: qué dijo el host y cuándo vendió",
            "Pruebas A/B guiadas",
            "Ranking de hosts",
            "40 análisis con IA al mes",
        ),
    ),
    "agency": Plan(
        code="agency",
        name="Agencia",
        price_mxn=6990,
        price_usd=389,
        tagline="Para agencias que operan lives de muchas marcas.",
        max_brands=20,
        max_users=10,
        ai_runs_per_month=150,
        features=frozenset(
            {
                F_AI_REPORTS,
                F_PLAYBOOKS,
                F_TRANSCRIPTS,
                F_EXPERIMENTS,
                F_HOST_SCORECARDS,
                F_WHITE_LABEL,
                F_SHARE_LINKS,
            }
        ),
        highlights=(
            "Hasta 20 marcas, 10 usuarios",
            "Reportes con tu logo y colores para tus clientes",
            "Links para compartir reportes con cada marca",
            "Todo lo de Pro",
            "150 análisis con IA al mes",
        ),
    ),
    "enterprise": Plan(
        code="enterprise",
        name="Enterprise",
        price_mxn=0,
        price_usd=0,
        tagline="Marcas ilimitadas, API, conexión directa con TikTok Shop.",
        max_brands=UNLIMITED,
        max_users=UNLIMITED,
        ai_runs_per_month=UNLIMITED,
        features=frozenset(
            {
                F_AI_REPORTS,
                F_PLAYBOOKS,
                F_TRANSCRIPTS,
                F_EXPERIMENTS,
                F_HOST_SCORECARDS,
                F_WHITE_LABEL,
                F_SHARE_LINKS,
                F_API,
            }
        ),
        highlights=(
            "Marcas y usuarios ilimitados",
            "Conexión con API de TikTok Shop",
            "Alertas en vivo",
            "Soporte dedicado",
        ),
    ),
}

TRIAL_DAYS = 14
TRIAL_PLAN = "pro"  # durante la prueba se desbloquea Pro

FEATURE_LABELS = {
    F_AI_REPORTS: "Reportes con IA",
    F_TRANSCRIPTS: "Análisis de transcripciones",
    F_PLAYBOOKS: "Playbooks",
    F_EXPERIMENTS: "Pruebas A/B",
    F_WHITE_LABEL: "Reportes con tu marca",
    F_HOST_SCORECARDS: "Ranking de hosts",
    F_SHARE_LINKS: "Links para compartir",
    F_API: "API",
}


def get_plan(code: str) -> Plan:
    return PLANS.get(code, PLANS["creator"])


def minimum_plan_for(feature: str) -> Plan:
    for code in ("creator", "pro", "agency", "enterprise"):
        if PLANS[code].has(feature):
            return PLANS[code]
    return PLANS["enterprise"]
