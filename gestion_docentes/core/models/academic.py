from django.db import models


class Grupo(models.Model):
    nombre = models.CharField(max_length=100, help_text="Ej: Grupo A, Grupo B, Grupo C")

    def __str__(self):
        return self.nombre


class Carrera(models.Model):
    nombre = models.CharField(max_length=100)

    def __str__(self):
        return self.nombre


class Especialidad(models.Model):
    nombre = models.CharField(max_length=100)
    grupo = models.ForeignKey(
        Grupo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="especialidades",
    )

    def __str__(self):
        return self.nombre


class Semestre(models.Model):
    ESTADOS = [
        ("PLANIFICACION", "En Planificación"),
        ("ACTIVO", "Activo"),
        ("CERRADO", "Cerrado"),
    ]
    TIPO_SEMESTRE = [("IMPAR", "Impar (A)"), ("PAR", "Par (B)")]
    nombre = models.CharField(max_length=100, help_text="Ej: Semestre 2025-A")
    tipo = models.CharField(max_length=10, choices=TIPO_SEMESTRE, default="IMPAR")
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    estado = models.CharField(max_length=20, choices=ESTADOS, default="PLANIFICACION")

    def __str__(self):
        return f"{self.nombre} ({self.get_estado_display()})"

    def save(self, *args, **kwargs):
        if self.estado == "ACTIVO":
            Semestre.objects.filter(estado="ACTIVO").exclude(pk=self.id).update(
                estado="CERRADO"
            )
        super(Semestre, self).save(*args, **kwargs)


class Curso(models.Model):
    TIPO_CURSO_CHOICES = [("ESPECIALIDAD", "Especialidad"), ("GENERAL", "General")]
    SEMESTRE_CURSADO_CHOICES = [
        (1, "Semestre I"),
        (2, "Semestre II"),
        (3, "Semestre III"),
        (4, "Semestre IV"),
        (5, "Semestre V"),
        (6, "Semestre VI"),
        (7, "Semestre VII"),
        (8, "Semestre VIII"),
        (9, "Semestre IX"),
        (10, "Semestre X"),
    ]
    nombre = models.CharField(max_length=100)
    tipo_curso = models.CharField(
        max_length=20,
        choices=TIPO_CURSO_CHOICES,
        default="ESPECIALIDAD",
        help_text="Indica si el curso es de especialidad o de estudios generales.",
    )
    # Using string reference to core.Docente
    docente = models.ForeignKey(
        "core.Docente",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cursos",
    )
    carrera = models.ForeignKey(Carrera, on_delete=models.CASCADE)
    especialidades = models.ManyToManyField(
        Especialidad, related_name="cursos", blank=True
    )
    semestre = models.ForeignKey(
        Semestre, on_delete=models.SET_NULL, null=True, related_name="cursos"
    )
    semestre_cursado = models.IntegerField(
        choices=SEMESTRE_CURSADO_CHOICES, null=True, blank=True
    )
    excepcion_horario = models.BooleanField(
        default=False,
        help_text="Permite que este curso se asigne en la tarde aunque sea de un semestre bajo.",
    )
    tolerancia_tardanza_minutos = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Tolerancia de tardanza en minutos, específica para este curso. Si se deja en blanco, se usará la configuración general de la institución.",
    )

    # NUEVO CAMPO PARA HORAS TOTALES
    horas_academicas_semanales = models.PositiveIntegerField(
        default=2,
        help_text="Número total de bloques de 50 minutos que el curso requiere a la semana.",
    )

    class Meta:
        permissions = [
            ("view_planificador", "Puede ver el planificador de horarios"),
        ]

    def get_horas_asignadas(self):
        """Bloques de 50 minutos ya asignados en el horario"""
        from .scheduling import BloqueHorario
        return sum(
            bh.duracion_bloques 
            for bh in BloqueHorario.objects.filter(curso=self)
        )

    def get_horas_pendientes(self):
        """Bloques de 50 minutos que faltan por asignar"""
        return max(0, self.horas_academicas_semanales - self.get_horas_asignadas())

    def __str__(self):
        esp_nombres = ", ".join([e.nombre for e in self.especialidades.all()])
        return f"{self.nombre} ({esp_nombres if esp_nombres else 'N/A'})"

    def save(self, *args, **kwargs):
        # La lógica de 'dia_semana' se ha movido a BloqueHorario
        super().save(*args, **kwargs)
