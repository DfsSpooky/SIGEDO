import json
import random
from collections import defaultdict

from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Count, Q
from django.views.decorators.csrf import csrf_exempt

from core.models import (
    Aula,
    BloqueHorario,
    BloqueNoLectivo,
    Curso,
    Especialidad,
    FranjaHoraria,
    Semestre,
)
from core.utils.responses import (
    error_response,
    not_found_response,
    server_error_response,
    success_response,
)


@staff_member_required
@csrf_exempt
def api_asignar_horario(request):
    if request.method != "POST":
        return error_response("Método no permitido", status_code=405)

    try:
        data = json.loads(request.body)
        curso_id = data.get("curso_id")
        franja_id = data.get("franja_id")
        dia = data.get("dia")
        aula_id = data.get("aula_id")  # Optional

        # La duración del bloque ahora debe ser enviada desde el frontend.
        # Asumimos un valor por defecto si no se envía, para compatibilidad temporal.
        duracion = data.get("duracion", 2)

        curso = Curso.objects.get(pk=curso_id)
        franja_inicio = FranjaHoraria.objects.get(pk=franja_id)

        aula = None
        if aula_id:
            try:
                aula = Aula.objects.get(pk=aula_id)
            except Aula.DoesNotExist:
                return error_response(f"El aula con ID {aula_id} no existe.")

        # Validar que no se excedan las horas semanales del curso
        horas_asignadas = (
            curso.bloques_horario.aggregate(total=models.Sum("duracion_bloques"))[
                "total"
            ]
            or 0
        )
        if horas_asignadas + duracion > curso.horas_academicas_semanales:
            return error_response(
                f"No se puede asignar: excede las horas semanales del curso ({curso.horas_academicas_semanales})."
            )

        # Validación de conflictos usando el método clean() del modelo
        bloque = BloqueHorario(
            curso=curso, dia=dia, franja_inicio=franja_inicio, duracion_bloques=duracion, aula=aula
        )
        try:
            bloque.full_clean()
        except ValidationError as e:
            # Extraer el mensaje de error de la excepción
            error_message = next(iter(e.message_dict.values()))[0] if hasattr(e, 'message_dict') else str(e)
            return error_response(f"Conflicto de horario: {error_message}")

        bloque.save()
        return success_response(message="Bloque asignado con éxito.")

    except Curso.DoesNotExist:
        return not_found_response("Curso no encontrado.")
    except FranjaHoraria.DoesNotExist:
        return not_found_response("Franja horaria no encontrada.")
    except Exception as e:
        return server_error_response(f"Error inesperado: {e}")


@staff_member_required
@csrf_exempt
def api_desasignar_horario(request):
    if request.method != "POST":
        return error_response("Método no permitido", status_code=405)
    try:
        data = json.loads(request.body)
        bloque_id = data.get(
            "bloque_id"
        )  # El frontend ahora debe enviar el ID del bloque
        if not bloque_id:
            return error_response("Falta el ID del bloque de horario.")

        bloque = BloqueHorario.objects.get(pk=bloque_id)
        bloque.delete()
        return success_response(message="Bloque de horario eliminado.")
    except BloqueHorario.DoesNotExist:
        return not_found_response("El bloque de horario especificado no existe.")
    except Exception as e:
        return server_error_response(str(e))


@staff_member_required
@csrf_exempt
def api_mover_bloque(request):
    if request.method != "POST":
        return error_response("Método no permitido", status_code=405)

    try:
        data = json.loads(request.body)
        bloque_id = data.get("bloque_id")
        nuevo_dia = data.get("dia")
        nueva_franja_id = data.get("franja_id")

        bloque = BloqueHorario.objects.select_related(
            "curso__docente"
        ).prefetch_related("curso__especialidades__grupo").get(pk=bloque_id)
        nueva_franja_inicio = FranjaHoraria.objects.get(pk=nueva_franja_id)

        bloque.dia = nuevo_dia
        bloque.franja_inicio = nueva_franja_inicio

        try:
            bloque.full_clean()
        except ValidationError as e:
            error_message = next(iter(e.message_dict.values()))[0] if hasattr(e, 'message_dict') else str(e)
            return error_response(f"No se puede mover: {error_message}")

        bloque.save()

        return success_response(message="Bloque movido con éxito.")

    except BloqueHorario.DoesNotExist:
        return not_found_response("El bloque a mover no existe.")
    except FranjaHoraria.DoesNotExist:
        return not_found_response("La nueva franja horaria no existe.")
    except Exception as e:
        return server_error_response(f"Error inesperado: {e}")


