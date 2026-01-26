import json
import random
import google.generativeai as genai
from collections import defaultdict
from datetime import datetime
from django.conf import settings
from rest_framework.views import APIView
from core.services.or_tools_solver import HorarioSolver

from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from django.db import models, transaction
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

def success_htmx_trigger(message, trigger):
    response = success_response(message=message)
    response['HX-Trigger'] = trigger
    return response

def calcular_puntaje(docente_id, dia, franja_idx, duracion, carga_docente_dia, docente_occupied_indices):
    """
    Calcula un puntaje para una asignación candidata. Menor puntaje es mejor.
    Reglas:
    1. Continuidad (-50 pts): Si es adyacente a un bloque existente.
    2. Huecos (+10 pts/hora): Si deja espacios vacíos.
    3. Dispersión (+5 pts): Si abre un día nuevo innecesariamente.
    """
    score = 0
    
    # Si no hay identificador de docente, es un "N/A", asignación aleatoria (score 0 base)
    if not docente_id:
        return 0

    indices_ocupados = docente_occupied_indices[docente_id][dia]
    
    # Regla 2 y 1: Huecos y Continuidad
    if indices_ocupados:
        min_dist_bloque = float('inf')
        # El bloque candidato ocupa desde franja_idx hasta franja_idx + duracion - 1
        # Buscamos la distancia con los bloques ya ocupados
        
        # Simplificación: Distancia mínima entre el final de uno y el inicio de otro
        # Como occupied_indices es un set de indices individuales, iteramos.
        
        candidatos_indices = set(range(franja_idx, franja_idx + duracion))
        
        for occ in indices_ocupados:
            for cand in candidatos_indices:
                dist = abs(occ - cand) - 1
                if dist < min_dist_bloque:
                    min_dist_bloque = dist
        
        # dist = 0 significa adyacente (e.g. ocupa 2, candidato 3 -> abs(2-3)-1 = 0)
        # dist = -1 significa superposición (ya filtrado antes, no debería pasar)
        if min_dist_bloque <= 0:
            score -= 50 # Bonificación fuerte por continuidad
        else:
            score += min_dist_bloque * 10 # Penalización por huecos
            
    # Regla 3: Dispersión (Evitar abrir dias nuevos si no es necesario)
    if carga_docente_dia == 0:
        score += 5
        
    return score


@staff_member_required
@csrf_exempt
@staff_member_required
@csrf_exempt
def api_asignar_horario(request):
    # Soporte para HTMX (POST form data) o JSON (fetch)
    if request.method != "POST":
        return error_response("Método no permitido", status_code=405)

    try:
        # Detectar si es JSON o Form Data (HTMX usa Form Data por defecto, pero htmx.ajax puede ser config)
        # SortableJS htmx.ajax enviara x-www-form-urlencoded o json dependiendo de config.
        # Asumiremos que leemos de request.POST si no es JSON body.
        
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST

        curso_id = data.get("curso_id")
        franja_id = data.get("franja_id")
        dia = data.get("dia")
        aula_id = data.get("aula_id")  # Optional

        # La duración del bloque ahora debe ser enviada desde el frontend.
        # Asumimos un valor por defecto si no se envía, para compatibilidad temporal.
        duracion = int(data.get("duracion", 2))

        curso = Curso.objects.get(pk=curso_id)
        franja_inicio = FranjaHoraria.objects.get(pk=franja_id)

        aula = None
        if aula_id:
            try:
                aula = Aula.objects.get(pk=aula_id)
            except Aula.DoesNotExist:
                return error_htmx(request, f"El aula con ID {aula_id} no existe.")

        # Validar que no se excedan las horas semanales del curso
        horas_asignadas = (
            curso.bloques_horario.aggregate(total=models.Sum("duracion_bloques"))[
                "total"
            ]
            or 0
        )
        if horas_asignadas + duracion > curso.horas_academicas_semanales:
            return error_htmx(request, 
                f"No se puede asignar: excede las horas semanales del curso ({curso.horas_academicas_semanales})."
            )

        # Validación de conflictos usando el método clean() del modelo
        # --- TRANSACCIÓN ATÓMICA ---
        try:
            with transaction.atomic():
                bloque = BloqueHorario(
                    curso=curso, dia=dia, franja_inicio=franja_inicio, duracion_bloques=duracion, aula=aula
                )
                bloque.full_clean()
                bloque.save()
        except ValidationError as e:
            # Extraer el mensaje de error de la excepción
            error_message = next(iter(e.message_dict.values()))[0] if hasattr(e, 'message_dict') else str(e)
            return error_htmx(request, f"Conflicto de horario: {error_message}")

        if request.headers.get('HX-Request'):
            # Prepara contexto para el partial
            # Calcular hora fin
            # Necesitamos todas las franjas para calcular la hora final visual
            all_franjas = list(FranjaHoraria.objects.order_by('hora_inicio'))
            try:
                start_idx = next(i for i, f in enumerate(all_franjas) if f.id == franja_inicio.id)
                end_idx = min(start_idx + duracion - 1, len(all_franjas) - 1)
                hora_fin = all_franjas[end_idx].hora_fin
            except StopIteration:
                hora_fin = franja_inicio.hora_fin # Fallback

            time_range = f"{franja_inicio.hora_inicio.strftime('%H:%M')} - {hora_fin.strftime('%H:%M')}"
            
            # Especialidades string
            esp_names = [e.nombre for e in curso.especialidades.all()]
            bloque.curso.especialidades_nombres_str = ", ".join(esp_names)

            context = {
                'bloque': bloque,
                'time_range': time_range,
                'es_ghost': False # TODO: Logic logic for ghost if needed
            }
            return render(request, 'partials/planner_cell.html', context)

        return success_htmx_trigger("Bloque asignado con éxito.", "reload-unassigned")

    except Curso.DoesNotExist:
        return error_htmx(request, "Curso no encontrado.")
    except FranjaHoraria.DoesNotExist:
        return error_htmx(request, "Franja horaria no encontrada.")
    except Exception as e:
        return error_htmx(request, f"Error inesperado: {e}")

