from django.db import models
from django.urls import reverse

# NOTA: Las dependencias de modelos de otras apps se manejan con strings
# para evitar importaciones circulares. Ej: 'inventario.Activo'.

class Reserva(models.Model):
    ESTADO_CHOICES = [
        ('RESERVADO', 'Reservado'),
        ('EN_USO', 'En Uso'),
        ('FINALIZADO', 'Finalizado'),
        ('CANCELADO', 'Cancelado por usuario'),
        ('EXPIRADO', 'Expirado automáticamente'),
    ]

    activo = models.ForeignKey('inventario.Activo', on_delete=models.CASCADE, related_name='reservas')
    docente = models.ForeignKey('core.Docente', on_delete=models.CASCADE, related_name='reservas')
    curso = models.ForeignKey('core.Curso', on_delete=models.SET_NULL, null=True, blank=True, related_name='reservas_equipos', help_text="Curso asociado a la reserva (opcional)")

    franja_horaria_inicio = models.ForeignKey('core.FranjaHoraria', on_delete=models.PROTECT, related_name='reservas_inicio', null=True, blank=True)
    franja_horaria_fin = models.ForeignKey('core.FranjaHoraria', on_delete=models.PROTECT, related_name='reservas_fin', null=True, blank=True)

    fecha_reserva = models.DateField()
    estado = models.CharField(max_length=30, choices=ESTADO_CHOICES, default='RESERVADO')

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_confirmacion = models.DateTimeField(null=True, blank=True, help_text="Momento en que se recoge el equipo.")
    fecha_finalizacion = models.DateTimeField(null=True, blank=True, help_text="Momento en que se devuelve el equipo.")

    def __str__(self):
        if self.curso:
            return f"Reserva de {self.activo.nombre} para el curso '{self.curso.nombre}' el {self.fecha_reserva}"
        elif self.franja_horaria_inicio and self.franja_horaria_fin:
            return f"Reserva de {self.activo.nombre} para {self.docente.username} el {self.fecha_reserva} de {self.franja_horaria_inicio.hora_inicio} a {self.franja_horaria_fin.hora_fin}"
        elif self.franja_horaria_inicio:
            return f"Reserva de {self.activo.nombre} para {self.docente.username} el {self.fecha_reserva} a las {self.franja_horaria_inicio.hora_inicio}"
        else:
            return f"Reserva de {self.activo.nombre} para {self.docente.username} el {self.fecha_reserva}"

    def save(self, *args, **kwargs):
        # La importación de 'Notificacion' se corregirá en la fase de limpieza de importaciones.
        from core.models import Notificacion

        is_new = self._state.adding
        if not is_new:
            try:
                old_instance = Reserva.objects.get(pk=self.pk)
                if old_instance.estado != 'FINALIZADO' and self.estado == 'FINALIZADO':
                    mensaje = f"El equipo '{self.activo.nombre}' ha sido devuelto. Tu reserva para el curso '{self.curso.nombre}' ha finalizado."
                    Notificacion.objects.create(
                        destinatario=self.docente,
                        mensaje=mensaje,
                        url=reverse('reservas:mis_reservas')
                    )
            except Reserva.DoesNotExist:
                pass

        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Reserva de Activo"
        verbose_name_plural = "Reservas de Activos"
        ordering = ['-fecha_reserva', '-franja_horaria_inicio__hora_inicio']
        db_table = 'core_reserva' # Apuntar a la tabla original
