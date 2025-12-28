import base64
from datetime import timedelta
from django.core.files.base import ContentFile
from django.utils import timezone
from core.models import Asistencia, AsistenciaDiaria, BloqueHorario, Curso, Docente

def process_attendance_action(docente, action_type, photo_file, course_id=None):
    """
    Procesa una acción de asistencia (entrada/salida general o por curso).

    Args:
        docente (Docente): El objeto docente.
        action_type (str): Tipo de acción ('general_entry', 'general_exit', 'course_entry', 'course_exit').
        photo_file (File): El archivo de foto ya decodificado/cargado.
        course_id (int, optional): ID del curso para acciones de curso.

    Returns:
        dict: Resultado de la operación con claves 'status', 'message', y opcionalmente 'data' o 'warning'.

    Raises:
        ValueError: Si hay errores de validación de negocio.
    """
    today = timezone.localtime(timezone.now()).date()
    now = timezone.now()

    if action_type == "general_entry":
        _, created = AsistenciaDiaria.objects.get_or_create(
            docente=docente, fecha=today, defaults={"foto_verificacion": photo_file}
        )
        if created:
            return {
                "status": "success",
                "message": "Entrada general registrada correctamente.",
            }
        else:
            return {
                "status": "success",
                "message": "La entrada general ya ha sido marcada hoy.",
                "data": {"already_marked": True},
            }

    elif action_type == "general_exit":
        asistencia_diaria = AsistenciaDiaria.objects.filter(
            docente=docente, fecha=today
        ).first()

        if not asistencia_diaria:
            raise ValueError("Debe marcar la entrada general antes de marcar la salida.")

        if asistencia_diaria.hora_salida:
            return {
                "status": "warning",
                "message": "La salida general ya ha sido marcada hoy.",
            }

        asistencia_diaria.hora_salida = now
        asistencia_diaria.foto_salida = photo_file
        asistencia_diaria.save()

        return {
            "status": "success",
            "message": "Salida general registrada correctamente.",
        }

    elif action_type in ["course_entry", "course_exit"]:
        if not course_id:
            raise ValueError("courseId es requerido para esta acción.")

        try:
            curso = Curso.objects.get(id=course_id)
        except Curso.DoesNotExist:
            raise ValueError("Curso no encontrado.")

        asistencia, _ = Asistencia.objects.get_or_create(
            docente=docente, curso=curso, fecha=today
        )
        response_data = {}

        if action_type == "course_entry":
            if asistencia.hora_entrada:
                return {
                    "status": "warning",
                    "message": "La entrada para este curso ya fue marcada.",
                }

            asistencia.hora_entrada = now
            asistencia.foto_entrada = photo_file
            response_data["es_tardanza"] = asistencia.es_tardanza()

            # --- MEJORA: Cálculo Dinámico de Duración ---
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
            # -------------------------------------------------------------

        elif action_type == "course_exit":
            if not asistencia.hora_entrada:
                raise ValueError("Debe marcar la entrada antes de poder marcar la salida.")

            if asistencia.hora_salida:
                 return {
                    "status": "warning",
                    "message": "La salida para este curso ya fue marcada.",
                }

            if not asistencia.puede_marcar_salida:
                raise ValueError("Aún no puede marcar la salida. No se ha cumplido el tiempo mínimo.")

            asistencia.hora_salida = now
            asistencia.foto_salida = photo_file
            asistencia.save()

        return {
            "status": "success",
            "message": "Asistencia registrada correctamente.",
            "data": response_data,
        }

    else:
         raise ValueError("Tipo de acción no válida.")
