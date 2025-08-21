from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse, Http404, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from datetime import time, timedelta, date, datetime
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
import json
import base64
from django.core.files.base import ContentFile
import random
import io
from collections import defaultdict
from django.db import models
from django.db.models import Q, Count
from django.templatetags.static import static
from django.core.serializers.json import DjangoJSONEncoder
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
import unicodedata

def remove_accents(input_str):
    if not input_str:
        return ""
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

# Importamos todos los modelos, incluyendo los nuevos
from .models import (
    Docente, Curso, Documento, Asistencia, Carrera, SolicitudIntercambio,
    TipoDocumento, AsistenciaDiaria, PersonalDocente, ConfiguracionInstitucion,
    Semestre, DiaEspecial, Especialidad, FranjaHoraria, VersionDocumento, Anuncio,
    Notificacion, Justificacion, TipoJustificacion, Activo, TipoActivo, Reserva
)
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .forms import DocumentoForm, SolicitudIntercambioForm, VersionDocumentoForm, JustificacionForm
from .utils.exports import exportar_reporte_excel, exportar_reporte_pdf, exportar_ficha_docente_pdf
from .utils.encryption import decrypt_id
from .utils.responses import success_response, error_response, not_found_response, server_error_response
from .utils.reports import _generar_datos_reporte_asistencia
import qrcode
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.urls import reverse
import uuid


def custom_login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    configuracion = ConfiguracionInstitucion.load()

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('dashboard')
        # Si el form no es válido, se renderiza de nuevo la página con los errores
    else:
        form = AuthenticationForm()

    return render(request, 'registration/login.html', {
        'form': form,
        'configuracion': configuracion
    })

@login_required
def dashboard(request):
    docente = request.user
    now = timezone.localtime(timezone.now())
    today = now.date()

    # --- LÓGICA MEJORADA PARA EL NUEVO DASHBOARD ---

    # 1. Datos para las tarjetas de métricas
    documentos_qs = Documento.objects.filter(docente=docente)
    documentos_observados_count = documentos_qs.filter(estado='OBSERVADO').count()
    asistencias_count = Asistencia.objects.filter(docente=docente, fecha=today).count()
    
    dia_actual_str = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'][today.weekday()]
    cursos_hoy_qs = Curso.objects.filter(
        docente=docente,
        dia=dia_actual_str,
        semestre__estado='ACTIVO'
    )
    cursos_hoy_count = cursos_hoy_qs.count()

    # 2. Encontrar el próximo curso del día
    proximo_curso = cursos_hoy_qs.filter(horario_inicio__gte=now.time()).order_by('horario_inicio').first()

    # 3. Crear la línea de tiempo de actividad reciente (últimas 3 acciones)
    asistencias_recientes = Asistencia.objects.filter(docente=docente).order_by('-hora_entrada')[:3]
    versiones_recientes = VersionDocumento.objects.filter(documento__docente=docente).select_related('documento').order_by('-fecha_version')[:3]
    
    actividad_reciente = []
    for asistencia in asistencias_recientes:
        if asistencia.hora_entrada:
            actividad_reciente.append({
                'fecha': asistencia.hora_entrada,
                'texto': f"Marcó entrada en '{asistencia.curso.nombre}'",
                'tipo': 'asistencia'
            })
    for version in versiones_recientes:
        actividad_reciente.append({
            'fecha': version.fecha_version,
            'texto': f"Subió el documento '{version.documento.titulo}'",
            'tipo': 'documento'
        })
    
    # Ordenamos la actividad combinada por fecha y tomamos los 3 más recientes
    actividad_reciente.sort(key=lambda item: item['fecha'], reverse=True)
    
    # 4. Encontrar las carreras asociadas al docente en el semestre activo
    semestre_activo = Semestre.objects.filter(estado='ACTIVO').first()
    carreras = []
    if semestre_activo:
        carreras = Carrera.objects.filter(
            curso__docente=docente,
            curso__semestre=semestre_activo
        ).distinct()

    configuracion = ConfiguracionInstitucion.load()

    context = {
        'asistencias_count': asistencias_count,
        'documentos_observados_count': documentos_observados_count,
        'cursos_hoy_count': cursos_hoy_count,
        'proximo_curso': proximo_curso,
        'actividad_reciente': actividad_reciente[:3], # Pasamos solo los 3 últimos eventos
        'configuracion': configuracion,
        'carreras': carreras,
    }
    return render(request, 'dashboard.html', context)


@login_required
def perfil(request):
    docente = request.user
    
    # --- PREPARACIÓN DE DATOS PARA EL NUEVO PERFIL ---

    # 1. Datos para el Gráfico de Documentos
    documentos = Documento.objects.filter(docente=docente)
    status_counts = {
        'APROBADO': documentos.filter(estado='APROBADO').count(),
        'EN_REVISION': documentos.filter(estado='EN_REVISION').count(),
        'OBSERVADO': documentos.filter(estado='OBSERVADO').count(),
        'RECIBIDO': documentos.filter(estado='RECIBIDO').count(),
    }
    # Convertimos a JSON para pasarlo al JavaScript del gráfico
    documentos_status_json = json.dumps(list(status_counts.values()))
    documentos_labels_json = json.dumps(list(status_counts.keys()))

    # 2. Creación de la Línea de Tiempo (Timeline)
    # Combinamos las asistencias de hoy y las versiones de documentos recientes
    
    today = timezone.localtime(timezone.now()).date()
    asistencias_hoy = Asistencia.objects.filter(docente=docente, fecha=today)
    versiones_recientes = VersionDocumento.objects.filter(documento__docente=docente).select_related('documento').order_by('-fecha_version')[:10]

    timeline = []
    
    # Añadimos las asistencias de hoy a la línea de tiempo
    for asistencia in asistencias_hoy:
        if asistencia.hora_entrada:
            timeline.append({
                'tipo': 'asistencia_entrada',
                'fecha': asistencia.hora_entrada,
                'texto': f"Marcó entrada en el curso '{asistencia.curso.nombre}'.",
            })
        if asistencia.hora_salida:
            timeline.append({
                'tipo': 'asistencia_salida',
                'fecha': asistencia.hora_salida,
                'texto': f"Marcó salida del curso '{asistencia.curso.nombre}'.",
            })
            
    # Añadimos las subidas de documentos a la línea de tiempo
    for version in versiones_recientes:
        timeline.append({
            'tipo': 'documento',
            'fecha': version.fecha_version,
            'texto': f"Subió una nueva versión (v{version.numero_version}) del documento '{version.documento.titulo}'.",
            'documento': version.documento # Pasamos el objeto para crear enlaces
        })
        
    # Ordenamos la línea de tiempo por fecha, de más reciente a más antiguo
    timeline.sort(key=lambda item: item['fecha'], reverse=True)

    context = {
        'timeline': timeline[:10],  # Mostramos los 10 eventos más recientes
        'documentos_status_json': documentos_status_json,
        'documentos_labels_json': documentos_labels_json,
        'total_documentos': documentos.count(),
    }
    
    return render(request, 'perfil.html', context)