def error_htmx(request, message):
    if request.headers.get('HX-Request'):
        from django.http import HttpResponse
        response = HttpResponse(status=200) # HTMX swaps even on 200, but we use triggers
        response['HX-Trigger'] = json.dumps({"showError": message})
        return response
    return error_response(message)


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

        # --- TRANSACCIÓN ATÓMICA ---
        with transaction.atomic():
            bloque = BloqueHorario.objects.select_for_update().get(pk=bloque_id)
            bloque.delete()
            
        return success_htmx_trigger("Bloque de horario eliminado.", "reload-unassigned")
    except BloqueHorario.DoesNotExist:
        return not_found_response("El bloque de horario especificado no existe.")
    except Exception as e:
        return server_error_response(str(e))


@staff_member_required
@csrf_exempt
@staff_member_required
@csrf_exempt
def api_mover_bloque(request):
    if request.method != "POST":
        return error_response("Método no permitido", status_code=405)

    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST

        bloque_id = data.get("bloque_id")
        nuevo_dia = data.get("dia")
        nueva_franja_id = data.get("franja_id")

        # --- TRANSACCIÓN ATÓMICA ---
        try:
            with transaction.atomic():
                bloque = BloqueHorario.objects.select_for_update().select_related(
                    "curso__docente"
                ).prefetch_related("curso__especialidades__grupo").get(pk=bloque_id)
                nueva_franja_inicio = FranjaHoraria.objects.get(pk=nueva_franja_id)

                bloque.dia = nuevo_dia
                bloque.franja_inicio = nueva_franja_inicio

                bloque.full_clean()
                bloque.save()
        except ValidationError as e:
            error_message = next(iter(e.message_dict.values()))[0] if hasattr(e, 'message_dict') else str(e)
            return error_htmx(request, f"No se puede mover: {error_message}")

        if request.headers.get('HX-Request'):
             # Prepara contexto para el partial
            all_franjas = list(FranjaHoraria.objects.order_by('hora_inicio'))
            try:
                start_idx = next(i for i, f in enumerate(all_franjas) if f.id == nueva_franja_inicio.id)
                end_idx = min(start_idx + bloque.duracion_bloques - 1, len(all_franjas) - 1)
                hora_fin = all_franjas[end_idx].hora_fin
            except StopIteration:
                hora_fin = nueva_franja_inicio.hora_fin # Fallback

            time_range = f"{nueva_franja_inicio.hora_inicio.strftime('%H:%M')} - {hora_fin.strftime('%H:%M')}"
            
            esp_names = [e.nombre for e in bloque.curso.especialidades.all()]
            bloque.curso.especialidades_nombres_str = ", ".join(esp_names)

            context = {
                'bloque': bloque,
                'time_range': time_range,
                'es_ghost': False
            }
            response = render(request, 'partials/planner_cell.html', context)
            return response

        return success_response(message="Bloque movido con éxito.")

    except BloqueHorario.DoesNotExist:
        return error_htmx(request, "El bloque a mover no existe.")
    except FranjaHoraria.DoesNotExist:
        return error_htmx(request, "La nueva franja horaria no existe.")
    except Exception as e:
        return error_htmx(request, f"Error inesperado: {e}")


