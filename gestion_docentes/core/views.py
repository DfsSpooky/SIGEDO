from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse, Http404, HttpResponse, HttpResponseRedirect
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

# Las vistas de la API del kiosco han sido movidas a core/api/views.py


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


# Las vistas de la API de reportes han sido movidas a core/api/views.py
        
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

# Las vistas de la API del planificador han sido movidas a core/api/views.py


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

        franjas_qs = FranjaHoraria.objects.all().order_by('hora_inicio')
        franjas_map = {franja.id: franja for franja in franjas_qs}
        franjas_list = list(franjas_qs)

        activos = Activo.objects.filter(estado__in=['DISPONIBLE', 'ASIGNADO'])

        reservas_activas = Reserva.objects.filter(
            fecha_reserva=fecha_seleccionada,
            estado__in=['RESERVADO', 'EN_USO']
        ).select_related('franja_horaria_inicio', 'franja_horaria_fin')

        # Usamos un diccionario para marcar las celdas ocupadas
        reservas_grid = defaultdict(bool)
        for reserva in reservas_activas:
            # Si es una reserva de un solo bloque (legado o intencional)
            if not reserva.franja_horaria_fin or reserva.franja_horaria_inicio == reserva.franja_horaria_fin:
                reservas_grid[(reserva.activo_id, reserva.franja_horaria_inicio_id)] = True
                continue

            # Para reservas de múltiples bloques
            try:
                start_index = franjas_list.index(reserva.franja_horaria_inicio)
                end_index = franjas_list.index(reserva.franja_horaria_fin)
                for i in range(start_index, end_index + 1):
                    reservas_grid[(reserva.activo_id, franjas_list[i].id)] = True
            except ValueError:
                # Si una franja no está en la lista (raro), simplemente la ignoramos
                continue

        grid = []
        for activo in activos:
            row = {'activo': activo, 'franjas': []}
            for franja in franjas_list:
                esta_reservado = reservas_grid[(activo.id, franja.id)]
                row['franjas'].append({'franja': franja, 'reservado': esta_reservado})
            grid.append(row)

        context['grid'] = grid
        context['franjas'] = franjas_list
        context['fecha_seleccionada'] = fecha_seleccionada
        context['fecha_seleccionada_str'] = fecha_seleccionada.strftime('%Y-%m-%d')
        context['turnos'] = {
            'MANANA': [f for f in franjas_list if f.turno == 'MANANA'],
            'TARDE': [f for f in franjas_list if f.turno == 'TARDE'],
            'NOCHE': [f for f in franjas_list if f.turno == 'NOCHE'],
        }

        return context

    def post(self, request, *args, **kwargs):
        fecha_str = request.POST.get('fecha')
        redirect_url = reverse('reservas:disponibilidad')
        if fecha_str:
            redirect_url += f'?fecha={fecha_str}'

        try:
            activo_id = request.POST.get('activo_id')
            franja_id_inicio = request.POST.get('franja_id_inicio')
            franja_id_fin = request.POST.get('franja_id_fin')

            if not all([activo_id, franja_id_inicio, franja_id_fin, fecha_str]):
                messages.error(request, 'Información incompleta. Por favor, seleccione un activo y un rango de horas.')
                return HttpResponseRedirect(redirect_url)

            activo = get_object_or_404(Activo, pk=activo_id)
            franja_inicio = get_object_or_404(FranjaHoraria, pk=franja_id_inicio)
            franja_fin = get_object_or_404(FranjaHoraria, pk=franja_id_fin)
            fecha = timezone.datetime.strptime(fecha_str, '%Y-%m-%d').date()
            docente = request.user

            if fecha < timezone.now().date():
                messages.error(request, 'No se pueden hacer reservas para fechas pasadas.')
                return HttpResponseRedirect(redirect_url)

            if franja_inicio.hora_inicio >= franja_fin.hora_inicio:
                messages.error(request, 'La hora de inicio debe ser anterior a la hora de fin de la reserva.')
                return HttpResponseRedirect(redirect_url)

            # Comprobar conflictos de solapamiento
            conflictos = Reserva.objects.filter(
                activo=activo,
                fecha_reserva=fecha,
                estado__in=['RESERVADO', 'EN_USO'],
                franja_horaria_inicio__hora_inicio__lt=franja_fin.hora_fin,
                franja_horaria_fin__hora_fin__gt=franja_inicio.hora_inicio
            ).exists()

            if conflictos:
                messages.error(request, 'El rango seleccionado se solapa con otra reserva existente.')
            else:
                Reserva.objects.create(
                    activo=activo,
                    franja_horaria_inicio=franja_inicio,
                    franja_horaria_fin=franja_fin,
                    fecha_reserva=fecha,
                    docente=docente
                )
                messages.success(request, f'Equipo "{activo.nombre}" reservado con éxito para el {fecha} de {franja_inicio.hora_inicio.strftime("%H:%M")} a {franja_fin.hora_fin.strftime("%H:%M")}.')

        except (ValueError, Activo.DoesNotExist, FranjaHoraria.DoesNotExist) as e:
            messages.error(request, f'Ocurrió un error al procesar la reserva: {e}')

        # Se utiliza la variable redirect_url construida al inicio del método
        # para asegurar consistencia y evitar errores.
        return HttpResponseRedirect(redirect_url)

class MisReservasView(LoginRequiredMixin, ListView):
    model = Reserva
    template_name = 'reservas/mis_reservas.html'
    context_object_name = 'reservas'
    paginate_by = 10

    def get_queryset(self):
        return Reserva.objects.filter(docente=self.request.user).order_by('-fecha_reserva', '-franja_horaria_inicio__hora_inicio')

@login_required
def cancelar_reserva(request, pk):
    reserva = get_object_or_404(Reserva, pk=pk, docente=request.user)

    hora_inicio_reserva = timezone.make_aware(
        timezone.datetime.combine(reserva.fecha_reserva, reserva.franja_horaria_inicio.hora_inicio)
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
