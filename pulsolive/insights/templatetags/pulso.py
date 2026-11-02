from django import template

register = template.Library()


@register.filter
def money(value):
    try:
        return f"${float(value):,.0f}"
    except (TypeError, ValueError):
        return "—"


@register.filter
def signed_pct(value):
    if value is None or value == "":
        return "—"
    try:
        return f"{float(value) * 100:+.0f}%"
    except (TypeError, ValueError):
        return "—"


@register.filter
def pct(value, digits=1):
    try:
        return f"{float(value) * 100:.{int(digits)}f}%"
    except (TypeError, ValueError):
        return "—"


@register.filter
def mmss(seconds):
    try:
        s = int(float(seconds))
    except (TypeError, ValueError):
        return "—"
    return f"{s // 60}:{s % 60:02d}"


@register.filter
def lift_class(value):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return ""
    return "lift-pos" if v > 0.02 else "lift-neg" if v < -0.02 else ""


@register.filter
def get(mapping, key):
    try:
        return mapping.get(key)
    except AttributeError:
        return None


@register.filter
def bar_width(value, max_value=1):
    """Ancho en % para barras (0..100)."""
    try:
        v, m = abs(float(value)), float(max_value) or 1
    except (TypeError, ValueError):
        return 0
    return max(2, min(100, round(v / m * 100)))


@register.filter
def num(value):
    try:
        return f"{float(value):,.0f}"
    except (TypeError, ValueError):
        return "—"


@register.filter
def times100(value):
    try:
        return round(float(value) * 100)
    except (TypeError, ValueError):
        return 0
