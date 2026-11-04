from django.urls import path

from . import views


app_name = "core"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("buscar/", views.busqueda_global, name="search"),
    path("guia/", views.guia_index, name="guia"),
    path("guia/<slug:slug>/", views.guia_tema, name="guia_tema"),
    path("healthz/", views.healthz, name="healthz"),
]
