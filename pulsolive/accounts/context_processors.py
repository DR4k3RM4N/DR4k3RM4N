from .plans import FEATURE_LABELS


def organization(request):
    org = getattr(request, "org", None)
    ctx = {"org": org, "membership": getattr(request, "membership", None), "feature_labels": FEATURE_LABELS}
    if org is not None:
        ctx["org_plan"] = org.plan
        ctx["user_orgs"] = [m.organization for m in request.user.memberships.select_related("organization")]
    return ctx
