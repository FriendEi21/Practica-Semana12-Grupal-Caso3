"""Formularios de marcación, corrección RRHH y permisos con validaciones cruzadas."""

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from asistencia.models import Asistencia, Permiso
from asistencia.utils import sanitize_input


class MarcacionAsistenciaForm(forms.Form):
    """Formulario clásico (forms.Form) para marcación rápida de entrada o salida (RF2)."""

    ACCIONES = [
        ("entrada", "Registrar Entrada"),
        ("salida", "Registrar Salida"),
    ]

    accion = forms.ChoiceField(choices=ACCIONES, label="Tipo de marcación")
    hora_referencia = forms.TimeField(
        label="Hora de marcación (rango permitido +/- 2h del horario real)",
        widget=forms.TimeInput(attrs={"type": "time"}),
    )

    def __init__(self, *args, empleado=None, **kwargs):
        """Prellena la hora actual local y recibe al empleado para validaciones."""
        hora_actual = None

        super().__init__(*args, **kwargs)
        self.empleado = empleado
        if not self.is_bound:
            hora_actual = timezone.localtime().time().replace(second=0, microsecond=0)
            self.fields["hora_referencia"].initial = hora_actual.strftime("%H:%M")
    # Fin def __init__(self, *args, empleado=None, **kwargs)

    def clean(self) -> dict:
        """Valida entrada única abierta del día y hora de salida posterior a entrada."""
        datos_limpios = {}
        accion = ""
        hora_ref = None
        hoy = None
        abierta = None

        datos_limpios = super().clean()
        accion = datos_limpios.get("accion", "")
        hora_ref = datos_limpios.get("hora_referencia")
        hoy = timezone.localdate()

        if self.empleado and hora_ref:
            abierta = Asistencia.objects.filter(
                empleado=self.empleado,
                fecha=hoy,
                hora_salida__isnull=True,
            ).first()

            if accion == "entrada" and abierta is not None:
                raise ValidationError(
                    "Ya existe una entrada registrada hoy sin marcación de salida."
                )

            if accion == "salida":
                if abierta is None:
                    raise ValidationError(
                        "No se encontró una entrada abierta hoy para registrar su salida."
                    )
                if hora_ref <= abierta.hora_entrada:
                    self.add_error(
                        "hora_referencia",
                        f"La hora de salida debe ser posterior a la entrada ({abierta.hora_entrada:%H:%M}).",
                    )

        return datos_limpios
    # Fin def clean(self)
# Fin class MarcacionAsistenciaForm


class CorreccionAsistenciaForm(forms.ModelForm):
    """ModelForm exclusivo de Admin RRHH para corregir asistencia con justificación >=50 chars."""

    class Meta:
        """Campos auditados de corrección."""

        model = Asistencia
        fields = [
            "hora_entrada",
            "hora_salida",
            "motivo_correccion",
            "justificacion_correccion",
        ]
        widgets = {
            "hora_entrada": forms.TimeInput(attrs={"type": "time"}),
            "hora_salida": forms.TimeInput(attrs={"type": "time"}),
            "justificacion_correccion": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Detallar sustento de la corrección (mínimo 50 caracteres).",
                }
            ),
        }
    # Fin class Meta

    def clean_motivo_correccion(self) -> str:
        """Exige seleccionar explícitamente un motivo de corrección."""
        motivo = ""

        motivo = self.cleaned_data.get("motivo_correccion", "")
        if not motivo:
            raise ValidationError("Debe especificar un motivo de corrección.")
        return motivo
    # Fin def clean_motivo_correccion(self)

    def clean_justificacion_correccion(self) -> str:
        """Sanitiza y valida longitud mínima de 50 caracteres (RF2)."""
        texto = ""

        texto = sanitize_input(self.cleaned_data.get("justificacion_correccion", ""))
        if len(texto) < 50:
            raise ValidationError(
                f"La justificación requiere mínimo 50 caracteres (actual: {len(texto)})."
            )
        return texto
    # Fin def clean_justificacion_correccion(self)

    def clean(self) -> dict:
        """Comprueba que la hora de salida sea posterior a la entrada."""
        datos_limpios = {}
        entrada = None
        salida = None

        datos_limpios = super().clean()
        entrada = datos_limpios.get("hora_entrada")
        salida = datos_limpios.get("hora_salida")

        if entrada and salida and salida <= entrada:
            self.add_error("hora_salida", "La hora de salida debe ser posterior a la entrada.")

        return datos_limpios
    # Fin def clean(self)
