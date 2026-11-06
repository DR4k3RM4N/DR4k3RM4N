"""Motor de análisis de PulsoLive.

Recibe lives (como diccionarios) y responde:
  * ¿Qué factores se asocian con vender más? (hora, día, host, género,
    estilo, promoción, guion, formato, duración, etiquetas…)
  * ¿Cuánto pesa cada factor cuando controlamos por los demás? (regresión)
  * ¿Qué momentos dentro del live dispararon pedidos? (minuto a minuto)
  * ¿Qué conviene repetir y qué corregir? (recomendaciones)

Todo es estadística sencilla y explicable a propósito: el usuario tiene que
poder confiar en las conclusiones y entender por qué se las damos. Siempre
reportamos el tamaño de muestra y un nivel de confianza; con pocos lives
lo decimos en lugar de inventar patrones.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from statistics import mean, median

import numpy as np
import pandas as pd

WEEKDAYS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

DAYPARTS = [
    (0, 6, "Madrugada (0–6 h)"),
    (6, 12, "Mañana (6–12 h)"),
    (12, 15, "Mediodía (12–15 h)"),
    (15, 19, "Tarde (15–19 h)"),
    (19, 22, "Noche (19–22 h)"),
    (22, 24, "Noche tarde (22–24 h)"),
]

DURATION_BUCKETS = [
    (0, 60, "Menos de 1 h"),
    (60, 120, "1 a 2 h"),
    (120, 180, "2 a 3 h"),
    (180, 10**6, "3 h o más"),
]

METRICS = {
    "gmv_per_hour": "ventas por hora",
    "conversion_rate": "conversión",
    "gmv": "ventas",
    "orders": "pedidos",
    "avg_watch_seconds": "tiempo de visualización",
}

# Embudo del live: (clave, nombre del paso, numerador, denominador, qué hacer cuando es el paso débil)
FUNNEL = [
    ("entry_rate", "Entraron al live", "viewers", "impressions",
     "Pocos entran cuando ven el live en el feed: cuida la portada y el título, abre con el producto y la oferta "
     "en pantalla y transmite cuando tus videos ya están jalando gente."),
    ("product_ctr", "Dieron clic en un producto", "product_clicks", "viewers",
     "Entran pero no abren los productos: fija el producto en pantalla, pide el clic al carrito con frecuencia "
     "y muestra el producto en uso desde el primer minuto."),
    ("click_to_order", "Compraron después del clic", "orders", "product_clicks",
     "Abren el producto pero no compran: revisa precio, envío y reseñas; usa precio ancla, urgencia real "
     "(tiempo o piezas) y responde las dudas en voz alta."),
]

# (columna, etiqueta legible, ¿es atributo del host?)
FACTORS = [
    ("daypart", "Horario", False),
    ("weekday", "Día de la semana", False),
    ("host", "Host", True),
    ("host_gender", "Género del host", True),
    ("host_style", "Estilo del host", True),
    ("host_experience", "Experiencia del host", True),
    ("promo_type", "Promoción", False),
    ("script_type", "Tipo de guion", False),
    ("format", "Formato", False),
    ("setting", "Escenario", False),
    ("duration_bucket", "Duración", False),
    ("product_category", "Categoría de producto", False),
    ("video_day", "Videos de la cuenta ese día", False),
]

MIN_N = 3  # mínimo de lives por grupo para opinar


# ---------------------------------------------------------------------------
# Utilidades estadísticas
# ---------------------------------------------------------------------------

def _norm_cdf(x: float) -> float:
    return 0.5 * math.erfc(-x / math.sqrt(2))


def welch_p_value(a: list[float], b: list[float]) -> float | None:
    """p-value bilateral aproximado de la prueba t de Welch (sin scipy)."""
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return None
    va, vb = float(np.var(a, ddof=1)), float(np.var(b, ddof=1))
    se2 = va / na + vb / nb
    if se2 <= 0:
        return 0.0 if mean(a) != mean(b) else 1.0
    t = abs(mean(a) - mean(b)) / math.sqrt(se2)
    df_num = se2**2
    df_den = (va / na) ** 2 / (na - 1) + (vb / nb) ** 2 / (nb - 1)
    df = df_num / df_den if df_den > 0 else na + nb - 2
    # Aproximación de la t de Student a la normal (buena para df >= 2)
    z = t * (1 - 1 / (4 * df)) / math.sqrt(1 + t**2 / (2 * df))
    return max(0.0, min(1.0, 2 * (1 - _norm_cdf(z))))


def confidence_label(n: int, p: float | None) -> str:
    if n < MIN_N or p is None:
        return "baja"
    if n >= 6 and p < 0.05:
        return "alta"
    if n >= 4 and p < 0.2:
        return "media"
    return "baja"


def pct(x: float) -> str:
    return f"{x * 100:+.0f}%"


def money(x: float) -> str:
    return f"${x:,.0f}"


# ---------------------------------------------------------------------------
# Normalización de datos
# ---------------------------------------------------------------------------

def daypart_of(hour: int) -> str:
    for lo, hi, label in DAYPARTS:
        if lo <= hour < hi:
            return label
    return DAYPARTS[-1][2]


def duration_bucket_of(minutes: int) -> str:
    for lo, hi, label in DURATION_BUCKETS:
        if lo <= minutes < hi:
            return label
    return DURATION_BUCKETS[-1][2]


def build_frame(rows: list[dict]) -> pd.DataFrame:
    """rows: dicts con las llaves de `lives.services.live_to_row`."""
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["started_at"] = pd.to_datetime(df["started_at"])
    df["hour"] = df["started_at"].dt.hour
    df["weekday_idx"] = df["started_at"].dt.weekday
    df["weekday"] = df["weekday_idx"].map(lambda i: WEEKDAYS[i])
    df["daypart"] = df["hour"].map(daypart_of)
    df["duration_bucket"] = df["duration_minutes"].map(duration_bucket_of)
    hours = df["duration_minutes"].clip(lower=1) / 60
    df["gmv"] = df["gmv"].astype(float)
    df["gmv_per_hour"] = df["gmv"] / hours
    df["conversion_rate"] = np.where(df["viewers"] > 0, df["orders"] / df["viewers"].replace(0, 1), 0.0)
    df["aov"] = np.where(df["orders"] > 0, df["gmv"] / df["orders"].replace(0, 1), 0.0)
    df["click_rate"] = np.where(df["viewers"] > 0, df["product_clicks"] / df["viewers"].replace(0, 1), 0.0)
    for col in ("impressions", "product_impressions", "customers", "video_views_day"):
        if col not in df:
            df[col] = 0
    # Tasas del embudo; NaN cuando el paso anterior no tiene datos (no es lo mismo que cero).
    for key, _, num, den, _ in FUNNEL:
        df[key] = np.where(df[den] > 0, df[num] / df[den].where(df[den] > 0, 1), np.nan)
    df["video_day"] = video_day_labels(df)
    for col, _, _ in FACTORS:
        if col not in df:
            df[col] = ""
        df[col] = df[col].fillna("").astype(str)
    if "tags" not in df:
        df["tags"] = [[] for _ in range(len(df))]
    return df


def video_day_labels(df: pd.DataFrame) -> pd.Series:
    """Marca los lives hechos en días en que los videos de la cuenta tuvieron muchas vistas (25% más alto)."""
    views = df.get("video_views_day")
    if views is None or (views > 0).sum() < 6:
        return pd.Series([""] * len(df), index=df.index)
    cut = float(views[views > 0].quantile(0.75))
    return views.map(lambda v: "Día con videos fuertes" if v >= cut and v > 0 else "Día normal")


def funnel(df: pd.DataFrame) -> dict | None:
    """Embudo agregado del periodo: tasas de cada paso y el paso más débil frente a los mejores lives."""
    if df.empty or df["impressions"].sum() == 0:
        return None
    steps = []
    for key, label, num, den, advice in FUNNEL:
        total_den = float(df[den].sum())
        rate = float(df[num].sum()) / total_den if total_den else None
        rates = df[key].dropna()
        top = float(rates.quantile(0.75)) if len(rates) >= 4 else None
        steps.append({"key": key, "label": label, "rate": rate, "top": top, "advice": advice,
                      "count": int(df[num].sum()), "base": int(total_den),
                      "gap": (rate / top - 1) if rate is not None and top else None})
    weak = min((s for s in steps if s["gap"] is not None), key=lambda s: s["gap"], default=None)
    return {"impressions": int(df["impressions"].sum()), "steps": steps,
            "weakest": weak["key"] if weak and weak["gap"] < -0.15 else None}


def live_funnel(live_row: dict, peers: pd.DataFrame) -> list[dict]:
    """Embudo de un live contra la mediana de los demás lives de la marca."""
    out = []
    for key, label, num, den, advice in FUNNEL:
        den_v = live_row.get(den) or 0
        rate = (live_row.get(num) or 0) / den_v if den_v else None
        med = float(peers[key].dropna().median()) if not peers.empty and peers[key].notna().any() else None
        out.append({"key": key, "label": label, "rate": rate, "median": med, "advice": advice,
                    "count": live_row.get(num) or 0, "base": den_v,
                    "delta": (rate / med - 1) if rate is not None and med else None})
    return out


# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------

def kpis(df: pd.DataFrame) -> dict:
    if df.empty:
        return {
            "lives": 0, "gmv": 0.0, "orders": 0, "hours": 0.0, "viewers": 0,
            "gmv_per_hour": 0.0, "conversion_rate": 0.0, "aov": 0.0, "avg_watch_seconds": 0.0,
            "new_followers": 0,
        }
    hours = float(df["duration_minutes"].sum()) / 60
    gmv = float(df["gmv"].sum())
    orders = int(df["orders"].sum())
    viewers = int(df["viewers"].sum())
    return {
        "lives": int(len(df)),
        "gmv": gmv,
        "orders": orders,
        "hours": round(hours, 1),
        "viewers": viewers,
        "gmv_per_hour": gmv / hours if hours else 0.0,
        "conversion_rate": orders / viewers if viewers else 0.0,
        "aov": gmv / orders if orders else 0.0,
        "avg_watch_seconds": float(df["avg_watch_seconds"].mean()),
        "new_followers": int(df["new_followers"].sum()),
    }


def compare_kpis(current: dict, previous: dict) -> dict:
    out = {}
    for key, value in current.items():
        prev = previous.get(key) or 0
        out[key] = {"value": value, "previous": prev, "delta": (value - prev) / prev if prev else None}
    return out


# ---------------------------------------------------------------------------
# Análisis por factor
# ---------------------------------------------------------------------------

@dataclass
class LevelStat:
    level: str
    n: int
    mean: float
    median: float
    lift: float
    p_value: float | None
    confidence: str
    adjusted_lift: float | None = None
    conversion_rate: float = 0.0
    avg_watch_seconds: float = 0.0

    def as_dict(self):
        return self.__dict__.copy()


@dataclass
class FactorResult:
    key: str
    label: str
    importance: float  # 0..1, varianza explicada (eta²)
    levels: list[LevelStat] = field(default_factory=list)

    def as_dict(self):
        return {
            "key": self.key,
            "label": self.label,
            "importance": self.importance,
            "levels": [lv.as_dict() for lv in self.levels],
        }

    @property
    def best(self) -> LevelStat | None:
        candidates = [lv for lv in self.levels if lv.n >= MIN_N]
        return max(candidates, key=lambda lv: lv.mean) if candidates else None

    @property
    def worst(self) -> LevelStat | None:
        candidates = [lv for lv in self.levels if lv.n >= MIN_N]
        return min(candidates, key=lambda lv: lv.mean) if candidates else None


def _eta_squared(values: np.ndarray, groups: pd.Series) -> float:
    if len(values) < 3:
        return 0.0
    grand = values.mean()
    ss_total = float(((values - grand) ** 2).sum())
    if ss_total == 0:
        return 0.0
    ss_between = 0.0
    for _, idx in groups.groupby(groups).groups.items():
        g = values[groups.index.get_indexer(idx)]
        ss_between += len(g) * (g.mean() - grand) ** 2
    # Corrección por número de grupos (evita que factores con muchos niveles "ganen" por azar)
    k = groups.nunique()
    n = len(values)
    eta = ss_between / ss_total
    adj = 1 - (1 - eta) * (n - 1) / max(n - k, 1)
    return float(max(0.0, min(1.0, adj)))


def factor_analysis(df: pd.DataFrame, metric: str = "gmv_per_hour") -> list[FactorResult]:
    if df.empty or len(df) < 2:
        return []
    overall = float(df[metric].mean()) or 1e-9
    log_metric = np.log1p(df[metric].clip(lower=0).to_numpy(dtype=float))
    adjusted = adjusted_effects(df, metric)
    results: list[FactorResult] = []

    factor_cols = [(c, lbl) for c, lbl, _ in FACTORS]
    # Etiquetas libres como factores sí/no
    tag_counts = defaultdict(int)
    for tags in df["tags"]:
        for t in tags:
            tag_counts[t] += 1
    tag_cols = []
    for tag, count in tag_counts.items():
        if count >= 2 and count <= len(df) - 2:
            col = f"tag::{tag}"
            df[col] = df["tags"].map(lambda ts, t=tag: "Con #" + t if t in ts else "Sin #" + t)
            tag_cols.append((col, f"Etiqueta #{tag}"))

    for col, label in factor_cols + tag_cols:
        series = df[col]
        mask = series != ""
        if series[mask].nunique() < 2:
            continue
        sub = df[mask]
        sub_log = log_metric[mask.to_numpy()]
        levels = []
        for level, g in sub.groupby(col):
            rest_log = sub_log[(sub[col] != level).to_numpy()]
            in_log = sub_log[(sub[col] == level).to_numpy()]
            p = welch_p_value(list(in_log), list(rest_log))
            m = float(g[metric].mean())
            levels.append(
                LevelStat(
                    level=str(level),
                    n=int(len(g)),
                    mean=m,
                    median=float(g[metric].median()),
                    lift=m / overall - 1,
                    p_value=p,
                    confidence=confidence_label(len(g), p),
                    adjusted_lift=adjusted.get((col, str(level))),
                    conversion_rate=float(g["conversion_rate"].mean()),
                    avg_watch_seconds=float(g["avg_watch_seconds"].mean()),
                )
            )
        levels.sort(key=lambda lv: lv.mean, reverse=True)
        importance = _eta_squared(sub_log, sub[col].reset_index(drop=True).set_axis(range(len(sub))))
        results.append(FactorResult(key=col, label=label, importance=importance, levels=levels))

    results.sort(key=lambda r: r.importance, reverse=True)
    return results


def _ridge_effects(df: pd.DataFrame, cols: list[str], metric: str, alpha: float) -> dict:
    X = pd.get_dummies(df[cols].replace("", "(sin dato)"), prefix_sep="=::=", dtype=float)
    y = np.log1p(df[metric].clip(lower=0).to_numpy(dtype=float))
    Xc = X.to_numpy() - X.to_numpy().mean(axis=0)
    yc = y - y.mean()
    beta = np.linalg.solve(Xc.T @ Xc + alpha * np.eye(Xc.shape[1]), Xc.T @ yc)
    by_col = defaultdict(list)
    for name, b in zip(X.columns, beta):
        col, level = name.split("=::=", 1)
        by_col[col].append((level, float(b)))
    out = {}
    for col, items in by_col.items():
        # Efectos relativos al promedio de los niveles del factor
        avg = mean(b for _, b in items)
        for level, b in items:
            out[(col, level)] = float(math.expm1(b - avg))
    return out


HOST_ATTRS = ("host_gender", "host_style", "host_experience")


def adjusted_effects(df: pd.DataFrame, metric: str = "gmv_per_hour", alpha: float = 2.0) -> dict:
    """Regresión ridge sobre log(métrica) con todos los factores a la vez.

    Devuelve {(columna, nivel): efecto %} = cuánto cambia la métrica por estar
    en ese nivel, *manteniendo constante lo demás*. Esto separa, por ejemplo,
    "la host vende más" de "a la host le tocan siempre los mejores horarios".

    El host y sus atributos (género, estilo, experiencia) son casi la misma
    información, así que se estiman en dos modelos separados para que no se
    "repartan" el efecto entre sí.
    """
    if len(df) < 8:
        return {}
    usable = [c for c, _, _ in FACTORS if c in df and df[c].replace("", np.nan).nunique() >= 2]
    base = [c for c in usable if c != "host" and c not in HOST_ATTRS]
    effects = {}
    model_a = base + (["host"] if "host" in usable else [])
    if model_a:
        effects.update(_ridge_effects(df, model_a, metric, alpha))
    attrs = [c for c in HOST_ATTRS if c in usable]
    for attr in attrs:
        res = _ridge_effects(df, base + [attr], metric, alpha)
        effects.update({k: v for k, v in res.items() if k[0] == attr})
    return effects


# ---------------------------------------------------------------------------
# Mapa de calor día × hora
# ---------------------------------------------------------------------------

def heatmap(df: pd.DataFrame, metric: str = "gmv_per_hour") -> dict:
    grid = [[None for _ in range(24)] for _ in range(7)]
    counts = [[0 for _ in range(24)] for _ in range(7)]
    if not df.empty:
        for (wd, hr), g in df.groupby(["weekday_idx", "hour"]):
            grid[int(wd)][int(hr)] = float(g[metric].mean())
            counts[int(wd)][int(hr)] = int(len(g))
    return {"weekdays": WEEKDAYS, "values": grid, "counts": counts}


def best_slots(df: pd.DataFrame, metric: str = "gmv_per_hour", top: int = 5) -> list[dict]:
    """Mejores combinaciones día + franja horaria con suficiente evidencia."""
    if df.empty:
        return []
    overall = float(df[metric].mean()) or 1e-9
    slots = []
    for (wd, dp), g in df.groupby(["weekday_idx", "daypart"]):
        if len(g) < 2:
            continue
        m = float(g[metric].mean())
        slots.append({"weekday": WEEKDAYS[int(wd)], "weekday_idx": int(wd), "daypart": dp, "n": int(len(g)),
                      "mean": m, "lift": m / overall - 1})
    slots.sort(key=lambda s: s["mean"], reverse=True)
    return slots[:top]


# ---------------------------------------------------------------------------
# Momentos dentro del live (minuto a minuto + eventos)
# ---------------------------------------------------------------------------

def moments_for_live(minutes: list[dict], events: list[dict], window: int = 5) -> dict:
    """minutes: [{minute, orders, viewers, gmv}], events: [{minute, kind, label}]."""
    if not minutes:
        return {"spikes": [], "event_impacts": [], "drops": []}
    s = pd.DataFrame(minutes).sort_values("minute").set_index("minute")
    full = s.reindex(range(int(s.index.min()), int(s.index.max()) + 1), fill_value=0)
    orders = full["orders"].astype(float)
    viewers = full["viewers"].astype(float)

    impacts = []
    for ev in events:
        m = int(ev["minute"])
        before = orders.loc[max(orders.index.min(), m - window): m - 1]
        after = orders.loc[m: m + window - 1]
        if len(before) < 2 or len(after) < 2:
            continue
        b, a = float(before.mean()), float(after.mean())
        impacts.append({**ev, "orders_before": b, "orders_after": a,
                        "uplift": (a - b) / b if b > 0 else (1.0 if a > 0 else 0.0)})

    # Picos: minutos con pedidos muy por encima del promedio móvil
    baseline = orders.rolling(10, min_periods=3).median().shift(1)
    spread = orders.rolling(10, min_periods=3).std().shift(1).fillna(0)
    spikes = []
    for minute, value in orders.items():
        base = baseline.get(minute)
        if pd.isna(base):
            continue
        sd = max(float(spread.get(minute, 0) or 0), math.sqrt(max(base, 0)), 1.0)
        if value >= max(4, base * 2.5, base + 3 * sd):
            near = [e for e in events if 0 <= minute - int(e["minute"]) <= 3]
            spikes.append({"minute": int(minute), "orders": int(value), "baseline": float(base),
                           "ratio": float(value / max(base, 0.5)), "cause": near[-1] if near else None})
    # Solo los picos más fuertes, en orden cronológico
    spikes = sorted(sorted(spikes, key=lambda x: x["ratio"], reverse=True)[:8], key=lambda x: x["minute"])

    # Caídas fuertes de audiencia (se fue la gente)
    drops = []
    roll = viewers.rolling(3, min_periods=1).mean()
    for minute in viewers.index[5:]:
        prev = roll.get(minute - 5)
        cur = roll.get(minute)
        if prev and prev > 20 and cur < prev * 0.7:
            if not drops or minute - drops[-1]["minute"] > 5:
                near = [e for e in events if 0 <= minute - int(e["minute"]) <= 5]
                drops.append({"minute": int(minute), "from": float(prev), "to": float(cur),
                              "cause": near[-1] if near else None})
    return {"spikes": spikes, "event_impacts": impacts, "drops": drops}


def event_effects(per_live_impacts: list[list[dict]]) -> list[dict]:
    """Agrega el impacto de cada tipo de evento a través de muchos lives."""
    by_kind = defaultdict(list)
    labels = {}
    for impacts in per_live_impacts:
        for imp in impacts:
            by_kind[imp["kind"]].append(imp["uplift"])
            labels[imp["kind"]] = imp.get("label", imp["kind"])
    out = []
    for kind, ups in by_kind.items():
        capped = [max(-1.0, min(u, 5.0)) for u in ups]
        out.append({"kind": kind, "label": labels[kind], "n": len(ups), "avg_uplift": mean(capped),
                    "median_uplift": median(capped),
                    "positive_share": sum(1 for u in ups if u > 0) / len(ups),
                    "confidence": "alta" if len(ups) >= 10 else "media" if len(ups) >= 4 else "baja"})
    out.sort(key=lambda r: r["median_uplift"], reverse=True)
    return out


# ---------------------------------------------------------------------------
# Hosts
# ---------------------------------------------------------------------------

def host_scorecards(df: pd.DataFrame) -> list[dict]:
    if df.empty or "host" not in df:
        return []
    team = {
        "gmv_per_hour": float(df["gmv_per_hour"].mean()) or 1e-9,
        "conversion_rate": float(df["conversion_rate"].mean()) or 1e-9,
        "avg_watch_seconds": float(df["avg_watch_seconds"].mean()) or 1e-9,
        "aov": float(df["aov"].mean()) or 1e-9,
    }
    cards = []
    for host, g in df[df["host"] != ""].groupby("host"):
        stats = {k: float(g[k].mean()) for k in team}
        rel = {k: stats[k] / team[k] - 1 for k in team}
        strengths = [k for k, v in rel.items() if v >= 0.15]
        weaknesses = [k for k, v in rel.items() if v <= -0.15]
        best_daypart = g.groupby("daypart")["gmv_per_hour"].mean().sort_values(ascending=False)
        cards.append({
            "host": host,
            "lives": int(len(g)),
            "gmv": float(g["gmv"].sum()),
            **stats,
            "relative": rel,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "best_daypart": best_daypart.index[0] if len(best_daypart) else "",
            "coaching": _host_coaching(rel),
            "enough_data": len(g) >= MIN_N,
        })
    cards.sort(key=lambda c: c["gmv_per_hour"], reverse=True)
    for i, c in enumerate(cards, 1):
        c["rank"] = i
    return cards


def _host_coaching(rel: dict) -> list[str]:
    tips = []
    if rel["avg_watch_seconds"] <= -0.15:
        tips.append("La gente se va rápido: trabaja el gancho de los primeros 30 segundos y repite cada 5–10 min "
                    "qué se está vendiendo y por qué quedarse.")
    if rel["conversion_rate"] <= -0.15 and rel["avg_watch_seconds"] > -0.15:
        tips.append("Retiene pero no cierra: más llamadas a la acción directas ('da clic en el carrito naranja'), "
                    "mostrar precio y beneficio juntos, y usar urgencia real.")
    if rel["aov"] <= -0.15:
        tips.append("Ticket bajo: ofrecer paquetes, 2x1 o 'agrega el complemento' para subir el valor por pedido.")
    if not tips and rel["gmv_per_hour"] >= 0.15:
        tips.append("Está arriba del equipo: documenta su guion y usa sus lives como ejemplo para capacitar a otros.")
    return tips


# ---------------------------------------------------------------------------
# Experimentos A/B
# ---------------------------------------------------------------------------

def evaluate_experiment(a_values: list[float], b_values: list[float], target: int) -> dict:
    res = {
        "n_a": len(a_values), "n_b": len(b_values),
        "mean_a": mean(a_values) if a_values else 0.0,
        "mean_b": mean(b_values) if b_values else 0.0,
        "p_value": None, "lift_b_vs_a": None, "winner": None, "status": "",
    }
    if a_values and b_values and res["mean_a"]:
        res["lift_b_vs_a"] = res["mean_b"] / res["mean_a"] - 1
    p = welch_p_value([math.log1p(max(v, 0)) for v in a_values], [math.log1p(max(v, 0)) for v in b_values])
    res["p_value"] = p
    if len(a_values) < target or len(b_values) < target:
        res["status"] = (f"Faltan lives: llevas {len(a_values)} de A y {len(b_values)} de B "
                         f"(meta {target} de cada una).")
    elif p is not None and p < 0.1:
        res["winner"] = "B" if res["mean_b"] > res["mean_a"] else "A"
        res["status"] = f"Ganó la variante {res['winner']} con confianza razonable (p={p:.2f})."
    else:
        res["status"] = ("Sin diferencia clara todavía. Puedes seguir la prueba unos lives más o quedarte con la "
                         "opción más barata/fácil de operar.")
    return res


# ---------------------------------------------------------------------------
# Recomendaciones
# ---------------------------------------------------------------------------

@dataclass
class Recommendation:
    title: str
    detail: str
    kind: str  # "repetir" | "corregir" | "probar" | "datos"
    priority: int  # 1 = más importante
    evidence: str = ""

    def as_dict(self):
        return self.__dict__.copy()


def _level_sentence(lv: LevelStat, metric_label: str) -> str:
    adj = ""
    if lv.adjusted_lift is not None:
        adj = f"; controlando lo demás, {pct(lv.adjusted_lift)}"
    return f"{pct(lv.lift)} de {metric_label} vs. el promedio ({lv.n} lives, confianza {lv.confidence}{adj})"


def recommendations(df: pd.DataFrame, factors: list[FactorResult], events: list[dict],
                    hosts: list[dict], metric: str = "gmv_per_hour") -> list[Recommendation]:
    recs: list[Recommendation] = []
    metric_label = METRICS.get(metric, metric)
    if df.empty:
        return [Recommendation("Importa tus primeros lives",
                               "Sube el archivo de TikTok Shop / LIVE Center para empezar el análisis.", "datos", 1)]

    n = len(df)
    if n < 10:
        recs.append(Recommendation(
            "Todavía hay pocos lives para conclusiones firmes",
            f"Llevas {n} lives. Con 20–30 lives etiquetados los patrones se vuelven confiables. Mientras tanto, "
            "trata las sugerencias como hipótesis para probar.", "datos", 1))

    by_key = {f.key: f for f in factors}

    def add_best_worst(key, repeat_tpl, fix_tpl, prio):
        f = by_key.get(key)
        if not f:
            return
        best, worst = f.best, f.worst
        if best and best.lift > 0.1 and best.confidence != "baja":
            recs.append(Recommendation(repeat_tpl.format(level=best.level), _level_sentence(best, metric_label),
                                       "repetir", prio, f.label))
        if worst and best and worst.level != best.level and worst.lift < -0.15 and worst.confidence != "baja":
            recs.append(Recommendation(fix_tpl.format(level=worst.level), _level_sentence(worst, metric_label),
                                       "corregir", prio + 1, f.label))

    add_best_worst("daypart", "Programa más lives en «{level}»", "Reduce o replantea los lives en «{level}»", 2)
    add_best_worst("weekday", "Prioriza los {level}", "Los {level} rinden poco: úsalos para pruebas o contenido", 3)
    add_best_worst("promo_type", "La promoción que mejor funciona: «{level}»",
                   "«{level}» no está empujando ventas: cámbiala o pruébala contra otra", 2)
    add_best_worst("script_type", "Repite el guion tipo «{level}»", "El guion «{level}» rinde por debajo", 3)
    add_best_worst("duration_bucket", "Duración que más rinde por hora: {level}",
                   "Los lives de {level} pierden rendimiento por hora", 4)
    add_best_worst("format", "Formato ganador: {level}", "El formato «{level}» rinde menos", 4)
    add_best_worst("setting", "Mejor escenario: {level}", "El escenario «{level}» rinde menos", 5)

    gender = by_key.get("host_gender")
    if gender and gender.best and gender.best.confidence != "baja" and gender.best.lift > 0.1:
        adj = gender.best.adjusted_lift
        note = ""
        if adj is not None and abs(adj) < abs(gender.best.lift) / 2:
            note = (" Ojo: al controlar horario, promoción y guion, la diferencia se reduce mucho; probablemente "
                    "se explica por esos factores y no por el género.")
        recs.append(Recommendation(
            f"Con esta audiencia rinden mejor los lives con host «{gender.best.level}»",
            _level_sentence(gender.best, metric_label) + "." + note +
            " Úsalo como dato de audiencia, combinado con estilo y experiencia del host, no como regla.",
            "probar", 5, gender.label))

    # Eventos que disparan pedidos
    good_events = [e for e in events if e["median_uplift"] > 0.2 and e["n"] >= 3]
    for e in good_events[:3]:
        recs.append(Recommendation(
            f"Repite: {e['label'].lower()}",
            f"Después de este momento los pedidos suben en mediana {pct(e['median_uplift'])} en los siguientes 5 "
            f"minutos ({e['n']} veces observado, {e['positive_share']*100:.0f}% de las veces subió). Agéndalo en el "
            "guion cada 15–20 minutos.", "repetir", 2, "Momentos del live"))
    bad_events = [e for e in events if e["median_uplift"] < -0.15 and e["n"] >= 3]
    for e in bad_events[:2]:
        recs.append(Recommendation(
            f"Cuidado con: {e['label'].lower()}",
            f"Después de este momento los pedidos bajan en mediana {pct(e['median_uplift'])}. Revisa cómo se está "
            "haciendo o haz la transición más rápida.", "corregir", 3, "Momentos del live"))

    # Diagnóstico del embudo
    k = kpis(df)
    avg_watch = k["avg_watch_seconds"]
    if avg_watch and avg_watch < 45:
        recs.append(Recommendation(
            "Mejora la retención en los primeros segundos",
            f"El tiempo promedio de visualización es {avg_watch:.0f} s. Abre con el beneficio principal y el precio, "
            "no con saludos largos; repite el gancho cada vez que entra mucha gente.", "corregir", 2, "Embudo"))
    if k["conversion_rate"] and k["conversion_rate"] < 0.01 and k["viewers"] > 1000:
        recs.append(Recommendation(
            "Tienes audiencia pero poca conversión",
            f"Solo {k['conversion_rate']*100:.2f}% de los espectadores compra. Prueba precio ancla + descuento, "
            "llamadas a la acción explícitas y fijar el producto en pantalla.", "corregir", 2, "Embudo"))

    # Embudo: el paso donde más se pierde la venta
    fn = funnel(df)
    if fn and fn["weakest"]:
        st = next(x for x in fn["steps"] if x["key"] == fn["weakest"])
        recs.append(Recommendation(
            f"Donde más se pierde la venta: «{st['label'].lower()}»",
            f"Solo {st['rate']*100:.1f}% en este paso; tus mejores lives llegan a {st['top']*100:.1f}%. " + st["advice"],
            "corregir", 2, "Embudo"))

    # Hosts
    for h in hosts:
        if h["enough_data"] and h["coaching"] and h["relative"]["gmv_per_hour"] < -0.15:
            recs.append(Recommendation(f"Coaching para {h['host']}", " ".join(h["coaching"]), "corregir", 3,
                                       "Hosts"))
    top = [h for h in hosts if h["enough_data"]]
    if len(top) >= 2 and top[0]["relative"]["gmv_per_hour"] > 0.2:
        recs.append(Recommendation(
            f"Clona lo que hace {top[0]['host']}",
            f"Vende {pct(top[0]['relative']['gmv_per_hour'])} por hora vs. el equipo. Su mejor franja es "
            f"{top[0]['best_daypart'].lower()}. Graba y comparte sus mejores momentos con el resto.", "repetir", 3,
            "Hosts"))

    # Datos faltantes
    untagged = int(((df["host"] == "") | (df["script_type"] == "")).sum())
    if untagged / n > 0.3:
        recs.append(Recommendation(
            "Etiqueta tus lives para análisis más finos",
            f"{untagged} de {n} lives no tienen host o tipo de guion. Toma 30 segundos por live y desbloquea el "
            "análisis de qué hizo la diferencia.", "datos", 4, "Calidad de datos"))
    if "has_minutes" in df and df["has_minutes"].sum() == 0:
        recs.append(Recommendation(
            "Sube datos minuto a minuto o la transcripción",
            "Así podemos decirte qué momento exacto del live disparó las ventas.", "datos", 5, "Calidad de datos"))

    # Sugerencia de prueba si un factor importante tiene poca evidencia
    for f in factors[:4]:
        thin = [lv for lv in f.levels if lv.n < MIN_N]
        if thin and len(recs) < 14:
            recs.append(Recommendation(
                f"Prueba más «{thin[0].level}» ({f.label.lower()})",
                f"Solo hay {thin[0].n} live(s) así; no alcanza para saber si funciona. Agenda 3–4 para comparar.",
                "probar", 6, f.label))
            break

    recs.sort(key=lambda r: r.priority)
    return recs


# ---------------------------------------------------------------------------
# Playbook
# ---------------------------------------------------------------------------

def playbook(df: pd.DataFrame, factors: list[FactorResult], events: list[dict], metric="gmv_per_hour") -> dict:
    """La "receta" del live ideal según los datos de la marca."""
    recipe = []
    for f in factors:
        if f.key.startswith("tag::") or f.key in ("host",):
            continue
        best = f.best
        if best and best.lift > 0.05:
            recipe.append({"factor": f.label, "choice": best.level, "lift": best.lift, "n": best.n,
                           "confidence": best.confidence, "importance": f.importance})
    good_events = [e for e in events if e["median_uplift"] > 0.1 and e["n"] >= 2]
    top_lives = df.sort_values(metric, ascending=False).head(max(3, len(df) // 5)) if not df.empty else df
    return {
        "recipe": recipe,
        "moments": good_events[:6],
        "benchmarks": {
            "top_gmv_per_hour": float(top_lives["gmv_per_hour"].mean()) if not top_lives.empty else 0.0,
            "top_conversion": float(top_lives["conversion_rate"].mean()) if not top_lives.empty else 0.0,
            "top_watch": float(top_lives["avg_watch_seconds"].mean()) if not top_lives.empty else 0.0,
            "avg_gmv_per_hour": float(df["gmv_per_hour"].mean()) if not df.empty else 0.0,
        },
        "top_live_ids": [int(i) for i in top_lives["id"].tolist()] if not top_lives.empty else [],
    }


def weekly_calendar(df: pd.DataFrame, start: datetime, metric="gmv_per_hour", days: int = 7) -> list[dict]:
    """Propone horarios para la próxima semana usando la evidencia disponible."""
    slots = best_slots(df, metric, top=50)
    by_day = defaultdict(list)
    for s in slots:
        by_day[s["weekday_idx"]].append(s)
    dayparts = factor_analysis(df, metric) if not df.empty else []
    dp = next((f for f in dayparts if f.key == "daypart"), None)
    fallback = dp.best.level if dp and dp.best else None
    plan = []
    for i in range(days):
        day = start + pd.Timedelta(days=i)
        options = by_day.get(day.weekday(), [])
        if options:
            choice = options[0]
            plan.append({"date": day.date().isoformat(), "weekday": WEEKDAYS[day.weekday()],
                         "daypart": choice["daypart"], "reason": f"{pct(choice['lift'])} vs. promedio en {choice['n']} lives",
                         "kind": "probado"})
        elif fallback:
            plan.append({"date": day.date().isoformat(), "weekday": WEEKDAYS[day.weekday()], "daypart": fallback,
                         "reason": "Mejor franja general; sin datos suficientes de este día", "kind": "explorar"})
    return plan
