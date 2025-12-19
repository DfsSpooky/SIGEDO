from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from ..models import Asistencia, BloqueHorario, Semestre


@login_required
def registrar_asistencia(request):
    # Esta vista puede servir como un historial simple para el docente.
    docente = request.user
    now = timezone.now()
    semestre_activo = Semestre.objects.filter(
        estado="ACTIVO", fecha_inicio__lte=now.date(), fecha_fin__gte=now.date()
    ).first()

    bloque_actual = None
    if semestre_activo:
        dia_actual_str = now.strftime("%A").capitalize()
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

    asistencia_obj = None
    if bloque_actual:
        asistencia_obj = Asistencia.objects.filter(
            docente=docente, curso=bloque_actual.curso, fecha=now.date()
        ).first()

    return render(
        request,
        "asistencia.html",
        {
            "curso_actual": bloque_actual.curso if bloque_actual else None,
            "asistencia": asistencia_obj,
        },
    )
