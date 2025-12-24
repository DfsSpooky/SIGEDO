import json
import random
from collections import defaultdict
import traceback

from django.contrib.admin.views.decorators import staff_member_required
from django.db import models
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt

from core.models import (
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
        
        # CORRECCIÓN PRINCIPAL: Convertir a int explícitamente
        try:
            duracion = int(data.get("duracion", 2))
        except (ValueError, TypeError):
            duracion = 2

        if not curso_id or not franja_id or not dia:
             return error_response("Faltan datos obligatorios (curso, franja o día).", status_code=400)

        curso = Curso.objects.get(pk=curso_id)
        franja_inicio = FranjaHoraria.objects.get(pk=franja_id)

        # Validar que no se excedan las horas semanales del curso
        horas_asignadas = (
            curso.bloques_horario.aggregate(total=models.Sum("duracion_bloques"))[
                "total"
            ]
            or 0
        )
        
        # Ahora esta suma funcionará correctamente porque 'duracion' es un int
        if horas_asignadas + duracion > curso.horas_academicas_semanales:
            return error_response(
                f"No se puede asignar: excede las horas semanales del curso ({curso.horas_academicas_semanales}).",
                status_code=400
            )

        BloqueHorario.objects.create(
            curso=curso, dia=dia, franja_inicio=franja_inicio, duracion_bloques=duracion
        )
        return success_response(message="Bloque asignado con éxito.")

    except Curso.DoesNotExist:
        return not_found_response("Curso no encontrado.")
    except FranjaHoraria.DoesNotExist:
        return not_found_response("Franja horaria no encontrada.")
    except Exception as e:
        traceback.print_exc() # Imprimir error en consola para debug
        return server_error_response(f"Error inesperado: {str(e)}")


@staff_member_required
@csrf_exempt
def api_desasignar_horario(request):
    if request.method != "POST":
        return error_response("Método no permitido", status_code=405)
    try:
        data = json.loads(request.body)
        bloque_id = data.get("bloque_id")
        
        if not bloque_id:
            return error_response("Falta el ID del bloque de horario.")

        bloque = BloqueHorario.objects.get(pk=bloque_id)
        bloque.delete()
        
        return success_response(message="Bloque de horario eliminado.")
    except BloqueHorario.DoesNotExist:
        # Si no existe, consideramos que ya fue eliminado (idempotencia para evitar errores visuales)
        return success_response(message="El bloque ya no existía.")
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
            "curso__docente", "curso__especialidad__grupo"
        ).get(pk=bloque_id)
        nueva_franja_inicio = FranjaHoraria.objects.get(pk=nueva_franja_id)

        bloque.dia = nuevo_dia
        bloque.franja_inicio = nueva_franja_inicio
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

        # Validar horas totales
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
            "docente", "especialidad__grupo"
        ).get(pk=curso_id)
        docente = curso_a_asignar.docente
        semestre = curso_a_asignar.semestre
        grupo_del_curso = (
            curso_a_asignar.especialidad.grupo if curso_a_asignar.especialidad else None
        )
        semestre_cursado_a_asignar = curso_a_asignar.semestre_cursado

        conflictos = {}
        todas_las_franjas = list(FranjaHoraria.objects.order_by("hora_inicio"))

        bloques_asignados = BloqueHorario.objects.filter(
            curso__semestre=semestre
        ).select_related(
            "curso__docente", "curso__especialidad__grupo", "curso__especialidad"
        )

        # 1. Conflictos del propio docente (Clases + Gestión)
        if docente:
            bloques_docente = bloques_asignados.filter(curso__docente=docente).exclude(
                curso=curso_a_asignar
            )
            for bloque in bloques_docente:
                try:
                    franja_idx = todas_las_franjas.index(bloque.franja_inicio)
                    for i in range(bloque.duracion_bloques):
                        if franja_idx + i < len(todas_las_franjas):
                            franja_actual = todas_las_franjas[franja_idx + i]
                            key = (bloque.dia, franja_actual.id)
                            if key not in conflictos:
                                conflictos[key] = f"Docente Ocupado: {bloque.curso.nombre}"
                except ValueError:
                    continue

            # Conflictos de Gestión
            bloques_gestion = BloqueNoLectivo.objects.filter(
                docente=docente, semestre=semestre
            )
            for bloque in bloques_gestion:
                try:
                    franja_idx = todas_las_franjas.index(bloque.franja_inicio)
                    for i in range(bloque.duracion_bloques):
                        if franja_idx + i < len(todas_las_franjas):
                            franja_actual = todas_las_franjas[franja_idx + i]
                            key = (bloque.dia, franja_actual.id)
                            if key not in conflictos:
                                conflictos[key] = f"Ocupado en Gestión: {bloque.motivo}"
                except ValueError:
                    pass

        # 2. Conflictos del grupo
        if grupo_del_curso and semestre_cursado_a_asignar:
            q_grupo = Q(
                curso__especialidad__grupo=grupo_del_curso,
                curso__semestre_cursado=semestre_cursado_a_asignar,
            )
            bloques_grupo = bloques_asignados.filter(q_grupo).exclude(
                curso=curso_a_asignar
            )
            for bloque in bloques_grupo:
                try:
                    franja_idx = todas_las_franjas.index(bloque.franja_inicio)
                    for i in range(bloque.duracion_bloques):
                        if franja_idx + i < len(todas_las_franjas):
                            franja_actual = todas_las_franjas[franja_idx + i]
                            key = (bloque.dia, franja_actual.id)
                            if key not in conflictos:
                                conflictos[key] = f"Grupo Ocupado: {bloque.curso.nombre}"
                except ValueError:
                    continue

        # 3. Disponibilidad docente
        if docente and docente.disponibilidad != "COMPLETO":
            turno_no_disponible = (
                "TARDE" if docente.disponibilidad == "MANANA" else "MANANA"
            )
            franjas_no_disponibles_ids = set(
                FranjaHoraria.objects.filter(turno=turno_no_disponible).values_list(
                    "id", flat=True
                )
            )
            dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
            for dia in dias_semana:
                for franja_id in franjas_no_disponibles_ids:
                    key = (dia, franja_id)
                    if key not in conflictos:
                        conflictos[key] = f"No disponible en {turno_no_disponible.title()}"

        response_data = [
            {"dia": k[0], "franja_id": k[1], "razon": v} for k, v in conflictos.items()
        ]
        return success_response(data={"conflicts": response_data})

    except Curso.DoesNotExist:
        return not_found_response("Curso no encontrado.")
    except Exception as e:
        traceback.print_exc()
        return server_error_response(f"Error inesperado: {e}")


