from django.db import models

class Notificacion(models.Model):
    # String reference
    destinatario = models.ForeignKey(
        "core.Docente", on_delete=models.CASCADE, related_name="notificaciones"
    )
    mensaje = models.TextField()
    leido = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    url = models.CharField(
        max_length=255,
        blank=True,
        help_text="URL a la que la notificación debe dirigir.",
    )

    class Meta:
        ordering = ["-fecha_creacion"]
        verbose_name = "Notificación"
        verbose_name_plural = "Notificaciones"

    def __str__(self):
        return f"Notificación para {self.destinatario.username}: {self.mensaje[:30]}..."

class Anuncio(models.Model):
    titulo = models.CharField(max_length=200)
    contenido = models.TextField()
    fecha_publicacion = models.DateTimeField(auto_now_add=True)
    # String reference
    autor = models.ForeignKey(
        "core.Docente",
        on_delete=models.SET_NULL,
        null=True,
        limit_choices_to={"is_staff": True},
    )

    class Meta:
        ordering = ["-fecha_publicacion"]
        verbose_name = "Anuncio"
        verbose_name_plural = "Anuncios"

    def __str__(self):
        return self.titulo