@staff_member_required
@csrf_exempt
def api_ajustar_duracion(request):
    if request.method != "POST":
        return error_response("Método no permitido", status_code=405)

    try:
        data = json.loads(request.body)
        bloque_id = data.get("bloque_id")
        accion = data.get("accion")  # 'increase' or 'decrease'

        # --- TRANSACCIÓN ATÓMICA ---
        try:
            with transaction.atomic():
                bloque = BloqueHorario.objects.select_for_update().select_related("curso").get(pk=bloque_id)

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
                bloque.full_clean()
                bloque.save()

        except ValidationError as e:
            error_message = next(iter(e.message_dict.values()))[0] if hasattr(e, 'message_dict') else str(e)
            return error_response(f"No se puede ajustar duración: {error_message}")

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


@staff_member_required
@csrf_exempt
def load_planner_content(request):
    especialidad_id = request.GET.get('especialidad_id')
    semestre_cursado = request.GET.get('semestre_cursado')

    if not especialidad_id or not semestre_cursado:
        return HttpResponse("") # Return empty if params missing

    try:
        data = _get_planner_data(especialidad_id, semestre_cursado)
        
        # Estructurar datos para el template (Grid)
        # Necesitamos grid[turno][franja_id][dia] = bloque
        
        franjas_manana = list(FranjaHoraria.objects.filter(turno='MANANA').order_by('hora_inicio'))
        franjas_tarde = list(FranjaHoraria.objects.filter(turno='TARDE').order_by('hora_inicio'))
        dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
        
        # Mapear bloques por posicion
        assigned_map = {} # Key: (dia, franja_id) -> bloquedict
        for b in data['cursos_asignados']:
             # Buscar franja idx para calcular duracion visual (rowspan logic)
             # Pero en el template iteramos franjas.
             # Solo necesitamos el objeto bloque en la celda de inicio.
             assigned_map[(b['dia'], b['franja_id_inicio'])] = b
             
             # Tambien necesitamos marcar las celdas ocupadas por la duracion > 1 (para ocultarlas)
             # Esto es complejo en template puro.
             # Lo haremos pre-calculado:
             # cell_state[dia][franja_id] = { 'bloque': b, 'span': duration, 'hidden': bool }

        schedule_grid = { 'MANANA': {}, 'TARDE': {} }
        
        # Helper para construir el grid
        def build_grid_data(franjas, turno_key):
            grid_rows = []
            for f in franjas:
                row_data = {'franja': f, 'cells': {}}
                for d in dias:
                    cell_data = {'dia': d, 'franja_id': f.id}
                    
                    # Check assignments
                    key = (d, f.id)
                    if key in assigned_map:
                        # Bloque de inicio
                        b = assigned_map[key]
                        # Hydrate objects for template tag usage manually or pass simple dict
                        # El partial usa bloque.curso.nombre etc.
                        # _get_planner_data devuelve dicts.
                        # El partial espera OBJETO o dict con access similar.
                        # _get_planner_data devuelve dict serializado.
                        # Re-construir objeto dummy o usar un template tag personalizado?
                        # Mejor: Pasar un objeto simple que funcione con el partial.
                        # El partial usa {{ bloque.curso.nombre }}.
                        # Nuestro dict tiene bloque['nombre'].
                        # Modificaremos _get_planner_data o convertiremos aqui.
                        
                        # Hack rapido: Convertir dict a objeto con dot notation
                        class Struct:
                            def __init__(self, **entries): self.__dict__.update(entries)
                        
                        # Nested structs for curso, docente, etc
                        # Esto es tedioso.
                        # Mejor opcion: que _get_planner_data devuelva objetos ORM reales si se pide internamente?
                        # O modificar el partial para aceptar dicts?
                        # Modificare el partial para ser robusto (obj o dict).
                        
                        cell_data['bloque'] = b 
                        cell_data['rowspan'] = b['duracion_bloques']
                        
                        # Marcar celdas siguientes como hidden
                        # Necesitamos encontrar los siguientes IDs de franja
                        f_idx = next((i for i, x in enumerate(franjas) if x.id == f.id), -1)
                        if f_idx != -1:
                            for i in range(1, b['duracion_bloques']):
                                if f_idx + i < len(franjas):
                                    next_f = franjas[f_idx + i]
                                    # Marcar en un set global de hidden? 
                                    # No podemos modificar el row futuro facilmente aqui porque estamos iterando.
                                    pass
                    cell_data['hidden'] = False # Default
                    row_data['cells'][d] = cell_data
                grid_rows.append(row_data)
            
            # Second pass for hidden
            # Actually easier to use a set of hidden keys
            hidden_keys = set()
            for b in data['cursos_asignados']:
                 f_start_id = b['franja_id_inicio']
                 # Find index in franjas
                 # This is O(N^2) but N is small (14 franjas)
                 try:
                     f_idx = next(i for i, x in enumerate(franjas) if x.id == f_start_id)
                     for i in range(1, b['duracion_bloques']):
                        if f_idx + i < len(franjas):
                            hn_f = franjas[f_idx + i]
                            hidden_keys.add((b['dia'], hn_f.id))
                 except StopIteration:
                     pass
            
            # Apply hidden
            for r in grid_rows:
                for d in dias:
                    if (d, r['franja'].id) in hidden_keys:
                        r['cells'][d]['hidden'] = True

            return grid_rows

        grid_manana = build_grid_data(franjas_manana, 'MANANA')
        grid_tarde = build_grid_data(franjas_tarde, 'TARDE')

        context = {
            'grid_manana': grid_manana,
            'grid_tarde': grid_tarde,
            'dias_semana': dias,
            'cursos_pendientes': data['cursos_pendientes'], # {generales: [], especialidad: []}
        }
        return render(request, 'partials/planner_body.html', context)
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return HttpResponse(f"<div class='alert alert-error'>Error cargando horario: {e}</div>")