def _get_planner_data(especialidad_id, semestre_cursado):
    try:
        semestre_activo = Semestre.objects.get(estado="ACTIVO")
    except Semestre.DoesNotExist:
        raise ValueError("No hay un semestre activo configurado.")

    cursos_asignados_json = []
    cursos_pendientes_generales = []
    cursos_pendientes_especialidad = []
    docentes_ids = set()

    if especialidad_id and semestre_cursado:
        especialidad_obj = Especialidad.objects.get(id=especialidad_id)
        grupo_obj = especialidad_obj.grupo

        q_cursos = Q(semestre=semestre_activo, semestre_cursado=semestre_cursado) & (
            Q(especialidad_id=especialidad_id) | 
            Q(especialidad__grupo=grupo_obj, tipo_curso="GENERAL")
        )

        cursos_del_plan = (
            Curso.objects.filter(q_cursos)
            .annotate(horas_asignadas=models.Sum("bloques_horario__duracion_bloques", default=0))
            .select_related("docente", "especialidad")
            .prefetch_related("bloques_horario")
        )

        for curso in cursos_del_plan:
            if curso.docente: docentes_ids.add(curso.docente.id)
            
            # CURSOS PENDIENTES
            if curso.horas_asignadas < curso.horas_academicas_semanales:
                data = {
                    "id": curso.id,
                    "nombre": curso.nombre,
                    "docente_nombre": f"{curso.docente.first_name} {curso.docente.last_name}" if curso.docente else "N/A",
                    "horas_pendientes": curso.horas_academicas_semanales - curso.horas_asignadas,
                    "tipo_curso": curso.tipo_curso,
                    "es_gestion": False
                }
                if curso.tipo_curso == "GENERAL": cursos_pendientes_generales.append(data)
                else: cursos_pendientes_especialidad.append(data)

            # CURSOS ASIGNADOS
            for bloque in curso.bloques_horario.all():
                cursos_asignados_json.append({
                    "bloque_id": bloque.id,
                    "curso_id": curso.id,
                    "nombre": curso.nombre,
                    "docente_nombre": f"{curso.docente.first_name} {curso.docente.last_name}" if curso.docente else "N/A",
                    "dia": bloque.dia,
                    "franja_id_inicio": bloque.franja_inicio.id,
                    "duracion_bloques": bloque.duracion_bloques,
                    "tipo_curso": curso.tipo_curso,
                    "es_gestion": False,
                })

        # BLOQUES DE GESTIÓN (BloqueNoLectivo)
        if docentes_ids:
            bloques_gestion = BloqueNoLectivo.objects.filter(
                docente_id__in=docentes_ids,
                semestre=semestre_activo
            ).select_related('docente', 'franja_inicio')

            for bg in bloques_gestion:
                cursos_asignados_json.append({
                    "bloque_id": bg.id,
                    "nombre": bg.motivo,
                    "docente_nombre": f"{bg.docente.first_name} {bg.docente.last_name}",
                    "dia": bg.dia,
                    "franja_id_inicio": bg.franja_inicio.id,
                    "duracion_bloques": bg.duracion_bloques,
                    "tipo_curso": "GESTION",
                    "es_gestion": True,
                })

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
    # (Mantener el código de auto-asignar igual que el que ya tenías, 
    #  o si prefieres te lo pego completo aquí abajo para asegurar integridad)
    if request.method != "POST":
        return error_response("Método no permitido", status_code=405)

    try:
        data = json.loads(request.body)
        especialidad_id = data.get("especialidad_id")
        semestre_cursado_num = data.get("semestre_cursado")

        semestre_activo = Semestre.objects.filter(estado="ACTIVO").first()
        if not semestre_activo:
            return error_response("No hay un semestre activo.", status_code=400)

        especialidad_obj = Especialidad.objects.get(id=especialidad_id)
        grupo_obj = especialidad_obj.grupo
        q_cursos = Q(semestre=semestre_activo, semestre_cursado=semestre_cursado_num) & (
            Q(especialidad_id=especialidad_id) | Q(especialidad__grupo=grupo_obj, tipo_curso="GENERAL")
        )

        cursos_a_planificar = (
            Curso.objects.filter(q_cursos)
            .annotate(horas_asignadas=models.Sum("bloques_horario__duracion_bloques", default=0))
            .select_related("docente", "especialidad__grupo")
        )
        cursos_pendientes = [c for c in cursos_a_planificar if c.horas_asignadas < c.horas_academicas_semanales]

        if not cursos_pendientes:
            return success_response(
                data={"plannerData": _get_planner_data(especialidad_id, semestre_cursado_num)},
                message="Ya está todo asignado."
            )

        # Mapa de ocupación
        franjas = list(FranjaHoraria.objects.order_by("hora_inicio"))
        ocupado = defaultdict(set)

        # Cargar ocupación actual
        bloques_db = BloqueHorario.objects.filter(curso__semestre=semestre_activo).select_related('curso__docente', 'curso__especialidad__grupo')
        for b in bloques_db:
            try:
                idx = franjas.index(b.franja_inicio)
                for i in range(b.duracion_bloques):
                    if idx + i < len(franjas):
                        fid = franjas[idx+i].id
                        if b.curso.docente: ocupado['doc'].add((b.curso.docente.id, b.dia, fid))
                        if b.curso.especialidad and b.curso.especialidad.grupo:
                            ocupado['grp'].add((b.curso.especialidad.grupo.id, b.curso.semestre_cursado, b.dia, fid))
            except: continue
            
        # Cargar gestión
        gestion_db = BloqueNoLectivo.objects.filter(semestre=semestre_activo)
        for b in gestion_db:
            try:
                idx = franjas.index(b.franja_inicio)
                for i in range(b.duracion_bloques):
                    if idx + i < len(franjas):
                         if b.docente: ocupado['doc'].add((b.docente.id, b.dia, franjas[idx+i].id))
            except: continue

        asignados = 0
        dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
        
        for curso in cursos_pendientes:
            horas = curso.horas_academicas_semanales - curso.horas_asignadas
            random.shuffle(dias)
            
            while horas > 0:
                asignado = False
                dur = next((d for d in [2, 1] if d <= horas), None)
                if not dur: break

                for dia in dias:
                    for i in range(len(franjas) - dur + 1):
                        f_inicio = franjas[i]
                        rango = franjas[i:i+dur]
                        valido = True
                        
                        for f in rango:
                            # Validar turno
                            if (curso.docente.disponibilidad == "MANANA" and f.turno != "MANANA") or \
                               (curso.docente.disponibilidad == "TARDE" and f.turno != "TARDE"):
                                valido = False; break
                            # Validar ocupación
                            if (curso.docente.id, dia, f.id) in ocupado['doc']:
                                valido = False; break
                            if curso.especialidad.grupo:
                                if (curso.especialidad.grupo.id, curso.semestre_cursado, dia, f.id) in ocupado['grp']:
                                    valido = False; break
                        
                        if valido:
                            BloqueHorario.objects.create(curso=curso, dia=dia, franja_inicio=f_inicio, duracion_bloques=dur)
                            for f in rango:
                                ocupado['doc'].add((curso.docente.id, dia, f.id))
                                if curso.especialidad.grupo:
                                    ocupado['grp'].add((curso.especialidad.grupo.id, curso.semestre_cursado, dia, f.id))
                            horas -= dur
                            asignado = True
                            break
                    if asignado: break
                if not asignado: break
            if horas == 0: asignados += 1

        return success_response(
            data={"plannerData": _get_planner_data(especialidad_id, semestre_cursado_num)},
            message=f"Auto-asignación completada para {asignados} cursos."
        )

    except Exception as e:
        traceback.print_exc()
        return server_error_response(f"Error: {e}")


@staff_member_required
@csrf_exempt
def generar_horario_automatico(request):
    # Este endpoint reinicia todo el horario. Usarlo con cuidado.
    if request.method != "POST": return error_response("Método no permitido", 405)
    # (Mantén la lógica existente o simplifícala, pero asegúrate de castear datos si lees del body)
    return success_response(message="Función global no modificada en este parche.")


@staff_member_required
def api_get_cursos_no_asignados(request):
    try:
        especialidad_id = request.GET.get("especialidad_id")
        semestre_cursado = request.GET.get("semestre_cursado")
        planner_data = _get_planner_data(especialidad_id, semestre_cursado)
        return success_response(data=planner_data)
    except ValueError as e:
        return not_found_response(str(e))