import os
import uuid
from pathlib import Path

from django.db import models
from django.utils import timezone
from django.utils.text import slugify


def respaldo_upload_to(instance, filename):
    timestamp = timezone.now()
    base_name = Path(filename).stem
    extension = Path(filename).suffix.lower() or ".dump"
    safe_name = slugify(base_name) or "respaldo"
    unique = uuid.uuid4().hex[:8]
    return (
        f"backups/{timestamp:%Y/%m/%d}/"
        f"{timestamp:%H%M%S}_{unique}_{safe_name}{extension}"
    )


class RespaldoSistema(models.Model):
    ORIGEN_CHOICES = [
        ("GENERADO", "Generado por el sistema"),
        ("SUBIDO", "Subido manualmente"),
        ("PRE_RESTORE", "Previo a restauracion"),
        ("SINCRONIZADO", "Sincronizado desde almacenamiento"),
    ]
    FORMATO_CHOICES = [
        ("POSTGRES_CUSTOM", "PostgreSQL Custom"),
        ("POSTGRES_PLAIN", "PostgreSQL SQL"),
        ("SQLITE", "SQLite"),
        ("DESCONOCIDO", "Desconocido"),
    ]
    ESTADO_CHOICES = [
        ("DISPONIBLE", "Disponible"),
        ("RESTAURANDO", "Restaurando"),
        ("RESTAURADO", "Restaurado"),
        ("ERROR", "Error"),
    ]

    nombre = models.CharField(max_length=255)
    descripcion = models.TextField(blank=True)
    archivo = models.FileField(upload_to=respaldo_upload_to, max_length=500)
    origen = models.CharField(
        max_length=20, choices=ORIGEN_CHOICES, default="GENERADO"
    )
    formato = models.CharField(
        max_length=20, choices=FORMATO_CHOICES, default="DESCONOCIDO"
    )
    estado = models.CharField(
        max_length=20, choices=ESTADO_CHOICES, default="DISPONIBLE"
    )
    checksum_sha256 = models.CharField(max_length=64, blank=True, db_index=True)
    tamano_bytes = models.BigIntegerField(default=0)
    creado_por = models.ForeignKey(
        "core.Docente",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="respaldos_creados",
    )
    restaurado_por = models.ForeignKey(
        "core.Docente",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="respaldos_restaurados",
    )
    respaldo_previo = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="restauraciones_relacionadas",
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    fecha_restauracion = models.DateTimeField(null=True, blank=True)
    log_restauracion = models.TextField(blank=True)

    class Meta:
        verbose_name = "Respaldo del sistema"
        verbose_name_plural = "Respaldos del sistema"
        ordering = ("-fecha_creacion",)

    def __str__(self):
        return self.nombre

    @property
    def nombre_archivo(self):
        return os.path.basename(self.archivo.name or "")
