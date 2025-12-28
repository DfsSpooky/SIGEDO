import base64
from django.core.files.base import ContentFile
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.api.serializers import MobileMarkAttendanceSerializer
from core.api.views.utils import get_kiosk_data_for_docente
from core.services.attendance import process_attendance_action


class MobileStatusView(APIView):
    """
    API View para que la App Móvil obtenga el estado actual del docente.
    Retorna la información del docente, estado de asistencia diaria y lista de cursos del día.
    Autenticación: Requiere token JWT (docente logueado).
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        # Reutilizamos la lógica del kiosco pero pasando el usuario autenticado
        response_data = get_kiosk_data_for_docente(request.user, request)
        return Response(response_data)


class MobileAttendanceView(APIView):
    """
    API View para marcar asistencia desde la App Móvil.
    Autenticación: Requiere token JWT.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = MobileMarkAttendanceSerializer(data=request.data)
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
        action_type = validated_data["actionType"]
        photo_base64 = validated_data["photoBase64"]
        course_id = validated_data.get("courseId")
        docente = request.user

        # Decodificar Base64 a ContentFile
        try:
            format, imgstr = photo_base64.split(";base64,")
            ext = format.split("/")[-1]
            now = timezone.now()
            photo_file = ContentFile(
                base64.b64decode(imgstr),
                name=f"{docente.username}_{now.timestamp()}.{ext}",
            )
        except Exception as e:
            return Response(
                {"status": "error", "message": "Error procesando la imagen."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Procesar la acción usando el servicio compartido
        try:
            result = process_attendance_action(
                docente=docente,
                action_type=action_type,
                photo_file=photo_file,
                course_id=course_id
            )

            # Mapeamos 'warning' a 200 OK pero con status warning en JSON (convención existente)
            return Response(result, status=status.HTTP_200_OK)

        except ValueError as e:
            return Response(
                {"status": "error", "message": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {"status": "error", "message": "Error interno del servidor."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
