"""
Modelos para la aplicación de Inventario.

NOTA PARA LA MIGRACIÓN: Para evitar una migración de datos compleja,
se debe añadir la clase Meta a cada modelo con la opción `db_table`
apuntando a su tabla original. Ej: `db_table = 'core_activo'`.
Esto se hará en un paso posterior de limpieza.
"""
from django.db import models
from datetime import date

# Las referencias a modelos de otras apps (como 'core.Docente') se mantienen como strings
# para evitar importaciones circulares y se resolverán más tarde.

class TipoActivo(models.Model):
    nombre = models.CharField(max_length=100, unique=True, help_text="Ej: Laptop, Proyector, Monitor")

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Tipo de Activo"
        verbose_name_plural = "Tipos de Activos"
        ordering = ['nombre']
        db_table = 'core_tipoactivo' # Apuntar a la tabla original

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
        db_table = 'core_activo' # Apuntar a la tabla original
