import base64
from datetime import timedelta

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.files.base import ContentFile
from django.utils import timezone
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from core.api.serializers import (
    CursoAsistenciaSerializer,
    DocenteInfoSerializer,
    MarkAttendanceSerializer,
    RegistrarAsistenciaRfidSerializer,
)
from core.models import (
    Asistencia,
    AsistenciaDiaria,
    BloqueHorario,
    Curso,
    Docente,
    Semestre,
)
from core.api.views.utils import get_kiosk_data_for_docente
from core.services.attendance import process_attendance_action


class TeacherInfoView(APIView):
    """
    API View para obtener la información de un docente y sus cursos del día.
    Reemplaza la función original get_teacher_info con una vista basada en clases de DRF.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        qr_id = request.data.get("qrId")
        if not qr_id:
            return Response(
                {"status": "error", "message": "qrId no proporcionado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            docente = Docente.objects.get(id_qr=qr_id)
        except Docente.DoesNotExist:
            return Response(
                {"status": "error", "message": "QR no válido o docente no encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Removed weekend check - Permitimos acceso siempre que haya horario programado

        response_data = get_kiosk_data_for_docente(docente, request)
        return Response(response_data)


class MarkAttendanceView(APIView):
    """
    API View para marcar la asistencia de un docente.
    Reemplaza la función mark_attendance_kiosk.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = MarkAttendanceSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "status": "error",
                    "message": "Datos inválidos.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        validated_data = serializer.validated_data
        qr_id = validated_data["qrId"]
        action_type = validated_data["actionType"]
        photo_base64 = validated_data["photoBase64"]
        course_id = validated_data.get("courseId")

        try:
            docente = Docente.objects.get(id_qr=qr_id)
        except Docente.DoesNotExist:
            return Response(
                {"status": "error", "message": "QR no válido o docente no encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Decodificar Base64 a ContentFile
        try:
            format, imgstr = photo_base64.split(";base64,")
            ext = format.split("/")[-1]
            now = timezone.now()
            photo_file = ContentFile(
                base64.b64decode(imgstr),
                name=f"{docente.username}_{now.timestamp()}.{ext}",
            )
        except Exception:
             return Response(
                {"status": "error", "message": "Formato de photoBase64 inválido."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Usar el servicio compartido
        try:
            result = process_attendance_action(
                docente=docente,
                action_type=action_type,
                photo_file=photo_file,
                course_id=course_id
            )
            return Response(result, status=status.HTTP_200_OK)

        except ValueError as e:
            return Response(
                {"status": "error", "message": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response(
                {"status": "error", "message": "Error interno del servidor."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class RegistrarAsistenciaRfidView(APIView):
    """
    API View para registrar la asistencia diaria de un docente mediante RFID.
    Reemplaza la función registrar_asistencia_rfid.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = RegistrarAsistenciaRfidSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "status": "error",
                    "message": "Datos inválidos.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        uid = serializer.validated_data["uid"]
        
        try:
            docente = Docente.objects.get(rfid_uid=uid)
        except Docente.DoesNotExist:
            return Response(
                {
                    "status": "error",
                    "message": "Tarjeta RFID no reconocida o no asignada.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # Updated to use shared logic - NO auto marking anymore, just data retrieval
        response_data = get_kiosk_data_for_docente(docente, request)

        # Enviar actualización a través de Channels
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "kiosk_group", {"type": "kiosk.update", "data": response_data}
        )

        return Response(response_data)