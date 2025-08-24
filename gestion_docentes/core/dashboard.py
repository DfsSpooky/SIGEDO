from itertools import chain
from operator import attrgetter
from django.urls import reverse
from .models import (
    PersonalDocente, Semestre, Curso, Documento, Justificacion, Reserva
)

def dashboard_callback(request, context):
    """
    Callback to prepare custom variables for the dashboard template.
    This function enriches the context for the admin dashboard with KPIs and a unified inbox.
    """
    # --- KPIs (Key Performance Indicators) ---
    docentes_activos = PersonalDocente.objects.filter(is_active=True).count()
    documentos_pendientes = Documento.objects.filter(estado__in=['RECIBIDO', 'EN_REVISION']).count()
    justificaciones_pendientes = Justificacion.objects.filter(estado='PENDIENTE').count()
    reservas_pendientes = Reserva.objects.filter(estado='PENDIENTE').count()

    semestre_actual = Semestre.objects.filter(estado='ACTIVO').first()
    cursos_semestre_actual = 0
    if semestre_actual:
        cursos_semestre_actual = Curso.objects.filter(semestre=semestre_actual).count()

    # --- Unified Inbox ---
    # Fetch the 5 most recent items of each type that require admin action.

    ultimas_justificaciones = Justificacion.objects.filter(estado='PENDIENTE').order_by('-fecha_creacion')[:5]
    ultimos_documentos = Documento.objects.filter(estado__in=['RECIBIDO', 'EN_REVISION']).order_by('-fecha_subida')[:5]
    ultimas_reservas = Reserva.objects.filter(estado='PENDIENTE').order_by('-fecha_creacion')[:5]

    # Normalize the data into a common structure for easy rendering.
    inbox_items = []

    for item in ultimas_justificaciones:
        inbox_items.append({
            'tipo': 'Justificación',
            'texto': f"{item.docente.get_full_name()} solicitó justificación.",
            'fecha': item.fecha_creacion,
            'url': reverse('admin:core_justificacion_change', args=[item.pk]),
            'icon': 'assignment_turned_in'
        })

    for item in ultimos_documentos:
        inbox_items.append({
            'tipo': 'Documento',
            'texto': f"{item.docente.get_full_name()} subió '{item.titulo}'.",
            'fecha': item.fecha_subida,
            'url': reverse('admin:core_documento_change', args=[item.pk]),
            'icon': 'folder'
        })

    for item in ultimas_reservas:
        inbox_items.append({
            'tipo': 'Reserva',
            'texto': f"{item.docente.get_full_name()} solicitó '{item.activo.nombre}'.",
            'fecha': item.fecha_creacion,
            'url': reverse('admin:core_reserva_change', args=[item.pk]),
            'icon': 'event_available'
        })

    # Sort the combined list by date, most recent first.
    inbox_items.sort(key=lambda x: x['fecha'], reverse=True)

    # --- Update Template Context ---
    context.update({
        # KPIs
        "docentes_activos": docentes_activos,
        "cursos_semestre_actual": cursos_semestre_actual,
        "documentos_pendientes": documentos_pendientes,
        "justificaciones_pendientes": justificaciones_pendientes,
        "reservas_pendientes": reservas_pendientes, # New KPI
        "semestre_nombre": semestre_actual.nombre if semestre_actual else "Ninguno",

        # Inbox
        "inbox_items": inbox_items[:10], # Pass the 10 most recent items overall
    })

    return context
