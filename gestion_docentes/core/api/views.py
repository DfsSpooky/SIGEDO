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
    Semestre, DiaEspecial, Especialidad, FranjaHoraria, Notificacion
)
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from ..utils.responses import success_response, error_response, not_found_response, server_error_response
from ..utils.reports import _generar_datos_reporte_asistencia
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from ..views import remove_accents # Importamos la función de `views` temporalmente
from .serializers import DocenteInfoSerializer, CursoAsistenciaSerializer

# --- VISTAS PARA EL KIOSCO (AHORA EN SU PROPIO ARCHIVO DE API) ---

class TeacherInfoView(APIView):
    """
    API View para obtener la información de un docente y sus cursos del día.
    Reemplaza la función original get_teacher_info con una vista basada en clases de DRF.
    """
    def post(self, request, *args, **kwargs):
        qr_id = request.data.get('qrId')
        if not qr_id:
            return Response({'status': 'error', 'message': 'qrId no proporcionado.'}, status=status.HTTP_400_BAD_REQUEST)

        today = timezone.localtime(timezone.now()).date()

        if today.weekday() in [5, 6]: # Sábado=5, Domingo=6
            return Response({'status': 'weekend_off', 'message': 'El kiosco no está disponible los fines de semana.'})

        try:
            docente = Docente.objects.get(id_qr=qr_id)
        except Docente.DoesNotExist:
            return Response({'status': 'error', 'message': 'QR no válido o docente no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        semestre_activo = Semestre.objects.filter(estado='ACTIVO', fecha_inicio__lte=today, fecha_fin__gte=today).first()
        if not semestre_activo:
            return Response({'status': 'error', 'message': 'No hay un semestre académico activo.'}, status=status.HTTP_400_BAD_REQUEST)

        # Usamos la consulta optimizada con el campo `dia_semana`
        dia_semana_hoy = today.weekday()
        cursos_hoy = Curso.objects.filter(
            docente=docente,
            semestre=semestre_activo,
            dia_semana=dia_semana_hoy
        )

        # Para cada curso del día, nos aseguramos de que exista un registro de asistencia
        # Esto simplifica la lógica y asegura que siempre tengamos un objeto para serializar.
        asistencias = []
        for curso in cursos_hoy:
            asistencia, _ = Asistencia.objects.get_or_create(
                docente=docente,
                curso=curso,
                fecha=today
            )
            asistencias.append(asistencia)

        # Usamos los serializers para construir la respuesta
        docente_serializer = DocenteInfoSerializer(docente, context={'request': request})
        cursos_asistencia_serializer = CursoAsistenciaSerializer(asistencias, many=True)
        is_daily_marked = AsistenciaDiaria.objects.filter(docente=docente, fecha=today).exists()

        response_data = {
            'status': 'success',
            'qrId': qr_id,
            'teacher': docente_serializer.data,
            'isDailyAttendanceMarked': is_daily_marked,
            'courses': cursos_asistencia_serializer.data
        }

        return Response(response_data)


from .serializers import DocenteInfoSerializer, CursoAsistenciaSerializer, MarkAttendanceSerializer, RegistrarAsistenciaRfidSerializer

class MarkAttendanceView(APIView):
    """
    API View para marcar la asistencia de un docente.
    Reemplaza la función mark_attendance_kiosk.
    """
    def post(self, request, *args, **kwargs):
        serializer = MarkAttendanceSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'status': 'error', 'message': 'Datos inválidos.', 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        validated_data = serializer.validated_data
        qr_id = validated_data['qrId']
        action_type = validated_data['actionType']
        photo_base64 = validated_data['photoBase64']

        try:
            docente = Docente.objects.get(id_qr=qr_id)
        except Docente.DoesNotExist:
            return Response({'status': 'error', 'message': 'QR no válido o docente no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        today = timezone.localtime(timezone.now()).date()
        now = timezone.now()

        try:
            format, imgstr = photo_base64.split(';base64,')
            ext = format.split('/')[-1]
            photo_file = ContentFile(base64.b64decode(imgstr), name=f'{docente.username}_{now.timestamp()}.{ext}')
        except:
            return Response({'status': 'error', 'message': 'Formato de photoBase64 inválido.'}, status=status.HTTP_400_BAD_REQUEST)

        if action_type == 'general_entry':
            _, created = AsistenciaDiaria.objects.get_or_create(
                docente=docente,
                fecha=today,
                defaults={'foto_verificacion': photo_file}
            )
            if created:
                return Response({'status': 'success', 'message': 'Entrada general registrada correctamente.'})
            else:
                return Response({'status': 'success', 'message': 'La entrada general ya ha sido marcada hoy.', 'data': {'already_marked': True}})

        elif action_type in ['course_entry', 'course_exit']:
            curso_id = validated_data.get('courseId')
            if not curso_id:
                return Response({'status': 'error', 'message': 'courseId es requerido para esta acción.'}, status=status.HTTP_400_BAD_REQUEST)

            try:
                curso = Curso.objects.get(id=curso_id)
            except Curso.DoesNotExist:
                return Response({'status': 'error', 'message': 'Curso no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

            asistencia, _ = Asistencia.objects.get_or_create(docente=docente, curso=curso, fecha=today)
            response_data = {}

            if action_type == 'course_entry':
                if asistencia.hora_entrada:
                    return Response({'status': 'warning', 'message': 'La entrada para este curso ya fue marcada.'})

                asistencia.hora_entrada = now
                asistencia.foto_entrada = photo_file
                response_data['es_tardanza'] = asistencia.es_tardanza()

                duracion_minima_minutos = (curso.duracion_bloques * 50) - 15
                if duracion_minima_minutos < 15: duracion_minima_minutos = 15
                asistencia.hora_salida_permitida = now + timedelta(minutes=duracion_minima_minutos)
                asistencia.save()

            elif action_type == 'course_exit':
                if not asistencia.hora_entrada:
                    return Response({'status': 'error', 'message': 'Debe marcar la entrada antes de poder marcar la salida.'}, status=status.HTTP_400_BAD_REQUEST)
                if asistencia.hora_salida:
                    return Response({'status': 'warning', 'message': 'La salida para este curso ya fue marcada.'})
                if not asistencia.puede_marcar_salida:
                    return Response({'status': 'error', 'message': 'Aún no puede marcar la salida.'}, status=status.HTTP_400_BAD_REQUEST)

                asistencia.hora_salida = now
                asistencia.foto_salida = photo_file
                asistencia.save()

            return Response({'status': 'success', 'message': 'Asistencia registrada correctamente.', 'data': response_data})

        return Response({'status': 'error', 'message': 'Tipo de acción no válida.'}, status=status.HTTP_400_BAD_REQUEST)


class RegistrarAsistenciaRfidView(APIView):
    """
    API View para registrar la asistencia diaria de un docente mediante RFID.
    Reemplaza la función registrar_asistencia_rfid.
    """
    def post(self, request, *args, **kwargs):
        serializer = RegistrarAsistenciaRfidSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'status': 'error', 'message': 'Datos inválidos.', 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        uid = serializer.validated_data['uid']
        today = timezone.localtime(timezone.now()).date()

        if today.weekday() in [5, 6]:
            return Response({'status': 'weekend_off', 'message': 'El registro de asistencia no está disponible los fines de semana.'})

        try:
            docente = Docente.objects.get(rfid_uid=uid)
        except Docente.DoesNotExist:
            return Response({'status': 'error', 'message': 'Tarjeta RFID no reconocida o no asignada.'}, status=status.HTTP_404_NOT_FOUND)

        asistencia_diaria, created = AsistenciaDiaria.objects.get_or_create(docente=docente, fecha=today)

        teacher_serializer = DocenteInfoSerializer(docente, context={'request': request})

        if created:
            response_data = {
                'status': 'success',
                'message': 'Asistencia registrada correctamente.',
                'teacher': teacher_serializer.data
            }
        else:
            response_data = {
                'status': 'warning',
                'message': f'La asistencia de hoy ya fue registrada a las {asistencia_diaria.hora_entrada.strftime("%H:%M:%S")}.',
                'teacher': teacher_serializer.data
            }

        # Enviar actualización a través de Channels
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            'kiosk_group',
            {'type': 'kiosk.update', 'data': response_data}
        )

        return Response(response_data)

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


from django.contrib.auth.decorators import login_required

@login_required
def notificaciones_json(request):
    """
    API view to get the user's notifications in JSON format.
    """
    notifications = Notificacion.objects.filter(destinatario=request.user).order_by('-fecha_creacion')[:10]
    unread_count = Notificacion.objects.filter(destinatario=request.user, leido=False).count()

    notifications_data = [
        {
            'id': n.id,
            'mensaje': n.mensaje,
            'url': n.url,
            'leido': n.leido,
            'fecha_creacion': n.fecha_creacion.isoformat()
        } for n in notifications
    ]

    return JsonResponse({
        'notifications': notifications_data,
        'unread_count': unread_count
    })

@login_required
def marcar_notificacion_como_leida(request, notificacion_id):
    """
    API view to mark a single notification as read.
    """
    notificacion = get_object_or_404(Notificacion, id=notificacion_id, destinatario=request.user)
    if not notificacion.leido:
        notificacion.leido = True
        notificacion.save()
    return JsonResponse({'status': 'success'})

@login_required
def marcar_todas_como_leidas(request):
    """
    API view to mark all unread notifications as read.
    """
    Notificacion.objects.filter(destinatario=request.user, leido=False).update(leido=True)
    return JsonResponse({'status': 'success'})