@login_required
def subir_documento(request):
    tipos_documento = TipoDocumento.objects.all() # Obtenemos todas las categorías

    if request.method == 'POST':
        form = DocumentoForm(request.POST, request.FILES)
        if form.is_valid():
            documento = form.save(commit=False)
            documento.docente = request.user
            # El estado por defecto 'RECIBIDO' se asigna desde el modelo
            documento.save() 

            VersionDocumento.objects.create(
                documento=documento,
                archivo=form.cleaned_data['archivo']
            )

            messages.success(request, f'El documento "{documento.titulo}" se ha subido correctamente.')
            return redirect('lista_documentos')
    else:
        form = DocumentoForm()
        
    context = {
        'form': form,
        'tipos_documento': tipos_documento # Le pasamos las categorías a la plantilla
    }
    return render(request, 'subir_documento.html', context)

@login_required
def subir_nueva_version(request, documento_id):
    documento = get_object_or_404(Documento, id=documento_id, docente=request.user)
    
    if request.method == 'POST':
        form = VersionDocumentoForm(request.POST, request.FILES)
        if form.is_valid():
            nueva_version = form.save(commit=False)
            nueva_version.documento = documento
            nueva_version.save()
            
            # Opcional: Cambiar el estado del documento a "En Revisión"
            documento.estado = 'EN_REVISION'
            documento.save()

            messages.success(request, f'Se ha subido una nueva versión para "{documento.titulo}".')
            return redirect('lista_documentos')
    else:
        form = VersionDocumentoForm()
        
    context = {
        'form': form,
        'documento': documento
    }
    return render(request, 'subir_version.html', context)

@login_required
def lista_documentos(request):
    documentos_qs = Documento.objects.filter(docente=request.user).prefetch_related('versiones').order_by('-fecha_subida')

    # Definir el orden de los estados
    status_order = ['OBSERVADO', 'EN_REVISION', 'RECIBIDO', 'APROBADO', 'VENCIDO']

    # Agrupar documentos por estado
    documentos_agrupados = {status: [] for status in status_order}
    for doc in documentos_qs:
        if doc.estado in documentos_agrupados:
            documentos_agrupados[doc.estado].append(doc)

    # Crear una lista ordenada de tuplas (nombre_visible_estado, lista_documentos)
    # para pasarla a la plantilla, omitiendo grupos vacíos.
    documentos_por_seccion = []
    estado_display_map = dict(Documento.ESTADOS_DOCUMENTO)

    for status_key in status_order:
        if documentos_agrupados[status_key]:
            documentos_por_seccion.append({
                'estado_key': status_key,
                'estado_display': estado_display_map.get(status_key, status_key),
                'documentos': documentos_agrupados[status_key]
            })

    return render(request, 'lista_documentos.html', {'documentos_por_seccion': documentos_por_seccion})

@login_required
def registrar_asistencia(request):
    # Esta vista puede servir como un historial simple para el docente.
    docente = request.user
    now = timezone.now()
    semestre_activo = Semestre.objects.filter(estado='ACTIVO', fecha_inicio__lte=now.date(), fecha_fin__gte=now.date()).first()
    
    curso_actual = None
    if semestre_activo:
        dia_actual_str = now.strftime('%A').capitalize()
        curso_actual = Curso.objects.filter(
            docente=docente,
            semestre=semestre_activo,
            dia=dia_actual_str,
            horario_inicio__lte=now.time(),
            horario_fin__gte=now.time()
        ).first()

    asistencia_obj = None
    if curso_actual:
        asistencia_obj = Asistencia.objects.filter(
            docente=docente, curso=curso_actual, fecha=now.date()
        ).first()

    return render(request, 'asistencia.html', {
        'curso_actual': curso_actual,
        'asistencia': asistencia_obj,
    })

@login_required
def ver_horarios(request, carrera_id):
    semestre_activo = Semestre.objects.filter(estado='ACTIVO').first()
    carrera = Carrera.objects.get(id=carrera_id)
    
    # Obtenemos solo los cursos que ya tienen un día y hora asignados
    cursos_asignados = Curso.objects.filter(
        carrera=carrera, 
        semestre=semestre_activo,
        dia__isnull=False, 
        horario_inicio__isnull=False
    ).order_by('dia', 'horario_inicio')
    
    # Preparamos los elementos necesarios para construir la parrilla del horario
    franjas_horarias = list(FranjaHoraria.objects.all().order_by('hora_inicio'))
    dias_semana = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes']
    
    # Inicializamos la parrilla vacía. Ej: horario_grid[franja_id][dia] = None
    horario_grid = {franja.id: {dia: None for dia in dias_semana} for franja in franjas_horarias}

    # Poblamos la parrilla con los cursos asignados
    for curso in cursos_asignados:
        try:
            # Buscamos la franja horaria donde inicia el curso
            franja_inicio_obj = next(f for f in franjas_horarias if f.hora_inicio == curso.horario_inicio)
            
            # Colocamos el objeto 'curso' en la celda correcta de la parrilla
            horario_grid[franja_inicio_obj.id][curso.dia] = curso
            
            # Si el curso dura más de un bloque, marcamos las celdas siguientes como 'OCUPADO'
            if curso.duracion_bloques > 1:
                start_index = franjas_horarias.index(franja_inicio_obj)
                for i in range(1, curso.duracion_bloques):
                    if (start_index + i) < len(franjas_horarias):
                        franja_ocupada = franjas_horarias[start_index + i]
                        horario_grid[franja_ocupada.id][curso.dia] = 'OCUPADO'
        except (StopIteration, TypeError, AttributeError):
            # Si un curso tiene una hora de inicio que no coincide con ninguna franja, lo omitimos
            continue

    context = {
        'carrera': carrera,
        'semestre_activo': semestre_activo,
        'horario_grid': horario_grid,
        'franjas_horarias': franjas_horarias,
        'dias_semana': dias_semana,
    }
    
    return render(request, 'ver_horarios.html', context)