@staff_member_required
@csrf_exempt
def api_ajustar_duracion(request):
    if request.method != "POST":
        return error_response("Método no permitido", status_code=405)

    try:
        data = json.loads(request.body)
        bloque_id = data.get("bloque_id")
        accion = data.get("accion")  # 'increase' or 'decrease'

        bloque = BloqueHorario.objects.select_related("curso").get(pk=bloque_id)

        nueva_duracion = bloque.duracion_bloques
        if accion == "increase":
            nueva_duracion += 1
        elif accion == "decrease":
            nueva_duracion -= 1
        else:
            return error_response("Acción no válida.", status_code=400)

        if nueva_duracion < 1:
            return error_response(
                "La duración no puede ser menor a 1 bloque.", status_code=400
            )

        # Validar que no se excedan las horas semanales del curso
        horas_asignadas = (
            bloque.curso.bloques_horario.exclude(pk=bloque_id).aggregate(
                total=models.Sum("duracion_bloques")
            )["total"]
            or 0
        )
        if horas_asignadas + nueva_duracion > bloque.curso.horas_academicas_semanales:
            return error_response(
                "La duración excede las horas semanales del curso.", status_code=400
            )

        bloque.duracion_bloques = nueva_duracion

        try:
            bloque.full_clean()
        except ValidationError as e:
            error_message = next(iter(e.message_dict.values()))[0] if hasattr(e, 'message_dict') else str(e)
            return error_response(f"No se puede ajustar duración: {error_message}")

        bloque.save()

        return success_response(message="Duración del bloque actualizada.")

    except BloqueHorario.DoesNotExist:
        return not_found_response("El bloque de horario no existe.")
    except Exception as e:
        return server_error_response(f"Error inesperado: {e}")


@staff_member_required
def api_get_teacher_conflicts(request):
    curso_id = request.GET.get("curso_id")
    if not curso_id:
        return error_response("Falta el ID del curso.")

    try:
        curso_a_asignar = Curso.objects.select_related(
            "docente"
        ).prefetch_related("especialidades__grupo").get(pk=curso_id)
        docente = curso_a_asignar.docente
        semestre = curso_a_asignar.semestre

        # Obtener todos los grupos asociados al curso
        grupos_del_curso = []
        for especialidad in curso_a_asignar.especialidades.all():
            if especialidad.grupo:
                grupos_del_curso.append(especialidad.grupo)

        semestre_cursado_a_asignar = curso_a_asignar.semestre_cursado

        # Usamos un diccionario para almacenar la razón del conflicto, evitando duplicados.
        conflictos = {}
        todas_las_franjas = list(FranjaHoraria.objects.order_by("hora_inicio"))
        mapa_franjas = {franja.id: franja for franja in todas_las_franjas}

        bloques_asignados = BloqueHorario.objects.filter(
            curso__semestre=semestre
        ).select_related(
            "curso__docente"
        ).prefetch_related("curso__especialidades__grupo")

        # 1. Conflictos del propio docente
        if docente:
            bloques_docente = bloques_asignados.filter(curso__docente=docente).exclude(
                curso=curso_a_asignar
            )
            for bloque in bloques_docente:
                franja_idx = todas_las_franjas.index(bloque.franja_inicio)
                for i in range(bloque.duracion_bloques):
                    franja_actual = todas_las_franjas[franja_idx + i]
                    key = (bloque.dia, franja_actual.id)
                    if key not in conflictos:
                        conflictos[key] = f"Docente Ocupado: {bloque.curso.nombre}"

        # 2. Conflictos de los grupos de estudiantes
        if grupos_del_curso and semestre_cursado_a_asignar:
            # Construir Q para cualquier curso que tenga ALGUNA de las mismas especialidades/grupos
            q_grupo = Q(
                curso__especialidades__grupo__in=grupos_del_curso,
                curso__semestre_cursado=semestre_cursado_a_asignar,
            )
            bloques_grupo = bloques_asignados.filter(q_grupo).exclude(
                curso=curso_a_asignar
            ).distinct() # Distinct porque M2M puede devolver duplicados

            for bloque in bloques_grupo:
                franja_idx = todas_las_franjas.index(bloque.franja_inicio)
                for i in range(bloque.duracion_bloques):
                    franja_actual = todas_las_franjas[franja_idx + i]
                    key = (bloque.dia, franja_actual.id)
                    if key not in conflictos:
                        conflictos[key] = f"Grupo Ocupado: {bloque.curso.nombre}"

        # 3. Conflictos de disponibilidad del docente
        if docente and docente.disponibilidad != "COMPLETO":
            turno_no_disponible = (
                "TARDE" if docente.disponibilidad == "MANANA" else "MANANA"
            )
            franjas_no_disponibles_ids = set(
                FranjaHoraria.objects.filter(turno=turno_no_disponible).values_list(
                    "id", flat=True
                )
            )
            if franjas_no_disponibles_ids:
                dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
                for dia in dias_semana:
                    for franja_id in franjas_no_disponibles_ids:
                        key = (dia, franja_id)
                        if key not in conflictos:
                            conflictos[key] = (
                                f"No disponible en turno de {turno_no_disponible.title()}"
                            )

        # Convertir el diccionario de conflictos al formato de lista esperado por el frontend
        response_data = [
            {"dia": k[0], "franja_id": k[1], "razon": v} for k, v in conflictos.items()
        ]

        return success_response(data={"conflicts": response_data})

    except Curso.DoesNotExist:
        return not_found_response("Curso no encontrado.")
    except Exception as e:
        return server_error_response(f"Error inesperado: {e}")


