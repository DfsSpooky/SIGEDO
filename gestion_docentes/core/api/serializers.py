from rest_framework import serializers



from ..models import Asistencia, BloqueHorario, Curso, Docente, Justificacion, TipoJustificacion
from ..models.settings import ConfiguracionInstitucion

class ConfiguracionInstitucionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfiguracionInstitucion
        fields = ['nombre_institucion', 'logo']


class TipoJustificacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoJustificacion
        fields = ['id', 'nombre']

class JustificationSerializer(serializers.ModelSerializer):
    tipo_nombre = serializers.ReadOnlyField(source='tipo.nombre')
    tipo_id = serializers.PrimaryKeyRelatedField(
        queryset=TipoJustificacion.objects.all(), source='tipo', write_only=True
    )

    class Meta:
        model = Justificacion
        fields = [
            'id', 'tipo_id', 'tipo_nombre', 'fecha_inicio', 'fecha_fin', 
            'motivo', 'estado', 'fecha_creacion', 'documento_adjunto'
        ]
        read_only_fields = ['id', 'estado', 'fecha_creacion']

    def create(self, validated_data):
        # El archivo ya viene en validated_data si se usa Multipart/Form-Data
        return super().create(validated_data)


class DocenteInfoSerializer(serializers.ModelSerializer):
    """
    Serializer para la información básica del docente que se muestra en el kiosco.
    """

    # Renombramos y formateamos campos para que coincidan con la salida JSON esperada
    photoUrl = serializers.ImageField(source="foto", use_url=True)
    name = serializers.CharField(source="get_full_name")

    class Meta:
        model = Docente
        fields = ["name", "dni", "photoUrl", "email", "is_staff"]


class CursoAsistenciaSerializer(serializers.ModelSerializer):
    """
    Serializer para la información de un curso y el estado de asistencia del docente.
    Combina datos del modelo Curso y Asistencia.
    """

    # Campos del modelo Curso
    id = serializers.IntegerField(source="curso.id")
    name = serializers.SerializerMethodField()

    # Campos calculados o renombrados del modelo Asistencia
    entryMarked = serializers.SerializerMethodField()
    exitMarked = serializers.SerializerMethodField()
    canMarkExit = serializers.BooleanField(source="puede_marcar_salida")
    hora_salida_permitida_str = serializers.SerializerMethodField()

    class Meta:
        model = Asistencia
        fields = [
            "id",
            "name",
            "entryMarked",
            "exitMarked",
            "canMarkExit",
            "hora_salida_permitida_str",
            "startTime",
            "endTime",
            "classroom",
        ]

    startTime = serializers.SerializerMethodField()
    endTime = serializers.SerializerMethodField()
    classroom = serializers.SerializerMethodField()

    def get_bloque(self, obj):
        try:
             if not obj.fecha: return None
             return BloqueHorario.objects.filter(
                curso=obj.curso, dia_semana=obj.fecha.weekday()
            ).first()
        except:
            return None

    def get_startTime(self, obj):
        bloque = self.get_bloque(obj)
        if bloque and bloque.horario_inicio:
            return bloque.horario_inicio.strftime("%H:%M:%S")
        return None

    def get_endTime(self, obj):
        bloque = self.get_bloque(obj)
        if bloque and bloque.horario_fin:
            return bloque.horario_fin.strftime("%H:%M:%S")
        return None

    def get_classroom(self, obj):
        bloque = self.get_bloque(obj)
        if bloque and bloque.aula:
            return bloque.aula.nombre
        return None

    def get_name(self, obj):
        try:
            # obj es una instancia de Asistencia, accedemos al curso relacionado
            # y buscamos el bloque de horario para la fecha de la asistencia.
            if not obj.fecha:
                return obj.curso.nombre

            bloque = BloqueHorario.objects.filter(
                curso=obj.curso, dia_semana=obj.fecha.weekday()
            ).first()
            
            if bloque and bloque.horario_inicio and bloque.horario_fin:
                return f'{obj.curso.nombre} ({bloque.horario_inicio.strftime("%I:%M %p")} - {bloque.horario_fin.strftime("%I:%M %p")})'
        except Exception:
            # En caso de cualquier error (ej. fecha invalida, hora nula, etc),
            # devolvemos solo el nombre del curso para no romper el endpoint.
            pass
        return obj.curso.nombre

    def get_entryMarked(self, obj):
        return obj.hora_entrada is not None

    def get_exitMarked(self, obj):
        return obj.hora_salida is not None

    def get_hora_salida_permitida_str(self, obj):
        if obj.hora_salida_permitida:
            from django.utils import timezone
            # Convertir a hora local si es necesario, o usar directamente si ya lo es.
            # Django DateTimeField suele ser timezone aware.
            local_dt = timezone.localtime(obj.hora_salida_permitida)
            return local_dt.strftime("%H:%M:%S")
        return None


class MarkAttendanceSerializer(serializers.Serializer):
    """
    Serializer para validar los datos de entrada al marcar una asistencia.
    """

    qrId = serializers.UUIDField()
    actionType = serializers.ChoiceField(
        choices=["general_entry", "general_exit", "course_entry", "course_exit"]
    )
    courseId = serializers.IntegerField(required=False, allow_null=True)
    photoBase64 = serializers.CharField()

    def validate_photoBase64(self, value):
        """
        Valida que el campo photoBase64 tenga el formato correcto de una imagen base64.
        """
        try:
            format, imgstr = value.split(";base64,")
            ext = format.split("/")[-1]
            if ext not in ["png", "jpeg", "jpg"]:
                raise serializers.ValidationError(
                    "Formato de imagen no válido. Use PNG o JPEG."
                )
        except:
            raise serializers.ValidationError("Formato de photoBase64 inválido.")
        return value


class RegistrarAsistenciaRfidSerializer(serializers.Serializer):
    """
    Serializer para validar el UID de RFID.
    """

    uid = serializers.CharField(max_length=100)


class MobileMarkAttendanceSerializer(serializers.Serializer):
    """
    Serializer para validar los datos de entrada al marcar una asistencia desde la App Móvil.
    No requiere qrId ya que el usuario está autenticado.
    """

    actionType = serializers.ChoiceField(
        choices=["general_entry", "general_exit", "course_entry", "course_exit"]
    )
    courseId = serializers.IntegerField(required=False, allow_null=True)
    photoBase64 = serializers.CharField()
    latitude = serializers.FloatField(required=False, allow_null=True)
    longitude = serializers.FloatField(required=False, allow_null=True)

    def validate_photoBase64(self, value):
        """
        Valida que el campo photoBase64 tenga el formato correcto de una imagen base64.
        """
        try:
            format, imgstr = value.split(";base64,")
            ext = format.split("/")[-1]
            if ext not in ["png", "jpeg", "jpg"]:
                raise serializers.ValidationError(
                    "Formato de imagen no válido. Use PNG o JPEG."
                )
        except:
            raise serializers.ValidationError("Formato de photoBase64 inválido.")
        return value
