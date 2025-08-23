from rest_framework import serializers
from ..models import Docente, Curso, Asistencia

class DocenteInfoSerializer(serializers.ModelSerializer):
    """
    Serializer para la información básica del docente que se muestra en el kiosco.
    """
    # Renombramos y formateamos campos para que coincidan con la salida JSON esperada
    photoUrl = serializers.ImageField(source='foto', use_url=True)
    name = serializers.CharField(source='get_full_name')

    class Meta:
        model = Docente
        fields = ['name', 'dni', 'photoUrl']


class CursoAsistenciaSerializer(serializers.ModelSerializer):
    """
    Serializer para la información de un curso y el estado de asistencia del docente.
    Combina datos del modelo Curso y Asistencia.
    """
    # Campos del modelo Curso
    id = serializers.IntegerField(source='curso.id')
    name = serializers.SerializerMethodField()

    # Campos calculados o renombrados del modelo Asistencia
    entryMarked = serializers.SerializerMethodField()
    exitMarked = serializers.SerializerMethodField()
    canMarkExit = serializers.BooleanField(source='puede_marcar_salida')
    hora_salida_permitida_str = serializers.TimeField(source='hora_salida_permitida', format='%H:%M:%S', allow_null=True)

    class Meta:
        model = Asistencia
        fields = ['id', 'name', 'entryMarked', 'exitMarked', 'canMarkExit', 'hora_salida_permitida_str']

    def get_name(self, obj):
        # obj es una instancia de Asistencia, accedemos al curso relacionado
        return f'{obj.curso.nombre} ({obj.curso.horario_inicio.strftime("%H:%M")} - {obj.curso.horario_fin.strftime("%H:%M")})'

    def get_entryMarked(self, obj):
        return obj.hora_entrada is not None

    def get_exitMarked(self, obj):
        return obj.hora_salida is not None


class MarkAttendanceSerializer(serializers.Serializer):
    """
    Serializer para validar los datos de entrada al marcar una asistencia.
    """
    qrId = serializers.UUIDField()
    actionType = serializers.ChoiceField(choices=['general_entry', 'course_entry', 'course_exit'])
    courseId = serializers.IntegerField(required=False, allow_null=True)
    photoBase64 = serializers.CharField()

    def validate_photoBase64(self, value):
        """
        Valida que el campo photoBase64 tenga el formato correcto de una imagen base64.
        """
        try:
            format, imgstr = value.split(';base64,')
            ext = format.split('/')[-1]
            if ext not in ['png', 'jpeg', 'jpg']:
                raise serializers.ValidationError("Formato de imagen no válido. Use PNG o JPEG.")
        except:
            raise serializers.ValidationError("Formato de photoBase64 inválido.")
        return value


class RegistrarAsistenciaRfidSerializer(serializers.Serializer):
    """
    Serializer para validar el UID de RFID.
    """
    uid = serializers.CharField(max_length=100)


# ========= SERIALIZERS PARA RESERVAS =========

from ..models import TipoActivo, Activo, FranjaHoraria, Reserva

class TipoActivoSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoActivo
        fields = ['id', 'nombre']

class ActivoSerializer(serializers.ModelSerializer):
    tipo = TipoActivoSerializer(read_only=True)

    class Meta:
        model = Activo
        fields = ['id', 'nombre', 'descripcion', 'codigo_patrimonial', 'tipo', 'estado']

class FranjaHorariaSerializer(serializers.ModelSerializer):
    class Meta:
        model = FranjaHoraria
        fields = ['id', 'hora_inicio', 'hora_fin', 'turno']

class ReservaSerializer(serializers.ModelSerializer):
    franja_horaria_inicio = FranjaHorariaSerializer(read_only=True)
    franja_horaria_fin = FranjaHorariaSerializer(read_only=True)

    class Meta:
        model = Reserva
        fields = ['id', 'estado', 'fecha_reserva', 'franja_horaria_inicio', 'franja_horaria_fin']

class ReservaCreateSerializer(serializers.Serializer):
    activo_id = serializers.IntegerField()
    fecha = serializers.DateField()
    franja_inicio_id = serializers.IntegerField()
    franja_fin_id = serializers.IntegerField()

    def validate(self, data):
        """
        Comprueba que la franja de fin no sea anterior a la de inicio.
        """
        try:
            franja_inicio = FranjaHoraria.objects.get(pk=data['franja_inicio_id'])
            franja_fin = FranjaHoraria.objects.get(pk=data['franja_fin_id'])
        except FranjaHoraria.DoesNotExist:
            raise serializers.ValidationError("Una de las franjas horarias no existe.")

        if franja_inicio.hora_inicio >= franja_fin.hora_inicio:
            raise serializers.ValidationError("La hora de fin debe ser posterior a la hora de inicio.")

        return data