def _get_planner_data(especialidad_id, semestre_cursado):
    try:
        semestre_activo = Semestre.objects.get(estado="ACTIVO")
    except Semestre.DoesNotExist:
        raise ValueError("No hay un semestre activo configurado.")

    cursos_asignados_json = []
    cursos_pendientes_generales = []
    cursos_pendientes_especialidad = []

    if especialidad_id and semestre_cursado:
        especialidad_obj = Especialidad.objects.get(id=especialidad_id)
        grupo_obj = especialidad_obj.grupo

        q_cursos_del_plan = Q(
            semestre=semestre_activo, semestre_cursado=semestre_cursado
        ) & (
            Q(especialidades__id=especialidad_id)
            | Q(especialidades__grupo=grupo_obj, tipo_curso="GENERAL")
        )

        cursos_del_plan = (
            Curso.objects.filter(q_cursos_del_plan)
            .annotate(
                horas_asignadas=models.Sum(
                    "bloques_horario__duracion_bloques", default=0
                )
            )
            .select_related("docente")
            .prefetch_related("bloques_horario", "especialidades")
            .distinct()
        )

        for curso in cursos_del_plan:
            # Lógica para cursos pendientes
            if curso.horas_asignadas < curso.horas_academicas_semanales:
                curso_data = {
                    "id": curso.id,
                    "nombre": curso.nombre,
                    "docente_nombre": (
                        f"{curso.docente.first_name} {curso.docente.last_name}"
                        if curso.docente
                        else "N/A"
                    ),
                    "horas_pendientes": curso.horas_academicas_semanales
                    - curso.horas_asignadas,
                    "horas_totales": curso.horas_academicas_semanales,
                    "tipo_curso": curso.tipo_curso,
                    "semestre_cursado": curso.semestre_cursado,
                    "excepcion_horario": curso.excepcion_horario,
                }
                if curso.tipo_curso == "GENERAL":
                    cursos_pendientes_generales.append(curso_data)
                else:
                    cursos_pendientes_especialidad.append(curso_data)

            # Lógica para bloques ya asignados (que se mostrarán en el horario)
            for bloque in curso.bloques_horario.all():
                cursos_asignados_json.append(
                    {
                        "bloque_id": bloque.id,
                        "curso_id": curso.id,
                        "nombre": curso.nombre,
                        "docente_nombre": (
                            f"{curso.docente.first_name} {curso.docente.last_name}"
                            if curso.docente
                            else "N/A"
                        ),
                        "dia": bloque.dia,
                        "franja_id_inicio": bloque.franja_inicio.id,
                        "duracion_bloques": bloque.duracion_bloques,
                        "tipo_curso": curso.tipo_curso,
                        "semestre_cursado": curso.semestre_cursado,
                        "excepcion_horario": curso.excepcion_horario,
                    }
                )

    return {
        "cursos_pendientes": {
            "generales": cursos_pendientes_generales,
            "especialidad": cursos_pendientes_especialidad,
        },
        "cursos_asignados": cursos_asignados_json,
    }


