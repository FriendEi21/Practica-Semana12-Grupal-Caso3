"""Modelos ORM para el Control de Asistencia y Permisos de TecnoAndes S.A.C."""

from datetime import datetime
from decimal import Decimal
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from .utils import validar_dni_regex, validar_email_corporativo


class Area(models.Model):
    """Áreas organizacionales de TecnoAndes S.A.C. (RF1)."""

    nombre = models.CharField(max_length=50, unique=True)
    descripcion = models.CharField(max_length=150, blank=True)

    objects = models.Manager()

    class Meta:
        """Metadatos del modelo Area."""

        verbose_name_plural = "Áreas"
        ordering = ["nombre"]
    # Fin class Meta

    def __str__(self) -> str:
        """Retorna el nombre del área."""
        etiqueta = ""
        etiqueta = str(self.nombre)
        return etiqueta
    # Fin def __str__(self)
# Fin class Area


class Empleado(models.Model):
    """Registro de trabajador con datos laborales, antigüedad y salario confidencial."""

    TIPOS_CONTRATO = [
        ("planilla", "Planilla"),
        ("locacion", "Locación de Servicios"),
    ]

    usuario = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="perfil_empleado",
    )
    dni = models.CharField(max_length=8, unique=True, validators=[validar_dni_regex])
    nombres = models.CharField(max_length=80)
    apellidos = models.CharField(max_length=80)
    cargo = models.CharField(max_length=80)
    area = models.ForeignKey(Area, on_delete=models.PROTECT, related_name="empleados")
    fecha_ingreso = models.DateField()
    tipo_contrato = models.CharField(max_length=15, choices=TIPOS_CONTRATO)
    email_corporativo = models.EmailField(unique=True, validators=[validar_email_corporativo])
    salario = models.DecimalField(max_digits=9, decimal_places=2, default=Decimal("2500.00"))
    activo = models.BooleanField(default=True)

    objects = models.Manager()

    class Meta:
        """Metadatos y permisos granulares de reportes corporativos (RF4)."""

        verbose_name_plural = "Empleados"
        ordering = ["area__nombre", "apellidos"]
        permissions = [
            ("ver_reportes_area", "Puede ver reportes de asistencia de su área"),
            ("ver_reportes_globales", "Puede ver reportes globales de asistencia"),
        ]
    # Fin class Meta

    @property
    def antiguedad_texto(self) -> str:
        """Campo calculado: antigüedad en años y meses desde la fecha de ingreso (RF1)."""
        hoy = None
        total_meses = 0
        anios = 0
        meses = 0
        resultado = ""

        hoy = timezone.localdate()
        total_meses = (hoy.year - self.fecha_ingreso.year) * 12 + (
            hoy.month - self.fecha_ingreso.month
        )
        if hoy.day < self.fecha_ingreso.day:
            total_meses -= 1

        total_meses = max(total_meses, 0)
        anios = total_meses // 12
        meses = total_meses % 12
        resultado = f"{anios} año(s), {meses} mes(es)"
        return resultado
    # Fin def antiguedad_texto(self)

    @property
    def dias_vacaciones_disponibles(self) -> int:
        """Campo calculado: 30 días anuales menos días de permisos/vacaciones aprobados (RF6)."""
        aprobados = None
        dias_tomados = 0
        disponibles = 30

        aprobados = self.permisos.filter(estado="aprobado")
        for perm in aprobados:
            dias_tomados += perm.dias_solicitados

        disponibles = max(30 - dias_tomados, 0)
        return disponibles
    # Fin def dias_vacaciones_disponibles(self)

    def __str__(self) -> str:
        """Retorna apellidos, nombres y área del empleado."""
        etiqueta = ""
        etiqueta = f"{self.apellidos}, {self.nombres} ({self.area.nombre})"
        return etiqueta
    # Fin def __str__(self)
# Fin class Empleado


