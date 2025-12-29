from datetime import timedelta
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib import messages

from ..models import Asistencia, BloqueHorario, Semestre


@login_required
def registrar_asistencia(request):
    docente = request.user
    now = timezone.localtime(timezone.now())  # Usamos hora local para evitar desfases
    error_message = None

    # 1. Obtener Semestre Activo
    semestre_activo = Semestre.objects.filter(
        estado="ACTIVO", 
        fecha_inicio__lte=now.date(), 
        fecha_fin__gte=now.date()
    ).first()

    bloque_actual = None
    if semestre_activo:
        # Mejora: Usamos weekday() (0=Lunes, 6=Domingo) para ser independientes del idioma del servidor
        dias_semana = [
            "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"
        ]
        dia_actual_str = dias_semana[now.weekday()]

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
            docente=docente, 
            curso=bloque_actual.curso, 
            fecha=now.date()
        ).first()

    # 3. MANEJAR EL POST
    if request.method == "POST":
        accion = request.POST.get("accion")  # 'entrada' o 'salida'

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
                    
                    # --- MEJORA: Cálculo dinámico de la duración ---
                    # Obtenemos la duración real basada en las franjas horarias
                    duracion_real_minutos = bloque_actual.get_duracion_real_minutos()
                    
                    # Definimos que se puede salir 15 minutos antes de que acabe la hora real
                    tiempo_minimo_clase = duracion_real_minutos - 15
                    
                    # Salvaguarda: Si la clase es muy corta (ej. < 30 min), forzamos al menos 15 min
                    if tiempo_minimo_clase < 15:
                        tiempo_minimo_clase = 15
                    
                    nueva_asistencia.hora_salida_permitida = now + timedelta(minutes=tiempo_minimo_clase)
                    # -----------------------------------------------

                    nueva_asistencia.full_clean()  # Valida reglas del modelo (ej. anti-passback)
                    nueva_asistencia.save()
                    
                    messages.success(request, f"Entrada marcada correctamente a las {now.strftime('%H:%M')}")
                    return redirect("asistencia")
                    
                except ValidationError as e:
                    # Extraemos el primer error disponible para mostrarlo limpio
                    error_message = e.message_dict.get('__all__', [str(e)])[0] if hasattr(e, 'message_dict') else str(e)

        elif accion == "salida":
            if not asistencia_obj:
                error_message = "No hay una entrada marcada para registrar salida."
            elif asistencia_obj.hora_salida:
                error_message = "La salida ya fue marcada anteriormente."
            else:
                # Validar si puede marcar salida usando la propiedad del modelo
                if not asistencia_obj.puede_marcar_salida and asistencia_obj.hora_salida_permitida:
                    restante = asistencia_obj.hora_salida_permitida - now
                    # Evitamos mostrar números negativos si acaba de pasar el tiempo
                    minutos = max(1, int(restante.total_seconds() / 60))
                    error_message = f"Aún no puede marcar salida. Espere {minutos} minutos más para completar el tiempo mínimo."
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
            "bloque_actual": bloque_actual,  # Necesario para mostrar info en el template
            "asistencia": asistencia_obj,
            "error": error_message,
        },
    )