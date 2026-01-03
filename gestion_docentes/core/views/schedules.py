import json
import random
from datetime import time, timedelta

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required, permission_required
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from ..models import (
    BloqueHorario,
    Carrera,
    Curso,
    Especialidad,
    FranjaHoraria,
    Semestre,
)


@login_required
def ver_horarios(request, carrera_id):
    semestre_activo = Semestre.objects.filter(estado="ACTIVO").first()
    carrera = get_object_or_404(Carrera, id=carrera_id)

    # Obtenemos los bloques de horario para la carrera y semestre seleccionados
    bloques_asignados = (
        BloqueHorario.objects.filter(
            curso__carrera=carrera, curso__semestre=semestre_activo
        )
        .select_related("curso", "curso__docente", "franja_inicio")
        .order_by("dia_semana", "horario_inicio")
    )

    # Preparamos los elementos necesarios para construir la parrilla del horario
    franjas_horarias = list(FranjaHoraria.objects.all().order_by("hora_inicio"))
    dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]

    horario_grid = {
        franja.id: {dia: None for dia in dias_semana} for franja in franjas_horarias
    }

    for bloque in bloques_asignados:
        # Colocamos el objeto 'bloque' en la celda correcta de la parrilla
        horario_grid[bloque.franja_inicio.id][bloque.dia] = bloque

        # Si el bloque dura más de una unidad, marcamos las celdas siguientes como 'OCUPADO'
        if bloque.duracion_bloques > 1:
            try:
                start_index = franjas_horarias.index(bloque.franja_inicio)
                for i in range(1, bloque.duracion_bloques):
                    if (start_index + i) < len(franjas_horarias):
                        franja_ocupada = franjas_horarias[start_index + i]
                        horario_grid[franja_ocupada.id][bloque.dia] = "OCUPADO"
            except (ValueError, IndexError):
                continue

    context = {
        "carrera": carrera,
        "semestre_activo": semestre_activo,
        "horario_grid": horario_grid,
        "franjas_horarias": franjas_horarias,
        "dias_semana": dias_semana,
    }

    return render(request, "ver_horarios.html", context)


@staff_member_required
def generar_horarios(request, carrera_id):
    semestre_activo = Semestre.objects.filter(estado="ACTIVO").first()
    if not semestre_activo:
        messages.error(request, "No hay un semestre activo para generar horarios.")
        return redirect("ver_horarios", carrera_id=carrera_id)

    carrera = Carrera.objects.get(id=carrera_id)
    cursos = Curso.objects.filter(
        carrera=carrera, semestre=semestre_activo, horario_inicio__isnull=True
    )
    dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
    horas_inicio = [time(hour=h) for h in range(8, 19, 2)]

    for curso in cursos:
        asignado = False
        random.shuffle(dias)
        for dia in dias:
            random.shuffle(horas_inicio)
            for hora in horas_inicio:
                hora_fin = (
                    timezone.datetime.combine(timezone.now(), hora)
                    + timedelta(hours=curso.duracion_horas)
                ).time()
                conflicto_docente = Curso.objects.filter(
                    docente=curso.docente,
                    dia=dia,
                    semestre=semestre_activo,
                    horario_inicio__lt=hora_fin,
                    horario_fin__gt=hora,
                ).exists()
                if not conflicto_docente:
                    curso.dia = dia
                    curso.horario_inicio = hora
                    curso.horario_fin = hora_fin
                    curso.aula = "Por asignar"
                    curso.save()
                    asignado = True
                    break
            if asignado:
                break
        if not asignado:
            curso.aula = "No asignado"
            curso.save()

    messages.success(
        request,
        f"Se han intentado generar los horarios para el semestre {semestre_activo.nombre}.",
    )
    return redirect("ver_horarios", carrera_id=carrera_id)


