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
            obj = cls.objects.create(nombre_institucion="Mi Institución")
        return obj

    def validar_ubicacion(self, lat, lng):
        """
        Valida si una ubicación dada está dentro del rango permitido del campus.
        Retorna (es_valido, distancia_o_error).
        """
        from django.conf import settings
        from core.utils.geo import calculate_haversine_distance
        
        if not self.validar_geolocalizacion:
            return True, 0
            
        if lat is None or lng is None:
            return False, "Ubicación requerida por política institucional."
            
        campus_lat, campus_lng = settings.CAMPUS_LOCATION
        distance = calculate_haversine_distance(campus_lat, campus_lng, lat, lng)
        
        if distance > settings.ALLOWED_RADIUS_METERS:
            return False, f"Fuera de rango. Distancia: {int(distance)}m (Máx: {settings.ALLOWED_RADIUS_METERS}m)."
            
        return True, distance
