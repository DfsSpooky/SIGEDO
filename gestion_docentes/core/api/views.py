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
    Semestre, DiaEspecial, Especialidad, FranjaHoraria, Notificacion, BloqueHorario
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

                # Lógica corregida para usar la duración del bloque específico de ese día
                bloque_del_dia = BloqueHorario.objects.filter(curso=curso, dia_semana=today.weekday()).first()
                duracion_bloques_hoy = bloque_del_dia.duracion_bloques if bloque_del_dia else 2 # Default a 2 si no se encuentra

                duracion_minima_minutos = (duracion_bloques_hoy * 50) - 15
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
                'message': f'La asistencia de hoy ya fue registrada a las {asistencia_diaria.hora_entrada.strftime("%I:%M:%S %p")}.',
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
    if request.method != 'POST':
        return error_response('Método no permitido', status_code=405)

    try:
        data = json.loads(request.body)
        curso_id = data.get('curso_id')
        franja_id = data.get('franja_id')
        dia = data.get('dia')
        # La duración del bloque ahora debe ser enviada desde el frontend.
        # Asumimos un valor por defecto si no se envía, para compatibilidad temporal.
        duracion = data.get('duracion', 2)

        curso = Curso.objects.get(pk=curso_id)
        franja_inicio = FranjaHoraria.objects.get(pk=franja_id)

        # Validar que no se excedan las horas semanales del curso
        horas_asignadas = curso.bloques_horario.aggregate(total=models.Sum('duracion_bloques'))['total'] or 0
        if horas_asignadas + duracion > curso.horas_academicas_semanales:
            return error_response(f'No se puede asignar: excede las horas semanales del curso ({curso.horas_academicas_semanales}).')

        # Aquí iría una validación de conflictos más robusta similar a la del generador automático
        # Por simplicidad, la omitimos en la asignación manual, pero en un sistema real sería necesaria.

        BloqueHorario.objects.create(
            curso=curso,
            dia=dia,
            franja_inicio=franja_inicio,
            duracion_bloques=duracion
        )
        return success_response(message='Bloque asignado con éxito.')

    except Curso.DoesNotExist:
        return not_found_response('Curso no encontrado.')
    except FranjaHoraria.DoesNotExist:
        return not_found_response('Franja horaria no encontrada.')
    except Exception as e:
        return server_error_response(f'Error inesperado: {e}')

@staff_member_required
@csrf_exempt
def api_desasignar_horario(request):
    if request.method != 'POST':
        return error_response('Método no permitido', status_code=405)
    try:
        data = json.loads(request.body)
        bloque_id = data.get('bloque_id') # El frontend ahora debe enviar el ID del bloque
        if not bloque_id:
            return error_response('Falta el ID del bloque de horario.')

        bloque = BloqueHorario.objects.get(pk=bloque_id)
        bloque.delete()
        return success_response(message='Bloque de horario eliminado.')
    except BloqueHorario.DoesNotExist:
        return not_found_response('El bloque de horario especificado no existe.')
    except Exception as e:
        return server_error_response(str(e))

@staff_member_required
@csrf_exempt
def api_mover_bloque(request):
    if request.method != 'POST':
        return error_response('Método no permitido', status_code=405)

    try:
        data = json.loads(request.body)
        bloque_id = data.get('bloque_id')
        nuevo_dia = data.get('dia')
        nueva_franja_id = data.get('franja_id')

        bloque = BloqueHorario.objects.select_related('curso__docente', 'curso__especialidad__grupo').get(pk=bloque_id)
        nueva_franja_inicio = FranjaHoraria.objects.get(pk=nueva_franja_id)

        # Aquí debería ir una validación de conflictos completa, similar a la de generar_horario_automatico
        # Por ahora, se omite por brevedad, pero en un sistema real sería crucial.

        bloque.dia = nuevo_dia
        bloque.franja_inicio = nueva_franja_inicio
        bloque.save()

        return success_response(message="Bloque movido con éxito.")

    except BloqueHorario.DoesNotExist:
        return not_found_response('El bloque a mover no existe.')
    except FranjaHoraria.DoesNotExist:
        return not_found_response('La nueva franja horaria no existe.')
    except Exception as e:
        return server_error_response(f'Error inesperado: {e}')

