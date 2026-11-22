"""Rutas de la aplicación asistencia corporativa."""

from django.urls import path
from .views import (
    corregir_asistencia_view,
    dashboard_view,
    decidir_permiso_view,
    exportar_asistencia_txt_view,
    gestionar_permisos_view,
    login_view,
    logout_view,
    reportes_view,
    solicitar_permiso_view,
)

urlpatterns = [
    path("", dashboard_view, name="dashboard"),
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
    path("asistencia/<int:asistencia_id>/corregir/", corregir_asistencia_view, name="corregir_asistencia"),
    path("permisos/solicitar/", solicitar_permiso_view, name="solicitar_permiso"),
    path("permisos/gestion/", gestionar_permisos_view, name="gestionar_permisos"),
    path("permisos/decidir/<int:permiso_id>/", decidir_permiso_view, name="decidir_permiso"),
    path("reportes/", reportes_view, name="reportes"),
    path("reportes/exportar/", exportar_asistencia_txt_view, name="exportar_asistencia"),
]
