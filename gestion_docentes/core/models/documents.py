from django.db import models


class TipoDocumento(models.Model):
    nombre = models.CharField(max_length=100)

    def __str__(self):
        return self.nombre


class Documento(models.Model):
    ESTADOS_DOCUMENTO = [
        ("RECIBIDO", "Recibido"),
        ("EN_REVISION", "En Revisión"),
        ("APROBADO", "Aprobado"),
        ("OBSERVADO", "Observado"),
        ("VENCIDO", "Vencido"),
    ]

    titulo = models.CharField(max_length=200)
    tipo_documento = models.ForeignKey(TipoDocumento, on_delete=models.CASCADE)
    # String reference
    docente = models.ForeignKey(
        "core.Docente", on_delete=models.CASCADE, related_name="documentos"
    )
    fecha_subida = models.DateTimeField(auto_now_add=True)
    fecha_vencimiento = models.DateField(
        null=True,
        blank=True,
        help_text="Opcional: Dejar en blanco si el documento no vence.",
    )
    estado = models.CharField(
        max_length=20, choices=ESTADOS_DOCUMENTO, default="RECIBIDO"
    )
    observaciones = models.TextField(
        blank=True,
        help_text="Notas internas para la administración. No son visibles para el docente.",
    )

    def __str__(self):
        return self.titulo


class VersionDocumento(models.Model):
    documento = models.ForeignKey(
        Documento, on_delete=models.CASCADE, related_name="versiones"
    )
    archivo = models.FileField(upload_to="documentos/%Y/%m/%d/")
    fecha_version = models.DateTimeField(auto_now_add=True)
    numero_version = models.PositiveIntegerField(editable=False)

    class Meta:
        ordering = ["-fecha_version"]

    def save(self, *args, **kwargs):
        if not self.pk:
            ultima_version = (
                VersionDocumento.objects.filter(documento=self.documento)
                .order_by("-numero_version")
                .first()
            )
            self.numero_version = (
                (ultima_version.numero_version + 1) if ultima_version else 1
            )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.documento.titulo} (v{self.numero_version})"