@staff_member_required
@csrf_exempt
def api_ajustar_duracion(request):
    if request.method != 'POST':
        return error_response('Método no permitido', status_code=405)

    try:
        data = json.loads(request.body)
        bloque_id = data.get('bloque_id')
        accion = data.get('accion') # 'increase' or 'decrease'

        bloque = BloqueHorario.objects.select_related('curso').get(pk=bloque_id)

        nueva_duracion = bloque.duracion_bloques
        if accion == 'increase':
            nueva_duracion += 1
        elif accion == 'decrease':
            nueva_duracion -= 1
        else:
            return error_response('Acción no válida.', status_code=400)

        if nueva_duracion < 1:
            return error_response('La duración no puede ser menor a 1 bloque.', status_code=400)

        # Validar que no se excedan las horas semanales del curso
        horas_asignadas = bloque.curso.bloques_horario.exclude(pk=bloque_id).aggregate(total=models.Sum('duracion_bloques'))['total'] or 0
        if horas_asignadas + nueva_duracion > bloque.curso.horas_academicas_semanales:
            return error_response('La duración excede las horas semanales del curso.', status_code=400)

        # Aquí también se necesitaría una validación de conflictos para la nueva duración

        bloque.duracion_bloques = nueva_duracion
        bloque.save()

        return success_response(message="Duración del bloque actualizada.")

    except BloqueHorario.DoesNotExist:
        return not_found_response('El bloque de horario no existe.')
    except Exception as e:
        return server_error_response(f'Error inesperado: {e}')

@staff_member_required
def api_get_teacher_conflicts(request):
    curso_id = request.GET.get('curso_id')
    if not curso_id:
        return error_response('Falta el ID del curso.')

    try:
        curso_a_asignar = Curso.objects.select_related('docente', 'especialidad__grupo').get(pk=curso_id)
        docente = curso_a_asignar.docente
        semestre = curso_a_asignar.semestre
        grupo_del_curso = curso_a_asignar.especialidad.grupo if curso_a_asignar.especialidad else None
        semestre_cursado_a_asignar = curso_a_asignar.semestre_cursado

        # Usamos un diccionario para almacenar la razón del conflicto, evitando duplicados.
        conflictos = {}
        todas_las_franjas = list(FranjaHoraria.objects.order_by('hora_inicio'))
        mapa_franjas = {franja.id: franja for franja in todas_las_franjas}

        bloques_asignados = BloqueHorario.objects.filter(curso__semestre=semestre).select_related('curso__docente', 'curso__especialidad__grupo', 'curso__especialidad')

        # 1. Conflictos del propio docente
        if docente:
            bloques_docente = bloques_asignados.filter(curso__docente=docente).exclude(curso=curso_a_asignar)
            for bloque in bloques_docente:
                franja_idx = todas_las_franjas.index(bloque.franja_inicio)
                for i in range(bloque.duracion_bloques):
                    franja_actual = todas_las_franjas[franja_idx + i]
                    key = (bloque.dia, franja_actual.id)
                    if key not in conflictos:
                        conflictos[key] = f"Docente Ocupado: {bloque.curso.nombre}"

        # 2. Conflictos del grupo de estudiantes
        if grupo_del_curso and semestre_cursado_a_asignar:
            q_grupo = Q(curso__especialidad__grupo=grupo_del_curso, curso__semestre_cursado=semestre_cursado_a_asignar)
            bloques_grupo = bloques_asignados.filter(q_grupo).exclude(curso=curso_a_asignar)
            for bloque in bloques_grupo:
                franja_idx = todas_las_franjas.index(bloque.franja_inicio)
                for i in range(bloque.duracion_bloques):
                    franja_actual = todas_las_franjas[franja_idx + i]
                    key = (bloque.dia, franja_actual.id)
                    if key not in conflictos:
                        conflictos[key] = f"Grupo Ocupado: {bloque.curso.nombre}"

        # 3. Conflictos de disponibilidad del docente
        if docente and docente.disponibilidad != 'COMPLETO':
            turno_no_disponible = 'TARDE' if docente.disponibilidad == 'MANANA' else 'MANANA'
            franjas_no_disponibles_ids = set(FranjaHoraria.objects.filter(turno=turno_no_disponible).values_list('id', flat=True))
            if franjas_no_disponibles_ids:
                dias_semana = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes']
                for dia in dias_semana:
                    for franja_id in franjas_no_disponibles_ids:
                        key = (dia, franja_id)
                        if key not in conflictos:
                            conflictos[key] = f"No disponible en turno de {turno_no_disponible.title()}"

        # Convertir el diccionario de conflictos al formato de lista esperado por el frontend
        response_data = [{'dia': k[0], 'franja_id': k[1], 'razon': v} for k, v in conflictos.items()]

        return success_response(data={'conflicts': response_data})

    except Curso.DoesNotExist:
        return not_found_response('Curso no encontrado.')
    except Exception as e:
        return server_error_response(f"Error inesperado: {e}")

