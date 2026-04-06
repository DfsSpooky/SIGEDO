from datetime import date

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Asistencia(models.Model):
    # String references
    docente = models.ForeignKey("core.Docente", on_delete=models.CASCADE)
    curso = models.ForeignKey("core.Curso", on_delete=models.CASCADE)
    fecha = models.DateField(default=timezone.now)
    hora_entrada = models.DateTimeField(null=True, blank=True)
    hora_salida = models.DateTimeField(null=True, blank=True)
    hora_salida_permitida = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Hora mínima a la que se puede marcar la salida.",
    )
    foto_entrada = models.ImageField(
        upload_to="verificacion_cursos/entradas/%Y/%m/%d/", null=True, blank=True
    )
    foto_salida = models.ImageField(
        upload_to="verificacion_cursos/salidas/%Y/%m/%d/", null=True, blank=True
    )

    class Meta:
        permissions = [
            ("view_reporte", "Puede ver reportes de asistencia"),
        ]

    def __str__(self):
        return f"Asistencia {self.docente} - {self.curso} ({self.fecha})"

    def es_tardanza(self):
        """
        Determina si la marca de entrada de esta asistencia se considera tardanza.
        """
        from datetime import datetime, timedelta

        # Use string import or get_model if necessary, but direct import might be risky if circular.
        # But we can import from siblings.
        from .scheduling import BloqueHorario
        from .settings import ConfiguracionInstitucion

        if not self.hora_entrada or not self.curso:
            return False

        # Determinar la tolerancia a usar
        if self.curso.tolerancia_tardanza_minutos is not None:
            minutos_tolerancia = self.curso.tolerancia_tardanza_minutos
        else:
            configuracion = ConfiguracionInstitucion.load()
            minutos_tolerancia = configuracion.tiempo_limite_tardanza

        # Obtener el horario de inicio del bloque para el día de la asistencia
        bloque_del_dia = BloqueHorario.objects.filter(
            curso=self.curso, dia_semana=self.fecha.weekday()
        ).first()
        if not bloque_del_dia:
            return False  # No hay bloque programado para este día

        horario_inicio_curso = bloque_del_dia.horario_inicio

        # Combinar la fecha de la asistencia con la hora de inicio del curso para crear un datetime
        horario_inicio_dt = timezone.make_aware(
            datetime.combine(self.fecha, horario_inicio_curso)
        )

        # Calcular el tiempo límite para marcar sin ser considerado tardanza
        limite_tardanza = horario_inicio_dt + timedelta(minutes=minutos_tolerancia)

        # Comparar la hora de entrada (que es un datetime) con el límite (que también es un datetime)
        return self.hora_entrada > limite_tardanza

    @property
    def puede_marcar_salida(self):
        """
        Determina si ya se puede marcar la salida para esta asistencia.
        """
        if self.hora_entrada and not self.hora_salida:
            if (
                self.hora_salida_permitida
                and timezone.now() >= self.hora_salida_permitida
            ):
                return True
        return False


class AsistenciaDiaria(models.Model):
    # String reference
    docente = models.ForeignKey("core.Docente", on_delete=models.CASCADE)
    fecha = models.DateField(default=date.today)
    hora_entrada = models.DateTimeField(auto_now_add=True)
    foto_verificacion = models.ImageField(
        upload_to="verificacion_diaria/%Y/%m/%d/", null=True, blank=True
    )

    def __str__(self):
        return f"Asistencia Diaria de {self.docente} - {self.fecha}"


class TipoJustificacion(models.Model):
    nombre = models.CharField(
        max_length=100,
        unique=True,
        help_text="Ej: Licencia Médica, Comisión de Servicio, Permiso Personal",
    )

    def __str__(self):
        return self.nombre


class Justificacion(models.Model):
    ESTADOS_APROBACION = [
        ("PENDIENTE", "Pendiente"),
        ("APROBADO", "Aprobado"),
        ("RECHAZADO", "Rechazado"),
    ]

    # String references
    docente = models.ForeignKey(
        "core.Docente", on_delete=models.CASCADE, related_name="justificaciones"
    )
    tipo = models.ForeignKey(
        TipoJustificacion, on_delete=models.PROTECT, related_name="justificaciones"
    )
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    motivo = models.TextField(help_text="Explique brevemente el motivo de su ausencia.")
    documento_adjunto = models.FileField(
        upload_to="justificaciones/",
        blank=True,
        null=True,
        help_text="Opcional: Adjunte un documento que respalde su solicitud (PDF, imagen, etc.)",
    )
    estado = models.CharField(
        max_length=20, choices=ESTADOS_APROBACION, default="PENDIENTE"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_revision = models.DateTimeField(null=True, blank=True)
    revisado_por = models.ForeignKey(
        "core.Docente",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="justificaciones_revisadas",
        limit_choices_to={"is_staff": True},
    )
    observaciones_revision = models.TextField(
        blank=True,
        help_text="Notas internas del administrador que revisa la solicitud. Visibles solo para otros administradores.",
    )

    def __str__(self):
        return f"Justificación de {self.docente} ({self.fecha_inicio} al {self.fecha_fin}) - {self.get_estado_display()}"

    def clean(self):
        if self.fecha_inicio > self.fecha_fin:
            raise ValidationError(
                "La fecha de inicio no puede ser posterior a la fecha de fin."
            )

    class Meta:
        ordering = ["-fecha_creacion"]
