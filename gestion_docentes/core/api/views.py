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
    Semestre, DiaEspecial, Especialidad, FranjaHoraria, Notificacion, BloqueCurso
)
from django.db.models import Sum
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
        DIAS_MAP = {0: 'Lunes', 1: 'Martes', 2: 'Miércoles', 3: 'Jueves', 4: 'Viernes', 5: 'Sábado', 6: 'Domingo'}
        dia_de_hoy_str = DIAS_MAP.get(today.weekday())

        if dia_de_hoy_str in ['Sábado', 'Domingo']:
            return Response({'status': 'weekend_off', 'message': 'El kiosco no está disponible los fines de semana.'})

        try:
            docente = Docente.objects.get(id_qr=qr_id)
        except Docente.DoesNotExist:
            return Response({'status': 'error', 'message': 'QR no válido o docente no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        semestre_activo = Semestre.objects.filter(estado='ACTIVO', fecha_inicio__lte=today, fecha_fin__gte=today).first()
        if not semestre_activo:
            return Response({'status': 'error', 'message': 'No hay un semestre académico activo.'}, status=status.HTTP_400_BAD_REQUEST)

        # La consulta ahora se basa en los BloqueCurso para el día de hoy
        bloques_hoy = BloqueCurso.objects.filter(
            curso__docente=docente,
            curso__semestre=semestre_activo,
            dia=dia_de_hoy_str
        ).select_related('curso')

        cursos_hoy_ids = set(b.curso.id for b in bloques_hoy)
        cursos_hoy = Curso.objects.filter(id__in=cursos_hoy_ids)

        asistencias = []
        for curso in cursos_hoy:
            asistencia, _ = Asistencia.objects.get_or_create(
                docente=docente,
                curso=curso,
                fecha=today
            )
            asistencias.append(asistencia)

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

                # TODO: La lógica de duración mínima debe ser más inteligente.
                # Si un curso tiene múltiples bloques, ¿cuál usamos?
                # Por ahora, usamos el primer bloque del día para ese curso.
                DIAS_MAP = {0: 'Lunes', 1: 'Martes', 2: 'Miércoles', 3: 'Jueves', 4: 'Viernes'}
                dia_de_hoy_str = DIAS_MAP.get(today.weekday())
                bloque_del_dia = BloqueCurso.objects.filter(curso=curso, dia=dia_de_hoy_str).order_by('hora_inicio').first()

                duracion_bloques_actual = bloque_del_dia.duracion_bloques if bloque_del_dia else 2 # Default a 2 si no se encuentra

                duracion_minima_minutos = (duracion_bloques_actual * 50) - 15
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
    if request.method != 'POST':
        return error_response('Método no permitido', status_code=405)

    try:
        data = json.loads(request.body)
        curso_id = data.get('curso_id')
        franja_id_inicio = data.get('franja_id')
        dia = data.get('dia')
        duracion_bloques = int(data.get('duracion_bloques', 1))

        curso = Curso.objects.get(pk=curso_id)
        franja_inicio = FranjaHoraria.objects.get(pk=franja_id_inicio)
        docente = curso.docente
        semestre = curso.semestre

        # Verificar que el docente existe
        if not docente:
            return error_response('El curso no tiene un docente asignado.')

        # Verificar que la asignación no exceda las horas semanales del curso
        horas_ya_asignadas = curso.bloques.aggregate(total=Sum('duracion_bloques'))['total'] or 0
        if horas_ya_asignadas + duracion_bloques > curso.horas_semanales:
            return error_response(f'El curso ya tiene {horas_ya_asignadas} de {curso.horas_semanales} horas asignadas. Este bloque excede el total.')

        # Lógica de comprobación de conflictos
        todas_las_franjas = list(FranjaHoraria.objects.order_by('hora_inicio'))
        start_index = todas_las_franjas.index(franja_inicio)
        franjas_a_ocupar = todas_las_franjas[start_index : start_index + duracion_bloques]

        if len(franjas_a_ocupar) < duracion_bloques:
            return error_response('La duración del bloque excede las franjas horarias disponibles para el día.')

        horas_a_ocupar = [f.hora_inicio for f in franjas_a_ocupar]

        # Conflicto de disponibilidad y de horario del docente
        for franja in franjas_a_ocupar:
            if (docente.disponibilidad == 'MANANA' and franja.turno != 'MANANA') or \
               (docente.disponibilidad == 'TARDE' and franja.turno != 'TARDE'):
                return error_response('Conflicto de Disponibilidad: El bloque choca con la disponibilidad del docente.')

            if BloqueCurso.objects.filter(curso__docente=docente, curso__semestre=semestre, dia=dia, hora_inicio=franja.hora_inicio).exists():
                conflicto = BloqueCurso.objects.get(curso__docente=docente, curso__semestre=semestre, dia=dia, hora_inicio=franja.hora_inicio)
                return error_response(f'Conflicto de Docente: Ya dicta "{conflicto.curso.nombre}" en este horario.')

        # Conflicto de grupo de estudiantes
        grupo = curso.especialidad.grupo if curso.especialidad else None
        if grupo:
            q_conflicto_base = Q(curso__especialidad__grupo=grupo, curso__semestre_cursado=curso.semestre_cursado, dia=dia)

            # Un curso de especialidad no puede chocar con uno general del mismo grupo/semestre
            if curso.tipo_curso == 'ESPECIALIDAD':
                q_conflicto = q_conflicto_base & Q(curso__tipo_curso='GENERAL', hora_inicio__in=horas_a_ocupar)
                if BloqueCurso.objects.filter(q_conflicto).exists():
                    conflicto = BloqueCurso.objects.filter(q_conflicto).first()
                    return error_response(f'Conflicto de Grupo: Choca con el curso general "{conflicto.curso.nombre}".')

            # Un curso general no puede chocar con uno de especialidad
            else: # GENERAL
                q_conflicto = q_conflicto_base & Q(curso__tipo_curso='ESPECIALIDAD', hora_inicio__in=horas_a_ocupar)
                if BloqueCurso.objects.filter(q_conflicto).exists():
                    conflicto = BloqueCurso.objects.filter(q_conflicto).first()
                    return error_response(f'Conflicto de Grupo: Choca con el curso "{conflicto.curso.nombre}" de {conflicto.curso.especialidad.nombre}.')

        # Crear el nuevo bloque de curso
        BloqueCurso.objects.create(
            curso=curso,
            dia=dia,
            hora_inicio=franja_inicio.hora_inicio,
            hora_fin=franjas_a_ocupar[-1].hora_fin,
            duracion_bloques=duracion_bloques
        )

        return success_response(message='Bloque de curso asignado con éxito.')
    except Curso.DoesNotExist:
        return error_response('El curso especificado no existe.', status_code=404)
    except FranjaHoraria.DoesNotExist:
        return error_response('La franja horaria especificada no existe.', status_code=404)
    except Exception as e:
        return error_response(f'Ocurrió un error inesperado: {str(e)}', status_code=500)


@staff_member_required
@csrf_exempt
def api_desasignar_horario(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            bloque_id = data.get('bloque_id')
            bloque = get_object_or_404(BloqueCurso, pk=bloque_id)
            bloque.delete()
            return success_response(message='Bloque de curso eliminado.')
        except Exception as e:
            return error_response(str(e))

    return error_response('Método no permitido', status_code=405)


@staff_member_required
def api_get_teacher_conflicts(request):
    curso_id = request.GET.get('curso_id')
    if not curso_id:
        return error_response('Falta el ID del curso.')

    try:
        curso_a_asignar = get_object_or_404(Curso, pk=curso_id)
        docente = curso_a_asignar.docente
        semestre = curso_a_asignar.semestre

        conflictos = set()

        if not docente:
            return success_response(data={'conflicts': []})

        # Pre-cache franjas for performance
        todas_las_franjas = list(FranjaHoraria.objects.order_by('hora_inicio'))
        franja_start_time_map = {f.hora_inicio: f for f in todas_las_franjas}

        bloques_asignados = BloqueCurso.objects.filter(curso__semestre=semestre).select_related('curso__docente')

        # STEP 1: Only check for the teacher's own schedule conflicts (using a simpler, more direct logic)
        for bloque in bloques_asignados.filter(curso__docente=docente):
            if bloque.curso_id == curso_a_asignar.id:
                continue

            franjas_del_bloque = FranjaHoraria.objects.filter(
                hora_inicio__gte=bloque.hora_inicio,
                hora_inicio__lt=bloque.hora_fin
            )
            for franja in franjas_del_bloque:
                conflictos.add((bloque.dia, franja.id))

        # 2. Conflictos de grupo
        if grupo_del_curso and semestre_cursado_a_asignar:
            q_grupo_base = Q(curso__especialidad__grupo=grupo_del_curso, curso__semestre_cursado=semestre_cursado_a_asignar)

            if curso_a_asignar.tipo_curso == 'ESPECIALIDAD':
                bloques_conflicto = bloques_asignados.filter(q_grupo_base & Q(curso__tipo_curso='GENERAL'))
            else: # GENERAL
                bloques_conflicto = bloques_asignados.filter(q_grupo_base & Q(curso__tipo_curso='ESPECIALIDAD'))

            for bloque in bloques_conflicto:
                franjas_del_bloque_conflicto = FranjaHoraria.objects.filter(
                    hora_inicio__gte=bloque.hora_inicio,
                    hora_inicio__lt=bloque.hora_fin
                )
                for franja in franjas_del_bloque_conflicto:
                    conflictos.add((bloque.dia, franja.id))

        # 3. Indisponibilidad del docente
        if docente:
            franjas_no_disponibles_ids = set()
            if docente.disponibilidad == 'MANANA':
                franjas_no_disponibles_ids = set(FranjaHoraria.objects.filter(turno='TARDE').values_list('id', flat=True))
            elif docente.disponibilidad == 'TARDE':
                franjas_no_disponibles_ids = set(FranjaHoraria.objects.filter(turno='MANANA').values_list('id', flat=True))

            if franjas_no_disponibles_ids:
                dias_semana = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes']
                for dia in dias_semana:
                    for franja_id in franjas_no_disponibles_ids:
                        conflictos.add((dia, franja_id))

        conflictos_list = [{'dia': dia, 'franja_id': franja_id} for dia, franja_id in conflictos]
        return success_response(data={'conflicts': conflictos_list})

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
        especialidad_obj = get_object_or_404(Especialidad, id=especialidad_id)
        grupo_obj = especialidad_obj.grupo

        # Cursos con horas pendientes de asignar
        q_cursos_base = Q(semestre=semestre_activo, semestre_cursado=semestre_cursado)
        cursos_del_semestre = Curso.objects.filter(q_cursos_base).annotate(
            horas_asignadas=Sum('bloques__duracion_bloques')
        )

        for curso in cursos_del_semestre:
            horas_asignadas = curso.horas_asignadas or 0
            if horas_asignadas < curso.horas_semanales:
                curso_data = {
                    'id': curso.id,
                    'nombre': curso.nombre,
                    'semestre_cursado': curso.semestre_cursado,
                    'tipo_curso': curso.tipo_curso,
                    'docente__first_name': curso.docente.first_name if curso.docente else '',
                    'docente__last_name': curso.docente.last_name if curso.docente else 'N/A',
                    'horas_semanales': curso.horas_semanales,
                    'horas_asignadas': horas_asignadas,
                    'horas_pendientes': curso.horas_semanales - horas_asignadas,
                }
                if curso.tipo_curso == 'GENERAL' and curso.especialidad and curso.especialidad.grupo == grupo_obj:
                    cursos_no_asignados_generales.append(curso_data)
                elif curso.especialidad_id == int(especialidad_id):
                    cursos_no_asignados_especialidad.append(curso_data)

        # Bloques ya asignados en el horario
        q_bloques_asignados = Q(curso__semestre=semestre_activo, curso__semestre_cursado=semestre_cursado) & (
            Q(curso__especialidad_id=especialidad_id) | Q(curso__especialidad__grupo=grupo_obj, curso__tipo_curso='GENERAL')
        )

        bloques_asignados_qs = BloqueCurso.objects.filter(q_bloques_asignados).select_related(
            'curso__docente', 'curso__especialidad__grupo'
        )

        franjas_map = {franja.hora_inicio: franja.id for franja in FranjaHoraria.objects.all()}
        for bloque in bloques_asignados_qs:
            cursos_asignados_json.append({
                'bloque_id': bloque.id,
                'id': bloque.curso.id,
                'nombre': bloque.curso.nombre,
                'docente__first_name': bloque.curso.docente.first_name if bloque.curso.docente else '',
                'docente__last_name': bloque.curso.docente.last_name if bloque.curso.docente else 'N/A',
                'especialidad__nombre': bloque.curso.especialidad.nombre if bloque.curso.especialidad else 'N/A',
                'especialidad__id': bloque.curso.especialidad.id if bloque.curso.especialidad else None,
                'grupo_id': bloque.curso.especialidad.grupo.id if bloque.curso.especialidad and bloque.curso.especialidad.grupo else None,
                'dia': bloque.dia,
                'hora_inicio': bloque.hora_inicio,
                'duracion_bloques': bloque.duracion_bloques,
                'franja_id_inicio': franjas_map.get(bloque.hora_inicio),
                'tipo_curso': bloque.curso.tipo_curso,
                'semestre_cursado': bloque.curso.semestre_cursado,
            })

    return {
        'cursos_no_asignados': {
            'generales': cursos_no_asignados_generales,
            'especialidad': cursos_no_asignados_especialidad,
        },
        'cursos_asignados': cursos_asignados_json
    }

def _check_conflicts(docente, grupo, semestre_cursado, dia, franjas_a_ocupar, horarios_ocupados):
    """Helper function to check for teacher and group conflicts."""
    for franja in franjas_a_ocupar:
        # Check teacher availability
        if (docente.disponibilidad == 'MANANA' and franja.turno != 'MANANA') or \
           (docente.disponibilidad == 'TARDE' and franja.turno != 'TARDE'):
            return True, 'disponibilidad'

        # Check teacher schedule conflict
        if horarios_ocupados['docente'].get((docente.id, dia, franja.id)):
            return True, 'docente'

        # Check group schedule conflict
        if grupo and semestre_cursado and horarios_ocupados['grupo'].get((grupo.id, semestre_cursado, dia, franja.id)):
            return True, 'grupo'

    return False, None

@staff_member_required
@csrf_exempt
def generar_horario_automatico(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

    try:
        semestre_activo = Semestre.objects.filter(estado='ACTIVO').first()
        if not semestre_activo:
            return error_response('No hay un semestre activo configurado.')

        BloqueCurso.objects.filter(curso__semestre=semestre_activo).delete()

        cursos_por_asignar = list(Curso.objects.filter(semestre=semestre_activo, docente__isnull=False)
                                  .select_related('docente', 'especialidad__grupo')
                                  .order_by('-horas_semanales'))

        total_cursos_a_asignar = len(cursos_por_asignar)
        cursos_sin_docente_count = Curso.objects.filter(semestre=semestre_activo, docente__isnull=True).count()

        franjas_horarias = list(FranjaHoraria.objects.order_by('hora_inicio'))
        dias_semana = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes']

        horarios_ocupados = {'docente': {}, 'grupo': {}}
        bloques_creados = []
        cursos_no_asignados_completamente = []

        for curso in cursos_por_asignar:
            horas_pendientes = curso.horas_semanales
            docente = curso.docente
            grupo = curso.especialidad.grupo if curso.especialidad and curso.especialidad.grupo else None

            while horas_pendientes > 0:
                bloque_asignado_en_iteracion = False
                # Intentar asignar en bloques grandes primero
                for tamano_bloque in sorted([4, 3, 2, 1], reverse=True):
                    if horas_pendientes < tamano_bloque:
                        continue

                    random.shuffle(dias_semana)
                    for dia in dias_semana:
                        # Introducir aleatoriedad en el punto de inicio de la búsqueda de franjas
                        start_index_franja = random.randint(0, len(franjas_horarias) - tamano_bloque)

                        # Iterar desde el punto aleatorio, dando la vuelta si es necesario
                        for i_offset in range(len(franjas_horarias) - tamano_bloque + 1):
                            i = (start_index_franja + i_offset) % (len(franjas_horarias) - tamano_bloque + 1)

                            franja_inicio = franjas_horarias[i]
                            franjas_del_bloque = franjas_horarias[i : i + tamano_bloque]

                            conflicto, _ = _check_conflicts(docente, grupo, curso.semestre_cursado, dia, franjas_del_bloque, horarios_ocupados)

                            if not conflicto:
                                nuevo_bloque = BloqueCurso(
                                    curso=curso, dia=dia, hora_inicio=franja_inicio.hora_inicio,
                                    hora_fin=franjas_del_bloque[-1].hora_fin, duracion_bloques=tamano_bloque
                                )
                                bloques_creados.append(nuevo_bloque)

                                for franja in franjas_del_bloque:
                                    horarios_ocupados['docente'][(docente.id, dia, franja.id)] = True
                                    if grupo:
                                        horarios_ocupados['grupo'][(grupo.id, curso.semestre_cursado, dia, franja.id)] = True

                                horas_pendientes -= tamano_bloque
                                bloque_asignado_en_iteracion = True
                                goto_next_curso_iteration = True
                                break # Salir del bucle de franjas
                        if bloque_asignado_en_iteracion:
                            break # Salir del bucle de días
                    if bloque_asignado_en_iteracion:
                        break # Salir del bucle de tamaños de bloque

                # Si en una iteración completa no se pudo asignar ningún bloque,
                # romper para evitar bucle infinito
                if not bloque_asignado_en_iteracion:
                    break

            if horas_pendientes > 0:
                cursos_no_asignados_completamente.append(f"{curso.nombre} ({horas_pendientes}h pendientes)")

        BloqueCurso.objects.bulk_create(bloques_creados)

        cursos_asignados_count = total_cursos_a_asignar - len(cursos_no_asignados_completamente)
        message = f"Proceso completado. Se asignaron total o parcialmente {cursos_asignados_count} de {total_cursos_a_asignar} cursos."
        if cursos_no_asignados_completamente:
            message += f" No se pudieron asignar completamente {len(cursos_no_asignados_completamente)} cursos: {', '.join(cursos_no_asignados_completamente)}."
        if cursos_sin_docente_count > 0:
            message += f" Además, hay {cursos_sin_docente_count} cursos sin docente que no se pudieron planificar."

        return success_response(message=message)

    except Exception as e:
        return server_error_response(f'Ocurrió un error inesperado durante la generación del horario: {e}')

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