@staff_member_required
@csrf_exempt
def load_planner_sidebar(request):
    especialidad_id = request.GET.get('especialidad_id')
    semestre_cursado = request.GET.get('semestre_cursado')

    # Si faltan datos, devolvemos sidebar vacío o error
    if not especialidad_id or not semestre_cursado:
         return HttpResponse("")

    try:
        data = _get_planner_data(especialidad_id, semestre_cursado)
        context = {
            'cursos_pendientes': data['cursos_pendientes'],
        }
        return render(request, 'partials/planner_sidebar.html', context)
    except Exception as e:
        return HttpResponse(f"<div class='alert alert-error'>Error sidebar: {e}</div>")

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
            # We construct dicts compatible with the template logic
            # Using simple dicts
            esp_names = [e.nombre for e in curso.especialidades.all()]
            
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
                "horas_asignadas": curso.horas_asignadas,
                "tipo_curso": curso.tipo_curso,
                "semestre_cursado": curso.semestre_cursado,
                "excepcion_horario": curso.excepcion_horario,
                "especialidades_nombres": esp_names,
                "especialidades_nombres_str": ", ".join(esp_names),
                "especialidades_count": len(esp_names)
            }

            # Lógica para cursos pendientes
            if curso.horas_asignadas < curso.horas_academicas_semanales:
                if curso.tipo_curso == "GENERAL":
                    cursos_pendientes_generales.append(curso_data)
                else:
                    cursos_pendientes_especialidad.append(curso_data)

            # Lógica para bloques ya asignados
            for bloque in curso.bloques_horario.all():
                # Necesitamos un objeto "bloque" que tenga .curso.nombre etc
                # Simularemos la estructura anidada usando dicts
                
                cursos_asignados_json.append(
                    {
                        "id": bloque.id, # for data-bloque-id
                        "dia": bloque.dia,
                        "franja_id_inicio": bloque.franja_inicio.id,
                        "duracion_bloques": bloque.duracion_bloques,
                        "curso": curso_data # Nested curso data
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

        # --- TRANSACCIÓN ATÓMICA ---
        with transaction.atomic():
            semestre_activo = Semestre.objects.filter(estado="ACTIVO").select_for_update().first()
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
            
            # Estructura para tracking de indices ocupados por docente (para compactacion)
            docente_occupied_indices = defaultdict(lambda: defaultdict(set)) # {docente_id: {dia: {indices}}}

            todos_los_bloques = BloqueHorario.objects.filter(
                curso__semestre=semestre_activo
            ).select_related("curso__docente").prefetch_related("curso__especialidades__grupo")

            for bloque in todos_los_bloques:
                try:
                    franja_idx = franjas_horarias.index(bloque.franja_inicio)
                    # Tracking de carga horaria
                    if bloque.curso.docente:
                         carga_docente[bloque.curso.docente.id][bloque.dia] += bloque.duracion_bloques
                         for i in range(bloque.duracion_bloques):
                             docente_occupied_indices[bloque.curso.docente.id][bloque.dia].add(franja_idx + i)

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
                            docente_occupied_indices[bloque.docente.id][bloque.dia].add(franja_idx + i)
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
                # Sort days based on teacher load (ascending) to balance workload
                if docente:
                    dias_semana_ordenados = sorted(
                        dias_semana, key=lambda d: carga_docente[docente.id][d]
                    )
                else:
                    dias_semana_ordenados = list(dias_semana)
                    random.shuffle(dias_semana_ordenados)

                while horas_pendientes > 0:
                    bloque_asignado_en_iteracion = False
                    duracion_a_intentar = next(
                        (d for d in posibles_duraciones if d <= horas_pendientes), None
                    )
                    if not duracion_a_intentar:
                        break

                    for dia in dias_semana_ordenados:
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
                            
                        # Compactación: Ordenar indices
                        posibles_indices = list(range(len(franjas_horarias) - duracion_a_intentar + 1))
                        if docente and docente_occupied_indices[docente.id][dia]:
                            occupied = docente_occupied_indices[docente.id][dia]
                            def calculate_gap_score(start_index):
                                new_indices = set(range(start_index, start_index + duracion_a_intentar))
                                min_dist = float('inf')
                                for occ in occupied:
                                    for new in new_indices:
                                        dist = abs(occ - new)
                                        if dist < min_dist:
                                            min_dist = dist
                                if min_dist == 1:
                                    return 0 # Perfecto, pegado
                                return min_dist 
                            posibles_indices.sort(key=calculate_gap_score)

                        for i in posibles_indices:
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
                                 for idx_offset in range(duracion_a_intentar):
                                     docente_occupied_indices[docente.id][dia].add(i + idx_offset)

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
        solver = HorarioSolver(semestre_nombre="2026-A")
        results = solver.solve()
        
        if results:
            if solver.save_results(results):
                return success_response(message="Horario generado con éxito usando OR-Tools.")
            else:
                return error_response("Error al guardar los resultados en la base de datos.")
        else:
            return error_response("El solver no pudo encontrar una solución factible con las restricciones dadas.")

    except Exception as e:
        return server_error_response(f"Error inesperado: {e}")


        try:
            # Configurar Gemini
            genai.configure(api_key=getattr(settings, "GEMINI_API_KEY", ""))
            model_name = getattr(settings, "GEMINI_MODEL_NAME", "gemini-flash-latest")
            model = genai.GenerativeModel(model_name)
            
            # Obtener lista completa de cursos para el contexto
            cursos_qs = Curso.objects.filter(semestre__estado="ACTIVO").select_related('docente')
            cursos_context = "\n".join([f"- ID {c.id}: {c.nombre} (Docente: {c.docente.first_name if c.docente else 'N/A'}, Horas: {c.horas_academicas_semanales})" for c in cursos_qs])
            
            # Extraer parámetros usando Gemini
            extraction_prompt = f"""
            Eres un asistente experto en gestión de horarios académicos. Tu tarea es extraer la intención del usuario.
            
            CURSOS DISPONIBLES EN EL SISTEMA:
            {cursos_context}
            
            TEXTO DEL USUARIO: "{prompt}"
            
            REQUERIMIENTOS DE EXTRACCIÓN:
            1. **curso_id**: Identifica el ID del curso. El usuario puede decir "mueve mate" o "pasa literatura", busca el ID que mejor coincida.
            2. **nuevo_dia**: El día destino (Lunes, Martes, Miércoles, Jueves, Viernes).
            3. **nuevo_turno**: MANANA (8am-1pm) o TARDE (2pm-8pm). Si no se especifica, deduce según el nombre del turno.
            
            RESPUESTA EN FORMATO JSON ESTRICTO:
            {{
                "curso_id": <int>,
                "nuevo_dia": "<string>",
                "nuevo_turno": "<string>"
            }}
            """
            try:
                response = model.generate_content(extraction_prompt)
            except Exception as e:
                if "429" in str(e) or "quota" in str(e).lower():
                    return error_response(f"El servicio de IA ha excedido su cuota temporalmente. Por favor intenta de nuevo en unos minutos. (Modelo: {model_name})")
                raise e

            import re
            json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
            if not json_match:
                return error_response(f"No logré procesar tu pedido. Intenta ser más específico, por ejemplo: 'Mueve el curso de Matemática al Lunes por la mañana'.")
            
            params = json.loads(json_match.group())
            curso_id = params.get("curso_id")
            nuevo_dia = params.get("nuevo_dia")
            nuevo_turno = params.get("nuevo_turno")

            if not curso_id or not nuevo_dia:
                return error_response(f"No pude identificar qué curso o a qué día deseas moverlo.")

            # Obtener info del curso para saber cuántas horas mover
            try:
                curso_obj = Curso.objects.get(id=curso_id)
            except Curso.DoesNotExist:
                return error_response(f"El ID de curso {curso_id} sugerido por la IA no existe. Intenta decir el nombre completo del curso.")

            # Intentar resolver con la nueva restricción
            solver = HorarioSolver(semestre_nombre="2026-A")
            
            # Buscar una franja que coincida con el turno
            franjas_turno = list(FranjaHoraria.objects.filter(turno=nuevo_turno).order_by('hora_inicio'))
            if not franjas_turno:
                return error_response(f"No hay franjas horarias configuradas para el turno {nuevo_turno}.")
            
            # --- CONSTRUIR ESTADO FIJO (CONSTRAINTS) ---
            fixed = []
            
            # 1. Mantener constantes el resto de los cursos
            bloques_otros = BloqueHorario.objects.filter(curso__semestre__nombre="2026-A").exclude(curso_id=curso_id)
            for b in bloques_otros:
                # Expandir bloque a sus slots individuales
                # (El solver actual asume 1 slot por fixed item, pero save_results ahora los agrupa)
                # Necesitamos encontrar el indice de inicio y la duracion.
                franjas_todas = solver.data['franjas']
                try:
                    idx_start = next(i for i, f in enumerate(franjas_todas) if f.id == b.franja_inicio_id)
                    for offset in range(b.duracion_bloques):
                        if idx_start + offset < len(franjas_todas):
                            fixed.append((b.curso_id, b.dia, franjas_todas[idx_start + offset].id))
                except StopIteration:
                    continue

            # 2. Fijar TODAS las horas del curso objetivo en el nuevo día
            # Intentamos ponerlas de forma contigua en el turno solicitado
            horas_a_mover = curso_obj.horas_academicas_semanales
            for h in range(min(horas_a_mover, len(franjas_turno))):
                fixed.append((curso_id, nuevo_dia, franjas_turno[h].id))

            results = solver.solve(fixed_assignments=fixed)
            
            if results:
                solver.save_results(results)
                return success_response(message=f"¡Optimización completada! He movido todas las horas de '{curso_obj.nombre}' al {nuevo_dia} ({nuevo_turno}) y ajustado el resto para evitar conflictos.")
            else:
                return error_response(f"No pude mover '{curso_obj.nombre}' al {nuevo_dia} porque genera conflictos con otros cursos o con la disponibilidad del docente.")

        except Exception as e:
            import traceback
            traceback.print_exc()
            return server_error_response(f"Error interno en el asistente: {e}")

def api_get_placement_suggestions(request):
    """
    API para obtener sugerencias de ubicación para un curso dado.
    Calcula el puntaje para todas las franjas posibles y devuelve las mejores y los conflictos.
    """
    curso_id = request.GET.get("curso_id")
    if not curso_id:
        return JsonResponse({"status": "error", "message": "Falta curso_id"}, status=400)

    try:
        curso = Curso.objects.get(id=curso_id)
        docente = curso.docente
        semestre_activo = Semestre.objects.filter(estado="ACTIVO").first()

        if not docente:
             return JsonResponse({"status": "error", "message": "El curso no tiene docente asignado (Sugerencias requieren docente)"}, status=400)

        # Configuraciones Básicas
        # Si estamos arrastrando desde "No Asignados", usamos el bloque estandar (ej. 2h o lo que quede).
        duracion_request = request.GET.get("duracion")
        if duracion_request:
            duracion = int(duracion_request)
        else:
             duracion = min(2, curso.horas_pendientes) if curso.horas_pendientes > 0 else 2

        franjas_horarias = list(FranjaHoraria.objects.order_by("hora_inicio"))
        franja_map = {f.id: i for i, f in enumerate(franjas_horarias)}
        dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]

        # --- PREPARAR DATOS DE OCUPACIÓN (Similar a auto_asignar) ---
        # 1. Ocupación Docente
        bloques_docente = BloqueHorario.objects.filter(
            curso__docente=docente, 
            curso__semestre=semestre_activo
        ).exclude(curso__id=curso_id) 
        
        docente_ocupado = set()
        carga_docente_diaria = {dia: 0 for dia in dias_semana}
        # Estructura: {docente_id: {dia: {indices}}}
        docente_occupied_indices = {docente.id: {dia: set() for dia in dias_semana}}

        for b in bloques_docente:
            carga_docente_diaria[b.dia] += b.duracion_bloques
            try:
                start_idx = franja_map[b.franja_inicio.id]
                for i in range(b.duracion_bloques):
                    idx = start_idx + i
                    if idx < len(franjas_horarias):
                        f_id = franjas_horarias[idx].id
                        docente_ocupado.add((b.dia, f_id))
                        docente_occupied_indices[docente.id][b.dia].add(idx)
            except (KeyError, IndexError):
                pass
        
        # 2. Ocupación Grupo (si aplica)
        grupo_ocupado = set()
        grupo_ocupado_detalle = {} # (dia, f_id) -> Razón
        grupos = []
        # Iterar sobre todas las especialidades asociadas al curso
        for especialidad in curso.especialidades.all():
            if especialidad.grupo:
                grupos.append(especialidad.grupo)

        semestre_cursado = curso.semestre_cursado
        
        if semestre_cursado and grupos:
            q_grupos = Q()
            for g in grupos:
                q_grupos |= Q(especialidad__grupo=g) | Q(tipo_curso='GENERAL', especialidades__grupo=g)
            
            bloques_grupo = BloqueHorario.objects.filter(
                q_grupos,
                curso__semestre_cursado=semestre_cursado, # Mismo semestre
                curso__semestre=semestre_activo
            ).exclude(curso__id=curso_id)

            for b in bloques_grupo:
                 try:
                    start_idx = franja_map[b.franja_inicio.id]
                    for i in range(b.duracion_bloques):
                        idx = start_idx + i
                        if idx < len(franjas_horarias):
                            f_id = franjas_horarias[idx].id
                            key = (b.dia, f_id)
                            grupo_ocupado.add(key)
                            # Guardar detalle del conflicto
                            grupo_ocupado_detalle[key] = f"Conflicto con Grupo: {b.curso.nombre}"
                 except (KeyError, IndexError):
                    pass


        suggestions = []
        conflicts = []

        # --- EVALUAR TODAS LAS POSICIONES ---
        for dia in dias_semana:
            # Check límite diario docente
            if carga_docente_diaria[dia] + duracion > 8:
                 # Todo el día bloqueado
                 for f in franjas_horarias:
                     conflicts.append({
                         'dia': dia,
                         'franja_id': f.id,
                         'razon': 'Carga diaria máxima (8h) excedida'
                     })
                 continue

            for i in range(len(franjas_horarias) - duracion + 1):
                franja_inicio = franjas_horarias[i]
                franjas_del_bloque = franjas_horarias[i : i + duracion]
                
                # Validar el bloque entero
                bloque_valido = True
                razon_invalidez = None

                for f in franjas_del_bloque:
                    # 1. Disponibilidad Turno
                    if (docente.disponibilidad == "MANANA" and f.turno != "MANANA") or \
                       (docente.disponibilidad == "TARDE" and f.turno != "TARDE"):
                        bloque_valido = False
                        razon_invalidez = f"Docente solo {docente.disponibilidad}"
                        break
                    
                    # 2. Ocupación Docente
                    if (dia, f.id) in docente_ocupado:
                        bloque_valido = False
                        razon_invalidez = "Docente ocupado"
                        break
                    
                    # 3. Ocupación Grupo
                    if (dia, f.id) in grupo_ocupado:
                         bloque_valido = False
                         razon_invalidez = grupo_ocupado_detalle.get((dia, f.id), "Grupo ocupado")
                         break
                
                if bloque_valido:
                    # CALCULAR SCORE
                    score = calcular_puntaje(
                        docente.id, 
                        dia, 
                        i, 
                        duracion, 
                        carga_docente_diaria[dia], 
                        docente_occupied_indices
                    )
                    
                    tipo_sugerencia = 'neutral'
                    if score <= -50: tipo_sugerencia = 'excelente'
                    elif score < 0: tipo_sugerencia = 'buena'
                    elif score > 0: tipo_sugerencia = 'regular' # Gaps
                    
                    suggestions.append({
                        'dia': dia,
                        'franja_id': franja_inicio.id, 
                        'duracion': duracion, 
                        'score': score,
                        'tipo': tipo_sugerencia
                    })
                else:
                    conflicts.append({
                        'dia': dia,
                        'franja_id': franja_inicio.id,
                        'duracion': duracion,
                        'razon': razon_invalidez
                    })
        
        # Ordenar sugerencias por mejor score (menor es mejor)
        suggestions.sort(key=lambda x: x['score'])
        
        # Marcar las top 3 como 'best'
        for idx, s in enumerate(suggestions):
            if idx < 3 and s['score'] <= 0: # Solo si son buenas/neutrales
                 s['is_best'] = True

        return JsonResponse({
            "status": "success",
            "suggestions": suggestions,
            "conflicts": conflicts
        })

    except Curso.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Curso no encontrado"}, status=404)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@staff_member_required
def api_get_cursos_no_asignados(request):
    try:
        especialidad_id = request.GET.get("especialidad_id")
        semestre_cursado = request.GET.get("semestre_cursado")
        planner_data = _get_planner_data(especialidad_id, semestre_cursado)
        return success_response(data=planner_data)
    except ValueError as e:
        return not_found_response(str(e))


@staff_member_required
def api_exportar_horario(request):
    """
    Genera una vista imprimible del horario manejando correctamente los rowspans.
    """
    especialidad_id = request.GET.get("especialidad_id")
    semestre_cursado = request.GET.get("semestre")

    if not especialidad_id or not semestre_cursado:
        return error_response("Faltan parámetros.")

    try:
        planner_data = _get_planner_data(especialidad_id, semestre_cursado)
        especialidad = Especialidad.objects.get(id=especialidad_id)
        
        franjas_manana = list(FranjaHoraria.objects.filter(turno='MANANA').order_by('hora_inicio'))
        franjas_tarde = list(FranjaHoraria.objects.filter(turno='TARDE').order_by('hora_inicio'))
        dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
        
        def build_grid(franjas):
            # 1. Crear estructura base vacía
            # grid es una lista de filas, cada fila tiene la franja y un diccionario de días
            grid = []
            for f in franjas:
                grid.append({'franja': f, 'dias': {d: None for d in dias}})
            
            # Mapa auxiliar para encontrar el índice de la fila (franja) rápidamente
            franja_map = {f.id: i for i, f in enumerate(franjas)}

            # 2. Llenar la grilla con los bloques
            for bloque in planner_data['cursos_asignados']:
                # Verificamos si el bloque empieza en alguna franja de este turno
                if bloque['franja_id_inicio'] in franja_map:
                    f_idx = franja_map[bloque['franja_id_inicio']]
                    dia = bloque['dia']
                    duracion = bloque['duracion_bloques']
                    
                    # Asignamos el bloque en su celda de inicio
                    grid[f_idx]['dias'][dia] = bloque
                    
                    # 3. MARCAR CELDAS OCUPADAS (SKIP)
                    # Si dura más de 1 hora, marcamos las filas de abajo como 'SKIP'
                    # para que el template sepa que NO debe dibujar un <td> ahí.
                    for i in range(1, duracion):
                        if f_idx + i < len(grid):
                            grid[f_idx + i]['dias'][dia] = 'SKIP'
            return grid

        context = {
            'especialidad': especialidad,
            'semestre_cursado': semestre_cursado,
            'grid_manana': build_grid(franjas_manana),
            'grid_tarde': build_grid(franjas_tarde),
            'dias': dias,
            'fecha_generacion': datetime.now()
        }
        
        return render(request, 'reporte_horario_pdf.html', context)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return server_error_response(f"Error generando reporte: {e}")