"""Vistas corporativas de asistencia, permisos, reportes y exportación en texto."""

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import PermissionDenied
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from asistencia.forms import CorreccionAsistenciaForm, MarcacionAsistenciaForm, SolicitudPermisoForm
from asistencia.models import Asistencia, Empleado, LogAuditoriaRRHH, Permiso
from asistencia.utils import obtener_rol_corporativo


def login_view(request):
    """Autenticación corporativa y reinicio de bandera de recordatorio laboral."""
    form = None
    usuario = None
    contexto = {}

    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            usuario = form.get_user()
            login(request, usuario)
            request.session["recordatorio_asistencia_visto"] = False
            request.session.modified = True
            return redirect("dashboard")
    else:
        form = AuthenticationForm()

    contexto = {"form": form, "rol": "Invitado"}
    return render(request, "login.html", contexto)
# Fin def login_view(request)


def logout_view(request):
    """Cierra la sesión corporativa únicamente mediante petición POST."""
    if request.method == "POST":
        logout(request)
        messages.info(request, "Sesión corporativa finalizada correctamente.")
    return redirect("login")
# Fin def logout_view(request)


@login_required
def dashboard_view(request):
    """Panel principal con marcación rápida de asistencia e historial del empleado."""
    rol = ""
    empleado = None
    form = None
    accion = ""
    hora_actual = None
    hoy = None
    registro = None
    mis_asistencias = None
    mis_permisos = None
    contexto = {}

    rol = obtener_rol_corporativo(request.user)
    empleado = getattr(request.user, "perfil_empleado", None)
    hoy = timezone.localdate()

    if request.method == "POST":
        if not request.user.has_perm("asistencia.registrar_asistencia") or not empleado:
            raise PermissionDenied("No cuenta con permiso o perfil para registrar asistencia.")

        form = MarcacionAsistenciaForm(request.POST, empleado=empleado)
        if form.is_valid():
            accion = form.cleaned_data["accion"]
            # Timestamp automático del servidor al guardar (RF2)
            hora_actual = timezone.localtime().time().replace(microsecond=0)

            if accion == "entrada":
                Asistencia.objects.create(
                    empleado=empleado,
                    fecha=hoy,
                    hora_entrada=hora_actual,
                )
                messages.success(request, f"Entrada registrada a las {hora_actual:%H:%M:%S}.")
            else:
                registro = Asistencia.objects.filter(
                    empleado=empleado,
                    fecha=hoy,
                    hora_salida__isnull=True,
                ).first()
                if registro:
                    registro.hora_salida = form.cleaned_data["hora_referencia"]
                    registro.calcular_jornada()
                    registro.save()
                    messages.success(
                        request,
                        f"Salida registrada. Jornada: {registro.horas_trabajadas}h "
                        f"(Extras: {registro.horas_extras}h).",
                    )
            return redirect("dashboard")
    else:
        form = MarcacionAsistenciaForm(empleado=empleado)

    if empleado:
        mis_asistencias = Asistencia.objects.filter(empleado=empleado)[:12]
        mis_permisos = Permiso.objects.select_related("revisado_por").filter(empleado=empleado)[:8]

    contexto = {
        "rol": rol,
        "empleado": empleado,
        "form": form,
        "mis_asistencias": mis_asistencias,
        "mis_permisos": mis_permisos,
        "puede_aprobar": request.user.has_perm("asistencia.aprobar_permiso"),
        "puede_reportes": (
            request.user.has_perm("asistencia.ver_reportes_area")
            or request.user.has_perm("asistencia.ver_reportes_globales")
        ),
        "puede_corregir": request.user.has_perm("asistencia.corregir_asistencia"),
    }
    return render(request, "dashboard.html", contexto)
# Fin def dashboard_view(request)


