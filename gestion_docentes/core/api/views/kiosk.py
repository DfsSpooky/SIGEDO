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

        # Removed weekend check

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

        try:
            docente = Docente.objects.get(id_qr=qr_id)
        except Docente.DoesNotExist:
            return Response(
                {"status": "error", "message": "QR no válido o docente no encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        today = timezone.localtime(timezone.now()).date()
        now = timezone.now()

        try:
            format, imgstr = photo_base64.split(";base64,")
            ext = format.split("/")[-1]
            photo_file = ContentFile(
                base64.b64decode(imgstr),
                name=f"{docente.username}_{now.timestamp()}.{ext}",
            )
        except:
            return Response(
                {"status": "error", "message": "Formato de photoBase64 inválido."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if action_type == "general_entry":
            _, created = AsistenciaDiaria.objects.get_or_create(
                docente=docente, fecha=today, defaults={"foto_verificacion": photo_file}
            )
            if created:
                return Response(
                    {
                        "status": "success",
                        "message": "Entrada general registrada correctamente.",
                    }
                )
            else:
                return Response(
                    {
                        "status": "success",
                        "message": "La entrada general ya ha sido marcada hoy.",
                        "data": {"already_marked": True},
                    }
                )

        elif action_type == "general_exit":
            asistencia_diaria = AsistenciaDiaria.objects.filter(
                docente=docente, fecha=today
            ).first()

            if not asistencia_diaria:
                return Response(
                    {
                        "status": "error",
                        "message": "Debe marcar la entrada general antes de marcar la salida.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if asistencia_diaria.hora_salida:
                return Response(
                    {
                        "status": "warning",
                        "message": "La salida general ya ha sido marcada hoy.",
                    }
                )

            asistencia_diaria.hora_salida = now
            asistencia_diaria.foto_salida = photo_file
            asistencia_diaria.save()

            return Response(
                {
                    "status": "success",
                    "message": "Salida general registrada correctamente.",
                }
            )

        elif action_type in ["course_entry", "course_exit"]:
            curso_id = validated_data.get("courseId")
            if not curso_id:
                return Response(
                    {
                        "status": "error",
                        "message": "courseId es requerido para esta acción.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                curso = Curso.objects.get(id=curso_id)
            except Curso.DoesNotExist:
                return Response(
                    {"status": "error", "message": "Curso no encontrado."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            asistencia, _ = Asistencia.objects.get_or_create(
                docente=docente, curso=curso, fecha=today
            )
            response_data = {}

            if action_type == "course_entry":
                if asistencia.hora_entrada:
                    return Response(
                        {
                            "status": "warning",
                            "message": "La entrada para este curso ya fue marcada.",
                        }
                    )

                asistencia.hora_entrada = now
                asistencia.foto_entrada = photo_file
                response_data["es_tardanza"] = asistencia.es_tardanza()

                # Lógica corregida para usar la duración del bloque específico de ese día
                bloque_del_dia = BloqueHorario.objects.filter(
                    curso=curso, dia_semana=today.weekday()
                ).first()
                duracion_bloques_hoy = (
                    bloque_del_dia.duracion_bloques if bloque_del_dia else 2
                )  # Default a 2 si no se encuentra

                duracion_minima_minutos = (duracion_bloques_hoy * 50) - 15
                if duracion_minima_minutos < 15:
                    duracion_minima_minutos = 15
                asistencia.hora_salida_permitida = now + timedelta(
                    minutes=duracion_minima_minutos
                )
                asistencia.save()

            elif action_type == "course_exit":
                if not asistencia.hora_entrada:
                    return Response(
                        {
                            "status": "error",
                            "message": "Debe marcar la entrada antes de poder marcar la salida.",
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if asistencia.hora_salida:
                    return Response(
                        {
                            "status": "warning",
                            "message": "La salida para este curso ya fue marcada.",
                        }
                    )
                if not asistencia.puede_marcar_salida:
                    return Response(
                        {
                            "status": "error",
                            "message": "Aún no puede marcar la salida.",
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                asistencia.hora_salida = now
                asistencia.foto_salida = photo_file
                asistencia.save()

            return Response(
                {
                    "status": "success",
                    "message": "Asistencia registrada correctamente.",
                    "data": response_data,
                }
            )

        return Response(
            {"status": "error", "message": "Tipo de acción no válida."},
            status=status.HTTP_400_BAD_REQUEST,
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
        # Removed weekend check

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
