"""Módulo auxiliar para validaciones corporativas, sanitización y jerarquía de roles."""

from datetime import datetime, time
from django.core.validators import RegexValidator
from django.utils import timezone
from django.utils.html import escape


validar_dni_regex = RegexValidator(
    regex=r"^\d{8}$",
    message="El DNI debe contener exactamente 8 dígitos numéricos.",
    code="dni_invalido",
)

validar_email_corporativo = RegexValidator(
    regex=r"^[a-zA-Z0-9._%+-]+@tecnoandes\.pe$",
    message="El correo corporativo debe terminar obligatoriamente en @tecnoandes.pe.",
    code="email_corporativo_invalido",
)


def sanitize_input(texto: str) -> str:
    """Elimina espacios innecesarios y escapa caracteres HTML peligrosos."""
    valor_crudo = ""
    valor_limpio = ""
    valor_seguro = ""

    if texto is None:
        return valor_seguro

    valor_crudo = str(texto)
    valor_limpio = valor_crudo.strip()
    valor_seguro = escape(valor_limpio)
    return valor_seguro
# Fin def sanitize_input(texto)


def obtener_ip_cliente(request) -> str:
    """Extrae la IP del cliente desde cabeceras de proxy o conexión directa."""
    x_forwarded = ""
    ip_final = ""

    x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if x_forwarded:
        ip_final = x_forwarded.split(",")[0].strip()
    else:
        ip_final = request.META.get("REMOTE_ADDR", "127.0.0.1")

    return ip_final
# Fin def obtener_ip_cliente(request)


def obtener_rol_corporativo(user) -> str:
    """Determina el rol jerárquico: Admin RRHH, Jefe de Área, Contador o Empleado."""
    rol = "Invitado"

    if not user or not user.is_authenticated:
        return rol

    if user.is_superuser or user.groups.filter(name="Admin RRHH").exists():
        rol = "Admin RRHH"
    elif user.groups.filter(name="Jefe de Área").exists():
        rol = "Jefe de Área"
    elif user.groups.filter(name="Contador").exists():
        rol = "Contador"
    elif user.groups.filter(name="Empleado").exists():
        rol = "Empleado"

    return rol
# Fin def obtener_rol_corporativo(user)


def validar_rango_dos_horas(hora_declarada: time) -> tuple:
    """Comprueba que la hora declarada esté dentro de +/- 2 horas de la hora real del servidor."""
    ahora_local = None
    dt_declarada = None
    diferencia_segundos = 0.0
    diferencia_horas = 0.0

    ahora_local = timezone.localtime()
    dt_declarada = datetime.combine(ahora_local.date(), hora_declarada)
    dt_declarada = timezone.make_aware(dt_declarada, timezone.get_current_timezone())

    diferencia_segundos = abs((dt_declarada - ahora_local).total_seconds())
    diferencia_horas = diferencia_segundos / 3600.0

    if diferencia_horas > 2.0:
        return (
            False,
            f"Hora fuera del rango permitido (+/- 2h del horario real: {ahora_local:%H:%M}).",
        )
    return True, ""
# Fin def validar_rango_dos_horas(hora_declarada)
