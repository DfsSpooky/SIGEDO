from rest_framework import serializers
from ..models import Docente, Curso, Asistencia, ChatConversation, ChatMessage

class UserSerializer(serializers.ModelSerializer):
    """
    Serializer para la información básica del usuario a ser usada en otros serializers.
    """
    class Meta:
        model = Docente
        fields = ['id', 'username', 'first_name', 'last_name', 'foto']

class ChatMessageSerializer(serializers.ModelSerializer):
    """
    Serializer para los mensajes de chat.
    """
    sender = UserSerializer(read_only=True)
    class Meta:
        model = ChatMessage
        fields = ['id', 'conversation', 'sender', 'content', 'timestamp', 'read_by']
        read_only_fields = ['id', 'sender', 'timestamp', 'read_by']


class ChatConversationSerializer(serializers.ModelSerializer):
    """
    Serializer para las conversaciones de chat. Incluye el último mensaje.
    """
    participants = UserSerializer(many=True, read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = ChatConversation
        fields = ['id', 'participants', 'is_group_chat', 'name', 'created_at', 'last_message', 'unread_count']

    def get_last_message(self, obj):
        last_msg = obj.messages.order_by('-timestamp').first()
        if last_msg:
            return ChatMessageSerializer(last_msg).data
        return None

    def get_unread_count(self, obj):
        user = self.context.get('request').user
        if user and user.is_authenticated:
            # Contar mensajes en esta conversación que no han sido leídos por el usuario actual
            return obj.messages.exclude(read_by=user).count()
        return 0


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