def _get_planner_data(especialidad_id, semestre_cursado):
    try:
        semestre_activo = Semestre.objects.get(estado='ACTIVO')
    except Semestre.DoesNotExist:
        raise ValueError('No hay un semestre activo configurado.')

    cursos_asignados_json = []
    cursos_pendientes_generales = []
    cursos_pendientes_especialidad = []

    if especialidad_id and semestre_cursado:
        especialidad_obj = Especialidad.objects.get(id=especialidad_id)
        grupo_obj = especialidad_obj.grupo

        q_cursos_del_plan = Q(semestre=semestre_activo, semestre_cursado=semestre_cursado) & (
            Q(especialidad_id=especialidad_id) | Q(especialidad__grupo=grupo_obj, tipo_curso='GENERAL')
        )

        cursos_del_plan = Curso.objects.filter(q_cursos_del_plan).annotate(
            horas_asignadas=models.Sum('bloques_horario__duracion_bloques', default=0)
        ).select_related('docente', 'especialidad').prefetch_related('bloques_horario')

        for curso in cursos_del_plan:
            # Lógica para cursos pendientes
            if curso.horas_asignadas < curso.horas_academicas_semanales:
                curso_data = {
                    'id': curso.id,
                    'nombre': curso.nombre,
                    'docente_nombre': f"{curso.docente.first_name} {curso.docente.last_name}" if curso.docente else 'N/A',
                    'horas_pendientes': curso.horas_academicas_semanales - curso.horas_asignadas,
                    'horas_totales': curso.horas_academicas_semanales,
                    'tipo_curso': curso.tipo_curso,
                    'semestre_cursado': curso.semestre_cursado,
                    'excepcion_horario': curso.excepcion_horario,
                }
                if curso.tipo_curso == 'GENERAL':
                    cursos_pendientes_generales.append(curso_data)
                else:
                    cursos_pendientes_especialidad.append(curso_data)

            # Lógica para bloques ya asignados (que se mostrarán en el horario)
            for bloque in curso.bloques_horario.all():
                cursos_asignados_json.append({
                    'bloque_id': bloque.id,
                    'curso_id': curso.id,
                    'nombre': curso.nombre,
                    'docente_nombre': f"{curso.docente.first_name} {curso.docente.last_name}" if curso.docente else 'N/A',
                    'dia': bloque.dia,
                    'franja_id_inicio': bloque.franja_inicio.id,
                    'duracion_bloques': bloque.duracion_bloques,
                    'tipo_curso': curso.tipo_curso,
                    'semestre_cursado': curso.semestre_cursado,
                    'excepcion_horario': curso.excepcion_horario,
                })

    return {
        'cursos_pendientes': {
            'generales': cursos_pendientes_generales,
            'especialidad': cursos_pendientes_especialidad,
        },
        'cursos_asignados': cursos_asignados_json
    }

