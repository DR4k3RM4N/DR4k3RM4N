from django.urls import path

from . import views

app_name = "insights"

urlpatterns = [
    path("panel/", views.dashboard, name="dashboard"),
    path("analisis/", views.analysis, name="analysis"),
    path("ranking-hosts/", views.host_ranking, name="hosts"),
    path("playbook/", views.playbook, name="playbook"),
    path("reportes/", views.report_list, name="report_list"),
    path("reportes/<int:pk>/", views.report_detail, name="report_detail"),
    path("reportes/<int:pk>/ia/", views.report_ai, name="report_ai"),
    path("reportes/<int:pk>/actualizar/", views.report_regenerate, name="report_regenerate"),
    path("reportes/<int:pk>/compartir/", views.report_share, name="report_share"),
    path("r/<str:token>/", views.report_public, name="report_public"),
    path("pruebas/", views.experiment_list, name="experiment_list"),
    path("pruebas/<int:pk>/", views.experiment_detail, name="experiment_detail"),
]
