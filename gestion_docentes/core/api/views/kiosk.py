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
    AdelantoClase,
)
from core.api.views.utils import get_kiosk_data_for_docente


class TeacherInfoView(APIView):
    """
    API View para obtener la información de un docente y sus cursos del día.
    Reemplaza la función original get_teacher_info con una vista basada en clases de DRF.
    """
    permission_classes = [permissions.AllowAny]
    throttle_scope = "kiosk_lookup"

    def post(self, request, *args, **kwargs):
        qr_id = request.data.get("qrId")
        if not qr_id:
            return Response(
                {"status": "error", "message": "qrId no proporcionado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Validar que sea un formato UUID válido antes de consultar
            import uuid
            try:
                uuid.UUID(str(qr_id))
            except (ValueError, TypeError):
                 return Response(
                    {"status": "error", "message": "Formato de código QR inválido. Por favor, use su carnet actualizado."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            docente = Docente.objects.get(id_qr=qr_id)
        except Docente.DoesNotExist:
            return Response(
                {"status": "error", "message": "Código QR no reconocido. Verifique su carnet digital."},
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
    throttle_scope = "kiosk_attendance"

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
            # Validar formato UUID
            import uuid
            try:
                uuid.UUID(str(qr_id))
            except:
                 return Response(
                    {"status": "error", "message": "Identificador de seguridad inválido."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
                
            docente = Docente.objects.get(id_qr=qr_id)
        except Docente.DoesNotExist:
            return Response(
                {"status": "error", "message": "Docente no identificado correctamente."},
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
            # --- Validar Horario Configurado (Igual que Mobile) ---
            from core.models.settings import ConfiguracionInstitucion
            config = ConfiguracionInstitucion.load()
            
            local_time = timezone.localtime(now).time()
            if config.hora_inicio_asistencia_general and local_time < config.hora_inicio_asistencia_general:
                return Response(
                    {"status": "error", "message": f"El registro de entrada inicia a las {config.hora_inicio_asistencia_general.strftime('%H:%M')}."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if config.hora_fin_asistencia_general and local_time > config.hora_fin_asistencia_general:
                 return Response(
                    {"status": "error", "message": f"El registro de entrada finalizó a las {config.hora_fin_asistencia_general.strftime('%H:%M')}."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            # ------------------------------------------------------

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

                # --- VALIDACIÓN 10 MINUTOS ANTES ---
                bloque_del_dia = BloqueHorario.objects.filter(
                    curso=curso, dia_semana=today.weekday()
                ).first()

                if bloque_del_dia and bloque_del_dia.horario_inicio:
                    # Crear datetime aware para la hora de inicio de hoy
                    inicio_clase_dt = timezone.make_aware(
                        timezone.datetime.combine(today, bloque_del_dia.horario_inicio)
                    )
                    
                    # Calcular diferencia
                    diff = inicio_clase_dt - now
                    # Si faltan más de 10 minutos (diff > 10 min)
                    if diff.total_seconds() > 600: 
                        # Verificar si existe AdelantoClase
                        has_adelanto = AdelantoClase.objects.filter(
                            docente=docente, curso=curso, fecha=today
                        ).exists()

                        if not has_adelanto:
                             return Response(
                                {
                                    "status": "error",
                                    "message": "Falta mucho para el inicio de clase (Mínimo 10 min antes). Use la opción 'Adelantar Clase' si es necesario.",
                                },
                                status=status.HTTP_400_BAD_REQUEST,
                            )

                # --- MEJORA: Cálculo Dinámico de Duración (Igual que en Web) ---
                if bloque_del_dia:
                    # Usamos el método del modelo para obtener minutos reales
                    duracion_real = bloque_del_dia.get_duracion_real_minutos()
                    # Salida permitida 15 min antes del fin real
                    duracion_minima_minutos = duracion_real - 15
                else:
                    # Fallback por seguridad (ej. clase extra no programada)
                    # Asumimos 90 min (2 bloques de 45) - 15 = 75 min
                    duracion_minima_minutos = 75

                # Salvaguarda de tiempo mínimo absoluto
                if duracion_minima_minutos < 15:
                    duracion_minima_minutos = 15

                asistencia.hora_salida_permitida = now + timedelta(
                    minutes=duracion_minima_minutos
                )
                asistencia.save()
                # -------------------------------------------------------------

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
                
                # Verificamos si ya cumplió el tiempo mínimo
                if not asistencia.puede_marcar_salida:
                    return Response(
                        {
                            "status": "error",
                            "message": "Aún no puede marcar la salida. No se ha cumplido el tiempo mínimo.",
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
    throttle_scope = "kiosk_attendance"

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
