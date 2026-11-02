from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from .plans import FEATURE_LABELS, minimum_plan_for


def org_required(view=None, *, edit=False, manage=False, active=True):
    """Exige usuario con organización. Opcionalmente permisos y suscripción vigente."""

    def decorator(fn):
        @login_required
        @wraps(fn)
        def wrapper(request, *args, **kwargs):
            if request.org is None:
                return redirect("accounts:onboarding")
            if edit and not request.membership.can_edit:
                raise PermissionDenied("Tu rol es de solo lectura.")
            if manage and not request.membership.can_manage:
                raise PermissionDenied("Solo administradores.")
            if active and not request.org.is_active:
                messages.warning(request, "Tu suscripción no está activa. Elige un plan para seguir usando PulsoLive.")
                return redirect("accounts:billing")
            return fn(request, *args, **kwargs)

        return wrapper

    return decorator(view) if view else decorator


def feature_required(feature):
    def decorator(fn):
        @wraps(fn)
        def wrapper(request, *args, **kwargs):
            if not request.org.has_feature(feature):
                plan = minimum_plan_for(feature)
                messages.info(
                    request,
                    f"«{FEATURE_LABELS.get(feature, feature)}» está disponible desde el plan {plan.name}.",
                )
                return redirect("accounts:billing")
            return fn(request, *args, **kwargs)

        return wrapper

    return decorator