class Asistencia(models.Model):
    """Registro diario de entrada/salida con cálculo de horas trabajadas y extras (RF2)."""

    MOTIVOS_CORRECCION = [
        ("error_sistema", "Error de sistema"),
        ("olvido", "Olvido de marcación"),
        ("otro", "Otro"),
    ]

    empleado = models.ForeignKey(
        Empleado,
        on_delete=models.PROTECT,
        related_name="asistencias",
    )
    fecha = models.DateField(default=timezone.localdate)
    hora_entrada = models.TimeField()
    hora_salida = models.TimeField(null=True, blank=True)
    horas_trabajadas = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    horas_extras = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    corregida = models.BooleanField(default=False)
    motivo_correccion = models.CharField(max_length=20, choices=MOTIVOS_CORRECCION, blank=True)
    justificacion_correccion = models.TextField(blank=True)
    corregida_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asistencias_corregidas",
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    objects = models.Manager()

    class Meta:
        """Metadatos y permisos específicos de asistencia (RF4)."""

        verbose_name_plural = "Asistencias"
        ordering = ["-fecha", "-hora_entrada"]
        permissions = [
            ("registrar_asistencia", "Puede registrar su marcación diaria de asistencia"),
            ("corregir_asistencia", "Puede corregir registros de asistencia con justificación"),
        ]
    # Fin class Meta

    def calcular_jornada(self) -> None:
        """Calcula horas trabajadas totales y horas extras (>8h diarias)."""
        dt_in = None
        dt_out = None
        segundos = 0.0
        horas = Decimal("0.00")
        extras = Decimal("0.00")

        if self.hora_entrada and self.hora_salida:
            dt_in = datetime.combine(self.fecha, self.hora_entrada)
            dt_out = datetime.combine(self.fecha, self.hora_salida)
            segundos = max((dt_out - dt_in).total_seconds(), 0.0)
            horas = Decimal(str(round(segundos / 3600.0, 2)))
            extras = max(horas - Decimal("8.00"), Decimal("0.00"))
            self.horas_trabajadas = horas
            self.horas_extras = extras
    # Fin def calcular_jornada(self)

    @property
    def es_editable_por_empleado(self) -> bool:
        """RNF Integridad: no modificable por el empleado después de 24 horas."""
        ahora = None
        transcurrido = 0.0

        ahora = timezone.now()
        transcurrido = (ahora - self.creado_en).total_seconds()
        return transcurrido <= 86400 and self.hora_salida is None
    # Fin def es_editable_por_empleado(self)

    def __str__(self) -> str:
        """Retorna resumen diario de asistencia."""
        texto = ""
        texto = f"{self.empleado.apellidos} | {self.fecha} ({self.hora_entrada:%H:%M})"
        return texto
    # Fin def __str__(self)
# Fin class Asistencia


class Permiso(models.Model):
    """Solicitudes de permisos y vacaciones con flujo de aprobación jerárquica (RF3)."""

    TIPOS_PERMISO = [
        ("personal", "Personal / Vacaciones"),
        ("medico", "Médico"),
        ("duelo", "Duelo"),
        ("maternidad_paternidad", "Maternidad / Paternidad"),
        ("otro", "Otro"),
    ]
    ESTADOS_PERMISO = [
        ("pendiente", "Pendiente"),
        ("aprobado", "Aprobado"),
        ("rechazado", "Rechazado"),
    ]

    empleado = models.ForeignKey(
        Empleado,
        on_delete=models.PROTECT,
        related_name="permisos",
    )
    tipo = models.CharField(max_length=25, choices=TIPOS_PERMISO)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    motivo = models.TextField()
    adjunto_descripcion = models.CharField(
        max_length=200,
        blank=True,
        help_text="Descripción del documento de respaldo (ej. certificado médico).",
    )
    estado = models.CharField(max_length=15, choices=ESTADOS_PERMISO, default="pendiente")
    revisado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="permisos_revisados",
    )
    fecha_revision = models.DateTimeField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    objects = models.Manager()

    class Meta:
        """Metadatos y permisos de solicitudes y aprobaciones (RF4)."""

        verbose_name_plural = "Permisos y Vacaciones"
        ordering = ["-creado_en"]
        permissions = [
            ("solicitar_permiso", "Puede solicitar permisos y vacaciones"),
            ("aprobar_permiso", "Puede aprobar o rechazar permisos"),
        ]
    # Fin class Meta

    @property
    def dias_solicitados(self) -> int:
        """Calcula la cantidad total de días calendario solicitados (inclusivo)."""
        diferencia = 0
        diferencia = (self.fecha_fin - self.fecha_inicio).days + 1
        return max(diferencia, 1)
    # Fin def dias_solicitados(self)

    def __str__(self) -> str:
        """Retorna resumen de la solicitud de permiso."""
        linea = ""
        linea = (
            f"Permiso #{self.id} - {self.empleado.apellidos} "
            f"({self.fecha_inicio} al {self.fecha_fin}) [{self.estado}]"
        )
        return linea
    # Fin def __str__(self)
# Fin class Permiso


class LogAuditoriaRRHH(models.Model):
    """Auditoría obligatoria de modificaciones en asistencia, permisos y bloqueos (RF5)."""

    usuario = models.CharField(max_length=60)
    fecha_hora = models.DateTimeField(auto_now_add=True)
    direccion_ip = models.GenericIPAddressField(null=True, blank=True)
    accion = models.CharField(max_length=220)
    ruta = models.CharField(max_length=150)

    objects = models.Manager()

    class Meta:
        """Metadatos del modelo LogAuditoriaRRHH."""

        verbose_name_plural = "Logs de Auditoría RRHH"
        ordering = ["-fecha_hora"]
    # Fin class Meta

    def __str__(self) -> str:
        """Retorna línea resumida del log corporativo."""
        etiqueta = ""
        etiqueta = f"[{self.fecha_hora:%d/%m/%Y %H:%M}] {self.usuario} - {self.accion}"
        return etiqueta
    # Fin def __str__(self)
# Fin class LogAuditoriaRRHH