@staff_member_required
def generar_horarios(request, carrera_id):
    semestre_activo = Semestre.objects.filter(estado='ACTIVO').first()
    if not semestre_activo:
        messages.error(request, "No hay un semestre activo para generar horarios.")
        return redirect('ver_horarios', carrera_id=carrera_id)

    carrera = Carrera.objects.get(id=carrera_id)
    cursos = Curso.objects.filter(carrera=carrera, semestre=semestre_activo, horario_inicio__isnull=True)
    dias = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes']
    horas_inicio = [time(hour=h) for h in range(8, 19, 2)]

    for curso in cursos:
        asignado = False
        random.shuffle(dias)
        for dia in dias:
            random.shuffle(horas_inicio)
            for hora in horas_inicio:
                hora_fin = (timezone.datetime.combine(timezone.now(), hora) + timedelta(hours=curso.duracion_horas)).time()
                conflicto_docente = Curso.objects.filter(
                    docente=curso.docente,
                    dia=dia,
                    semestre=semestre_activo,
                    horario_inicio__lt=hora_fin,
                    horario_fin__gt=hora
                ).exists()
                if not conflicto_docente:
                    curso.dia = dia
                    curso.horario_inicio = hora
                    curso.horario_fin = hora_fin
                    curso.aula = 'Por asignar'
                    curso.save()
                    asignado = True
                    break
            if asignado:
                break
        if not asignado:
            curso.aula = 'No asignado'
            curso.save()

    messages.success(request, f"Se han intentado generar los horarios para el semestre {semestre_activo.nombre}.")
    return redirect('ver_horarios', carrera_id=carrera_id)

@login_required
def solicitar_intercambio(request, curso_id):
    curso_solicitante = Curso.objects.get(id=curso_id)
    if curso_solicitante.docente != request.user:
        return redirect('ver_horarios', carrera_id=curso_solicitante.carrera.id)
    
    if request.method == 'POST':
        form = SolicitudIntercambioForm(request.POST, curso_solicitante=curso_solicitante)
        if form.is_valid():
            solicitud = form.save(commit=False)
            solicitud.docente_solicitante = request.user
            solicitud.curso_solicitante = curso_solicitante
            solicitud.save()
            messages.success(request, 'La solicitud de intercambio ha sido enviada.')
            return redirect('ver_solicitudes')
    else:
        form = SolicitudIntercambioForm(curso_solicitante=curso_solicitante)
    
    return render(request, 'solicitar_intercambio.html', {'form': form, 'curso': curso_solicitante})

@login_required
def ver_solicitudes(request):
    solicitudes_enviadas = SolicitudIntercambio.objects.filter(docente_solicitante=request.user)
    solicitudes_recibidas = SolicitudIntercambio.objects.filter(docente_destino=request.user, estado='pendiente')
    return render(request, 'ver_solicitudes.html', {
        'solicitudes_enviadas': solicitudes_enviadas,
        'solicitudes_recibidas': solicitudes_recibidas,
    })

@login_required
def responder_solicitud(request, solicitud_id):
    solicitud = SolicitudIntercambio.objects.get(id=solicitud_id)
    if solicitud.docente_destino != request.user:
        return redirect('ver_solicitudes')
    
    if request.method == 'POST':
        accion = request.POST.get('accion')
        if accion == 'aprobar':
            curso_solicitante = solicitud.curso_solicitante
            curso_destino = solicitud.curso_destino
            conflicto_solicitante = Curso.objects.filter(
                docente=solicitud.docente_destino,
                semestre=curso_solicitante.semestre,
                dia=curso_solicitante.dia,
                horario_inicio__lt=curso_solicitante.horario_fin,
                horario_fin__gt=curso_solicitante.horario_inicio
            ).exclude(id=curso_solicitante.id).exists()
            conflicto_destino = Curso.objects.filter(
                docente=solicitud.docente_solicitante,
                semestre=curso_destino.semestre,
                dia=curso_destino.dia,
                horario_inicio__lt=curso_destino.horario_fin,
                horario_fin__gt=curso_destino.horario_inicio
            ).exclude(id=curso_destino.id).exists()
            if conflicto_solicitante or conflicto_destino:
                messages.error(request, 'El intercambio no se puede aprobar porque genera un conflicto de horario.')
                return render(request, 'responder_solicitud.html', {'solicitud': solicitud})
            
            curso_solicitante.docente, curso_destino.docente = curso_destino.docente, curso_solicitante.docente
            curso_solicitante.save()
            curso_destino.save()
            solicitud.estado = 'aprobado'
            solicitud.save()
            messages.success(request, 'El intercambio ha sido aprobado correctamente.')
        elif accion == 'rechazar':
            solicitud.estado = 'rechazado'
            solicitud.save()
            messages.info(request, 'La solicitud de intercambio ha sido rechazada.')
        return redirect('ver_solicitudes')
    
    return render(request, 'responder_solicitud.html', {'solicitud': solicitud})

@login_required
def solicitar_justificacion(request):
    if request.method == 'POST':
        form = JustificacionForm(request.POST, request.FILES)
        if form.is_valid():
            justificacion = form.save(commit=False)
            justificacion.docente = request.user
            justificacion.save()
            messages.success(request, 'Su solicitud de justificación ha sido enviada correctamente.')
            return redirect('lista_justificaciones')
    else:
        form = JustificacionForm()

    return render(request, 'solicitar_justificacion.html', {'form': form})

@login_required
def lista_justificaciones(request):
    user = request.user
    is_admin = user.is_staff

    # Lógica para aprobar/rechazar (solo para staff con permisos)
    if request.method == 'POST' and is_admin and user.has_perm('core.change_justificacion'):
        justificacion_id = request.POST.get('justificacion_id')
        accion = request.POST.get('accion')
        justificacion = get_object_or_404(Justificacion, id=justificacion_id)

        if accion == 'aprobar':
            justificacion.estado = 'APROBADO'
            messages.success(request, f"Se aprobó la justificación de {justificacion.docente}.")
        elif accion == 'rechazar':
            justificacion.estado = 'RECHAZADO'
            messages.warning(request, f"Se rechazó la justificación de {justificacion.docente}.")

        justificacion.revisado_por = user
        justificacion.fecha_revision = timezone.now()
        justificacion.save()
        return redirect('lista_justificaciones')

    # Preparar el contexto
    if is_admin:
        # Para el admin, separamos las justificaciones por estado para las pestañas
        base_qs = Justificacion.objects.select_related('docente', 'tipo').order_by('-fecha_creacion')
        context = {
            'justificaciones': {
                'pending': base_qs.filter(estado='PENDIENTE'),
                'approved': base_qs.filter(estado='APROBADO'),
                'rejected': base_qs.filter(estado='RECHAZADO'),
                'pending_count': base_qs.filter(estado='PENDIENTE').count(),
            },
            'is_admin_view': True,
        }
    else:
        # Para el docente, solo una lista de sus propias justificaciones
        context = {
            'justificaciones': Justificacion.objects.filter(docente=user).select_related('tipo').order_by('-fecha_creacion'),
            'is_admin_view': False,
        }

    return render(request, 'lista_justificaciones.html', context)