@login_required
def corregir_asistencia_view(request, asistencia_id: int):
    """Corrección de registro de asistencia exclusiva para Admin RRHH (RF2 y RF4)."""
    rol = ""
    registro = None
    form = None
    asist_obj = None
    contexto = {}

    if not request.user.has_perm("asistencia.corregir_asistencia"):
        raise PermissionDenied("Solo Admin RRHH puede corregir registros de asistencia.")

    rol = obtener_rol_corporativo(request.user)
    registro = get_object_or_404(
        Asistencia.objects.select_related("empleado", "empleado__area"),
        id=asistencia_id,
    )

    if request.method == "POST":
        form = CorreccionAsistenciaForm(request.POST, instance=registro)
        if form.is_valid():
            asist_obj = form.save(commit=False)
            asist_obj.corregida = True
            asist_obj.corregida_por = request.user
            asist_obj.calcular_jornada()
            asist_obj.save()
            messages.success(request, f"Asistencia #{asist_obj.id} corregida y auditada.")
            return redirect("reportes")
    else:
        form = CorreccionAsistenciaForm(instance=registro)

    contexto = {"form": form, "registro": registro, "rol": rol}
    return render(request, "corregir_asistencia.html", contexto)
# Fin def corregir_asistencia_view(request, asistencia_id)


@login_required
def solicitar_permiso_view(request):
    """Permite a cualquier empleado solicitar permisos o vacaciones (RF3)."""
    rol = ""
    empleado = None
    form = None
    permiso_obj = None
    contexto = {}

    if not request.user.has_perm("asistencia.solicitar_permiso"):
        raise PermissionDenied("No cuenta con permiso para solicitar licencias.")

    rol = obtener_rol_corporativo(request.user)
    empleado = getattr(request.user, "perfil_empleado", None)
    if not empleado:
        raise PermissionDenied("Su cuenta no tiene un perfil de empleado asociado.")

    if request.method == "POST":
        form = SolicitudPermisoForm(request.POST, empleado=empleado)
        if form.is_valid():
            permiso_obj = form.save(commit=False)
            permiso_obj.empleado = empleado
            permiso_obj.estado = "pendiente"
            permiso_obj.save()
            messages.success(
                request,
                f"Solicitud #{permiso_obj.id} enviada para aprobación "
                f"({permiso_obj.dias_solicitados} día(s)).",
            )
            return redirect("dashboard")
    else:
        form = SolicitudPermisoForm(empleado=empleado)

    contexto = {"form": form, "empleado": empleado, "rol": rol}
    return render(request, "solicitar_permiso.html", contexto)
# Fin def solicitar_permiso_view(request)


@login_required
def gestionar_permisos_view(request):
    """Bandeja de aprobación: Jefe de Área ve solo su equipo; Admin RRHH ve todos (RF3)."""
    rol = ""
    mi_empleado = None
    permisos = None
    contexto = {}

    if not request.user.has_perm("asistencia.aprobar_permiso"):
        raise PermissionDenied("Solo Jefes de Área y Admin RRHH pueden aprobar permisos.")

    rol = obtener_rol_corporativo(request.user)
    mi_empleado = getattr(request.user, "perfil_empleado", None)

    if rol == "Admin RRHH":
        permisos = Permiso.objects.select_related("empleado", "empleado__area", "revisado_por").all()
    elif rol == "Jefe de Área" and mi_empleado:
        permisos = Permiso.objects.select_related(
            "empleado", "empleado__area", "revisado_por"
        ).filter(empleado__area=mi_empleado.area)
    else:
        raise PermissionDenied("No tiene un área asignada para aprobar solicitudes.")

    contexto = {"permisos": permisos, "rol": rol, "mi_empleado": mi_empleado}
    return render(request, "gestionar_permisos.html", contexto)
# Fin def gestionar_permisos_view(request)


@login_required
def decidir_permiso_view(request, permiso_id: int):
    """Aprueba o rechaza una solicitud verificando jerarquía de área."""
    rol = ""
    mi_empleado = None
    permiso = None
    decision = ""

    if not request.user.has_perm("asistencia.aprobar_permiso"):
        raise PermissionDenied("No cuenta con permiso para aprobar o rechazar solicitudes.")

    rol = obtener_rol_corporativo(request.user)
    mi_empleado = getattr(request.user, "perfil_empleado", None)
    permiso = get_object_or_404(
        Permiso.objects.select_related("empleado", "empleado__area"),
        id=permiso_id,
    )

    if rol == "Jefe de Área":
        if not mi_empleado or permiso.empleado.area_id != mi_empleado.area_id:
            raise PermissionDenied("Un Jefe de Área solo puede aprobar permisos de su propia área.")

    if request.method == "POST" and permiso.estado == "pendiente":
        decision = request.POST.get("decision", "")
        if decision in ("aprobado", "rechazado"):
            permiso.estado = decision
            permiso.revisado_por = request.user
            permiso.fecha_revision = timezone.now()
            permiso.save()
            messages.success(
                request,
                f"Permiso #{permiso.id} de {permiso.empleado.apellidos} marcado como {decision.upper()}. "
                "Notificación registrada en el panel del empleado.",
            )

    return redirect("gestionar_permisos")
