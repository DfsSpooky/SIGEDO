import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from PIL import Image


class Docente(AbstractUser):
    DISPONIBILIDAD_CHOICES = [
        ("COMPLETO", "Tiempo Completo (Mañana y Tarde)"),
        ("MANANA", "Solo Mañana"),
        ("TARDE", "Solo Tarde"),
    ]
    dni = models.CharField(max_length=8, unique=True, db_index=True)
    # Using string reference for Especialidad to avoid circular import with academic.py
    especialidades = models.ManyToManyField(
        "core.Especialidad", related_name="docentes"
    )
    disponibilidad = models.CharField(
        max_length=20,
        choices=DISPONIBILIDAD_CHOICES,
        default="COMPLETO",
        help_text="Define la disponibilidad del docente para la asignación de horarios.",
    )
    id_qr = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    rfid_uid = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
        help_text="UID de la tarjeta RFID asignada al docente",
    )
    foto = models.ImageField(
        upload_to="fotos_docentes/",
        null=True,
        blank=True,
        default="fotos_docentes/placeholder.png",
    )
    fcm_token = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        help_text="Token de notificaciones Push (Firebase)"
    )

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.foto:
            try:
                img = Image.open(self.foto.path)
                if img.height > 300 or img.width > 300:
                    output_size = (300, 300)
                    img.thumbnail(output_size)
                    img.save(self.foto.path, format="PNG", quality=85)
            except Exception as e:
                # Log the error, but don't prevent the model from saving
                print(f"Error al redimensionar la imagen para {self.username}: {e}")


class PersonalDocente(Docente):
    class Meta:
        proxy = True
        verbose_name = "Personal Docente"
        verbose_name_plural = "Personal Docente"


class Administrador(Docente):
    class Meta:
        proxy = True
        verbose_name = "Administrador"
        verbose_name_plural = "Administradores"
