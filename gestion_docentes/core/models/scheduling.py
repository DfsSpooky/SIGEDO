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


class Aula(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    ubicacion = models.CharField(max_length=200, blank=True, null=True)
    es_laboratorio = models.BooleanField(default=False)

    def __str__(self):
        return self.nombre


class BloqueNoLectivo(models.Model):
    DIAS_SEMANA_CHOICES = [
        ("Lunes", "Lunes"),
        ("Martes", "Martes"),
        ("Miércoles", "Miércoles"),
        ("Jueves", "Jueves"),
        ("Viernes", "Viernes"),
    ]
    # Usamos string reference para evitar circular imports si Docente estuviera aquí
    docente = models.ForeignKey(
        "core.Docente", on_delete=models.CASCADE, related_name="bloques_no_lectivos"
    )
    dia = models.CharField(max_length=20, choices=DIAS_SEMANA_CHOICES)
    franja_inicio = models.ForeignKey(
        FranjaHoraria, on_delete=models.PROTECT, related_name="bloques_no_lectivos"
    )
    duracion_bloques = models.PositiveIntegerField(default=1)
    motivo = models.CharField(max_length=255)

    # Campos denormalizados
    horario_inicio = models.TimeField(editable=False)
    horario_fin = models.TimeField(editable=False)
    dia_semana = models.PositiveSmallIntegerField(editable=False, db_index=True)

    def _calculate_times(self):
        # Misma lógica que BloqueHorario. Se podría extraer a un mixin/utils
        if not self.franja_inicio_id:
            return None, None

        start_time = self.franja_inicio.hora_inicio
        end_time = self.franja_inicio.hora_fin

        if self.duracion_bloques <= 1:
            return start_time, end_time

        todas_las_franjas = list(FranjaHoraria.objects.order_by("hora_inicio"))
        try:
            start_index = todas_las_franjas.index(self.franja_inicio)
            end_index = start_index + self.duracion_bloques - 1
            if end_index < len(todas_las_franjas):
                end_time = todas_las_franjas[end_index].hora_fin
            else:
                end_time = todas_las_franjas[-1].hora_fin
        except (ValueError, IndexError):
            pass
        return start_time, end_time

    def clean(self):
        start_time, end_time = self._calculate_times()
        if not start_time or not end_time:
            return

        # Validar superposición con BloqueHorario del mismo docente
        conflicto_clase = BloqueHorario.objects.filter(
            curso__docente=self.docente,
            dia=self.dia,
            horario_inicio__lt=end_time,
            horario_fin__gt=start_time
        ).exists()

        if conflicto_clase:
            raise ValidationError(f"El docente {self.docente} tiene clases asignadas en este horario.")

        # Validar superposición con otros BloqueNoLectivo
        conflicto_otro = BloqueNoLectivo.objects.filter(
            docente=self.docente,
            dia=self.dia,
            horario_inicio__lt=end_time,
            horario_fin__gt=start_time
        ).exclude(pk=self.pk).exists()

        if conflicto_otro:
            raise ValidationError(f"El docente {self.docente} ya tiene otro bloque no lectivo en este horario.")

    def save(self, *args, **kwargs):
        DIAS = {"Lunes": 0, "Martes": 1, "Miércoles": 2, "Jueves": 3, "Viernes": 4}
        self.dia_semana = DIAS.get(self.dia)
        start_time, end_time = self._calculate_times()
        if start_time and end_time:
            self.horario_inicio = start_time
            self.horario_fin = end_time
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.docente} - {self.motivo} ({self.dia})"


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
    aula = models.ForeignKey(
        Aula, on_delete=models.SET_NULL, null=True, blank=True, related_name="bloques_horario"
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

    def _calculate_times(self):
        """
        Calcula el horario de inicio y fin basado en la franja inicial y la duración.
        Retorna una tupla (hora_inicio, hora_fin).
        """
        if not self.franja_inicio_id:
            return None, None

        start_time = self.franja_inicio.hora_inicio
        end_time = self.franja_inicio.hora_fin

        # Optimización: si la duración es 1, no necesitamos consultar la lista de franjas
        if self.duracion_bloques <= 1:
            return start_time, end_time

        todas_las_franjas = list(FranjaHoraria.objects.order_by("hora_inicio"))
        try:
            start_index = todas_las_franjas.index(self.franja_inicio)
            end_index = start_index + self.duracion_bloques - 1
            if end_index < len(todas_las_franjas):
                end_time = todas_las_franjas[end_index].hora_fin
            else:
                end_time = todas_las_franjas[-1].hora_fin
        except (ValueError, IndexError):
            pass

        return start_time, end_time

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

        # Validación de cruces de horarios
        start_time, end_time = self._calculate_times()
        if not start_time or not end_time:
            # Si no se pueden calcular los tiempos (ej. falta franja_inicio), salimos.
            # La validación de campos obligatorios se hace en otra parte.
            return

        # 1. Validar conflicto de Docente
        if self.curso.docente:
            conflicto_docente = (
                BloqueHorario.objects.filter(
                    curso__docente=self.curso.docente,
                    dia=self.dia,
                    horario_inicio__lt=end_time,
                    horario_fin__gt=start_time,
                )
                .exclude(pk=self.pk)
                .first()
            )

            if conflicto_docente:
                raise ValidationError(
                    f"El docente {self.curso.docente} ya tiene clase asignada en este horario ({conflicto_docente.curso})."
                )

        # 2. Validar conflicto de Grupo + Semestre (Estudiantes)
        # Iterar sobre todas las especialidades asociadas al curso
        if self.curso.pk:  # Solo si el curso ya está guardado (tiene especialidades)
            for especialidad in self.curso.especialidades.all():
                if especialidad.grupo:
                    conflicto_grupo = (
                        BloqueHorario.objects.filter(
                            curso__especialidades__grupo=especialidad.grupo,
                            curso__semestre_cursado=self.curso.semestre_cursado,
                            dia=self.dia,
                            horario_inicio__lt=end_time,
                            horario_fin__gt=start_time,
                        )
                        .exclude(pk=self.pk)
                        .first()
                    )

                    if conflicto_grupo:
                        raise ValidationError(
                            f"El Grupo {especialidad.grupo} (Semestre {self.curso.semestre_cursado}) de la especialidad {especialidad.nombre} ya tiene clase asignada en este horario ({conflicto_grupo.curso})."
                        )

        # 3. Validar conflicto de Aula
        if self.aula:
            conflicto_aula = (
                BloqueHorario.objects.filter(
                    aula=self.aula,
                    dia=self.dia,
                    horario_inicio__lt=end_time,
                    horario_fin__gt=start_time,
                )
                .exclude(pk=self.pk)
                .first()
            )

            if conflicto_aula:
                raise ValidationError(
                    f"El aula {self.aula} ya está ocupada en este horario ({conflicto_aula.curso})."
                )

        # 4. Validar conflicto con Bloques No Lectivos
        if self.curso.docente:
            conflicto_no_lectivo = BloqueNoLectivo.objects.filter(
                docente=self.curso.docente,
                dia=self.dia,
                horario_inicio__lt=end_time,
                horario_fin__gt=start_time,
            ).first()

            if conflicto_no_lectivo:
                raise ValidationError(
                    f"El docente {self.curso.docente} tiene un bloque no lectivo ({conflicto_no_lectivo.motivo}) en este horario."
                )

        # 5. Validar Carga Académica Diaria del Docente (Max 8 horas)
        if self.curso.docente:
            horas_existentes = BloqueHorario.objects.filter(
                curso__docente=self.curso.docente,
                dia=self.dia
            ).exclude(pk=self.pk).aggregate(total=models.Sum("duracion_bloques"))["total"] or 0

            if horas_existentes + self.duracion_bloques > 8:
                raise ValidationError(
                    f"El docente {self.curso.docente} excede el límite de 8 horas diarias."
                )

        # 6. Validar Carga Académica Diaria del Grupo (Max 6 horas)
        if self.curso.pk:
            for especialidad in self.curso.especialidades.all():
                if especialidad.grupo:
                    horas_grupo = BloqueHorario.objects.filter(
                        curso__especialidades__grupo=especialidad.grupo,
                        curso__semestre_cursado=self.curso.semestre_cursado,
                        dia=self.dia
                    ).exclude(pk=self.pk).aggregate(total=models.Sum("duracion_bloques"))["total"] or 0

                    if horas_grupo + self.duracion_bloques > 6:
                        raise ValidationError(
                            f"El grupo {especialidad.grupo} de {especialidad.nombre} excede el límite de 6 horas diarias."
                        )

        # 7. Validar Carga Continua del Docente (Max 4 horas seguidas)
        # Nota: Esta validación es compleja porque requiere analizar la contigüidad.
        # Por simplicidad y eficiencia, validamos si la suma total del día excede un umbral seguro
        # o si el bloque actual es excesivamente largo.
        if self.duracion_bloques > 4:
             raise ValidationError("No se pueden asignar bloques de más de 4 horas continuas.")

    def save(self, *args, **kwargs):
        # Salvaguarda para ignorar la creación de bloques vacíos desde el admin inline
        if not self.franja_inicio_id:
            return

        # Actualizar campos denormalizados
        DIAS = {"Lunes": 0, "Martes": 1, "Miércoles": 2, "Jueves": 3, "Viernes": 4}
        self.dia_semana = DIAS.get(self.dia)

        # Usar el método centralizado para calcular tiempos
        start_time, end_time = self._calculate_times()
        if start_time and end_time:
            self.horario_inicio = start_time
            self.horario_fin = end_time
        else:
             # Fallback en caso de error (no debería ocurrir si franja_inicio existe)
            self.horario_inicio = self.franja_inicio.hora_inicio
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
