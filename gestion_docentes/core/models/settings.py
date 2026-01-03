from django.db import models


class ConfiguracionInstitucion(models.Model):
    nombre_institucion = models.CharField(
        max_length=255, help_text="El nombre oficial de la institución."
    )
    logo = models.ImageField(
        upload_to="configuracion/",
        help_text="Logo que aparecerá en las credenciales y reportes.",
    )
    direccion = models.CharField(
        max_length=255, blank=True, help_text="Dirección física de la institución."
    )
    telefono = models.CharField(
        max_length=20, blank=True, help_text="Teléfono de contacto."
    )
    email_contacto = models.EmailField(
        blank=True, help_text="Email de contacto oficial."
    )
    # String reference
    facultad = models.ForeignKey(
        "core.Carrera",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Seleccione la facultad o carrera principal para la cual se está configurando el sistema.",
    )
    tiempo_limite_tardanza = models.PositiveIntegerField(
        default=10,
        help_text="Minutos de tolerancia para considerar una asistencia como tardanza.",
    )
    nombre_dashboard = models.CharField(
        max_length=100,
        default="Gestión Docente",
        help_text="El nombre que se mostrará en el dashboard.",
    )
    
    validar_geolocalizacion = models.BooleanField(
        default=True,
        help_text="Si está activo, se validará que el docente esté dentro del campus para marcar."
    )
    
    hora_inicio_asistencia_general = models.TimeField(
        default="07:00",
        help_text="Hora desde la cual se permite marcar la Entrada General.",
    )
    
    hora_fin_asistencia_general = models.TimeField(
        default="23:00",
        help_text="Hora hasta la cual se permite marcar la Entrada General.",
    )

    class Meta:
        verbose_name = "Configuración de la Institución"
        verbose_name_plural = "Configuración de la Institución"

    def __str__(self):
        return self.nombre_institucion

    @classmethod
    def load(cls):
        obj = cls.objects.first()
        if obj is None:
            obj = cls.objects.create()
        return obj
