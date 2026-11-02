from django.urls import path

from . import views

app_name = "lives"

urlpatterns = [
    path("marcas/", views.brand_list, name="brand_list"),
    path("marcas/<int:pk>/editar/", views.brand_edit, name="brand_edit"),
    path("hosts/", views.host_list, name="host_list"),
    path("hosts/<int:pk>/editar/", views.host_edit, name="host_edit"),
    path("lives/", views.live_list, name="live_list"),
    path("lives/nuevo/", views.live_create, name="live_create"),
    path("lives/etiquetar/", views.quick_tag, name="quick_tag"),
    path("lives/<int:pk>/", views.live_detail, name="live_detail"),
    path("lives/<int:pk>/editar/", views.live_edit, name="live_edit"),
    path("lives/<int:pk>/momentos/", views.event_add, name="event_add"),
    path("lives/<int:pk>/momentos/<int:event_id>/borrar/", views.event_delete, name="event_delete"),
    path("lives/<int:pk>/minutos/", views.minutes_upload, name="minutes_upload"),
    path("lives/<int:pk>/transcripcion/", views.transcript_upload, name="transcript_upload"),
    path("lives/<int:pk>/transcripcion/analizar/", views.transcript_analyze, name="transcript_analyze"),
    path("importar/", views.import_view, name="import"),
    path("importar/plantilla.csv", views.import_template, name="import_template"),
    path("importar/plantilla-minutos.csv", views.minute_template, name="minute_template"),
]