@staff_member_required
@permission_required("core.view_planificador", raise_exception=True)
def planificador_horarios(request):
    semestre_activo = Semestre.objects.filter(estado="ACTIVO").first()
    if not semestre_activo:
        messages.error(
            request,
            "No hay un semestre activo. Por favor, active un semestre en el panel de administración.",
        )
        return render(request, "planificador_vacio.html")

    # Determinar los semestres cursados válidos para el semestre activo
    semestres_validos = []
    if semestre_activo.tipo == "IMPAR":
        semestres_validos = [1, 3, 5, 7, 9]
    elif semestre_activo.tipo == "PAR":
        semestres_validos = [2, 4, 6, 8, 10]

    # Pre-serializar datos para JavaScript de forma segura
    franjas = FranjaHoraria.objects.order_by("hora_inicio")
    franjas_manana_json = json.dumps(
        list(franjas.filter(turno="MANANA").values("id", "hora_inicio", "hora_fin")),
        cls=DjangoJSONEncoder,
    )
    franjas_tarde_json = json.dumps(
        list(franjas.filter(turno="TARDE").values("id", "hora_inicio", "hora_fin")),
        cls=DjangoJSONEncoder,
    )

    dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
    dias_semana_json = json.dumps(dias_semana)

    context = {
        "semestre_activo": semestre_activo,
        "especialidades": Especialidad.objects.all(),
        "franjas_manana_json": franjas_manana_json,
        "franjas_tarde_json": franjas_tarde_json,
        "dias_semana_json": dias_semana_json,
        "dias_semana": dias_semana,  # <-- Añadido para el template
        "semestres_validos": semestres_validos,
        # Pasamos los filtros seleccionados para que la plantilla los recuerde
        "especialidad_seleccionada_id": request.GET.get("especialidad"),
        "semestre_seleccionado": request.GET.get("semestre_cursado"),
    }
    return render(request, "planificador_horarios.html", context)


@login_required
def vista_publica_horarios(request):
    semestre_activo = Semestre.objects.filter(estado="ACTIVO").first()
    especialidades = Especialidad.objects.all()

    especialidad_seleccionada_id = request.GET.get("especialidad")
    especialidad_seleccionada = None

    horarios_por_semestre_cursado = {}

    if especialidad_seleccionada_id:
        try:
            especialidad_seleccionada = Especialidad.objects.get(
                id=especialidad_seleccionada_id
            )
            grupo_seleccionado = especialidad_seleccionada.grupo

            query_cursos_propios = Q(curso__especialidad=especialidad_seleccionada)
            query_cursos_generales_del_grupo = Q(
                curso__tipo_curso="GENERAL",
                curso__especialidad__grupo=grupo_seleccionado,
            )

            bloques_asignados = (
                BloqueHorario.objects.filter(
                    query_cursos_propios | query_cursos_generales_del_grupo,
                    curso__semestre=semestre_activo,
                )
                .distinct()
                .select_related("curso", "curso__docente", "franja_inicio")
                .order_by("curso__semestre_cursado")
            )

            semestres_cursados = sorted(
                list(
                    bloques_asignados.values_list(
                        "curso__semestre_cursado", flat=True
                    ).distinct()
                )
            )
            franjas_horarias = list(FranjaHoraria.objects.order_by("hora_inicio"))
            dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]

            for semestre_num in semestres_cursados:
                grid = {
                    franja.id: {dia: None for dia in dias_semana}
                    for franja in franjas_horarias
                }

                bloques_del_semestre = bloques_asignados.filter(
                    curso__semestre_cursado=semestre_num
                )
                for bloque in bloques_del_semestre:
                    try:
                        grid[bloque.franja_inicio.id][bloque.dia] = bloque
                        if bloque.duracion_bloques > 1:
                            start_index = franjas_horarias.index(bloque.franja_inicio)
                            for i in range(1, bloque.duracion_bloques):
                                if (start_index + i) < len(franjas_horarias):
                                    franja_ocupada = franjas_horarias[start_index + i]
                                    grid[franja_ocupada.id][bloque.dia] = "OCUPADO"
                    except (ValueError, IndexError):
                        continue
                horarios_por_semestre_cursado[semestre_num] = grid

        except Especialidad.DoesNotExist:
            especialidad_seleccionada = None

    context = {
        "semestre_activo": semestre_activo,
        "especialidades": especialidades,
        "especialidad_seleccionada": especialidad_seleccionada,
        "horarios_por_semestre_cursado": horarios_por_semestre_cursado,
        "franjas_horarias": FranjaHoraria.objects.all().order_by("hora_inicio"),
        "dias_semana": ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"],
    }
    return render(request, "vista_publica_horarios.html", context)


@login_required
def calendario_view(request):
    """
    Muestra la página del calendario de horarios del docente.
    """
    semestre_activo = Semestre.objects.filter(estado="ACTIVO").first()
    context = {
        "semestre_activo": semestre_activo,
    }
    return render(request, "calendario.html", context)