# --- VISTAS PARA EL KIOSCO ---

def kiosco_page(request):
    return render(request, 'kiosco.html')

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
            
            # NORMALIZAMOS LOS DÍAS PARA EVITAR PROBLEMAS CON TILDES
            dia_actual_normalized = remove_accents(dia_actual_str).lower()

            # Obtenemos todos los cursos del docente en el semestre activo
            cursos_del_docente = Curso.objects.filter(docente=docente, semestre=semestre_activo)

            # Filtramos por día en Python
            cursos_hoy = [
                c for c in cursos_del_docente
                if c.dia and remove_accents(c.dia).lower() == dia_actual_normalized
            ]
            
            courses_data = []
            for curso in cursos_hoy:
                asistencia_curso = Asistencia.objects.filter(docente=docente, curso=curso, fecha=today).first()
                
                # --- LÓGICA MEJORADA PARA DECIDIR QUÉ MOSTRAR ---
                can_mark_exit = False
                if asistencia_curso and asistencia_curso.hora_entrada and not asistencia_curso.hora_salida:
                    if asistencia_curso.hora_salida_permitida and timezone.now() >= asistencia_curso.hora_salida_permitida:
                        can_mark_exit = True
                # --- FIN DE LA LÓGICA MEJORADA ---

                courses_data.append({
                    'id': curso.id,
                    'name': f'{curso.nombre} ({curso.horario_inicio.strftime("%H:%M")} - {curso.horario_fin.strftime("%H:%M")})',
                    'entryMarked': asistencia_curso is not None and asistencia_curso.hora_entrada is not None,
                    'exitMarked': asistencia_curso is not None and asistencia_curso.hora_salida is not None,
                    'canMarkExit': can_mark_exit, # Nueva bandera para el frontend
                    'hora_salida_permitida_str': asistencia_curso.hora_salida_permitida.strftime('%H:%M:%S') if asistencia_curso and asistencia_curso.hora_salida_permitida else None,
                })

            # --- CORRECCIÓN DE ESTRUCTURA DE RESPUESTA ---
            # Se anida la información del docente bajo la clave "teacher" para que coincida
            # con lo que espera el JavaScript del kiosco (displayInfoAndActions).
            # También se añade el qrId a la respuesta para usarlo en las acciones de marcado.
            response_data = {
                'status': 'success',
                'qrId': qr_id,  # El frontend necesita esto para las acciones posteriores
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
            
            # --- CORRECCIÓN DE ZONA HORARIA ---
            # Ahora esta función también usa la hora local, igual que la otra.
            today = timezone.localtime(timezone.now()).date()
            now = timezone.now()
            # --- FIN DE LA CORRECCIÓN ---

            format, imgstr = photo_base64.split(';base64,')
            ext = format.split('/')[-1]
            photo_file = ContentFile(base64.b64decode(imgstr), name=f'{docente.username}_{now.timestamp()}.{ext}')
            
            if action_type == 'general_entry':
                if not AsistenciaDiaria.objects.filter(docente=docente, fecha=today).exists():
                    AsistenciaDiaria.objects.create(docente=docente, foto_verificacion=photo_file)

            elif action_type in ['course_entry', 'course_exit']:
                curso_id = data.get('courseId')
                curso = Curso.objects.get(id=curso_id)
                asistencia, created = Asistencia.objects.get_or_create(docente=docente, curso=curso, fecha=today)

                response_data = {}

                if action_type == 'course_entry' and not asistencia.hora_entrada:
                    asistencia.hora_entrada = now
                    asistencia.foto_entrada = photo_file
                    
                    # Lógica de tardanza
                    configuracion = ConfiguracionInstitucion.load()
                    horario_inicio_dt = timezone.make_aware(datetime.combine(today, curso.horario_inicio))
                    limite_tardanza = horario_inicio_dt + timedelta(minutes=configuracion.tiempo_limite_tardanza)
                    es_tardanza = now > limite_tardanza
                    response_data['es_tardanza'] = es_tardanza

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

            # 1. Comprobar si es fin de semana (Sábado=5, Domingo=6)
            if today.weekday() in [5, 6]:
                return JsonResponse({'status': 'weekend_off', 'message': 'El registro de asistencia no está disponible los fines de semana.'})

            # 2. Buscar al docente
            docente = Docente.objects.get(rfid_uid=rfid_uid)

            # 3. Preparar la información del docente para devolverla siempre
            photo_url = request.build_absolute_uri(docente.foto.url) if docente.foto and hasattr(docente.foto, 'url') else request.build_absolute_uri(static('placeholder.png'))
            teacher_data = {
                'name': f'{docente.first_name} {docente.last_name}',
                'dni': docente.dni,
                'photoUrl': photo_url,
            }

            # 4. Comprobar si ya se marcó la asistencia
            if AsistenciaDiaria.objects.filter(docente=docente, fecha=today).exists():
                response_data = {
                    'status': 'warning',
                    'message': f'La asistencia de hoy ya fue registrada a las {AsistenciaDiaria.objects.get(docente=docente, fecha=today).hora_entrada.strftime("%H:%M:%S")}.',
                    'teacher': teacher_data
                }
            else:
                # 5. Registrar la asistencia diaria (sin foto)
                AsistenciaDiaria.objects.create(docente=docente, fecha=today)
                response_data = {
                    'status': 'success',
                    'message': 'Asistencia registrada correctamente.',
                    'teacher': teacher_data
                }

            # 6. Enviar actualización a través de Channels
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
            # Log del error para depuración en el servidor
            print(f"Error inesperado en registrar_asistencia_rfid: {e}")
            return server_error_response('Ocurrió un error interno en el servidor.')

    return error_response('Método no permitido', status_code=405)


# --- VISTAS PARA CREDENCIALES ---

@staff_member_required
def lista_docentes_credenciales(request):
    query = request.GET.get('q', '')
    docentes = PersonalDocente.objects.all()

    if query:
        docentes = docentes.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(dni__icontains=query)
        ).distinct()

    context = {
        'docentes': docentes,
        'query': query,
    }
    return render(request, 'lista_credenciales.html', context)

