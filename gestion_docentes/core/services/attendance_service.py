from datetime import timedelta
from django.utils import timezone
from django.core.exceptions import ValidationError
from core.models import Asistencia, AdelantoClase, BloqueHorario, Semestre

def can_mark_entry(docente, course, now=None):
    """
    Validates if a teacher can mark entry for a course at the given time.
    Returns (can_mark, error_message, bloque)
    """
    if now is None:
        now = timezone.localtime(timezone.now())
    
    # 1. Get Active Semester
    semestre_activo = Semestre.objects.filter(
        estado="ACTIVO", 
        fecha_inicio__lte=now.date(), 
        fecha_fin__gte=now.date()
    ).first()

    if not semestre_activo:
        return False, "No hay un semestre activo configurado.", None

    # 2. Get current block
    dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    dia_actual_str = dias_semana[now.weekday()]

    bloque = BloqueHorario.objects.filter(
        curso=course,
        dia=dia_actual_str,
        horario_fin__gte=now.time(),
    ).order_by("horario_inicio").first()

    if not bloque:
        return False, "No se encontró un bloque horario activo para este curso ahora.", None

    # 3. Check for existing attendance
    if Asistencia.objects.filter(docente=docente, curso=course, fecha=now.date()).exists():
        return False, "Ya existe un registro de asistencia para este curso hoy.", bloque

    # 4. Check early arrival (10 min tolerance)
    inicio_clase_dt = timezone.make_aware(
        timezone.datetime.combine(now.date(), bloque.horario_inicio)
    )
    diff = inicio_clase_dt - now
    
    if diff.total_seconds() > 600: # More than 10 mins early
        has_adelanto = AdelantoClase.objects.filter(
            docente=docente, 
            curso=course, 
            fecha=now.date()
        ).exists()
        
        if not has_adelanto:
            minutos_restantes = int(diff.total_seconds() / 60)
            return False, f"Falta mucho para el inicio ({minutos_restantes} min). Use 'Adelantar Clase' si es necesario.", bloque

    return True, None, bloque

def calculate_allowed_exit_time(bloque, entry_time):
    """
    Calculates the time after which a teacher can mark exit.
    """
    today = entry_time.date()
    # Logic from mobile.py: Fin Programada - 15 mins
    if bloque.horario_fin:
        fin_clase_dt = timezone.make_aware(
            timezone.datetime.combine(today, bloque.horario_fin)
        )
        return fin_clase_dt - timedelta(minutes=15)
    
    # Fallback from mobile.py: entry + 75 mins
    return entry_time + timedelta(minutes=75)
