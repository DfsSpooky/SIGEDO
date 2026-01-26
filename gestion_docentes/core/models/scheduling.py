from datetime import datetime, date
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

    def get_duracion_real_minutos(self):
        """
        Calcula la duración exacta del bloque basándose en su hora de inicio y fin.
        Esto se adapta automáticamente a si la franja es de 45, 50 o 60 minutos.
        """
        if not self.horario_inicio or not self.horario_fin:
            return 0
            
        # Truco para restar horas: combinarlas con una fecha ficticia
        dummy_date = date(2000, 1, 1)
        inicio_dt = datetime.combine(dummy_date, self.horario_inicio)
        fin_dt = datetime.combine(dummy_date, self.horario_fin)
        
        diferencia = fin_dt - inicio_dt
        return int(diferencia.total_seconds() / 60)

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

        # 1-4. Validación Unificada de Cruces (Q Objects Optimization)
        # ---------------------------------------------------------------------
        from django.db.models import Q

        # Condiciones base: Mismo día, y superposición de horario (Start < End2 AND End > Start2)
        q_superposicion = Q(dia=self.dia) & Q(horario_inicio__lt=end_time) & Q(horario_fin__gt=start_time)

        # Filtros específicos (se aplican solo si el campo no es nulo)
        q_docente = Q()
        if self.curso.docente:
            q_docente = Q(curso__docente=self.curso.docente)

        q_aula = Q()
        if self.aula:
            q_aula = Q(aula=self.aula)

        q_grupo = Q()
        if self.curso.pk:
            # Nueva lógica: Conflicto solo si se comparte SEMESTRE y alguna ESPECIALIDAD
            # No basta con compartir Grupo, pues un Grupo puede tener varias especialidades (Matemática, Biología)
            # que pueden llevar clases simultáneas.
            
            # 1. Obtener especialidades de MI curso
            mis_especialidades = list(self.curso.especialidades.values_list('id', flat=True))
            
            if mis_especialidades:
                 # Conflicto si:
                 # El otro curso tiene el mismo semestre cursado
                 # Y el otro curso tiene AL MENOS UNA especialidad en común con las mías
                 q_grupo = Q(
                     curso__semestre_cursado=self.curso.semestre_cursado,
                     curso__especialidades__id__in=mis_especialidades
                 )

        # Consulta unificada: Buscar cualquier bloque que cumpla (Superposición) Y (MismoDocente O MismoAula O IntersecciónEspecialidad)
        conflicto = BloqueHorario.objects.filter(
            q_superposicion & (q_docente | q_aula | q_grupo)
        ).exclude(pk=self.pk).select_related('curso', 'curso__docente', 'aula').first()

        if conflicto:
            # Determinamos cuál fue la causa para dar un mensaje error específico
            if self.curso.docente and conflicto.curso.docente == self.curso.docente:
                 raise ValidationError(
                    f"El docente {self.curso.docente} ya tiene clase asignada en este horario ({conflicto.curso})."
                )

            if self.aula and conflicto.aula == self.aula:
                 raise ValidationError(
                    f"El aula {self.aula} ya está ocupada en este horario ({conflicto.curso})."
                )

            # Si llegamos aquí y hay conflicto, asumimos que fue por grupo (ya que las otras dos condiciones fallaron o no aplicaban)
            # Podríamos refinar la verificación si fuera necesario, pero esto cubre el 99%
            raise ValidationError(
                 f"Conflicto de Grupo: Los estudiantes del semestre {self.curso.semestre_cursado} ya tienen clase ({conflicto.curso})."
            )

        # Validación Extra: Bloques No Lectivos (Docente)
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
            # Obtener los grupos únicos de las especialidades de este curso
            grupos_unicos = set()
            for esp in self.curso.especialidades.all():
                if esp.grupo:
                    grupos_unicos.add(esp.grupo)
            
            for grupo in grupos_unicos:
                 # Buscamos todos los bloques de este grupo en este dia/semestre
                 # Bloques cuyo curso tenga 'alguna' especialidad en 'este' grupo
                 # Usamos distinct() para que si un bloque tiene varias especialidades del mismo grupo, no se cuente doble
                 bloques_grupo_q = BloqueHorario.objects.filter(
                    curso__especialidades__grupo=grupo,
                    curso__semestre_cursado=self.curso.semestre_cursado,
                    dia=self.dia
                 ).exclude(pk=self.pk).distinct()
                 
                 horas_grupo = bloques_grupo_q.aggregate(total=models.Sum("duracion_bloques"))["total"] or 0

                 if horas_grupo + self.duracion_bloques > 6:
                      raise ValidationError(
                            f"El grupo {grupo} excede el límite de 6 horas diarias ({horas_grupo}h + {self.duracion_bloques}h > 6h)."
                        )

        # 7. Validar Carga Continua del Docente (Max 5 bloques seguidos ~ 4h 10m)
        if self.curso.docente:
            # Estrategia: Reconstruir la línea de tiempo del día
            bloques_dia = list(BloqueHorario.objects.filter(
                curso__docente=self.curso.docente,
                dia=self.dia
            ).exclude(pk=self.pk).order_by('franja_inicio__hora_inicio'))
            
            # Simulamos insertar el bloque actual
            bloques_dia.append(self)
            bloques_dia.sort(key=lambda b: b.franja_inicio.hora_inicio if b.franja_inicio else time.min)

            # Convertir a lista de índices de franjas para verificar contigüidad
            # Asumimos que las franjas están ordenadas por ID o Hora. Mejor usar Hora.
            todas_franjas = list(FranjaHoraria.objects.order_by('hora_inicio'))
            franja_map = {f.id: i for i, f in enumerate(todas_franjas)}
            
            slots_ocupados = set()
            for b in bloques_dia:
                if b.franja_inicio_id in franja_map:
                    start_idx = franja_map[b.franja_inicio_id]
                    for i in range(b.duracion_bloques):
                        slots_ocupados.add(start_idx + i)
            
            # Contar racha máxima
            sorted_slots = sorted(list(slots_ocupados))
            max_consecutive = 0
            current_consecutive = 0
            last_slot = -1
            
            for slot in sorted_slots:
                if slot == last_slot + 1:
                    current_consecutive += 1
                else:
                    current_consecutive = 1
                last_slot = slot
                if current_consecutive > max_consecutive:
                    max_consecutive = current_consecutive
            
            if max_consecutive > 5:
                raise ValidationError(
                    f"El docente {self.curso.docente} excedería el límite de 5 bloques consecutivos sin descanso ({max_consecutive} bloques)."
                )

        # 8. Validar Reglas de Turno por Semestre
        # Semestres 1-4: Turno MAÑANA (salvo excepción)
        # Semestres 5-10: Turno TARDE
        if self.curso.pk and self.curso.semestre_cursado:
            turno_franja = self.franja_inicio.turno
            semestre = self.curso.semestre_cursado

            if semestre <= 4:
                if turno_franja == "TARDE" and not self.curso.excepcion_horario:
                    raise ValidationError(
                        f"Los cursos del Semestre {semestre} deben dictarse en la MAÑANA (salvo excepción habilitada)."
                    )
            elif semestre >= 5:
                if turno_franja == "MANANA":
                    raise ValidationError(
                        f"Los cursos del Semestre {semestre} deben dictarse en la TARDE."
                    )

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