@staff_member_required
def generar_credencial_docente(request, encrypted_id):
    docente_id = decrypt_id(encrypted_id)
    if docente_id is None:
        raise Http404("El enlace de la credencial no es válido o ha expirado.")

    docente = get_object_or_404(PersonalDocente, id=docente_id)
    configuracion = ConfiguracionInstitucion.load()

    # Preparamos la URL absoluta para la FOTO del docente
    foto_url_absoluta = ''
    if docente.foto and hasattr(docente.foto, 'url'):
        foto_url_absoluta = request.build_absolute_uri(docente.foto.url)
    else:
        foto_url_absoluta = request.build_absolute_uri(static('placeholder.png'))

    # --- CORRECCIÓN PARA EL LOGO ---
    # Ahora también preparamos la URL absoluta para el LOGO de la institución
    logo_url_absoluto = ''
    if configuracion and configuracion.logo and hasattr(configuracion.logo, 'url'):
        logo_url_absoluto = request.build_absolute_uri(configuracion.logo.url)
    # --- FIN DE LA CORRECCIÓN ---
    
    # Preparamos el contexto completo para la plantilla
    context = {
        'docente': docente, 
        'configuracion': configuracion,
        'foto_url_absoluta': foto_url_absoluta,
        'logo_url_absoluto': logo_url_absoluto  # Pasamos la nueva variable del logo
    }
    
    return render(request, 'credencial.html', context)

@staff_member_required
def rotate_qr_code(request, docente_id):
    """
    Generates a new id_qr for a given docente, effectively invalidating the old one.
    """
    docente = get_object_or_404(Docente, id=docente_id)
    docente.id_qr = uuid.uuid4()
    docente.save()
    messages.success(request, f"Se ha generado un nuevo código QR para {docente.get_full_name()}. La credencial anterior ya no es válida.")
    # Redirect back to the admin change page for that user
    return redirect(reverse('admin:core_personaldocente_change', args=[docente.id]))


# --- VISTA PARA REPORTES ---

