from .models import Membership


class CurrentOrganizationMiddleware:
    """Pone request.org y request.membership para el usuario autenticado.

    Si el usuario pertenece a varias organizaciones, la activa se guarda en
    la sesión (ver accounts.views.switch_org).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.org = None
        request.membership = None
        if request.user.is_authenticated:
            qs = Membership.objects.select_related("organization").filter(user=request.user)
            org_id = request.session.get("org_id")
            membership = (qs.filter(organization_id=org_id).first() if org_id else None) or qs.order_by("created_at").first()
            if membership:
                request.membership = membership
                request.org = membership.organization
        return self.get_response(request)
