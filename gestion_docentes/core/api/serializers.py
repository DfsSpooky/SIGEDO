from rest_framework import serializers


from ..models import Asistencia, BloqueHorario, Curso, Docente, Justificacion, TipoJustificacion

# ... (Existing Serializers) ...

class TipoJustificacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoJustificacion
        fields = ['id', 'nombre']

class JustificationSerializer(serializers.ModelSerializer):
    tipo_nombre = serializers.ReadOnlyField(source='tipo.nombre')
    tipo_id = serializers.PrimaryKeyRelatedField(
        queryset=TipoJustificacion.objects.all(), source='tipo', write_only=True
    )
    documentoBase64 = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Justificacion
        fields = [
            'id', 'tipo_id', 'tipo_nombre', 'fecha_inicio', 'fecha_fin', 
            'motivo', 'estado', 'fecha_creacion', 'documento_adjunto', 'documentoBase64'
        ]
        read_only_fields = ['id', 'estado', 'fecha_creacion', 'documento_adjunto']

    def validate_documentoBase64(self, value):
        if not value:
            return None
        try:
            # Simple check, real decoding happens in view or create method
            format, imgstr = value.split(";base64,")
            return value
        except:
            raise serializers.ValidationError("Formato de archivo inválido. Use data:application/pdf;base64,... o similar.")

    def create(self, validated_data):
        documento_base64 = validated_data.pop('documentoBase64', None)
        justificacion = Justificacion.objects.create(**validated_data)
        
        if documento_base64:
            import base64
            from django.core.files.base import ContentFile
            from django.utils import timezone
            
            try:
                format, imgstr = documento_base64.split(";base64,")
                ext = format.split("/")[-1]
                if ext == "pdf": 
                    ext = "pdf"
                elif "image" in format:
                    ext = format.split("/")[-1]
                
                # Nombre de archivo único
                current_time = timezone.now().strftime("%Y%m%d_%H%M%S")
                filename = f"justificacion_{justificacion.id}_{current_time}.{ext}"
                
                data = ContentFile(base64.b64decode(imgstr), name=filename)
                justificacion.documento_adjunto = data
                justificacion.save()
            except Exception as e:
                print(f"Error guardando archivo: {e}")
                # No fallamos la request principal, pero logueamos el error
        
        return justificacion


class DocenteInfoSerializer(serializers.ModelSerializer):
    """
    Serializer para la información básica del docente que se muestra en el kiosco.
    """

    # Renombramos y formateamos campos para que coincidan con la salida JSON esperada
    photoUrl = serializers.ImageField(source="foto", use_url=True)
    name = serializers.CharField(source="get_full_name")

    class Meta:
        model = Docente
        fields = ["name", "dni", "photoUrl"]


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
    hora_salida_permitida_str = serializers.TimeField(
        source="hora_salida_permitida", format="%H:%M:%S", allow_null=True
    )

    class Meta:
        model = Asistencia
        fields = [
            "id",
            "name",
            "entryMarked",
            "exitMarked",
            "canMarkExit",
            "hora_salida_permitida_str",
        ]

    def get_name(self, obj):
        # obj es una instancia de Asistencia, accedemos al curso relacionado
        # y buscamos el bloque de horario para la fecha de la asistencia.
        bloque = BloqueHorario.objects.filter(
            curso=obj.curso, dia_semana=obj.fecha.weekday()
        ).first()
        if bloque:
            return f'{obj.curso.nombre} ({bloque.horario_inicio.strftime("%I:%M %p")} - {bloque.horario_fin.strftime("%I:%M %p")})'
        return obj.curso.nombre

    def get_entryMarked(self, obj):
        return obj.hora_entrada is not None

    def get_exitMarked(self, obj):
        return obj.hora_salida is not None


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
