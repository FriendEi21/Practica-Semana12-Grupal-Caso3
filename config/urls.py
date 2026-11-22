"""Enrutador raíz del proyecto config."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("asistencia.urls")),
]
