from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models import BloqueHorario, DiaEspecial, Semestre


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def api_horario_docente(request):
    """
    API endpoint para devolver los eventos del horario de un docente para FullCalendar.
    """
    try:
        docente = request.user
        semestre_activo = Semestre.objects.filter(estado="ACTIVO").first()

        if not semestre_activo:
            return Response(
                {"status": "error", "message": "No hay un semestre académico activo."},
                status=status.HTTP_404_NOT_FOUND,
            )

        eventos = []

        # 1. Obtener los bloques de horario (clases recurrentes)
        bloques = BloqueHorario.objects.filter(
            curso__docente=docente, curso__semestre=semestre_activo
        ).select_related("curso", "franja_inicio")

        # Mapeo de dia_semana (Lunes=0) a FullCalendar (Domingo=0, Lunes=1)
        # Sumamos 1 a nuestro valor.
        dias_semana_map = {
            0: 1,  # Lunes
            1: 2,  # Martes
            2: 3,  # Miércoles
            3: 4,  # Jueves
            4: 5,  # Viernes
        }

        for bloque in bloques:
            if bloque.dia_semana in dias_semana_map:
                eventos.append(
                    {
                        "id": f"bloque_{bloque.id}",
                        "title": bloque.curso.nombre,
                        "daysOfWeek": [dias_semana_map[bloque.dia_semana]],
                        "startTime": bloque.horario_inicio.strftime("%H:%M:%S"),
                        "endTime": bloque.horario_fin.strftime("%H:%M:%S"),
                        "startRecur": semestre_activo.fecha_inicio.isoformat(),
                        "endRecur": semestre_activo.fecha_fin.isoformat(),
                        "display": "auto",
                        "color": "#367BFF",  # Un color base para las clases
                    }
                )

        # 2. Obtener los días especiales (feriados, eventos)
        dias_especiales = DiaEspecial.objects.filter(semestre=semestre_activo)

        for dia in dias_especiales:
            color = "#FF5733"  # Rojo para feriados/suspensiones
            rendering = "background"

            if dia.tipo == "EVENTO":
                color = "#FFC300"  # Amarillo para eventos

            eventos.append(
                {
                    "id": f"especial_{dia.id}",
                    "title": dia.motivo,
                    "start": dia.fecha.isoformat(),
                    "allDay": True,
                    "display": rendering,
                    "color": color,
                }
            )

        return Response(eventos)

    except Exception as e:
        import traceback

        traceback.print_exc()
        return Response(
            {"status": "error", "message": f"Ocurrió un error inesperado: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
