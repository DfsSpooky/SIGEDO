from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from datetime import time, timedelta, date
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
import json
import base64
from django.core.files.base import ContentFile
import random
import io
from django.db import models
from django.db.models import Q
from django.templatetags.static import static
from django.core.serializers.json import DjangoJSONEncoder

# Importamos todos los modelos, incluyendo los nuevos
from .models import (
    Docente, Curso, Documento, Asistencia, Carrera, SolicitudIntercambio,
    TipoDocumento, AsistenciaDiaria, PersonalDocente, ConfiguracionInstitucion,
    Semestre, DiaEspecial, Especialidad, FranjaHoraria, VersionDocumento, Anuncio,
    Notificacion
)
from .forms import DocumentoForm, SolicitudIntercambioForm, VersionDocumentoForm
from .utils.exports import exportar_reporte_excel, exportar_reporte_pdf
from .utils.encryption import decrypt_id
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
    
    context = {
        'asistencias_count': asistencias_count,
        'documentos_observados_count': documentos_observados_count,
        'cursos_hoy_count': cursos_hoy_count,
        'proximo_curso': proximo_curso,
        'actividad_reciente': actividad_reciente[:3], # Pasamos solo los 3 últimos eventos
    }
    return render(request, 'dashboard.html', context)

@staff_member_required
def admin_dashboard(request):
    # This is a placeholder for the admin dashboard.
    # We can add context data here later (e.g., stats, recent activity).
    context = {
        'welcome_message': 'Bienvenido al Panel de Control de Administración',
    }
    return render(request, 'admin_dashboard.html', context)

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
            
            cursos_hoy = Curso.objects.filter(docente=docente, dia=dia_actual_str, semestre=semestre_activo)
            
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
                })

            response_data = {
                'status': 'success',
                'name': f'{docente.first_name} {docente.last_name}',
                'dni': docente.dni,
                'photoUrl': photo_url,
                'isDailyAttendanceMarked': is_daily_marked,
                'courses': courses_data
            }
            return JsonResponse(response_data)
            
        except Docente.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'QR no válido o docente no encontrado.'}, status=404)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)


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
                
                # Esta función ahora encontrará el registro correcto porque la fecha coincide.
                asistencia, created = Asistencia.objects.get_or_create(docente=docente, curso=curso, fecha=today)

                if action_type == 'course_entry' and not asistencia.hora_entrada:
                    asistencia.hora_entrada = now
                    asistencia.foto_entrada = photo_file
                    
                    duracion_minima_minutos = (curso.duracion_bloques * 50) - 15 
                    if duracion_minima_minutos < 15:
                        duracion_minima_minutos = 15
                    
                    asistencia.hora_salida_permitida = now + timedelta(minutes=duracion_minima_minutos)
                    asistencia.save()
                
                elif action_type == 'course_exit' and asistencia.hora_entrada and not asistencia.hora_salida:
                    if asistencia.hora_salida_permitida and now >= asistencia.hora_salida_permitida:
                        asistencia.hora_salida = now
                        asistencia.foto_salida = photo_file
                        asistencia.save()
            
            return JsonResponse({'status': 'success', 'message': 'Asistencia registrada correctamente.'})

        except Exception as e:
            print(f"Error en mark_attendance_kiosk: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)


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
def reporte_asistencia(request):
    # 1. MANEJO DE FILTROS Y FECHAS
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')
    estado_filtro = request.GET.get('estado', 'todos')
    curso_id = request.GET.get('curso')
    especialidad_id = request.GET.get('especialidad')

    try:
        fecha_inicio = timezone.datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date() if fecha_inicio_str else date.today()
        fecha_fin = timezone.datetime.strptime(fecha_fin_str, '%Y-%m-%d').date() if fecha_fin_str else date.today()
    except ValueError:
        fecha_inicio = fecha_fin = date.today()

    # 2. OBTENER QUERYSETS BASE
    docentes_qs = Docente.objects.all().order_by('last_name', 'first_name')
    if especialidad_id:
        docentes_qs = docentes_qs.filter(especialidades__id=especialidad_id)

    # Pre-fetch de datos relacionados para optimizar
    asistencias_qs = Asistencia.objects.filter(
        fecha__range=[fecha_inicio, fecha_fin]
    ).select_related('docente', 'curso')

    semestre_activo = Semestre.objects.filter(estado='ACTIVO').first()
    cursos_programados_qs = Curso.objects.filter(semestre=semestre_activo, dia__isnull=False)
    if curso_id:
        cursos_programados_qs = cursos_programados_qs.filter(id=curso_id)
        # Si filtramos por curso, filtramos también los docentes que lo dictan
        docente_del_curso_id = cursos_programados_qs.first().docente_id
        docentes_qs = docentes_qs.filter(id=docente_del_curso_id)

    # 3. PROCESAMIENTO DE DATOS Y CÁLCULO DE ESTADO
    reporte_final = []
    configuracion = ConfiguracionInstitucion.load()
    limite_tardanza = configuracion.tiempo_limite_tardanza or timedelta(minutes=10) # Default de 10 min

    dias_del_rango = [fecha_inicio + timedelta(days=i) for i in range((fecha_fin - fecha_inicio).days + 1)]
    dias_semana_map = {0: 'Lunes', 1: 'Martes', 2: 'Miércoles', 3: 'Jueves', 4: 'Viernes', 5: 'Sábado', 6: 'Domingo'}

    for docente in docentes_qs:
        for dia_actual in dias_del_rango:
            dia_semana_str = dias_semana_map[dia_actual.weekday()]

            # Cursos que el docente DEBÍA dictar ese día
            cursos_del_dia = cursos_programados_qs.filter(docente=docente, dia=dia_semana_str)

            # Asistencias que el docente MARCÓ ese día
            asistencias_del_dia = asistencias_qs.filter(docente=docente, fecha=dia_actual)

            estado_dia = 'No Requerido'
            tiene_tardanza = False

            if cursos_del_dia.exists():
                # Si tenía cursos, por defecto es "Falta" hasta que se demuestre lo contrario
                estado_dia = 'Falta'

                if asistencias_del_dia.exists():
                    # Si marcó al menos una asistencia, ya no es "Falta"
                    estado_dia = 'Presente'

                    # Verificamos si alguna de sus asistencias fue tardía
                    for asis in asistencias_del_dia:
                        if asis.hora_entrada and asis.curso.horario_inicio:
                            hora_entrada_dt = timezone.datetime.combine(dia_actual, asis.hora_entrada.time())
                            hora_inicio_dt = timezone.datetime.combine(dia_actual, asis.curso.horario_inicio)
                            if (hora_entrada_dt - hora_inicio_dt) > timedelta(minutes=limite_tardanza):
                                asis.es_tardanza = True
                                tiene_tardanza = True
                            else:
                                asis.es_tardanza = False

                    if tiene_tardanza:
                        estado_dia = 'Tardanza'

            # Aplicar el filtro de ESTADO
            if estado_filtro != 'todos' and estado_dia.lower() != estado_filtro:
                continue

            # Solo añadir al reporte si no es "No Requerido" o si se muestran todos
            if estado_dia != 'No Requerido' or estado_filtro == 'todos':
                reporte_final.append({
                    'docente': docente,
                    'fecha': dia_actual,
                    'estado': estado_dia,
                    'asistencias': asistencias_del_dia,
                    'cursos_programados': cursos_del_dia
                })
    
    # 4. CONTADORES Y PAGINACIÓN
    total_docentes = docentes_qs.count()
    # Los contadores ahora se basan en los datos procesados, son más precisos
    presentes_count = len([r for r in reporte_final if r['estado'] == 'Presente'])
    ausentes_count = len([r for r in reporte_final if r['estado'] == 'Falta'])

    # Paginación
    paginator = Paginator(reporte_final, 20)
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.get_page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.get_page(1)
    except EmptyPage:
        page_obj = paginator.get_page(paginator.num_pages)

    # Preparamos los parámetros de la URL para la paginación, excluyendo 'page'
    query_params = request.GET.copy()
    if 'page' in query_params:
        del query_params['page']

    context = {
        'page_obj': page_obj,
        'reporte_data': page_obj.object_list,
        'total_docentes': total_docentes,
        'presentes_count': presentes_count,
        'ausentes_count': ausentes_count,
        'cursos': Curso.objects.all(),
        'especialidades': Especialidad.objects.all(),
        'fecha_inicio': fecha_inicio.strftime('%Y-%m-%d'),
        'fecha_fin': fecha_fin.strftime('%Y-%m-%d'),
        'estado': estado_filtro,
        'curso_id': curso_id,
        'especialidad_id': especialidad_id,
        'filter_params': query_params.urlencode(),
    }

    return render(request, 'reporte_asistencia.html', context)

@staff_member_required
def api_get_report_chart_data(request):
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')
    especialidad_id = request.GET.get('especialidad')
    curso_id = request.GET.get('curso')

    try:
        fecha_inicio = timezone.datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
        fecha_fin = timezone.datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        today = date.today()
        fecha_inicio = today
        fecha_fin = today

    # Base queryset
    asistencias_qs = Asistencia.objects.filter(fecha__range=[fecha_inicio, fecha_fin])
    docentes_qs = Docente.objects.all()

    if especialidad_id:
        docentes_qs = docentes_qs.filter(especialidades__id=especialidad_id)
        asistencias_qs = asistencias_qs.filter(docente__in=docentes_qs)

    if curso_id:
        asistencias_qs = asistencias_qs.filter(curso_id=curso_id)

    # Data for Bar Chart (daily breakdown)
    from django.db.models.functions import TruncDate
    from django.db.models import Count

    daily_data = asistencias_qs.filter(curso__isnull=True).annotate(
        dia=TruncDate('fecha')
    ).values('dia').annotate(
        present_count=Count('id')
    ).order_by('dia')

    # Data for Pie Chart (total breakdown)
    total_docentes = docentes_qs.count()
    total_presentes = asistencias_qs.filter(curso__isnull=True).values('docente').distinct().count()
    total_ausentes = total_docentes - total_presentes

    # Lateness calculation
    configuracion = ConfiguracionInstitucion.load()
    limite_tardanza = configuracion.tiempo_limite_tardanza
    from django.db.models import F, ExpressionWrapper, DurationField
    asistencias_tardias_count = asistencias_qs.filter(
        curso__horario_inicio__isnull=False, hora_entrada__isnull=False
    ).annotate(
        lateness=ExpressionWrapper(F('hora_entrada') - F('curso__horario_inicio'), output_field=DurationField())
    ).filter(lateness__gt=timedelta(minutes=limite_tardanza)).values('docente').distinct().count()

    chart_data = {
        'bar_chart': {
            'labels': [d['dia'].strftime('%d/%m') for d in daily_data],
            'presentes': [d['present_count'] for d in daily_data],
            'ausentes': [total_docentes - d['present_count'] for d in daily_data]
        },
        'pie_chart': {
            'presentes': total_presentes,
            'ausentes': total_ausentes,
            'tardanzas': asistencias_tardias_count
        }
    }

    return JsonResponse(chart_data)


@staff_member_required
def detalle_asistencia_docente_ajax(request, docente_id):
    """Devuelve los detalles de asistencia de un docente en formato JSON."""
    try:
        docente = Docente.objects.get(pk=docente_id)
        asistencias_generales = Asistencia.objects.filter(docente=docente, curso__isnull=True).order_by('-fecha')
        asistencias_cursos = Asistencia.objects.filter(docente=docente, curso__isnull=False).order_by('-fecha')
        
        data = {
            'docente': {
                'nombre_completo': f'{docente.first_name} {docente.last_name}',
                'dni': docente.dni,
                'foto_url': docente.foto.url if docente.foto else None,
            },
            'asistencias_generales': [
                {
                    'fecha': asis.fecha,
                    'hora_entrada': asis.hora_entrada.strftime('%H:%M') if asis.hora_entrada else None,
                    'hora_salida': asis.hora_salida.strftime('%H:%M') if asis.hora_salida else None,
                    'foto_entrada_url': asis.foto_entrada.url if asis.foto_entrada else None,
                }
                for asis in asistencias_generales
            ],
            'asistencias_cursos': [
                {
                    'curso': asis.curso.nombre,
                    'fecha': asis.fecha,
                    'hora_entrada': asis.hora_entrada.strftime('%H:%M') if asis.hora_entrada else None,
                    'hora_salida': asis.hora_salida.strftime('%H:%M') if asis.hora_salida else None,
                    'foto_entrada_url': asis.foto_entrada.url if asis.foto_entrada else None,
                    'foto_salida_url': asis.foto_salida.url if asis.foto_salida else None,
                }
                for asis in asistencias_cursos
            ]
        }
        return JsonResponse(data)
    except Docente.DoesNotExist:
        return JsonResponse({'error': 'Docente no encontrado'}, status=404)
        
@staff_member_required
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
    franjas_horarias_json = json.dumps(list(FranjaHoraria.objects.order_by('hora_inicio').values('id', 'hora_inicio', 'hora_fin', 'turno')), cls=DjangoJSONEncoder)
    dias_semana_json = json.dumps(['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes'])

    context = {
        'semestre_activo': semestre_activo,
        'especialidades': Especialidad.objects.all(),
        'franjas_horarias_json': franjas_horarias_json,
        'dias_semana_json': dias_semana_json,
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
                    return JsonResponse({'status': 'error', 'message': f'Conflicto de Disponibilidad del docente.'}, status=400)
                conflicto_docente = Curso.objects.filter(docente=docente, semestre=semestre, dia=dia, horario_inicio=franja.hora_inicio).exclude(pk=curso.id).first()
                if conflicto_docente:
                    return JsonResponse({'status': 'error', 'message': f'Conflicto: El docente ya dicta "{conflicto_docente.nombre}" en este horario.'}, status=400)

            # 2. Validar Cruce de GRUPO
            grupo = curso.especialidad.grupo if curso.especialidad else None
            if grupo:
                q_conflicto = models.Q(especialidad__grupo=grupo, semestre_cursado=curso.semestre_cursado, dia=dia, horario_inicio__in=[f.hora_inicio for f in franjas_a_ocupar])
                if curso.tipo_curso == 'ESPECIALIDAD':
                    conflicto_grupo = Curso.objects.filter(q_conflicto, tipo_curso='GENERAL').first()
                    if conflicto_grupo: return JsonResponse({'status': 'error', 'message': f'Conflicto de Grupo: El curso general "{conflicto_grupo.nombre}" ya está programado.'}, status=400)
                else: # GENERAL
                    conflicto_grupo = Curso.objects.filter(q_conflicto, tipo_curso='ESPECIALIDAD').first()
                    if conflicto_grupo: return JsonResponse({'status': 'error', 'message': f'Conflicto de Grupo: El curso "{conflicto_grupo.nombre}" ({conflicto_grupo.especialidad.nombre}) ya está programado.'}, status=400)

            # Si pasa todo, asignamos
            curso.dia = dia; curso.horario_inicio = franja_inicio.hora_inicio; curso.horario_fin = franjas_a_ocupar[-1].hora_fin; curso.save()
            return JsonResponse({'status': 'success', 'message': 'Curso asignado con éxito.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

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

            return JsonResponse({'status': 'success', 'message': 'Curso devuelto a la lista de pendientes.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)


@staff_member_required
def api_get_teacher_conflicts(request):
    curso_id = request.GET.get('curso_id')
    if not curso_id:
        return JsonResponse({'status': 'error', 'message': 'Falta el ID del curso.'}, status=400)

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

        return JsonResponse({'status': 'success', 'conflicts': conflictos})

    except Curso.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Curso no encontrado.'}, status=404)
    

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

        return JsonResponse({
            'status': 'success',
            'message': message,
            'plannerData': planner_data
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@staff_member_required
def api_get_cursos_no_asignados(request):
    try:
        especialidad_id = request.GET.get('especialidad_id')
        semestre_cursado = request.GET.get('semestre_cursado')
        planner_data = _get_planner_data(especialidad_id, semestre_cursado)
        return JsonResponse(planner_data)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=404)


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