@staff_member_required
@permission_required('core.view_reporte', raise_exception=True)
def reporte_asistencia(request):
    reporte_final, total_docentes = _generar_datos_reporte_asistencia(request.GET)
    
    presentes_count = len([r for r in reporte_final if r['estado'] == 'Presente'])
    ausentes_count = len([r for r in reporte_final if r['estado'] == 'Falta'])

    paginator = Paginator(reporte_final, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    query_params = request.GET.copy()
    if 'page' in query_params:
        del query_params['page']

    context = {
        'page_obj': page_obj,
        'reporte_data': page_obj.object_list,
        'total_docentes': total_docentes,
        'presentes_count': presentes_count,
        'ausentes_count': ausentes_count,
        'docentes': Docente.objects.all().order_by('last_name'), # Para el nuevo filtro
        'cursos': Curso.objects.all(),
        'especialidades': Especialidad.objects.all(),
        'fecha_inicio': request.GET.get('fecha_inicio', date.today().strftime('%Y-%m-%d')),
        'fecha_fin': request.GET.get('fecha_fin', date.today().strftime('%Y-%m-%d')),
        'estado': request.GET.get('estado', 'todos'),
        'curso_id': request.GET.get('curso'),
        'especialidad_id': request.GET.get('especialidad'),
        'docente_id': request.GET.get('docente'), # Para el nuevo filtro
        'filter_params': query_params.urlencode(),
    }
    return render(request, 'reporte_asistencia.html', context)


@staff_member_required
@permission_required('core.view_reporte', raise_exception=True)
def analytics_dashboard(request):
    """
    Displays the analytics dashboard with charts and stats for administrators.
    """
    # The data is fetched asynchronously by the frontend.
    # This view can pass filter options like date ranges or semester lists if needed.
    context = {
        'semestres': Semestre.objects.all().order_by('-fecha_inicio'),
        'especialidades': Especialidad.objects.all(),
    }
    return render(request, 'analytics_dashboard.html', context)


@staff_member_required
def api_get_report_chart_data(request):
    """
    API endpoint to get chart data. Reuses the main report generation logic
    for consistency and performance.
    """
    # 1. REUTILIZAR LA LÓGICA DEL REPORTE PRINCIPAL
    # Pasamos request.GET directamente para que la función de reporte use los mismos filtros.
    report_data, _ = _generar_datos_reporte_asistencia(request.GET)

    # 2. PROCESAR LOS DATOS DEL REPORTE PARA GENERAR ESTADÍSTICAS
    # Agrupar los estados por día
    daily_stats = defaultdict(lambda: {'Presente': 0, 'Falta': 0, 'Tardanza': 0, 'Justificado': 0})

    for record in report_data:
        # Solo contamos los estados relevantes para el gráfico
        if record['estado'] in ['Presente', 'Falta', 'Tardanza', 'Justificado']:
            fecha_str = record['fecha'].strftime('%d/%m')
            daily_stats[fecha_str][record['estado']] += 1

    # Ordenar las fechas para el gráfico de barras
    sorted_labels = sorted(daily_stats.keys(), key=lambda d: timezone.datetime.strptime(d, '%d/%m').date())

    # 3. FORMATEAR PARA CHART.JS
    bar_chart_data = {
        'labels': sorted_labels,
        'presentes': [daily_stats[label]['Presente'] for label in sorted_labels],
        'faltas': [daily_stats[label]['Falta'] for label in sorted_labels],
        'tardanzas': [daily_stats[label]['Tardanza'] for label in sorted_labels],
    }

    # Calcular totales para el gráfico de pie
    total_presentes = sum(bar_chart_data['presentes'])
    total_faltas = sum(bar_chart_data['faltas'])
    total_tardanzas = sum(bar_chart_data['tardanzas'])
    # total_justificados = sum(stats['Justificado'] for stats in daily_stats.values()) # Opcional si se quiere añadir al pie

    pie_chart_data = {
        'presentes': total_presentes,
        'faltas': total_faltas,
        'tardanzas': total_tardanzas,
    }

    return success_response(data={'bar_chart': bar_chart_data, 'pie_chart': pie_chart_data})


@staff_member_required
def detalle_asistencia_docente_ajax(request, docente_id):
    """
    Devuelve los detalles de asistencia de un docente en formato JSON.
    Esta vista ha sido mejorada para ser más robusta.
    """
    try:
        docente = Docente.objects.get(pk=docente_id)
        
        # Obtenemos todas las asistencias del docente en el rango de fechas del reporte
        # (o un rango por defecto si no se especifica)
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

        # Construcción de datos segura
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
        # Captura cualquier otro error inesperado para evitar que el servidor crashee.
        return server_error_response(f'Error inesperado: {str(e)}')
        
from django.contrib.auth.decorators import permission_required

@staff_member_required
@permission_required('core.view_planificador', raise_exception=True)
def planificador_horarios(request):
    semestre_activo = Semestre.objects.filter(estado='ACTIVO').first()
    if not semestre_activo:
        messages.error(request, "No hay un semestre activo. Por favor, active un semestre en el panel de administración.")
        return render(request, 'planificador_vacio.html')

    # Determinar los semestres cursados válidos para el semestre activo
    semestres_validos = []
    if semestre_activo.tipo == 'IMPAR':
        semestres_validos = [1, 3, 5, 7, 9]
    elif semestre_activo.tipo == 'PAR':
        semestres_validos = [2, 4, 6, 8, 10]

    # Pre-serializar datos para JavaScript de forma segura
    franjas = FranjaHoraria.objects.order_by('hora_inicio')
    franjas_manana_json = json.dumps(list(franjas.filter(turno='MANANA').values('id', 'hora_inicio', 'hora_fin')), cls=DjangoJSONEncoder)
    franjas_tarde_json = json.dumps(list(franjas.filter(turno='TARDE').values('id', 'hora_inicio', 'hora_fin')), cls=DjangoJSONEncoder)

    dias_semana = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes']
    dias_semana_json = json.dumps(dias_semana)

    context = {
        'semestre_activo': semestre_activo,
        'especialidades': Especialidad.objects.all(),
        'franjas_manana_json': franjas_manana_json,
        'franjas_tarde_json': franjas_tarde_json,
        'dias_semana_json': dias_semana_json,
        'dias_semana': dias_semana,  # <-- Añadido para el template
        'semestres_validos': semestres_validos,
        # Pasamos los filtros seleccionados para que la plantilla los recuerde
        'especialidad_seleccionada_id': request.GET.get('especialidad'),
        'semestre_seleccionado': request.GET.get('semestre_cursado'),
    }
    return render(request, 'planificador_horarios.html', context)

@staff_member_required
@csrf_exempt # Usamos csrf_exempt para simplificar la llamada AJAX
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

            # 1. Validar Disponibilidad y Cruce de DOCENTE
            for franja in franjas_a_ocupar:
                if (docente.disponibilidad == 'MANANA' and franja.turno != 'MANANA') or (docente.disponibilidad == 'TARDE' and franja.turno != 'TARDE'):
                    return error_response('Conflicto de Disponibilidad del docente.')
                conflicto_docente = Curso.objects.filter(docente=docente, semestre=semestre, dia=dia, horario_inicio=franja.hora_inicio).exclude(pk=curso.id).first()
                if conflicto_docente:
                    return error_response(f'Conflicto: El docente ya dicta "{conflicto_docente.nombre}" en este horario.')

            # 2. Validar Cruce de GRUPO
            grupo = curso.especialidad.grupo if curso.especialidad else None
            if grupo:
                q_conflicto = models.Q(especialidad__grupo=grupo, semestre_cursado=curso.semestre_cursado, dia=dia, horario_inicio__in=[f.hora_inicio for f in franjas_a_ocupar])
                if curso.tipo_curso == 'ESPECIALIDAD':
                    conflicto_grupo = Curso.objects.filter(q_conflicto, tipo_curso='GENERAL').first()
                    if conflicto_grupo: return error_response(f'Conflicto de Grupo: El curso general "{conflicto_grupo.nombre}" ya está programado.')
                else: # GENERAL
                    conflicto_grupo = Curso.objects.filter(q_conflicto, tipo_curso='ESPECIALIDAD').first()
                    if conflicto_grupo: return error_response(f'Conflicto de Grupo: El curso "{conflicto_grupo.nombre}" ({conflicto_grupo.especialidad.nombre}) ya está programado.')

            # Si pasa todo, asignamos
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

            # Simplemente limpiamos los campos del horario
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

        # 1. Conflictos del DOCENTE
        for curso in cursos_asignados.filter(docente=docente):
            try:
                franja_inicio_obj = next(f for f in todas_las_franjas if f.hora_inicio == curso.horario_inicio)
                start_index = todas_las_franjas.index(franja_inicio_obj)
                for i in range(curso.duracion_bloques):
                    if (start_index + i) < len(todas_las_franjas):
                        franja_ocupada = todas_las_franjas[start_index + i]
                        conflictos.append({'dia': curso.dia, 'franja_id': franja_ocupada.id})
            except (StopIteration, TypeError, AttributeError): continue

        # 2. Conflictos de GRUPO
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

        # 3. Conflictos de DISPONIBILIDAD del docente
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
    """
    Función auxiliar para obtener los datos del planificador en un formato consistente.
    Devuelve un diccionario con los cursos asignados y no asignados.
    """
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
        
        # Cursos NO asignados
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

        # Cursos YA asignados
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
        semestre_cursado = data.get('semestre_cursado') # Necesitamos el semestre para obtener los datos correctos
        semestre_activo = Semestre.objects.filter(estado='ACTIVO').first()
        if not semestre_activo:
            return JsonResponse({'status': 'error', 'message': 'No hay un semestre activo.'}, status=400)

        # Filtramos los cursos por especialidad Y semestre cursado, incluyendo los generales del grupo
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

        # Construir el estado actual de los horarios ocupados
        horarios_ocupados = {}
        cursos_ya_asignados = Curso.objects.filter(semestre=semestre_activo, dia__isnull=False)
        for curso in cursos_ya_asignados:
            try:
                franja_inicio_obj = next(f for f in franjas_horarias if f.hora_inicio == curso.horario_inicio)
                start_index = franjas_horarias.index(franja_inicio_obj)
                for i in range(curso.duracion_bloques):
                    franja_ocupada = franjas_horarias[start_index + i]
                    # Clave: (dia, hora, docente_id) y (dia, hora, grupo_id, semestre_cursado)
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
                        # Conflicto de disponibilidad del docente
                        if (docente.disponibilidad == 'MANANA' and franja.turno != 'MANANA') or \
                           (docente.disponibilidad == 'TARDE' and franja.turno != 'TARDE'):
                            bloque_valido = False; break
                        # Conflicto de horario del docente
                        if horarios_ocupados.get((dia, franja.hora_inicio, docente.id)):
                            bloque_valido = False; break
                        # Conflicto de horario del grupo
                        if grupo and horarios_ocupados.get((dia, franja.hora_inicio, grupo.id, curso.semestre_cursado)):
                             bloque_valido = False; break

                    if bloque_valido:
                        curso.dia = dia
                        curso.horario_inicio = franja_inicio.hora_inicio
                        curso.horario_fin = franjas_del_curso[-1].hora_fin
                        curso.save()

                        # Actualizar horarios ocupados
                        for franja in franjas_del_curso:
                            horarios_ocupados[(dia, franja.hora_inicio, docente.id)] = True
                            if grupo:
                                horarios_ocupados[(dia, franja.hora_inicio, grupo.id, curso.semestre_cursado)] = True

                        cursos_asignados_count += 1
                        asignado = True
                        break
                if asignado: break

        message = f"Proceso finalizado. Se asignaron {cursos_asignados_count} de {len(cursos_por_asignar) + cursos_asignados_count} cursos."

        # Usamos la función auxiliar para devolver el estado actualizado
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

        # Paso 1: Limpiar todos los horarios existentes para el semestre activo
        Curso.objects.filter(semestre=semestre_activo).update(dia=None, horario_inicio=None, horario_fin=None)

        # Paso 2: Obtener todos los cursos, priorizando los más largos y los que tienen docente asignado
        cursos_por_asignar = list(Curso.objects.filter(semestre=semestre_activo, docente__isnull=False)
                                  .select_related('docente', 'especialidad__grupo')
                                  .order_by('-duracion_bloques'))

        total_cursos_a_asignar = len(cursos_por_asignar)
        cursos_sin_docente = Curso.objects.filter(semestre=semestre_activo, docente__isnull=True).count()

        # Paso 3: Obtener franjas horarias y días
        franjas_horarias = list(FranjaHoraria.objects.order_by('hora_inicio'))
        dias_semana = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes']
        random.shuffle(dias_semana)

        # Paso 4: Estructura para seguir los horarios ocupados
        horarios_ocupados = {
            'docente': {},  # (docente_id, dia, franja_id) -> True
            'grupo': {}     # (grupo_id, semestre_cursado, dia, franja_id) -> True
        }

        cursos_asignados_count = 0
        cursos_no_asignados = []

        # Paso 5: Algoritmo de asignación
        for curso in cursos_por_asignar:
            docente = curso.docente
            grupo = curso.especialidad.grupo if curso.especialidad and curso.especialidad.grupo else None
            semestre_cursado = curso.semestre_cursado

            asignado = False
            # Iterar aleatoriamente sobre los días para evitar sesgos
            random.shuffle(dias_semana)
            for dia in dias_semana:
                # Iterar sobre las franjas de inicio posibles
                for i in range(len(franjas_horarias) - curso.duracion_bloques + 1):
                    franja_inicio = franjas_horarias[i]
                    franjas_del_curso = franjas_horarias[i : i + curso.duracion_bloques]

                    bloque_valido = True
                    for franja in franjas_del_curso:
                        # 1. Conflicto de Disponibilidad del Docente
                        if (docente.disponibilidad == 'MANANA' and franja.turno != 'MANANA') or \
                           (docente.disponibilidad == 'TARDE' and franja.turno != 'TARDE'):
                            bloque_valido = False
                            break
                        # 2. Conflicto de Horario del Docente
                        if horarios_ocupados['docente'].get((docente.id, dia, franja.id)):
                            bloque_valido = False
                            break
                        # 3. Conflicto de Horario del Grupo/Semestre
                        if grupo and semestre_cursado:
                            if horarios_ocupados['grupo'].get((grupo.id, semestre_cursado, dia, franja.id)):
                                bloque_valido = False
                                break

                    if bloque_valido:
                        # Asignar y actualizar horarios ocupados
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

        # Guardar todos los cambios a la vez al final si se prefiere, pero guardar uno por uno es más seguro
        # si el proceso es largo. Dado que ya estamos guardando, lo dejamos así.
        for curso in cursos_por_asignar:
            if curso.dia: # Solo guardar los que fueron asignados
                curso.save()

        # Paso 6: Preparar el mensaje de respuesta
        message = f"Proceso completado. Se asignaron exitosamente {cursos_asignados_count} de {total_cursos_a_asignar} cursos."
        if cursos_no_asignados:
            message += f" No se pudieron asignar {len(cursos_no_asignados)} cursos por falta de espacio o conflictos."
        if cursos_sin_docente > 0:
            message += f" Además, hay {cursos_sin_docente} cursos sin docente que no se pueden planificar."

        return success_response(message=message)

    except Exception as e:
        # Log del error para depuración
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


@login_required
def vista_publica_horarios(request):
    semestre_activo = Semestre.objects.filter(estado='ACTIVO').first()
    especialidades = Especialidad.objects.all()
    
    especialidad_seleccionada_id = request.GET.get('especialidad')
    especialidad_seleccionada = None
    
    horarios_por_semestre_cursado = {} 

    if especialidad_seleccionada_id:
        try:
            especialidad_seleccionada = Especialidad.objects.get(id=especialidad_seleccionada_id)
            
            # --- INICIO DE LA LÓGICA CORREGIDA ---
            
            # Obtenemos el grupo de la especialidad seleccionada
            grupo_seleccionado = especialidad_seleccionada.grupo
            
            # 1. Preparamos una consulta para los cursos propios de la especialidad
            query_cursos_propios = Q(especialidad=especialidad_seleccionada)
            
            # 2. Preparamos otra para los cursos generales del mismo grupo
            query_cursos_generales_del_grupo = Q(tipo_curso='GENERAL', especialidad__grupo=grupo_seleccionado)
            
            # 3. Unimos las consultas: tráeme los cursos que cumplan la condición 1 O la condición 2
            cursos_asignados = Curso.objects.filter(
                query_cursos_propios | query_cursos_generales_del_grupo,
                semestre=semestre_activo,
                dia__isnull=False
            ).distinct().order_by('semestre_cursado')
            
            # --- FIN DE LA LÓGICA CORREGIDA ---

            # El resto de la función que construye la parrilla no necesita cambios
            semestres_cursados = sorted(list(cursos_asignados.values_list('semestre_cursado', flat=True).distinct()))
            franjas_horarias = list(FranjaHoraria.objects.order_by('hora_inicio'))
            dias_semana = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes']
            
            for semestre_num in semestres_cursados:
                grid = {}
                for franja in franjas_horarias:
                    grid[franja.id] = {dia: None for dia in dias_semana}

                cursos_del_semestre = cursos_asignados.filter(semestre_cursado=semestre_num)
                for curso in cursos_del_semestre:
                    try:
                        franja_inicio_obj = next(f for f in franjas_horarias if f.hora_inicio == curso.horario_inicio)
                        start_index = franjas_horarias.index(franja_inicio_obj)
                        grid[franja_inicio_obj.id][curso.dia] = curso
                        for i in range(1, curso.duracion_bloques):
                            if (start_index + i) < len(franjas_horarias):
                                franja_ocupada = franjas_horarias[start_index + i]
                                grid[franja_ocupada.id][curso.dia] = 'OCUPADO'
                    except (StopIteration, TypeError, AttributeError):
                        continue
                horarios_por_semestre_cursado[semestre_num] = grid

        except Especialidad.DoesNotExist:
            especialidad_seleccionada = None

    context = {
        'semestre_activo': semestre_activo,
        'especialidades': especialidades,
        'especialidad_seleccionada': especialidad_seleccionada,
        'horarios_por_semestre_cursado': horarios_por_semestre_cursado,
        'franjas_horarias': FranjaHoraria.objects.all().order_by('hora_inicio'),
        'dias_semana': ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes'],
    }
    return render(request, 'vista_publica_horarios.html', context)

@login_required
def ver_notificaciones(request):
    # Get all notifications for the user
    notificaciones = request.user.notificaciones.all()

    context = {
        'notificaciones': notificaciones
    }

    # Mark all unread notifications as read
    request.user.notificaciones.filter(leido=False).update(leido=True)

    return render(request, 'ver_notificaciones.html', context)

@login_required
def ver_anuncios(request):
    anuncios = Anuncio.objects.all()
    context = {
        'anuncios': anuncios
    }
    return render(request, 'ver_anuncios.html', context)

@staff_member_required
def generar_ficha_docente(request, docente_id):
    docente = get_object_or_404(Docente, id=docente_id)
    semestre_activo = Semestre.objects.filter(estado='ACTIVO').first()
    if not semestre_activo:
        messages.error(request, "No hay un semestre activo para generar la ficha.")
        return redirect('perfil')

    pdf = exportar_ficha_docente_pdf(docente, semestre_activo)

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="ficha_integral_{docente.username}.pdf"'
    return response


# ========= VISTAS PARA RESERVA DE EQUIPOS =========

class DisponibilidadEquiposView(LoginRequiredMixin, TemplateView):
    template_name = 'reservas/disponibilidad.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        fecha_str = self.request.GET.get('fecha', timezone.now().strftime('%Y-%m-%d'))
        try:
            fecha_seleccionada = timezone.datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            fecha_seleccionada = timezone.now().date()

        franjas = FranjaHoraria.objects.all().order_by('hora_inicio')
        activos = Activo.objects.filter(estado__in=['DISPONIBLE', 'ASIGNADO'])

        # Obtenemos todas las reservas activas para la fecha seleccionada para optimizar
        reservas_activas = set(
            Reserva.objects.filter(
                fecha_reserva=fecha_seleccionada,
                estado__in=['RESERVADO', 'EN_USO']
            ).values_list('activo_id', 'franja_horaria_id')
        )

        grid = []
        for activo in activos:
            row = {'activo': activo, 'franjas': []}
            for franja in franjas:
                esta_reservado = (activo.id, franja.id) in reservas_activas
                row['franjas'].append({'franja': franja, 'reservado': esta_reservado})
            grid.append(row)

        context['grid'] = grid
        context['franjas'] = franjas
        context['fecha_seleccionada'] = fecha_seleccionada
        context['fecha_seleccionada_str'] = fecha_seleccionada.strftime('%Y-%m-%d')

        return context

    def post(self, request, *args, **kwargs):
        try:
            activo_id = request.POST.get('activo_id')
            franja_id = request.POST.get('franja_id')
            fecha_str = request.POST.get('fecha')

            activo = get_object_or_404(Activo, pk=activo_id)
            franja = get_object_or_404(FranjaHoraria, pk=franja_id)
            fecha = timezone.datetime.strptime(fecha_str, '%Y-%m-%d').date()
            docente = request.user

            # Doble chequeo de disponibilidad y fecha
            if fecha < timezone.now().date():
                messages.error(request, 'No se pueden hacer reservas para fechas pasadas.')
            elif Reserva.objects.filter(activo=activo, franja_horaria=franja, fecha_reserva=fecha, estado__in=['RESERVADO', 'EN_USO']).exists():
                messages.error(request, 'Este equipo ya no está disponible en la franja seleccionada. Alguien más lo reservó.')
            else:
                Reserva.objects.create(
                    activo=activo,
                    franja_horaria=franja,
                    fecha_reserva=fecha,
                    docente=docente
                )
                messages.success(request, f'Equipo "{activo.nombre}" reservado con éxito para el {fecha} a las {franja.hora_inicio.strftime("%H:%M")}.')

        except (ValueError, Activo.DoesNotExist, FranjaHoraria.DoesNotExist) as e:
            messages.error(request, f'Ocurrió un error al procesar la reserva: {e}')

        return redirect('reservas:disponibilidad' + f'?fecha={fecha_str}')

class MisReservasView(LoginRequiredMixin, ListView):
    model = Reserva
    template_name = 'reservas/mis_reservas.html'
    context_object_name = 'reservas'
    paginate_by = 10

    def get_queryset(self):
        return Reserva.objects.filter(docente=self.request.user).order_by('-fecha_reserva', '-franja_horaria__hora_inicio')

@login_required
def cancelar_reserva(request, pk):
    reserva = get_object_or_404(Reserva, pk=pk, docente=request.user)

    hora_inicio_reserva = timezone.make_aware(
        timezone.datetime.combine(reserva.fecha_reserva, reserva.franja_horaria.hora_inicio)
    )
    if reserva.estado == 'RESERVADO' and hora_inicio_reserva > timezone.now():
        reserva.estado = 'CANCELADO'
        reserva.save()
        messages.success(request, 'La reserva ha sido cancelada.')
    else:
        messages.error(request, 'No es posible cancelar esta reserva (ya está en curso, finalizada o fue cancelada).')

    return redirect('reservas:mis_reservas')


# ========= VISTAS PARA INVENTARIO (ACTIVOS) =========

class ActivoListView(LoginRequiredMixin, ListView):
    model = Activo
    template_name = 'inventario/lista_activos.html'
    context_object_name = 'activos'
    paginate_by = 15

    def get_queryset(self):
        queryset = super().get_queryset().select_related('tipo', 'asignado_a')
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(nombre__icontains=query) |
                Q(codigo_patrimonial__icontains=query) |
                Q(asignado_a__first_name__icontains=query) |
                Q(asignado_a__last_name__icontains=query)
            )
        return queryset

class ActivoDetailView(LoginRequiredMixin, DetailView):
    model = Activo
    template_name = 'inventario/detalle_activo.html'
    context_object_name = 'activo'

class ActivoCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Activo
    template_name = 'inventario/form_activo.html'
    fields = ['nombre', 'descripcion', 'codigo_patrimonial', 'tipo', 'estado', 'asignado_a', 'fecha_adquisicion', 'observaciones']
    success_url = reverse_lazy('inventario:lista')
    permission_required = 'core.add_activo'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Crear Nuevo Activo'
        return context

class ActivoUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Activo
    template_name = 'inventario/form_activo.html'
    fields = ['nombre', 'descripcion', 'codigo_patrimonial', 'tipo', 'estado', 'asignado_a', 'fecha_adquisicion', 'observaciones']
    success_url = reverse_lazy('inventario:lista')
    permission_required = 'core.change_activo'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Editar Activo'
        return context

class ActivoDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Activo
    template_name = 'inventario/confirmar_eliminacion_activo.html'
    success_url = reverse_lazy('inventario:lista')
    permission_required = 'core.delete_activo'
