from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("precios/", views.pricing, name="pricing"),
    path("registro/", views.signup, name="signup"),
    path("entrar/", auth_views.LoginView.as_view(template_name="accounts/login.html"), name="login"),
    path("salir/", auth_views.LogoutView.as_view(), name="logout"),
    path("recuperar/", auth_views.PasswordResetView.as_view(
        template_name="accounts/password_reset.html",
        success_url="/recuperar/enviado/"), name="password_reset"),
    path("recuperar/enviado/", auth_views.PasswordResetDoneView.as_view(
        template_name="accounts/password_reset_done.html"), name="password_reset_done"),
    path("recuperar/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="accounts/password_reset_confirm.html",
        success_url="/entrar/"), name="password_reset_confirm"),
    path("bienvenida/", views.onboarding, name="onboarding"),
    path("cuenta/", views.org_settings, name="settings"),
    path("cuenta/equipo/", views.team, name="team"),
    path("cuenta/equipo/<int:membership_id>/quitar/", views.remove_member, name="remove_member"),
    path("cuenta/cambiar/<int:org_id>/", views.switch_org, name="switch_org"),
    path("cuenta/plan/", views.billing_view, name="billing"),
    path("cuenta/plan/<str:plan_code>/elegir/", views.choose_plan, name="choose_plan"),
    path("cuenta/plan/portal/", views.billing_portal, name="billing_portal"),
    path("invitacion/<str:token>/", views.accept_invitation, name="accept_invitation"),
    path("stripe/webhook/", views.stripe_webhook, name="stripe_webhook"),
]
