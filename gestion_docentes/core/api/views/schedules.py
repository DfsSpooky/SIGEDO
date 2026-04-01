from datetime import datetime, timedelta

import pytz
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from icalendar import Calendar, Event, vRecur

from core.models import BloqueHorario, Docente, Semestre
from core.utils.responses import error_response


@login_required
def export_schedule_ics(request, docente_id=None):
    """
    Exporta el horario de clases de un docente en formato .ics
    """
    # Si no se especifica docente_id, usar el del usuario actual si es docente
    if docente_id:
        if not request.user.is_staff:
            return error_response("No tiene permisos para ver este horario.", status_code=403)
        docente = get_object_or_404(Docente, pk=docente_id)
    else:
        # Asumiendo que el usuario logueado es el docente
        try:
            # Assuming Docente extends AbstractUser or has a OneToOne to User.
            # If Docente IS the user model (AUTH_USER_MODEL='core.Docente'), then request.user IS the instance.
            # Checking settings.AUTH_USER_MODEL... it is 'core.Docente'.
            # So request.user IS already a Docente instance.
            if not isinstance(request.user, Docente):
                 # Fallback if request.user is somehow not the right model (e.g. admin superuser distinct from docente)
                 return error_response("Usuario no es un docente válido.", status_code=400)
            docente = request.user
        except Exception:
             return error_response("Error al identificar al docente.", status_code=400)

    semestre_activo = Semestre.objects.filter(estado="ACTIVO").first()
    if not semestre_activo:
        return error_response("No hay un semestre activo.")

    if not semestre_activo.fecha_inicio or not semestre_activo.fecha_fin:
         return error_response("El semestre activo no tiene fechas de inicio/fin configuradas.")

    bloques = BloqueHorario.objects.filter(
        curso__docente=docente, curso__semestre=semestre_activo
    ).select_related("curso", "franja_inicio")

    cal = Calendar()
    cal.add("prodid", "-//Gestion Docentes//mxm.dk//")
    cal.add("version", "2.0")
    cal.add('x-wr-calname', f'Horario {docente.first_name} {docente.last_name}')

    dias_map = {
        "Lunes": 0, "Martes": 1, "Miércoles": 2, "Jueves": 3, "Viernes": 4, "Sábado": 5, "Domingo": 6
    }
    ical_days = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]

    tz = pytz.timezone("America/Lima")

    for bloque in bloques:
        dia_idx = dias_map.get(bloque.dia)
        if dia_idx is None:
            continue

        # Calcular la fecha de la primera ocurrencia del bloque en el semestre
        # Start date of semester
        start_date = semestre_activo.fecha_inicio
        days_ahead = dia_idx - start_date.weekday()
        if days_ahead < 0:
            days_ahead += 7
        first_occurrence_date = start_date + timedelta(days=days_ahead)

        # Combinar fecha y hora
        dt_start = datetime.combine(first_occurrence_date, bloque.franja_inicio.hora_inicio)

        # Calcular hora fin basándonos en duración (asumiendo 45min por bloque, o calcular vs franja siguiente)
        # Por simplicidad, asumiremos que cada bloque dura 45 min * duracion_bloques
        # Idealmente deberíamos buscar la franja final.
        duration_minutes = 45 * bloque.duracion_bloques
        dt_end = dt_start + timedelta(minutes=duration_minutes)

        event = Event()
        event.add("summary", f"{bloque.curso.nombre} ({bloque.curso.codigo})")
        event.add("dtstart", dt_start)
        event.add("dtend", dt_end)
        event.add("dtstamp", datetime.now())

        # Recurrencia semanal hasta el fin del semestre
        event.add("rrule", {"freq": "weekly", "until": semestre_activo.fecha_fin, "byday": ical_days[dia_idx]})

        cal.add_component(event)

    response = HttpResponse(cal.to_ical(), content_type="text/calendar")
    response["Content-Disposition"] = f'attachment; filename="horario_{docente.dni}.ics"'
    return response
