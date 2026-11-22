"""Middleware de control laboral, bloqueo de cuentas, horario +/-2h y auditoría (RF5)."""

from datetime import datetime
from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.utils import timezone
from asistencia.models import Asistencia, LogAuditoriaRRHH
from asistencia.utils import obtener_ip_cliente, validar_rango_dos_horas


class ControlYAuditoriaRRHHMiddleware:
    """Ejecuta las 4 capas del RF5: bloqueo, recordatorio laboral, rango +/-2h y auditoría."""

    def __init__(self, get_response):
        """Almacena la referencia al siguiente handler de Django."""
        self.get_response = get_response
    # Fin def __init__(self, get_response)

    def __call__(self, request):
        """Intercepta request/response aplicando las reglas de control corporativo."""
        ip_cliente = ""
        usuario_actual = "anonimo"
        empleado = None
        hoy = None
        marco_hoy = False
        hora_raw = ""
        hora_obj = None
        rango_ok = True
        msg_rango = ""
        response = None
        accion_log = ""

        ip_cliente = obtener_ip_cliente(request)
        if hasattr(request, "user") and request.user.is_authenticated:
            usuario_actual = request.user.username

            if hasattr(request.user, "perfil_empleado"):
                empleado = request.user.perfil_empleado

                # 1. Middleware de bloqueo: impedir acceso a cuentas desactivadas
                if not empleado.activo and not request.user.is_superuser:
                    self._registrar_log(
                        usuario_actual,
                        ip_cliente,
                        "ACCESO BLOQUEADO: CUENTA DESACTIVADA",
                        request.path,
                    )
                    logout(request)
                    messages.error(
                        request,
                        "Acceso denegado: Su cuenta corporativa se encuentra desactivada. "
                        "Contacte con Recursos Humanos.",
                    )
                    return redirect("login")

                # 2. Recordatorio de asistencia en día laborable (L-V) al iniciar sesión
                if not request.session.get("recordatorio_asistencia_visto", False):
                    hoy = timezone.localdate()
                    if hoy.weekday() < 5:  # Lunes a Viernes
                        marco_hoy = Asistencia.objects.filter(
                            empleado=empleado,
                            fecha=hoy,
                        ).exists()
                        if not marco_hoy:
                            messages.warning(
                                request,
                                "Recordatorio laboral: Hoy es día laborable y aún no has "
                                "registrado tu marcación de entrada.",
                            )
                    request.session["recordatorio_asistencia_visto"] = True
                    request.session.modified = True

        # 3. Validación de horario: permitir marcación solo dentro de +/- 2h del horario real
        if request.method == "POST" and request.path == "/":
            hora_raw = request.POST.get("hora_referencia", "")
            if hora_raw:
                try:
                    hora_obj = datetime.strptime(hora_raw[:5], "%H:%M").time()
                    rango_ok, msg_rango = validar_rango_dos_horas(hora_obj)
                    if not rango_ok:
                        self._registrar_log(
                            usuario_actual,
                            ip_cliente,
                            f"BLOQUEO MARCACIÓN FUERA DE RANGO +/-2H ({hora_raw})",
                            request.path,
                        )
                        messages.error(request, f"[Control de Horario] {msg_rango}")
                        return redirect("dashboard")
                except ValueError:
                    pass

        response = self.get_response(request)

        # 4. Auditoría de modificaciones en asistencia, permisos y accesos 403
        if response.status_code == 403:
            accion_log = "INTENTO DE ACCESO NO AUTORIZADO (403)"
        elif request.method == "POST" and response.status_code in (200, 302):
            if request.path == "/":
                accion_log = "REGISTRO DE ASISTENCIA DIARIA"
            elif "/corregir/" in request.path:
                accion_log = "CORRECCIÓN DE ASISTENCIA POR RRHH"
            elif "/permisos/solicitar/" in request.path:
                accion_log = "SOLICITUD DE PERMISO / VACACIONES"
            elif "/permisos/decidir/" in request.path:
                accion_log = "APROBACIÓN O RECHAZO DE PERMISO"

        if accion_log:
            self._registrar_log(usuario_actual, ip_cliente, accion_log, request.path)

        return response
    # Fin def __call__(self, request)

    def _registrar_log(self, usuario: str, ip_addr: str, accion: str, ruta: str) -> None:
        """Persiste el registro de auditoría en SQLite e imprime la traza en consola."""
        LogAuditoriaRRHH.objects.create(
            usuario=usuario,
            direccion_ip=ip_addr,
            accion=accion,
            ruta=ruta,
        )
        print(
            f"[AUDITORÍA TECNOANDES] Usuario: {usuario} | IP: {ip_addr} | "
            f"Acción: {accion} | Ruta: {ruta}"
        )
    # Fin def _registrar_log(self, usuario, ip_addr, accion, ruta)
# Fin class ControlYAuditoriaRRHHMiddleware