@staff_member_required
@csrf_exempt
def api_auto_asignar(request):
    if request.method != "POST":
        return error_response("Método no permitido", status_code=405)

    try:
        data = json.loads(request.body)
        especialidad_id = data.get("especialidad_id")
        semestre_cursado_num = data.get("semestre_cursado")

        semestre_activo = Semestre.objects.filter(estado="ACTIVO").first()
        if not semestre_activo:
            return error_response("No hay un semestre activo.", status_code=400)

        # 1. Identificar los cursos con horas pendientes para esta especialidad/semestre
        especialidad_obj = Especialidad.objects.get(id=especialidad_id)
        grupo_obj = especialidad_obj.grupo
        q_cursos_del_plan = Q(
            semestre=semestre_activo, semestre_cursado=semestre_cursado_num
        ) & (
            Q(especialidades__id=especialidad_id)
            | Q(especialidades__grupo=grupo_obj, tipo_curso="GENERAL")
        )

        cursos_a_planificar = (
            Curso.objects.filter(q_cursos_del_plan)
            .annotate(
                horas_asignadas=models.Sum(
                    "bloques_horario__duracion_bloques", default=0
                )
            )
            .select_related("docente")
            .prefetch_related("especialidades__grupo")
            .distinct()
        )

        cursos_con_pendientes = [
            c
            for c in cursos_a_planificar
            if c.horas_asignadas < c.horas_academicas_semanales
        ]

        if not cursos_con_pendientes:
            planner_data = _get_planner_data(especialidad_id, semestre_cursado_num)
            return success_response(
                data={"plannerData": planner_data},
                message="Todos los cursos para esta selección ya están completamente asignados.",
            )

        # 2. Construir el mapa de horarios ocupados y cargas horarias
        franjas_horarias = list(FranjaHoraria.objects.order_by("hora_inicio"))
        horarios_ocupados = defaultdict(set)

        # Estructuras para tracking de carga horaria
        carga_docente = defaultdict(lambda: defaultdict(int)) # {docente_id: {dia: horas}}
        carga_grupo = defaultdict(lambda: defaultdict(int))   # {(grupo_id, semestre): {dia: horas}}

        todos_los_bloques = BloqueHorario.objects.filter(
            curso__semestre=semestre_activo
        ).select_related("curso__docente").prefetch_related("curso__especialidades__grupo")

        for bloque in todos_los_bloques:
            try:
                franja_idx = franjas_horarias.index(bloque.franja_inicio)
                # Tracking de carga horaria
                if bloque.curso.docente:
                     carga_docente[bloque.curso.docente.id][bloque.dia] += bloque.duracion_bloques

                # Iterar sobre especialidades para tracking de grupo
                for especialidad in bloque.curso.especialidades.all():
                    if especialidad.grupo:
                        key_grupo = (especialidad.grupo.id, bloque.curso.semestre_cursado)
                        carga_grupo[key_grupo][bloque.dia] += bloque.duracion_bloques

                for i in range(bloque.duracion_bloques):
                    franja_ocupada = franjas_horarias[franja_idx + i]
                    if bloque.curso.docente:
                        horarios_ocupados["docente"].add(
                            (bloque.curso.docente.id, bloque.dia, franja_ocupada.id)
                        )
                    # Iterar sobre especialidades para ocupar horarios de grupo
                    for especialidad in bloque.curso.especialidades.all():
                        if especialidad.grupo:
                            horarios_ocupados["grupo"].add(
                                (
                                    especialidad.grupo.id,
                                    bloque.curso.semestre_cursado,
                                    bloque.dia,
                                    franja_ocupada.id,
                                )
                            )
            except ValueError:
                continue

        # Cargar Bloques No Lectivos
        bloques_no_lectivos = BloqueNoLectivo.objects.select_related("docente")
        for bloque in bloques_no_lectivos:
             try:
                franja_idx = franjas_horarias.index(bloque.franja_inicio)
                for i in range(bloque.duracion_bloques):
                    if franja_idx + i < len(franjas_horarias):
                        franja_ocupada = franjas_horarias[franja_idx + i]
                        horarios_ocupados["docente"].add(
                            (bloque.docente.id, bloque.dia, franja_ocupada.id)
                        )
             except ValueError:
                continue

        # 3. Lógica de asignación (similar a la global, pero no destructiva)
        cursos_asignados_ahora = 0
        dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
        posibles_duraciones = [3, 2, 1]

        for curso in cursos_con_pendientes:
            horas_pendientes = curso.horas_academicas_semanales - curso.horas_asignadas
            docente = curso.docente
            grupos = []
            for especialidad in curso.especialidades.all():
                if especialidad.grupo:
                    grupos.append(especialidad.grupo)

            semestre_cursado = curso.semestre_cursado
            random.shuffle(dias_semana)

            while horas_pendientes > 0:
                bloque_asignado_en_iteracion = False
                duracion_a_intentar = next(
                    (d for d in posibles_duraciones if d <= horas_pendientes), None
                )
                if not duracion_a_intentar:
                    break

                for dia in dias_semana:
                    # Validar límites diarios antes de intentar buscar hueco
                    if docente and carga_docente[docente.id][dia] + duracion_a_intentar > 8:
                        continue

                    # Validar límite de grupo para CADA grupo asociado
                    grupo_excede_limite = False
                    if semestre_cursado:
                        for grupo in grupos:
                            key_grupo = (grupo.id, semestre_cursado)
                            if carga_grupo[key_grupo][dia] + duracion_a_intentar > 6:
                                grupo_excede_limite = True
                                break
                    if grupo_excede_limite:
                        continue

                    for i in range(len(franjas_horarias) - duracion_a_intentar + 1):
                        franja_inicio = franjas_horarias[i]
                        franjas_del_bloque = franjas_horarias[
                            i : i + duracion_a_intentar
                        ]
                        bloque_valido = True
                        for franja in franjas_del_bloque:
                            if (
                                docente.disponibilidad == "MANANA"
                                and franja.turno != "MANANA"
                            ) or (
                                docente.disponibilidad == "TARDE"
                                and franja.turno != "TARDE"
                            ):
                                bloque_valido = False
                                break
                            if (docente.id, dia, franja.id) in horarios_ocupados[
                                "docente"
                            ]:
                                bloque_valido = False
                                break

                            # Verificar conflicto para CADA grupo asociado
                            if semestre_cursado:
                                for grupo in grupos:
                                    if (
                                        grupo.id,
                                        semestre_cursado,
                                        dia,
                                        franja.id,
                                    ) in horarios_ocupados["grupo"]:
                                        bloque_valido = False
                                        break
                                if not bloque_valido:
                                    break

                        if not bloque_valido:
                            continue

                        BloqueHorario.objects.create(
                            curso=curso,
                            dia=dia,
                            franja_inicio=franja_inicio,
                            duracion_bloques=duracion_a_intentar,
                        )

                        # Actualizar tracking de carga
                        if docente:
                             carga_docente[docente.id][dia] += duracion_a_intentar
                        if semestre_cursado:
                            for grupo in grupos:
                                key_grupo = (grupo.id, semestre_cursado)
                                carga_grupo[key_grupo][dia] += duracion_a_intentar

                        for franja in franjas_del_bloque:
                            horarios_ocupados["docente"].add(
                                (docente.id, dia, franja.id)
                            )
                            if semestre_cursado:
                                for grupo in grupos:
                                    horarios_ocupados["grupo"].add(
                                        (grupo.id, semestre_cursado, dia, franja.id)
                                    )
                        horas_pendientes -= duracion_a_intentar
                        bloque_asignado_en_iteracion = True
                        break
                    if bloque_asignado_en_iteracion:
                        break
                if not bloque_asignado_en_iteracion:
                    break

            if horas_pendientes == 0:
                cursos_asignados_ahora += 1

        message = f"Proceso finalizado. Se completó la asignación para {cursos_asignados_ahora} cursos."
        planner_data = _get_planner_data(especialidad_id, semestre_cursado_num)
        return success_response(data={"plannerData": planner_data}, message=message)

    except Exception as e:
        import traceback

        traceback.print_exc()
        return server_error_response(f"Ocurrió un error inesperado: {e}")