@staff_member_required
@csrf_exempt
def api_auto_asignar(request):
    if request.method != 'POST':
        return error_response('Método no permitido', status_code=405)

    try:
        data = json.loads(request.body)
        especialidad_id = data.get('especialidad_id')
        semestre_cursado_num = data.get('semestre_cursado')

        semestre_activo = Semestre.objects.filter(estado='ACTIVO').first()
        if not semestre_activo:
            return error_response('No hay un semestre activo.', status_code=400)

        # 1. Identificar los cursos con horas pendientes para esta especialidad/semestre
        especialidad_obj = Especialidad.objects.get(id=especialidad_id)
        grupo_obj = especialidad_obj.grupo
        q_cursos_del_plan = Q(semestre=semestre_activo, semestre_cursado=semestre_cursado_num) & (
            Q(especialidad_id=especialidad_id) | Q(especialidad__grupo=grupo_obj, tipo_curso='GENERAL')
        )

        cursos_a_planificar = Curso.objects.filter(q_cursos_del_plan).annotate(
            horas_asignadas=models.Sum('bloques_horario__duracion_bloques', default=0)
        ).select_related('docente', 'especialidad__grupo')

        cursos_con_pendientes = [
            c for c in cursos_a_planificar if c.horas_asignadas < c.horas_academicas_semanales
        ]

        if not cursos_con_pendientes:
            planner_data = _get_planner_data(especialidad_id, semestre_cursado_num)
            return success_response(
                data={'plannerData': planner_data},
                message="Todos los cursos para esta selección ya están completamente asignados."
            )

        # 2. Construir el mapa de horarios ocupados de TODO el semestre
        franjas_horarias = list(FranjaHoraria.objects.order_by('hora_inicio'))
        horarios_ocupados = defaultdict(set)

        todos_los_bloques = BloqueHorario.objects.filter(curso__semestre=semestre_activo).select_related('curso__docente', 'curso__especialidad__grupo')
        for bloque in todos_los_bloques:
            try:
                franja_idx = franjas_horarias.index(bloque.franja_inicio)
                for i in range(bloque.duracion_bloques):
                    franja_ocupada = franjas_horarias[franja_idx + i]
                    if bloque.curso.docente:
                        horarios_ocupados['docente'].add((bloque.curso.docente.id, bloque.dia, franja_ocupada.id))
                    if bloque.curso.especialidad and bloque.curso.especialidad.grupo:
                        horarios_ocupados['grupo'].add((bloque.curso.especialidad.grupo.id, bloque.curso.semestre_cursado, bloque.dia, franja_ocupada.id))
            except ValueError:
                continue # La franja de inicio del bloque no está en la lista (caso raro)


        # 3. Lógica de asignación (similar a la global, pero no destructiva)
        cursos_asignados_ahora = 0
        dias_semana = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes']
        posibles_duraciones = [3, 2, 1]

        for curso in cursos_con_pendientes:
            horas_pendientes = curso.horas_academicas_semanales - curso.horas_asignadas
            docente = curso.docente
            grupo = curso.especialidad.grupo if curso.especialidad and curso.especialidad.grupo else None
            semestre_cursado = curso.semestre_cursado
            random.shuffle(dias_semana)

            while horas_pendientes > 0:
                bloque_asignado_en_iteracion = False
                duracion_a_intentar = next((d for d in posibles_duraciones if d <= horas_pendientes), None)
                if not duracion_a_intentar: break

                for dia in dias_semana:
                    for i in range(len(franjas_horarias) - duracion_a_intentar + 1):
                        franja_inicio = franjas_horarias[i]
                        franjas_del_bloque = franjas_horarias[i : i + duracion_a_intentar]
                        bloque_valido = True
                        for franja in franjas_del_bloque:
                            if (docente.disponibilidad == 'MANANA' and franja.turno != 'MANANA') or \
                               (docente.disponibilidad == 'TARDE' and franja.turno != 'TARDE'):
                                bloque_valido = False; break
                            if (docente.id, dia, franja.id) in horarios_ocupados['docente']:
                                bloque_valido = False; break
                            if grupo and semestre_cursado:
                                if (grupo.id, semestre_cursado, dia, franja.id) in horarios_ocupados['grupo']:
                                    bloque_valido = False; break
                        if not bloque_valido: continue

                        BloqueHorario.objects.create(curso=curso, dia=dia, franja_inicio=franja_inicio, duracion_bloques=duracion_a_intentar)
                        for franja in franjas_del_bloque:
                            horarios_ocupados['docente'].add((docente.id, dia, franja.id))
                            if grupo and semestre_cursado:
                                horarios_ocupados['grupo'].add((grupo.id, semestre_cursado, dia, franja.id))
                        horas_pendientes -= duracion_a_intentar
                        bloque_asignado_en_iteracion = True
                        break
                    if bloque_asignado_en_iteracion: break
                if not bloque_asignado_en_iteracion: break

            if horas_pendientes == 0:
                cursos_asignados_ahora += 1

        message = f"Proceso finalizado. Se completó la asignación para {cursos_asignados_ahora} cursos."
        planner_data = _get_planner_data(especialidad_id, semestre_cursado_num)
        return success_response(data={'plannerData': planner_data}, message=message)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return server_error_response(f'Ocurrió un error inesperado: {e}')