# Fin def decidir_permiso_view(request, permiso_id)


@login_required
def reportes_view(request):
    """Reportes de asistencia y horas extras filtrados por alcance jerárquico (RF4 y RF6)."""
    rol = ""
    mi_empleado = None
    ver_global = False
    ver_area = False
    asistencias = None
    resumen_extras = None
    logs = None
    contexto = {}

    ver_global = request.user.has_perm("asistencia.ver_reportes_globales")
    ver_area = request.user.has_perm("asistencia.ver_reportes_area")

    if not (ver_global or ver_area):
        raise PermissionDenied("Acceso denegado: Su rol no puede visualizar reportes de asistencia.")

    rol = obtener_rol_corporativo(request.user)
    mi_empleado = getattr(request.user, "perfil_empleado", None)

    if ver_global:
        asistencias = Asistencia.objects.select_related("empleado", "empleado__area").all()[:40]
        resumen_extras = (
            Empleado.objects.select_related("area")
            .annotate(total_extras=Sum("asistencias__horas_extras"))
            .order_by("-total_extras")
        )
    else:
        asistencias = Asistencia.objects.select_related("empleado", "empleado__area").filter(
            empleado__area=mi_empleado.area
        )[:40]
        resumen_extras = (
            Empleado.objects.select_related("area")
            .filter(area=mi_empleado.area)
            .annotate(total_extras=Sum("asistencias__horas_extras"))
            .order_by("-total_extras")
        )

    if rol == "Admin RRHH":
        logs = LogAuditoriaRRHH.objects.all()[:25]

    contexto = {
        "rol": rol,
        "asistencias": asistencias,
        "resumen_extras": resumen_extras,
        "logs": logs,
        "es_rrhh": rol == "Admin RRHH",
        "ver_global": ver_global,
    }
    return render(request, "reportes.html", contexto)
# Fin def reportes_view(request)


@login_required
def exportar_asistencia_txt_view(request):
    """Exportación simulada de planilla de asistencia en formato texto plano (RF6)."""
    ver_global = False
    ver_area = False
    mi_empleado = None
    registros = None
    lineas = []
    contenido = ""
    response = None

    ver_global = request.user.has_perm("asistencia.ver_reportes_globales")
    ver_area = request.user.has_perm("asistencia.ver_reportes_area")
    if not (ver_global or ver_area):
        raise PermissionDenied("No cuenta con permiso para exportar reportes.")

    mi_empleado = getattr(request.user, "perfil_empleado", None)
    if ver_global:
        registros = Asistencia.objects.select_related("empleado", "empleado__area").all()[:100]
    else:
        registros = Asistencia.objects.select_related("empleado", "empleado__area").filter(
            empleado__area=mi_empleado.area
        )[:100]

    lineas.append("TECNOANDES S.A.C. - EXPORTACION DE ASISTENCIA Y HORAS EXTRAS")
    lineas.append("=" * 82)
    lineas.append("FECHA       | DNI      | EMPLEADO             | AREA         | ENT   | SAL   | HORAS | EXTRAS")
    lineas.append("-" * 82)

    for reg in registros:
        salida_str = reg.hora_salida.strftime("%H:%M") if reg.hora_salida else "--:--"
        nombre_corto = f"{reg.empleado.apellidos}, {reg.empleado.nombres}"[:20]
        lineas.append(
            f"{reg.fecha} | {reg.empleado.dni} | {nombre_corto:<20} | "
            f"{reg.empleado.area.nombre:<12} | {reg.hora_entrada:%H:%M} | {salida_str} | "
            f"{reg.horas_trabajadas:>5} | {reg.horas_extras:>6}"
        )

    contenido = "\n".join(lineas)
    response = HttpResponse(contenido, content_type="text/plain; charset=utf-8")
    response["Content-Disposition"] = 'inline; filename="reporte_asistencia_tecnoandes.txt"'
    return response
# Fin def exportar_asistencia_txt_view(request)