@staff_member_required
@csrf_exempt
def generar_horario_automatico(request):
    if request.method != "POST":
        return error_response("Método no permitido", status_code=405)

    try:
        semestre_activo = Semestre.objects.filter(estado="ACTIVO").first()
        if not semestre_activo:
            return error_response(
                "No hay un semestre activo configurado.", status_code=400
            )

        # 1. Reset: Borrar todos los bloques de horario existentes para el semestre activo
        BloqueHorario.objects.filter(curso__semestre=semestre_activo).delete()

        # 2. Obtener recursos y restricciones
        cursos_a_asignar = list(
            Curso.objects.filter(semestre=semestre_activo, docente__isnull=False)
            .select_related("docente")
            .prefetch_related("especialidades__grupo")
            .annotate(num_especialidades=Count("especialidades"))
            .order_by(
                "-num_especialidades", "-horas_academicas_semanales"
            )  # Priorizar cursos más restrictivos (compartidos) y luego más horas
        )
        franjas_horarias = list(FranjaHoraria.objects.order_by("hora_inicio"))
        dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]

        # Estructura para mantener los horarios ocupados y evitar consultas a la BD en el bucle
        horarios_ocupados = defaultdict(set)  # (tipo, id, dia, franja_id) -> True

        # Estructuras para tracking de carga horaria
        carga_docente = defaultdict(lambda: defaultdict(int)) # {docente_id: {dia: horas}}
        carga_grupo = defaultdict(lambda: defaultdict(int))   # {(grupo_id, semestre): {dia: horas}}

        # Pre-cargar Bloques No Lectivos en horarios_ocupados
        bloques_no_lectivos = BloqueNoLectivo.objects.select_related("docente")
        for bloque in bloques_no_lectivos:
             try:
                franja_idx = franjas_horarias.index(bloque.franja_inicio)
                for i in range(bloque.duracion_bloques):
                    if franja_idx + i < len(franjas_horarias):
                        franja_ocupada = franjas_horarias[franja_idx + i]
                        horarios_ocupados["docente"].add(
                            (bloque.docente.id, bloque.dia, franja_ocupada.id)
                        )
             except ValueError:
                continue

        cursos_completados = 0
        cursos_no_asignados_completamente = []

        # 3. Iterar y asignar bloques para cada curso
        for curso in cursos_a_asignar:
            horas_pendientes = curso.horas_academicas_semanales
            docente = curso.docente
            grupos = []
            for especialidad in curso.especialidades.all():
                if especialidad.grupo:
                    grupos.append(especialidad.grupo)

            semestre_cursado = curso.semestre_cursado

            # Estrategia de división de bloques: intentar con bloques más grandes primero
            posibles_duraciones = [3, 2, 1]

            random.shuffle(
                dias_semana
            )  # Aleatorizar el día de inicio para variar los horarios

            while horas_pendientes > 0:
                bloque_asignado_en_iteracion = False

                # Intentar asignar un bloque de la mayor duración posible
                duracion_a_intentar = next(
                    (d for d in posibles_duraciones if d <= horas_pendientes), None
                )
                if not duracion_a_intentar:
                    break  # No se pueden asignar las horas restantes con las duraciones posibles

                for dia in dias_semana:
                    # Validar límites diarios antes de intentar buscar hueco
                    if docente and carga_docente[docente.id][dia] + duracion_a_intentar > 8:
                        continue

                    # Validar carga grupo para todos los grupos
                    grupo_excede_limite = False
                    if semestre_cursado:
                        for grupo in grupos:
                            key_grupo = (grupo.id, semestre_cursado)
                            if carga_grupo[key_grupo][dia] + duracion_a_intentar > 6:
                                grupo_excede_limite = True
                                break
                    if grupo_excede_limite:
                        continue

                    for i in range(len(franjas_horarias) - duracion_a_intentar + 1):
                        franja_inicio = franjas_horarias[i]
                        franjas_del_bloque = franjas_horarias[
                            i : i + duracion_a_intentar
                        ]

                        # --- Verificación de conflictos ---
                        bloque_valido = True
                        for franja in franjas_del_bloque:
                            # Conflicto de disponibilidad del docente (Mañana/Tarde)
                            if (
                                docente.disponibilidad == "MANANA"
                                and franja.turno != "MANANA"
                            ) or (
                                docente.disponibilidad == "TARDE"
                                and franja.turno != "TARDE"
                            ):
                                bloque_valido = False
                                break

                            # Conflicto de horario del docente
                            if (docente.id, dia, franja.id) in horarios_ocupados[
                                "docente"
                            ]:
                                bloque_valido = False
                                break

                            # Conflicto de horario de LOS grupos
                            if semestre_cursado:
                                for grupo in grupos:
                                    if (
                                        grupo.id,
                                        semestre_cursado,
                                        dia,
                                        franja.id,
                                    ) in horarios_ocupados["grupo"]:
                                        bloque_valido = False
                                        break
                                if not bloque_valido:
                                    break

                        if not bloque_valido:
                            continue

                        # --- Si el bloque es válido, crearlo y actualizar estructuras ---
                        BloqueHorario.objects.create(
                            curso=curso,
                            dia=dia,
                            franja_inicio=franja_inicio,
                            duracion_bloques=duracion_a_intentar,
                        )

                        # Actualizar tracking de carga
                        if docente:
                             carga_docente[docente.id][dia] += duracion_a_intentar
                        if semestre_cursado:
                            for grupo in grupos:
                                key_grupo = (grupo.id, semestre_cursado)
                                carga_grupo[key_grupo][dia] += duracion_a_intentar

                        # Marcar las franjas como ocupadas
                        for franja in franjas_del_bloque:
                            horarios_ocupados["docente"].add(
                                (docente.id, dia, franja.id)
                            )
                            if semestre_cursado:
                                for grupo in grupos:
                                    horarios_ocupados["grupo"].add(
                                        (grupo.id, semestre_cursado, dia, franja.id)
                                    )

                        horas_pendientes -= duracion_a_intentar
                        bloque_asignado_en_iteracion = True
                        break  # Salir del bucle de franjas
                    if bloque_asignado_en_iteracion:
                        break  # Salir del bucle de dias

                if not bloque_asignado_en_iteracion:
                    # Si no se pudo asignar ningún bloque en una iteración completa, romper para evitar bucles infinitos
                    break

            if horas_pendientes == 0:
                cursos_completados += 1
            else:
                cursos_no_asignados_completamente.append(
                    f"{curso.nombre} ({horas_pendientes}h pendientes)"
                )

        # 4. Construir el mensaje de respuesta
        total_cursos = len(cursos_a_asignar)
        message = f"Proceso completado. Se asignaron completamente {cursos_completados} de {total_cursos} cursos planificables."
        if cursos_no_asignados_completamente:
            message += f" Cursos no asignados completamente: {', '.join(cursos_no_asignados_completamente)}."

        cursos_sin_docente = Curso.objects.filter(
            semestre=semestre_activo, docente__isnull=True
        ).count()
        if cursos_sin_docente > 0:
            message += f" Hay {cursos_sin_docente} cursos sin docente asignado que no pudieron ser planificados."

        return success_response(message=message)

    except Exception as e:
        import traceback

        traceback.print_exc()
        return server_error_response(f"Ocurrió un error inesperado: {e}")


@staff_member_required
def api_get_cursos_no_asignados(request):
    try:
        especialidad_id = request.GET.get("especialidad_id")
        semestre_cursado = request.GET.get("semestre_cursado")
        planner_data = _get_planner_data(especialidad_id, semestre_cursado)
        return success_response(data=planner_data)
    except ValueError as e:
        return not_found_response(str(e))
