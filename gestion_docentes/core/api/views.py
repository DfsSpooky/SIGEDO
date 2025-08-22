# -*- coding: utf-8 -*-
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import permission_required
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from datetime import time, timedelta, date, datetime
import json
import base64
from django.core.files.base import ContentFile
import random
from collections import defaultdict
from django.db import models
from django.db.models import Q
from django.templatetags.static import static

# Imports relativos al estar en un subdirectorio
from ..models import (
    Docente, Curso, Asistencia, AsistenciaDiaria, ConfiguracionInstitucion,
    Semestre, DiaEspecial, Especialidad, FranjaHoraria
)
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from ..utils.responses import success_response, error_response, not_found_response, server_error_response
from ..utils.reports import _generar_datos_reporte_asistencia
from ..views import remove_accents # Importamos la función de `views` temporalmente

# --- VISTAS PARA EL KIOSCO (AHORA EN SU PROPIO ARCHIVO DE API) ---

@csrf_exempt
def get_teacher_info(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            qr_id = data.get('qrId')
            today = timezone.localtime(timezone.now()).date()

            if today.weekday() in [5, 6]:
                return JsonResponse({'status': 'weekend_off', 'message': 'El kiosco de asistencia no está disponible los fines de semana.'})

            docente = Docente.objects.get(id_qr=qr_id)

            photo_url = request.build_absolute_uri(docente.foto.url) if docente.foto and hasattr(docente.foto, 'url') else request.build_absolute_uri(static('placeholder.png'))

            dia_especial = DiaEspecial.objects.filter(fecha=today).first()
            if dia_especial:
                # ... (la lógica de día especial no cambia)
                pass

            semestre_activo = Semestre.objects.filter(estado='ACTIVO', fecha_inicio__lte=today, fecha_fin__gte=today).first()
            if not semestre_activo:
                return JsonResponse({'status': 'error', 'message': 'No hay un semestre académico activo.'}, status=400)

            is_daily_marked = AsistenciaDiaria.objects.filter(docente=docente, fecha=today).exists()
            dia_actual_str = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'][today.weekday()]

            dia_actual_normalized = remove_accents(dia_actual_str).lower()

            cursos_del_docente = Curso.objects.filter(docente=docente, semestre=semestre_activo)

            cursos_hoy = [
                c for c in cursos_del_docente
                if c.dia and remove_accents(c.dia).lower() == dia_actual_normalized
            ]

            courses_data = []
            for curso in cursos_hoy:
                asistencia_curso = Asistencia.objects.filter(docente=docente, curso=curso, fecha=today).first()

                # La lógica para determinar si se puede marcar la salida ahora está en el modelo.
                can_mark_exit = asistencia_curso.puede_marcar_salida if asistencia_curso else False

                courses_data.append({
                    'id': curso.id,
                    'name': f'{curso.nombre} ({curso.horario_inicio.strftime("%H:%M")} - {curso.horario_fin.strftime("%H:%M")})',
                    'entryMarked': asistencia_curso is not None and asistencia_curso.hora_entrada is not None,
                    'exitMarked': asistencia_curso is not None and asistencia_curso.hora_salida is not None,
                    'canMarkExit': can_mark_exit,
                    'hora_salida_permitida_str': asistencia_curso.hora_salida_permitida.strftime('%H:%M:%S') if asistencia_curso and asistencia_curso.hora_salida_permitida else None,
                })

            response_data = {
                'status': 'success',
                'qrId': qr_id,
                'teacher': {
                    'name': f'{docente.first_name} {docente.last_name}',
                    'dni': docente.dni,
                    'photoUrl': photo_url,
                },
                'isDailyAttendanceMarked': is_daily_marked,
                'courses': courses_data
            }
            return JsonResponse(response_data)

        except Docente.DoesNotExist:
            return not_found_response('QR no válido o docente no encontrado.')
        except Exception as e:
            return server_error_response(str(e))
    return error_response('Método no permitido', status_code=405)


@csrf_exempt
def mark_attendance_kiosk(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            qr_id = data.get('qrId')
            action_type = data.get('actionType')
            photo_base64 = data.get('photoBase64')

            docente = Docente.objects.get(id_qr=qr_id)

            today = timezone.localtime(timezone.now()).date()
            now = timezone.now()

            format, imgstr = photo_base64.split(';base64,')
            ext = format.split('/')[-1]
            photo_file = ContentFile(base64.b64decode(imgstr), name=f'{docente.username}_{now.timestamp()}.{ext}')

            if action_type == 'general_entry':
                asistencia_diaria, created = AsistenciaDiaria.objects.get_or_create(
                    docente=docente,
                    fecha=today,
                    defaults={'foto_verificacion': photo_file}
                )
                if created:
                    return success_response(message='Entrada general registrada correctamente.')
                else:
                    return success_response(message='La entrada general ya ha sido marcada hoy.', data={'already_marked': True})

            elif action_type in ['course_entry', 'course_exit']:
                curso_id = data.get('courseId')
                curso = Curso.objects.get(id=curso_id)
                asistencia, created = Asistencia.objects.get_or_create(docente=docente, curso=curso, fecha=today)

                response_data = {}

                if action_type == 'course_entry' and not asistencia.hora_entrada:
                    asistencia.hora_entrada = now
                    asistencia.foto_entrada = photo_file

                    # Lógica de tardanza (ahora en el modelo)
                    # El método es_tardanza() usa asistencia.hora_entrada que acabamos de asignar.
                    response_data['es_tardanza'] = asistencia.es_tardanza()

                    duracion_minima_minutos = (curso.duracion_bloques * 50) - 15
                    if duracion_minima_minutos < 15: duracion_minima_minutos = 15
                    asistencia.hora_salida_permitida = now + timedelta(minutes=duracion_minima_minutos)
                    asistencia.save()

                elif action_type == 'course_exit' and asistencia.hora_entrada and not asistencia.hora_salida:
                    if asistencia.hora_salida_permitida and now >= asistencia.hora_salida_permitida:
                        asistencia.hora_salida = now
                        asistencia.foto_salida = photo_file
                        asistencia.save()
                    else:
                        return error_response(message="Aún no puede marcar la salida.")

                return success_response(message='Asistencia registrada correctamente.', data=response_data)

        except Exception as e:
            print(f"Error en mark_attendance_kiosk: {e}")
            return server_error_response(str(e))
    return error_response('Método no permitido', status_code=405)


@csrf_exempt
def registrar_asistencia_rfid(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            rfid_uid = data.get('uid')
            today = timezone.localtime(timezone.now()).date()

            if not rfid_uid:
                return error_response('UID de RFID no proporcionado.')

            if today.weekday() in [5, 6]:
                return JsonResponse({'status': 'weekend_off', 'message': 'El registro de asistencia no está disponible los fines de semana.'})

            docente = Docente.objects.get(rfid_uid=rfid_uid)

            photo_url = request.build_absolute_uri(docente.foto.url) if docente.foto and hasattr(docente.foto, 'url') else request.build_absolute_uri(static('placeholder.png'))
            teacher_data = {
                'name': f'{docente.first_name} {docente.last_name}',
                'dni': docente.dni,
                'photoUrl': photo_url,
            }

            if AsistenciaDiaria.objects.filter(docente=docente, fecha=today).exists():
                response_data = {
                    'status': 'warning',
                    'message': f'La asistencia de hoy ya fue registrada a las {AsistenciaDiaria.objects.get(docente=docente, fecha=today).hora_entrada.strftime("%H:%M:%S")}.',
                    'teacher': teacher_data
                }
            else:
                AsistenciaDiaria.objects.create(docente=docente, fecha=today)
                response_data = {
                    'status': 'success',
                    'message': 'Asistencia registrada correctamente.',
                    'teacher': teacher_data
                }

            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                'kiosk_group',
                {
                    'type': 'kiosk.update',
                    'data': response_data
                }
            )

            return JsonResponse(response_data)

        except Docente.DoesNotExist:
            return not_found_response('Tarjeta RFID no reconocida o no asignada.')
        except json.JSONDecodeError:
            return error_response('Datos de la petición en formato incorrecto.')
        except Exception as e:
            print(f"Error inesperado en registrar_asistencia_rfid: {e}")
            return server_error_response('Ocurrió un error interno en el servidor.')

    return error_response('Método no permitido', status_code=405)

# --- VISTAS DE API PARA EL PLANIFICADOR ---

@staff_member_required
@csrf_exempt
def api_asignar_horario(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        curso_id = data.get('curso_id'); franja_id_inicio = data.get('franja_id'); dia = data.get('dia')
        try:
            curso = Curso.objects.get(pk=curso_id); franja_inicio = FranjaHoraria.objects.get(pk=franja_id_inicio)
            docente = curso.docente; semestre = curso.semestre

            todas_las_franjas = list(FranjaHoraria.objects.order_by('hora_inicio'))
            start_index = todas_las_franjas.index(franja_inicio)
            franjas_a_ocupar = todas_las_franjas[start_index : start_index + curso.duracion_bloques]

            for franja in franjas_a_ocupar:
                if (docente.disponibilidad == 'MANANA' and franja.turno != 'MANANA') or (docente.disponibilidad == 'TARDE' and franja.turno != 'TARDE'):
                    return error_response('Conflicto de Disponibilidad del docente.')
                conflicto_docente = Curso.objects.filter(docente=docente, semestre=semestre, dia=dia, horario_inicio=franja.hora_inicio).exclude(pk=curso.id).first()
                if conflicto_docente:
                    return error_response(f'Conflicto: El docente ya dicta "{conflicto_docente.nombre}" en este horario.')

            grupo = curso.especialidad.grupo if curso.especialidad else None
            if grupo:
                q_conflicto = models.Q(especialidad__grupo=grupo, semestre_cursado=curso.semestre_cursado, dia=dia, horario_inicio__in=[f.hora_inicio for f in franjas_a_ocupar])
                if curso.tipo_curso == 'ESPECIALIDAD':
                    conflicto_grupo = Curso.objects.filter(q_conflicto, tipo_curso='GENERAL').first()
                    if conflicto_grupo: return error_response(f'Conflicto de Grupo: El curso general "{conflicto_grupo.nombre}" ya está programado.')
                else: # GENERAL
                    conflicto_grupo = Curso.objects.filter(q_conflicto, tipo_curso='ESPECIALIDAD').first()
                    if conflicto_grupo: return error_response(f'Conflicto de Grupo: El curso "{conflicto_grupo.nombre}" ({conflicto_grupo.especialidad.nombre}) ya está programado.')

            curso.dia = dia; curso.horario_inicio = franja_inicio.hora_inicio; curso.horario_fin = franjas_a_ocupar[-1].hora_fin; curso.save()
            return success_response(message='Curso asignado con éxito.')
        except Exception as e:
            return error_response(str(e))

@staff_member_required
@csrf_exempt
def api_desasignar_horario(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            curso_id = data.get('curso_id')
            curso = Curso.objects.get(pk=curso_id)

            curso.dia = None
            curso.horario_inicio = None
            curso.horario_fin = None
            curso.save()

            return success_response(message='Curso devuelto a la lista de pendientes.')
        except Exception as e:
            return error_response(str(e))

    return error_response('Método no permitido', status_code=405)


@staff_member_required
def api_get_teacher_conflicts(request):
    curso_id = request.GET.get('curso_id')
    if not curso_id:
        return error_response('Falta el ID del curso.')

    try:
        curso_a_asignar = Curso.objects.get(pk=curso_id)
        docente = curso_a_asignar.docente
        semestre = curso_a_asignar.semestre
        grupo_del_curso = curso_a_asignar.especialidad.grupo if curso_a_asignar.especialidad else None
        semestre_cursado_a_asignar = curso_a_asignar.semestre_cursado

        conflictos = []
        todas_las_franjas = list(FranjaHoraria.objects.order_by('hora_inicio'))
        cursos_asignados = Curso.objects.filter(semestre=semestre, dia__isnull=False).exclude(pk=curso_id)

        for curso in cursos_asignados.filter(docente=docente):
            try:
                franja_inicio_obj = next(f for f in todas_las_franjas if f.hora_inicio == curso.horario_inicio)
                start_index = todas_las_franjas.index(franja_inicio_obj)
                for i in range(curso.duracion_bloques):
                    if (start_index + i) < len(todas_las_franjas):
                        franja_ocupada = todas_las_franjas[start_index + i]
                        conflictos.append({'dia': curso.dia, 'franja_id': franja_ocupada.id})
            except (StopIteration, TypeError, AttributeError): continue

        if grupo_del_curso:
            if curso_a_asignar.tipo_curso == 'ESPECIALIDAD':
                cursos_conflicto = cursos_asignados.filter(especialidad__grupo=grupo_del_curso, tipo_curso='GENERAL', semestre_cursado=semestre_cursado_a_asignar)
            else: # Es GENERAL
                cursos_conflicto = cursos_asignados.filter(especialidad__grupo=grupo_del_curso, tipo_curso='ESPECIALIDAD', semestre_cursado=semestre_cursado_a_asignar)

            for curso in cursos_conflicto:
                try:
                    franja_inicio_obj = next(f for f in todas_las_franjas if f.hora_inicio == curso.horario_inicio)
                    start_index = todas_las_franjas.index(franja_inicio_obj)
                    for i in range(curso.duracion_bloques):
                        if (start_index + i) < len(todas_las_franjas):
                            franja_ocupada = todas_las_franjas[start_index + i]
                            conflictos.append({'dia': curso.dia, 'franja_id': franja_ocupada.id})
                except (StopIteration, TypeError, AttributeError): continue

        if docente:
            disponibilidad = docente.disponibilidad
            franjas_no_disponibles = []
            if disponibilidad == 'MANANA':
                franjas_no_disponibles = FranjaHoraria.objects.filter(turno__in=['TARDE', 'NOCHE'])
            elif disponibilidad == 'TARDE':
                franjas_no_disponibles = FranjaHoraria.objects.filter(turno__in=['MANANA', 'NOCHE'])

            dias_semana = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes']
            for franja in franjas_no_disponibles:
                for dia in dias_semana:
                    conflictos.append({'dia': dia, 'franja_id': franja.id})

        return success_response(data={'conflicts': conflictos})

    except Curso.DoesNotExist:
        return not_found_response('Curso no encontrado.')

def _get_planner_data(especialidad_id, semestre_cursado):
    try:
        semestre_activo = Semestre.objects.get(estado='ACTIVO')
    except Semestre.DoesNotExist:
        raise ValueError('No hay un semestre activo configurado.')

    cursos_asignados_json = []
    cursos_no_asignados_generales = []
    cursos_no_asignados_especialidad = []

    if especialidad_id and semestre_cursado:
        especialidad_obj = Especialidad.objects.get(id=especialidad_id)
        grupo_obj = especialidad_obj.grupo

        q_cursos_base = Q(semestre=semestre_activo, semestre_cursado=semestre_cursado)

        q_no_asignados = q_cursos_base & Q(dia__isnull=True)
        cursos_para_filtrar = Curso.objects.filter(q_no_asignados).select_related('docente', 'especialidad')

        for curso in cursos_para_filtrar:
            curso_data = {
                'id': curso.id, 'nombre': curso.nombre, 'semestre_cursado': curso.semestre_cursado,
                'tipo_curso': curso.tipo_curso, 'docente__first_name': curso.docente.first_name if curso.docente else '',
                'docente__last_name': curso.docente.last_name if curso.docente else 'N/A', 'duracion_bloques': curso.duracion_bloques
            }
            if curso.tipo_curso == 'GENERAL' and curso.especialidad.grupo == grupo_obj:
                cursos_no_asignados_generales.append(curso_data)
            elif curso.especialidad_id == int(especialidad_id):
                cursos_no_asignados_especialidad.append(curso_data)

        q_cursos_asignados = q_cursos_base & Q(dia__isnull=False) & (
            Q(especialidad_id=especialidad_id) | Q(especialidad__grupo=grupo_obj, tipo_curso='GENERAL')
        )
        cursos_asignados_qs = Curso.objects.filter(q_cursos_asignados).select_related('docente', 'especialidad', 'especialidad__grupo')
        franjas_map = {franja.hora_inicio: franja.id for franja in FranjaHoraria.objects.all()}
        for curso in cursos_asignados_qs:
            cursos_asignados_json.append({
                'id': curso.id, 'nombre': curso.nombre, 'docente__first_name': curso.docente.first_name if curso.docente else '',
                'docente__last_name': curso.docente.last_name if curso.docente else 'N/A',
                'especialidad__nombre': curso.especialidad.nombre if curso.especialidad else 'N/A',
                'especialidad__id': curso.especialidad.id if curso.especialidad else None,
                'grupo_id': curso.especialidad.grupo.id if curso.especialidad and curso.especialidad.grupo else None,
                'dia': curso.dia, 'horario_inicio': curso.horario_inicio, 'duracion_bloques': curso.duracion_bloques,
                'franja_id_inicio': franjas_map.get(curso.horario_inicio), 'tipo_curso': curso.tipo_curso,
                'semestre_cursado': curso.semestre_cursado,
            })

    return {
        'cursos_no_asignados': {
            'generales': cursos_no_asignados_generales,
            'especialidad': cursos_no_asignados_especialidad,
        },
        'cursos_asignados': cursos_asignados_json
    }

@staff_member_required
@csrf_exempt
def api_auto_asignar(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

    try:
        data = json.loads(request.body)
        especialidad_id = data.get('especialidad_id')
        semestre_cursado = data.get('semestre_cursado')
        semestre_activo = Semestre.objects.filter(estado='ACTIVO').first()
        if not semestre_activo:
            return JsonResponse({'status': 'error', 'message': 'No hay un semestre activo.'}, status=400)

        especialidad_obj = Especialidad.objects.get(id=especialidad_id)
        grupo_obj = especialidad_obj.grupo

        q_cursos_por_asignar = (
            Q(especialidad_id=especialidad_id) |
            Q(tipo_curso='GENERAL', especialidad__grupo=grupo_obj)
        )

        cursos_por_asignar = list(Curso.objects.filter(
            q_cursos_por_asignar,
            semestre=semestre_activo,
            semestre_cursado=semestre_cursado,
            dia__isnull=True
        ).distinct().order_by('-duracion_bloques'))

        franjas_horarias = list(FranjaHoraria.objects.order_by('hora_inicio'))
        dias_semana = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes']

        horarios_ocupados = {}
        cursos_ya_asignados = Curso.objects.filter(semestre=semestre_activo, dia__isnull=False)
        for curso in cursos_ya_asignados:
            try:
                franja_inicio_obj = next(f for f in franjas_horarias if f.hora_inicio == curso.horario_inicio)
                start_index = franjas_horarias.index(franja_inicio_obj)
                for i in range(curso.duracion_bloques):
                    franja_ocupada = franjas_horarias[start_index + i]
                    horarios_ocupados[(curso.dia, franja_ocupada.hora_inicio, curso.docente_id)] = True
                    if curso.especialidad and curso.especialidad.grupo:
                        horarios_ocupados[(curso.dia, franja_ocupada.hora_inicio, curso.especialidad.grupo_id, curso.semestre_cursado)] = True
            except (StopIteration, IndexError):
                continue

        cursos_asignados_count = 0
        for curso in cursos_por_asignar:
            docente = curso.docente
            grupo = curso.especialidad.grupo if curso.especialidad else None
            asignado = False
            for dia in dias_semana:
                for i, franja_inicio in enumerate(franjas_horarias):
                    if i + curso.duracion_bloques > len(franjas_horarias): continue

                    bloque_valido = True
                    franjas_del_curso = franjas_horarias[i : i + curso.duracion_bloques]

                    for franja in franjas_del_curso:
                        if (docente.disponibilidad == 'MANANA' and franja.turno != 'MANANA') or \
                           (docente.disponibilidad == 'TARDE' and franja.turno != 'TARDE'):
                            bloque_valido = False; break
                        if horarios_ocupados.get((dia, franja.hora_inicio, docente.id)):
                            bloque_valido = False; break
                        if grupo and horarios_ocupados.get((dia, franja.hora_inicio, grupo.id, curso.semestre_cursado)):
                             bloque_valido = False; break

                    if bloque_valido:
                        curso.dia = dia
                        curso.horario_inicio = franja_inicio.hora_inicio
                        curso.horario_fin = franjas_del_curso[-1].hora_fin
                        curso.save()

                        for franja in franjas_del_curso:
                            horarios_ocupados[(dia, franja.hora_inicio, docente.id)] = True
                            if grupo:
                                horarios_ocupados[(dia, franja.hora_inicio, grupo.id, curso.semestre_cursado)] = True

                        cursos_asignados_count += 1
                        asignado = True
                        break
                if asignado: break

        message = f"Proceso finalizado. Se asignaron {cursos_asignados_count} de {len(cursos_por_asignar) + cursos_asignados_count} cursos."

        planner_data = _get_planner_data(especialidad_id, semestre_cursado)

        return success_response(
            data={'plannerData': planner_data},
            message=message
        )

    except Exception as e:
        return error_response(str(e), status_code=500)

@staff_member_required
@csrf_exempt
def generar_horario_automatico(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

    try:
        semestre_activo = Semestre.objects.filter(estado='ACTIVO').first()
        if not semestre_activo:
            return JsonResponse({'status': 'error', 'message': 'No hay un semestre activo configurado para la planificación.'}, status=400)

        Curso.objects.filter(semestre=semestre_activo).update(dia=None, horario_inicio=None, horario_fin=None)

        cursos_por_asignar = list(Curso.objects.filter(semestre=semestre_activo, docente__isnull=False)
                                  .select_related('docente', 'especialidad__grupo')
                                  .order_by('-duracion_bloques'))

        total_cursos_a_asignar = len(cursos_por_asignar)
        cursos_sin_docente = Curso.objects.filter(semestre=semestre_activo, docente__isnull=True).count()

        franjas_horarias = list(FranjaHoraria.objects.order_by('hora_inicio'))
        dias_semana = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes']
        random.shuffle(dias_semana)

        horarios_ocupados = {
            'docente': {},
            'grupo': {}
        }

        cursos_asignados_count = 0
        cursos_no_asignados = []

        for curso in cursos_por_asignar:
            docente = curso.docente
            grupo = curso.especialidad.grupo if curso.especialidad and curso.especialidad.grupo else None
            semestre_cursado = curso.semestre_cursado

            asignado = False
            random.shuffle(dias_semana)
            for dia in dias_semana:
                for i in range(len(franjas_horarias) - curso.duracion_bloques + 1):
                    franja_inicio = franjas_horarias[i]
                    franjas_del_curso = franjas_horarias[i : i + curso.duracion_bloques]

                    bloque_valido = True
                    for franja in franjas_del_curso:
                        if (docente.disponibilidad == 'MANANA' and franja.turno != 'MANANA') or \
                           (docente.disponibilidad == 'TARDE' and franja.turno != 'TARDE'):
                            bloque_valido = False
                            break
                        if horarios_ocupados['docente'].get((docente.id, dia, franja.id)):
                            bloque_valido = False
                            break
                        if grupo and semestre_cursado:
                            if horarios_ocupados['grupo'].get((grupo.id, semestre_cursado, dia, franja.id)):
                                bloque_valido = False
                                break

                    if bloque_valido:
                        curso.dia = dia
                        curso.horario_inicio = franja_inicio.hora_inicio
                        curso.horario_fin = franjas_del_curso[-1].hora_fin

                        for franja in franjas_del_curso:
                            horarios_ocupados['docente'][(docente.id, dia, franja.id)] = True
                            if grupo and semestre_cursado:
                                horarios_ocupados['grupo'][(grupo.id, semestre_cursado, dia, franja.id)] = True

                        asignado = True
                        break
                if asignado:
                    break

            if asignado:
                cursos_asignados_count += 1
            else:
                cursos_no_asignados.append(curso.nombre)

        for curso in cursos_por_asignar:
            if curso.dia:
                curso.save()

        message = f"Proceso completado. Se asignaron exitosamente {cursos_asignados_count} de {total_cursos_a_asignar} cursos."
        if cursos_no_asignados:
            message += f" No se pudieron asignar {len(cursos_no_asignados)} cursos por falta de espacio o conflictos."
        if cursos_sin_docente > 0:
            message += f" Además, hay {cursos_sin_docente} cursos sin docente que no se pueden planificar."

        return success_response(message=message)

    except Exception as e:
        print(f"Error en generar_horario_automatico: {e}")
        return server_error_response(f'Ocurrió un error inesperado: {e}')

@staff_member_required
def api_get_cursos_no_asignados(request):
    try:
        especialidad_id = request.GET.get('especialidad_id')
        semestre_cursado = request.GET.get('semestre_cursado')
        planner_data = _get_planner_data(especialidad_id, semestre_cursado)
        return success_response(data=planner_data)
    except ValueError as e:
        return not_found_response(str(e))

@staff_member_required
def api_get_report_chart_data(request):
    report_data, _ = _generar_datos_reporte_asistencia(request.GET)

    daily_stats = defaultdict(lambda: {'Presente': 0, 'Falta': 0, 'Tardanza': 0, 'Justificado': 0})

    for record in report_data:
        if record['estado'] in ['Presente', 'Falta', 'Tardanza', 'Justificado']:
            fecha_str = record['fecha'].strftime('%d/%m')
            daily_stats[fecha_str][record['estado']] += 1

    sorted_labels = sorted(daily_stats.keys(), key=lambda d: timezone.datetime.strptime(d, '%d/%m').date())

    bar_chart_data = {
        'labels': sorted_labels,
        'presentes': [daily_stats[label]['Presente'] for label in sorted_labels],
        'faltas': [daily_stats[label]['Falta'] for label in sorted_labels],
        'tardanzas': [daily_stats[label]['Tardanza'] for label in sorted_labels],
    }

    total_presentes = sum(bar_chart_data['presentes'])
    total_faltas = sum(bar_chart_data['faltas'])
    total_tardanzas = sum(bar_chart_data['tardanzas'])

    pie_chart_data = {
        'presentes': total_presentes,
        'faltas': total_faltas,
        'tardanzas': total_tardanzas,
    }

    return success_response(data={'bar_chart': bar_chart_data, 'pie_chart': pie_chart_data})


@staff_member_required
def detalle_asistencia_docente_ajax(request, docente_id):
    try:
        docente = Docente.objects.get(pk=docente_id)

        fecha_inicio_str = request.GET.get('fecha_inicio')
        fecha_fin_str = request.GET.get('fecha_fin')

        try:
            fecha_inicio = timezone.datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date() if fecha_inicio_str else date.today() - timedelta(days=30)
            fecha_fin = timezone.datetime.strptime(fecha_fin_str, '%Y-%m-%d').date() if fecha_fin_str else date.today()
        except (ValueError, TypeError):
            fecha_fin = date.today()
            fecha_inicio = fecha_fin - timedelta(days=30)

        asistencias_cursos = Asistencia.objects.filter(
            docente=docente,
            curso__isnull=False,
            fecha__range=[fecha_inicio, fecha_fin]
        ).select_related('curso').order_by('-fecha', '-hora_entrada')

        data = {
            'docente': {
                'nombre_completo': f'{docente.first_name} {docente.last_name}',
                'dni': docente.dni,
                'foto_url': docente.foto.url if docente.foto and hasattr(docente.foto, 'url') else static('placeholder.png'),
            },
            'asistencias_cursos': [
                {
                    'curso': asis.curso.nombre if asis.curso else 'N/A',
                    'fecha': asis.fecha.strftime('%d/%m/%Y'),
                    'hora_entrada': asis.hora_entrada.strftime('%H:%M') if asis.hora_entrada else '-',
                    'hora_salida': asis.hora_salida.strftime('%H:%M') if asis.hora_salida else '-',
                    'foto_entrada_url': asis.foto_entrada.url if asis.foto_entrada else None,
                    'foto_salida_url': asis.foto_salida.url if asis.foto_salida else None,
                }
                for asis in asistencias_cursos
            ]
        }
        return success_response(data=data)
    except Docente.DoesNotExist:
        return not_found_response('Docente no encontrado')
    except Exception as e:
        return server_error_response(f'Error inesperado: {str(e)}')
