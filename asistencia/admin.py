"""Django Admin personalizado para operaciones de RRHH en TecnoAndes S.A.C. (RF6)."""

from django.contrib import admin
from django.utils import timezone
from asistencia.models import Area, Asistencia, Empleado, LogAuditoriaRRHH, Permiso


@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    """Administración de áreas corporativas."""

    list_display = ("id", "nombre", "descripcion")
    search_fields = ("nombre",)
# Fin class AreaAdmin


@admin.register(Empleado)
class EmpleadoAdmin(admin.ModelAdmin):
    """Gestión de empleados con antigüedad, vacaciones disponibles y protección salarial."""

    list_display = (
        "dni",
        "apellidos",
        "nombres",
        "cargo",
        "area",
        "tipo_contrato",
        "mostrar_antiguedad",
        "mostrar_vacaciones",
        "activo",
    )
    list_filter = ("area", "tipo_contrato", "activo")
    search_fields = ("dni", "nombres", "apellidos", "email_corporativo", "cargo")

    def get_queryset(self, request):
        """Optimiza la carga de áreas con select_related."""
        queryset_base = None
        queryset_opt = None

        queryset_base = super().get_queryset(request)
        queryset_opt = queryset_base.select_related("area", "usuario")
        return queryset_opt
    # Fin def get_queryset(self, request)

    def get_exclude(self, request, obj=None):
        """RNF Confidencialidad: oculta el campo salario si no es Admin RRHH."""
        es_rrhh = False

        es_rrhh = bool(
            request.user.is_superuser
            or request.user.groups.filter(name="Admin RRHH").exists()
        )
        if not es_rrhh:
            return ("salario",)
        return ()
    # Fin def get_exclude(self, request, obj=None)

    @admin.display(description="Antigüedad")
    def mostrar_antiguedad(self, obj) -> str:
        """Campo calculado: años y meses en la empresa."""
        etiqueta = ""
        etiqueta = obj.antiguedad_texto
        return etiqueta
    # Fin def mostrar_antiguedad(self, obj)

    @admin.display(description="Vacaciones Disp.")
    def mostrar_vacaciones(self, obj) -> str:
        """Campo calculado: 30 días menos días tomados."""
        texto = ""
        texto = f"{obj.dias_vacaciones_disponibles} / 30 días"
        return texto
    # Fin def mostrar_vacaciones(self, obj)
# Fin class EmpleadoAdmin


@admin.register(Asistencia)
class AsistenciaAdmin(admin.ModelAdmin):
    """Vista de asistencia diaria con filtros por área/fecha y horas extras (RF6)."""

    list_display = (
        "fecha",
        "empleado",
        "obtener_area",
        "hora_entrada",
        "hora_salida",
        "horas_trabajadas",
        "horas_extras",
        "corregida",
    )
    list_filter = ("empleado__area", "fecha", "corregida")
    search_fields = ("empleado__dni", "empleado__apellidos", "empleado__nombres")
    date_hierarchy = "fecha"

    def get_queryset(self, request):
        """Optimiza las consultas con select_related."""
        queryset_base = None
        queryset_opt = None

        queryset_base = super().get_queryset(request)
        queryset_opt = queryset_base.select_related("empleado", "empleado__area")
        return queryset_opt
    # Fin def get_queryset(self, request)

    @admin.display(description="Área")
    def obtener_area(self, obj) -> str:
        """Muestra el área del empleado en el listado diario."""
        nombre_area = ""
        nombre_area = obj.empleado.area.nombre
        return nombre_area
    # Fin def obtener_area(self, obj)
# Fin class AsistenciaAdmin


@admin.register(Permiso)
class PermisoAdmin(admin.ModelAdmin):
    """Gestión de permisos con filtro de pendientes y acción masiva de aprobación (RF6)."""

    list_display = (
        "id",
        "empleado",
        "tipo",
        "fecha_inicio",
        "fecha_fin",
        "mostrar_dias",
        "estado",
        "revisado_por",
    )
    list_filter = ("estado", "tipo", "empleado__area")
    search_fields = ("empleado__dni", "empleado__apellidos", "motivo")
    actions = ["aprobar_permisos_seleccionados"]

    def get_queryset(self, request):
        """Optimiza el listado de permisos con select_related."""
        queryset_base = None
        queryset_opt = None

        queryset_base = super().get_queryset(request)
        queryset_opt = queryset_base.select_related("empleado", "empleado__area", "revisado_por")
        return queryset_opt
    # Fin def get_queryset(self, request)

    @admin.display(description="Días")
    def mostrar_dias(self, obj) -> int:
        """Retorna total de días solicitados."""
        dias = 0
        dias = obj.dias_solicitados
        return dias
    # Fin def mostrar_dias(self, obj)

    @admin.action(description="Aprobar permisos seleccionados")
    def aprobar_permisos_seleccionados(self, request, queryset) -> None:
        """Acción masiva que aprueba solicitudes pendientes y registra auditoría."""
        actualizados = 0

        actualizados = queryset.filter(estado="pendiente").update(
            estado="aprobado",
            revisado_por=request.user,
            fecha_revision=timezone.now(),
        )
        LogAuditoriaRRHH.objects.create(
            usuario=request.user.username,
            accion=f"APROBACIÓN MASIVA EN ADMIN ({actualizados} permiso(s))",
            ruta=request.path,
        )
        self.message_user(
            request,
            f"Se aprobaron {actualizados} permiso(s) pendiente(s) correctamente.",
        )
    # Fin def aprobar_permisos_seleccionados(self, request, queryset)
# Fin class PermisoAdmin


@admin.register(LogAuditoriaRRHH)
class LogAuditoriaRRHHAdmin(admin.ModelAdmin):
    """Registro de auditoría de solo lectura para RRHH."""

    list_display = ("fecha_hora", "usuario", "direccion_ip", "accion", "ruta")
    list_filter = ("usuario", "fecha_hora")
    search_fields = ("usuario", "accion", "ruta")
    readonly_fields = ("usuario", "fecha_hora", "direccion_ip", "accion", "ruta")

    def has_add_permission(self, request) -> bool:
        """Evita inserciones manuales en la bitácora."""
        return False
    # Fin def has_add_permission(self, request)
# Fin class LogAuditoriaRRHHAdmin
