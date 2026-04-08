from django.db import models
from django.db.models import Q
from datetime import date

# Se usa una referencia string 'core.Docente' en el ForeignKey para evitar importaciones circulares,
# ya que este archivo será importado por 'models.py', que a su vez define a Docente.

class TipoActivo(models.Model):
    nombre = models.CharField(max_length=100, unique=True, help_text="Ej: Laptop, Proyector, Monitor")

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Tipo de Activo"
        verbose_name_plural = "Tipos de Activos"
        ordering = ['nombre']

class Activo(models.Model):
    ESTADO_CHOICES = [
        ('DISPONIBLE', 'Disponible'),
        ('ASIGNADO', 'Asignado'),
        ('EN_MANTENIMIENTO', 'En Mantenimiento'),
        ('DE_BAJA', 'De Baja'),
    ]

    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, null=True)
    codigo_patrimonial = models.CharField(max_length=100, unique=True, help_text="Código único patrimonial o número de serie")
    tipo = models.ForeignKey(TipoActivo, on_delete=models.PROTECT, related_name='activos')
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='DISPONIBLE')
    asignado_a = models.ForeignKey('core.Docente', on_delete=models.SET_NULL, null=True, blank=True, related_name='activos')
    fecha_adquisicion = models.DateField(null=True, blank=True)
    fecha_asignacion = models.DateField(null=True, blank=True)
    observaciones = models.TextField(blank=True)

    def __str__(self):
        return f"{self.nombre} ({self.codigo_patrimonial})"

    def save(self, *args, **kwargs):
        # Si se está asignando un docente y no hay fecha de asignación, la ponemos.
        if self.asignado_a and not self.fecha_asignacion:
            self.fecha_asignacion = date.today()
            self.estado = 'ASIGNADO'
        # Si se quita el docente, limpiamos la fecha y cambiamos el estado a disponible.
        elif not self.asignado_a:
            self.fecha_asignacion = None
            if self.estado == 'ASIGNADO':
                self.estado = 'DISPONIBLE'
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Activo"
        verbose_name_plural = "Activos"
        ordering = ['nombre']


class Reserva(models.Model):
    ESTADO_CHOICES = [
        ('RESERVADO', 'Reservado'),
        ('EN_USO', 'En Uso'),
        ('FINALIZADO', 'Finalizado'),
        ('CANCELADO', 'Cancelado por usuario'),
        ('EXPIRADO', 'Expirado automáticamente'),
    ]

    activo = models.ForeignKey(Activo, on_delete=models.CASCADE, related_name='reservas')
    docente = models.ForeignKey('core.Docente', on_delete=models.CASCADE, related_name='reservas')
    franja_horaria = models.ForeignKey('core.FranjaHoraria', on_delete=models.PROTECT, related_name='reservas')
    fecha_reserva = models.DateField()
    estado = models.CharField(max_length=30, choices=ESTADO_CHOICES, default='RESERVADO')

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_confirmacion = models.DateTimeField(null=True, blank=True, help_text="Momento en que se recoge el equipo.")
    fecha_finalizacion = models.DateTimeField(null=True, blank=True, help_text="Momento en que se devuelve el equipo.")

    def __str__(self):
        return f"Reserva de {self.activo.nombre} para {self.docente.username} el {self.fecha_reserva} a las {self.franja_horaria.hora_inicio}"

    class Meta:
        verbose_name = "Reserva de Activo"
        verbose_name_plural = "Reservas de Activos"
        ordering = ['-fecha_reserva', '-franja_horaria__hora_inicio']
        constraints = [
            models.UniqueConstraint(
                fields=['activo', 'fecha_reserva', 'franja_horaria'],
                condition=Q(estado__in=['RESERVADO', 'EN_USO']),
                name='unique_reserva_activa'
            )
        ]
