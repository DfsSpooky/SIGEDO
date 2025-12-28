import base64
from datetime import timedelta

from django.core.files.base import ContentFile
from django.utils import timezone
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from core.api.serializers import MobileMarkAttendanceSerializer
from core.models import (
    Asistencia,
    AsistenciaDiaria,
    BloqueHorario,
    Curso,
)
from core.api.views.utils import get_kiosk_data_for_docente


class MobileStatusView(APIView):
    """
    API View para obtener la información del docente autenticado y sus cursos del día.
    Utilizada por la App Móvil.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        docente = request.user
        response_data = get_kiosk_data_for_docente(docente, request)
        return Response(response_data)


class MobileMarkAttendanceView(APIView):
    """
    API View para marcar asistencia desde la App Móvil.
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
        latitude = validated_data.get("latitude")
        longitude = validated_data.get("longitude")
        
        # --- VALIDACIÓN GEOLOCALIZACIÓN ---
        from django.conf import settings
        import math

        if latitude is not None and longitude is not None:
             # Coordenadas Campus
             campus_lat, campus_lng = settings.CAMPUS_LOCATION
             
             # Fórmula Haversine
             R = 6371000 # Radio Tierra en metros
             phi1 = math.radians(campus_lat)
             phi2 = math.radians(latitude)
             delta_phi = math.radians(latitude - campus_lat)
             delta_lambda = math.radians(longitude - campus_lng)

             a = math.sin(delta_phi / 2.0)**2 + \
                 math.cos(phi1) * math.cos(phi2) * \
                 math.sin(delta_lambda / 2.0)**2
             c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
             
             distance = R * c

             if distance > settings.ALLOWED_RADIUS_METERS:
                 return Response(
                     {
                         "status": "error",
                         "message": f"Fuera de rango. Distancia: {int(distance)}m (Máx: {settings.ALLOWED_RADIUS_METERS}m).",
                     },
                     status=status.HTTP_400_BAD_REQUEST,
                 )
        else:
             # Si es obligatorio, descomentar esto:
             # return Response({"status": "error", "message": "Ubicación requerida."}, status=400)
             pass 
        # ----------------------------------

        docente = request.user
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

                # --- Cálculo Dinámico de Duración (Igual que en Kiosk/Web) ---
                bloque_del_dia = BloqueHorario.objects.filter(
                    curso=curso, dia_semana=today.weekday()
                ).first()

                if bloque_del_dia:
                    duracion_real = bloque_del_dia.get_duracion_real_minutos()
                    duracion_minima_minutos = duracion_real - 15
                else:
                    duracion_minima_minutos = 75

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


class UpdateFCMTokenView(APIView):
    """
    API View para actualizar el token FCM del usuario.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        token = request.data.get('fcm_token')
        if not token:
            return Response({'error': 'Token is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        user = request.user
        user.fcm_token = token
        user.save()
        return Response({'status': 'Token updated'})
