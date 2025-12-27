from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib import messages

from ..models import Asistencia, BloqueHorario, Semestre

@login_required
def registrar_asistencia(request):
    docente = request.user
    now = timezone.now()
    error_message = None

    # 1. Obtener Semestre y Bloque Actual (Lógica existente)
    semestre_activo = Semestre.objects.filter(
        estado="ACTIVO", fecha_inicio__lte=now.date(), fecha_fin__gte=now.date()
    ).first()

    bloque_actual = None
    if semestre_activo:
        # Nota: Asegúrate que tus días en BD estén capitalizados ("Lunes", "Martes")
        # .strftime("%A") devuelve en inglés ("Monday"). Django suele manejarlo, 
        # pero si tus datos están en español, podrías necesitar un mapeo.
        # Asumiremos que tu populate crea los días en inglés o tienes un sistema bilingüe.
        # Si falla, revisa que 'dia_actual_str' coincida con lo que hay en BloqueHorario.
        dia_nombre = now.strftime("%A") 
        dias_traduccion = {
            "Monday": "Lunes", "Tuesday": "Martes", "Wednesday": "Miércoles",
            "Thursday": "Jueves", "Friday": "Viernes", "Saturday": "Sábado", "Sunday": "Domingo"
        }
        dia_actual_str = dias_traduccion.get(dia_nombre, dia_nombre)

        bloque_actual = (
            BloqueHorario.objects.filter(
                curso__docente=docente,
                curso__semestre=semestre_activo,
                dia=dia_actual_str,
                horario_inicio__lte=now.time(),
                horario_fin__gte=now.time(),
            )
            .select_related("curso")
            .first()
        )

    # 2. Buscar asistencia existente para hoy y este curso
    asistencia_obj = None
    if bloque_actual:
        asistencia_obj = Asistencia.objects.filter(
            docente=docente, curso=bloque_actual.curso, fecha=now.date()
        ).first()

    # 3. MANEJAR EL POST (Esto es lo que faltaba)
    if request.method == "POST":
        accion = request.POST.get("accion") # 'entrada' o 'salida'

        if not bloque_actual:
             error_message = "No se encontró un bloque horario activo en este momento."
        
        elif accion == "entrada":
            if asistencia_obj:
                error_message = "Ya existe un registro de entrada para este curso hoy."
            else:
                try:
                    nueva_asistencia = Asistencia(
                        docente=docente,
                        curso=bloque_actual.curso,
                        fecha=now.date(),
                        hora_entrada=now
                    )
                    # Calcular hora de salida permitida (Lógica similar a la API)
                    duracion_minutos = (bloque_actual.duracion_bloques * 45) # Asumiendo 45min por hora académica
                    if duracion_minutos < 15: duracion_minutos = 15
                    
                    # Opcional: Si quieres ser estricto con la salida mínima
                    # nueva_asistencia.hora_salida_permitida = now + timezone.timedelta(minutes=duracion_minutos)
                    
                    nueva_asistencia.full_clean() # Valida el Anti-Passback del modelo
                    nueva_asistencia.save()
                    messages.success(request, f"Entrada marcada correctamente a las {now.strftime('%H:%M')}")
                    return redirect("asistencia")
                    
                except ValidationError as e:
                    error_message = e.message_dict.get('__all__', [str(e)])[0]

        elif accion == "salida":
            if not asistencia_obj:
                error_message = "No hay una entrada marcada para registrar salida."
            elif asistencia_obj.hora_salida:
                 error_message = "La salida ya fue marcada anteriormente."
            else:
                # Validar si puede marcar salida (usando tu propiedad del modelo)
                # Si quieres saltarte esta validación para pruebas manuales, comenta el if.
                if not asistencia_obj.puede_marcar_salida and asistencia_obj.hora_salida_permitida:
                     restante = asistencia_obj.hora_salida_permitida - now
                     minutos = int(restante.total_seconds() / 60)
                     error_message = f"Aún no puede marcar salida. Espere {minutos} minutos."
                else:
                    asistencia_obj.hora_salida = now
                    asistencia_obj.save()
                    messages.success(request, f"Salida marcada correctamente a las {now.strftime('%H:%M')}")
                    return redirect("asistencia")

    # 4. Renderizar
    return render(
        request,
        "asistencia.html",
        {
            "curso_actual": bloque_actual.curso if bloque_actual else None,
            "bloque_actual": bloque_actual, # Necesario para el template
            "asistencia": asistencia_obj,
            "error": error_message,
        },
    )