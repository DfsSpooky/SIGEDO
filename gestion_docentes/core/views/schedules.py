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
        "carreras": Carrera.objects.all().order_by("nombre"),
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


@staff_member_required
def ver_horario_docente_admin(request, docente_id):
    from ..models import Docente  # Import local to avoid circular deps if any

    docente = get_object_or_404(Docente, pk=docente_id)
    semestre_activo = Semestre.objects.filter(estado="ACTIVO").first()

    # Obtener Bloques (Clases)
    bloques_clase = BloqueHorario.objects.filter(
        curso__docente=docente,
        curso__semestre=semestre_activo
    ).select_related('curso', 'franja_inicio', 'aula')

    # Obtener Bloques No Lectivos
    bloques_no_lectivos = BloqueNoLectivo.objects.filter(
        docente=docente,
        # Filtro de semestre opcional si BloqueNoLectivo tuviera, por ahora filtramos por vigencia si aplica
        # Ojo: BloqueNoLectivo se define por día de semana génerico, así que asumimos vigencia actual
    ).select_related('franja_inicio')

    # Construir Grid
    # Estructura: grid[franja_id][dia] = {'tipo': 'CLASE'|'NO_LECTIVO', 'titulo': ..., 'duracion': ...}
    
    franjas = list(FranjaHoraria.objects.order_by("hora_inicio"))
    dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
    
    grid = {f.id: {d: None for d in dias_semana} for f in franjas}

    # Helper para asignar al grid
    def asignar_al_grid(bloque, tipo):
        try:
            franja_id = bloque.franja_inicio.id
            dia = bloque.dia
            duracion = bloque.duracion_bloques
            
            # Base data
            data = {
                'tipo': tipo,
                'duracion': duracion,
                'obj': bloque
            }
            
            if tipo == 'CLASE':
                data['titulo'] = bloque.curso.nombre
                data['aula'] = bloque.aula.nombre if bloque.aula else "Sin Aula"
            elif tipo == 'NO_LECTIVO':
                data['titulo'] = bloque.motivo
                data['aula'] = "-"

            # Asignar a celda inicio
            grid[franja_id][dia] = data
            
            # Marcar celdas ocupadas por duración > 1
            if duracion > 1:
                start_index = franjas.index(bloque.franja_inicio)
                for i in range(1, duracion):
                    if start_index + i < len(franjas):
                        f_ocupada = franjas[start_index + i]
                        # Marcar como ocupado por span (None o string especial, el template manejará el span)
                        # Pero para el template con rowspan, las celdas cubiertas NO deben renderizarse o estar vacías/ocultas.
                        # En CSS Grid con rowspan, simplemente no ponermos nada en las celdas cubiertas si el HTML estructura lo maneja,
                        # pero mi lógica de template itera celdas.
                        # Mi template propuesto dice: {% if bloque.duracion > 1 %} style="grid-row: span ..." {% endif %}
                        # Eso implica que el elemento DIV cubre el espacio.
                        # IMPORTANTE: Si usamos CSS Grid puro con celdas explicitas, necesitamos saltar las celdas cubiertas o ponerles "hidden".
                        # En el template propuesto user:
                        # {% with bloque=grid|get_item:franja.id|get_item:dia %} ...
                        # Si devuelve None se renderiza vacío.
                        # Si devuelve un objeto, se renderiza.
                        # Si es una celda cubierta por un rowspan anterior, grid[...] debería ser un marcador especial para NO renderizar nada?
                        # O mejor, si es cubierta, grid[...] = None?
                        # No, si es None, renderiza hueco vacío.
                        # Si es ocupada, necesitamos saberlo para NO pintar un hueco vacío si el span ya lo cubre visualmente?
                        # CSS Grid autoplacement es tricky.
                        # El template propuesto usa celdas explicitas en un grid de columnas predefinidas?
                        # <div class="grid grid-cols-[auto_repeat(5,1fr)] ...">
                        #    Header...
                        #    Iteración Franjas:
                        #       Iteración Días:
                        #           Cell ...
                        # Si una celda tiene rowspan 2, ocupará visualmente la siguiente fila.
                        # La siguiente fila, en esa columna, intentará poner otra celda. 
                        # Si ponemos un <div> ahí, Grid intentará ubicarlo en el siguiente hueco disponible? No necesariamente.
                        # Si usamos Grid Area o posicionamiento explicito sí.
                        # Pero con "grid-flow-row dense" o simple flow, poner un div extra empujará todo.
                        # SOLUCIÓN: Usar "display: contents" o simplemente NO renderizar el div si está cubierto.
                        # Pondremos un marcador 'SPAN_COVERED'
                        grid[f_ocupada.id][dia] = 'SPAN_COVERED'
                        
        except (ValueError, IndexError, AttributeError):
            pass

    for b in bloques_clase:
        asignar_al_grid(b, 'CLASE')
        
    for b in bloques_no_lectivos:
        asignar_al_grid(b, 'NO_LECTIVO')

    context = {
        'docente': docente,
        'franjas': franjas,
        'dias_semana': dias_semana,
        'grid': grid
    }
    return render(request, "admin/ver_horario_docente.html", context)