# Fin class CorreccionAsistenciaForm


class SolicitudPermisoForm(forms.ModelForm):
    """ModelForm para solicitud de permisos/vacaciones con validaciones de cruce y saldo (RF3)."""

    class Meta:
        """Campos de la solicitud de permiso."""

        model = Permiso
        fields = ["tipo", "fecha_inicio", "fecha_fin", "motivo", "adjunto_descripcion"]
        widgets = {
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}),
            "fecha_fin": forms.DateInput(attrs={"type": "date"}),
            "motivo": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Explique el motivo del permiso (mínimo 30 caracteres).",
                }
            ),
            "adjunto_descripcion": forms.TextInput(
                attrs={"placeholder": "Ej. Certificado de descanso médico ESSALUD N° 4451"}
            ),
        }
    # Fin class Meta

    def __init__(self, *args, empleado=None, **kwargs):
        """Recibe la instancia de empleado para validar solapamientos y saldo vacacional."""
        super().__init__(*args, **kwargs)
        self.empleado = empleado
    # Fin def __init__(self, *args, empleado=None, **kwargs)

    def clean_motivo(self) -> str:
        """Sanitiza y exige un mínimo de 30 caracteres en el motivo (RF3)."""
        texto = ""

        texto = sanitize_input(self.cleaned_data.get("motivo", ""))
        if len(texto) < 30:
            raise ValidationError(
                f"El motivo detallado debe tener al menos 30 caracteres (actual: {len(texto)})."
            )
        return texto
    # Fin def clean_motivo(self)

    def clean_adjunto_descripcion(self) -> str:
        """Sanitiza el campo de documento adjunto simulado."""
        texto = ""
        texto = sanitize_input(self.cleaned_data.get("adjunto_descripcion", ""))
        return texto
    # Fin def clean_adjunto_descripcion(self)

    def clean(self) -> dict:
        """Valida fin >= inicio, no superposición de permisos y días disponibles >= solicitados."""
        datos_limpios = {}
        f_ini = None
        f_fin = None
        dias_req = 0
        disponibles = 0
        superpuesto = False

        datos_limpios = super().clean()
        f_ini = datos_limpios.get("fecha_inicio")
        f_fin = datos_limpios.get("fecha_fin")

        if f_ini and f_fin:
            if f_fin < f_ini:
                self.add_error(
                    "fecha_fin",
                    "La fecha de fin debe ser igual o posterior a la fecha de inicio.",
                )
            elif self.empleado:
                # Validación de superposición con permisos pendientes o aprobados
                superpuesto = (
                    Permiso.objects.filter(
                        empleado=self.empleado,
                        estado__in=["pendiente", "aprobado"],
                        fecha_inicio__lte=f_fin,
                        fecha_fin__gte=f_ini,
                    ).exists()
                )
                if superpuesto:
                    raise ValidationError(
                        "Conflicto de fechas: Ya existe un permiso pendiente o aprobado en ese rango."
                    )

                dias_req = (f_fin - f_ini).days + 1
                disponibles = self.empleado.dias_vacaciones_disponibles
                if dias_req > disponibles:
                    raise ValidationError(
                        f"Saldo insuficiente: solicita {dias_req} día(s) y solo cuenta con "
                        f"{disponibles} día(s) de vacaciones disponibles."
                    )

        return datos_limpios
    # Fin def clean(self)
# Fin class SolicitudPermisoForm
