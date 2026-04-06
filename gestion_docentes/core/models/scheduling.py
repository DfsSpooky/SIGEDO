from django.core.exceptions import ValidationError
from django.db import models


class FranjaHoraria(models.Model):
    TURNO_CHOICES = [("MANANA", "Mañana"), ("TARDE", "Tarde"), ("NOCHE", "Noche")]
    turno = models.CharField(max_length=10, choices=TURNO_CHOICES)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()

    class Meta:
        verbose_name = "Franja Horaria"
        verbose_name_plural = "Franjas Horarias"
        ordering = ["hora_inicio"]

    def __str__(self):
        return f"{self.get_turno_display()}: {self.hora_inicio.strftime('%I:%M %p')} - {self.hora_fin.strftime('%I:%M %p')}"


class DiaEspecial(models.Model):
    TIPO_CHOICES = [
        ("FERIADO", "Feriado (No se labora)"),
        ("EVENTO", "Evento Institucional (Se labora, sin clases)"),
        ("SUSPENSION", "Suspensión de Clases"),
    ]
    fecha = models.DateField(unique=True)
    motivo = models.CharField(max_length=255)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    # Using string reference for Semestre
    semestre = models.ForeignKey(
        "core.Semestre", on_delete=models.CASCADE, null=True, blank=True
    )

    def __str__(self):
        return f"{self.fecha}: {self.motivo} ({self.get_tipo_display()})"


class BloqueHorario(models.Model):
    DIAS_SEMANA_CHOICES = [
        ("Lunes", "Lunes"),
        ("Martes", "Martes"),
        ("Miércoles", "Miércoles"),
        ("Jueves", "Jueves"),
        ("Viernes", "Viernes"),
    ]

    # Using string reference for Curso
    curso = models.ForeignKey(
        "core.Curso", on_delete=models.CASCADE, related_name="bloques_horario"
    )
    dia = models.CharField(max_length=20, choices=DIAS_SEMANA_CHOICES)
    franja_inicio = models.ForeignKey(
        FranjaHoraria, on_delete=models.PROTECT, related_name="bloques_inicio"
    )
    duracion_bloques = models.PositiveIntegerField(
        default=1,
        help_text="Duración de este bloque específico en unidades de 50 minutos.",
    )

    # Campos denormalizados para facilitar consultas. Se actualizan con save().
    horario_inicio = models.TimeField(editable=False)
    horario_fin = models.TimeField(editable=False)
    dia_semana = models.PositiveSmallIntegerField(editable=False, db_index=True)

    class Meta:
        verbose_name = "Bloque de Horario"
        verbose_name_plural = "Bloques de Horario"
        ordering = ["dia_semana", "horario_inicio"]
        unique_together = (
            "curso",
            "dia",
            "franja_inicio",
        )  # Un curso no puede estar dos veces en el mismo bloque

    def __str__(self):
        return (
            f"{self.curso.nombre} - {self.dia} {self.horario_inicio}-{self.horario_fin}"
        )

    def clean(self):
        # Asegurarse de que el docente esté disponible
        if self.curso.docente:
            turno_franja = self.franja_inicio.turno
            disponibilidad_docente = self.curso.docente.disponibilidad
            if (disponibilidad_docente == "MANANA" and turno_franja != "MANANA") or (
                disponibilidad_docente == "TARDE" and turno_franja != "TARDE"
            ):
                raise ValidationError(
                    f"El docente {self.curso.docente} no está disponible en el turno de {turno_franja}."
                )

    def save(self, *args, **kwargs):
        # Salvaguarda para ignorar la creación de bloques vacíos desde el admin inline
        if not self.franja_inicio_id:
            return

        # Actualizar campos denormalizados
        DIAS = {"Lunes": 0, "Martes": 1, "Miércoles": 2, "Jueves": 3, "Viernes": 4}
        self.dia_semana = DIAS.get(self.dia)
        self.horario_inicio = self.franja_inicio.hora_inicio

        # Calcular la hora de fin
        todas_las_franjas = list(FranjaHoraria.objects.order_by("hora_inicio"))
        try:
            start_index = todas_las_franjas.index(self.franja_inicio)
            end_index = start_index + self.duracion_bloques - 1
            if end_index < len(todas_las_franjas):
                self.horario_fin = todas_las_franjas[end_index].hora_fin
            else:
                self.horario_fin = todas_las_franjas[-1].hora_fin
        except (ValueError, IndexError):
            self.horario_fin = self.franja_inicio.hora_fin

        super().save(*args, **kwargs)


class SolicitudIntercambio(models.Model):
    # Using string references
    docente_solicitante = models.ForeignKey(
        "core.Docente", on_delete=models.CASCADE, related_name="solicitudes_enviadas"
    )
    curso_solicitante = models.ForeignKey(
        "core.Curso", on_delete=models.CASCADE, related_name="solicitudes_solicitante"
    )
    docente_destino = models.ForeignKey(
        "core.Docente", on_delete=models.CASCADE, related_name="solicitudes_recibidas"
    )
    curso_destino = models.ForeignKey(
        "core.Curso", on_delete=models.CASCADE, related_name="solicitudes_destino"
    )
    estado = models.CharField(
        max_length=20,
        choices=[
            ("pendiente", "Pendiente"),
            ("aprobado", "Aprobado"),
            ("rechazado", "Rechazado"),
        ],
        default="pendiente",
    )
    fecha_solicitud = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Solicitud {self.docente_solicitante} -> {self.docente_destino} ({self.estado})"