@staff_member_required
@csrf_exempt
def generar_horario_automatico(request):
    if request.method != 'POST':
        return error_response('Método no permitido', status_code=405)

    try:
        semestre_activo = Semestre.objects.filter(estado='ACTIVO').first()
        if not semestre_activo:
            return error_response('No hay un semestre activo configurado.', status_code=400)

        # 1. Reset: Borrar todos los bloques de horario existentes para el semestre activo
        BloqueHorario.objects.filter(curso__semestre=semestre_activo).delete()

        # 2. Obtener recursos y restricciones
        cursos_a_asignar = list(
            Curso.objects.filter(semestre=semestre_activo, docente__isnull=False)
            .select_related('docente', 'especialidad__grupo')
            .order_by('-horas_academicas_semanales') # Priorizar cursos con más horas
        )
        franjas_horarias = list(FranjaHoraria.objects.order_by('hora_inicio'))
        dias_semana = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes']

        # Estructura para mantener los horarios ocupados y evitar consultas a la BD en el bucle
        horarios_ocupados = defaultdict(set) # (tipo, id, dia, franja_id) -> True

        cursos_completados = 0
        cursos_no_asignados_completamente = []

        # 3. Iterar y asignar bloques para cada curso
        for curso in cursos_a_asignar:
            horas_pendientes = curso.horas_academicas_semanales
            docente = curso.docente
            grupo = curso.especialidad.grupo if curso.especialidad and curso.especialidad.grupo else None
            semestre_cursado = curso.semestre_cursado

            # Estrategia de división de bloques: intentar con bloques más grandes primero
            posibles_duraciones = [3, 2, 1]

            random.shuffle(dias_semana) # Aleatorizar el día de inicio para variar los horarios

            while horas_pendientes > 0:
                bloque_asignado_en_iteracion = False

                # Intentar asignar un bloque de la mayor duración posible
                duracion_a_intentar = next((d for d in posibles_duraciones if d <= horas_pendientes), None)
                if not duracion_a_intentar:
                    break # No se pueden asignar las horas restantes con las duraciones posibles

                for dia in dias_semana:
                    for i in range(len(franjas_horarias) - duracion_a_intentar + 1):
                        franja_inicio = franjas_horarias[i]
                        franjas_del_bloque = franjas_horarias[i : i + duracion_a_intentar]

                        # --- Verificación de conflictos ---
                        bloque_valido = True
                        for franja in franjas_del_bloque:
                            # Conflicto de disponibilidad del docente (Mañana/Tarde)
                            if (docente.disponibilidad == 'MANANA' and franja.turno != 'MANANA') or \
                               (docente.disponibilidad == 'TARDE' and franja.turno != 'TARDE'):
                                bloque_valido = False; break

                            # Conflicto de horario del docente
                            if (docente.id, dia, franja.id) in horarios_ocupados['docente']:
                                bloque_valido = False; break

                            # Conflicto de horario del grupo/semestre
                            if grupo and semestre_cursado:
                                if (grupo.id, semestre_cursado, dia, franja.id) in horarios_ocupados['grupo']:
                                    bloque_valido = False; break

                        if not bloque_valido:
                            continue

                        # --- Si el bloque es válido, crearlo y actualizar estructuras ---
                        BloqueHorario.objects.create(
                            curso=curso,
                            dia=dia,
                            franja_inicio=franja_inicio,
                            duracion_bloques=duracion_a_intentar
                        )

                        # Marcar las franjas como ocupadas
                        for franja in franjas_del_bloque:
                            horarios_ocupados['docente'].add((docente.id, dia, franja.id))
                            if grupo and semestre_cursado:
                                horarios_ocupados['grupo'].add((grupo.id, semestre_cursado, dia, franja.id))

                        horas_pendientes -= duracion_a_intentar
                        bloque_asignado_en_iteracion = True
                        break # Salir del bucle de franjas
                    if bloque_asignado_en_iteracion:
                        break # Salir del bucle de dias

                if not bloque_asignado_en_iteracion:
                    # Si no se pudo asignar ningún bloque en una iteración completa, romper para evitar bucles infinitos
                    break

            if horas_pendientes == 0:
                cursos_completados += 1
            else:
                cursos_no_asignados_completamente.append(f"{curso.nombre} ({horas_pendientes}h pendientes)")

        # 4. Construir el mensaje de respuesta
        total_cursos = len(cursos_a_asignar)
        message = f"Proceso completado. Se asignaron completamente {cursos_completados} de {total_cursos} cursos planificables."
        if cursos_no_asignados_completamente:
            message += f" Cursos no asignados completamente: {', '.join(cursos_no_asignados_completamente)}."

        cursos_sin_docente = Curso.objects.filter(semestre=semestre_activo, docente__isnull=True).count()
        if cursos_sin_docente > 0:
            message += f" Hay {cursos_sin_docente} cursos sin docente asignado que no pudieron ser planificados."

        return success_response(message=message)

    except Exception as e:
        import traceback
        traceback.print_exc()
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
                    'hora_entrada': asis.hora_entrada.strftime('%I:%M %p') if asis.hora_entrada else '-',
                    'hora_salida': asis.hora_salida.strftime('%I:%M %p') if asis.hora_salida else '-',
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
