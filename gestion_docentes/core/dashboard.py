from django.urls import reverse
from .models import PersonalDocente, Semestre, Curso, Documento, Justificacion

def dashboard_callback(request, context):
    """
    Callback to prepare custom variables for the dashboard template.
    """
    # --- KPI Calculations ---
    docentes_activos = PersonalDocente.objects.filter(is_active=True).count()
    semestre_actual = Semestre.objects.filter(estado='ACTIVO').first()
    cursos_semestre_actual = Curso.objects.filter(semestre=semestre_actual).count() if semestre_actual else 0
    documentos_pendientes = Documento.objects.filter(estado__in=['RECIBIDO', 'EN_REVISION']).count()
    justificaciones_pendientes = Justificacion.objects.filter(estado='PENDIENTE').count()

    # --- Data for Tracker Component ---
    tracker_data = [
        {
            "title": "Docentes Activos",
            "metric": docentes_activos,
            "icon": "group",
            "link": reverse("admin:core_personaldocente_changelist"),
        },
        {
            "title": "Cursos del Semestre",
            "metric": cursos_semestre_actual,
            "icon": "book",
            "link": reverse("admin:core_curso_changelist"),
        },
        {
            "title": "Documentos Pendientes",
            "metric": documentos_pendientes,
            "icon": "folder_open",
            "link": reverse("admin:core_documento_changelist") + "?estado__exact=RECIBIDO",
        },
        {
            "title": "Justificaciones Pendientes",
            "metric": justificaciones_pendientes,
            "icon": "assignment_late",
            "link": reverse("admin:core_justificacion_changelist") + "?estado__exact=PENDIENTE",
        },
    ]

    # --- Data for Tables ---
    ultimos_documentos = Documento.objects.filter(estado__in=['RECIBIDO', 'EN_REVISION']).order_by('-fecha_subida')[:5]
    ultimas_justificaciones = Justificacion.objects.filter(estado='PENDIENTE').order_by('-fecha_creacion')[:5]

    context.update({
        "tracker_data": tracker_data,
        "ultimos_documentos": ultimos_documentos,
        "ultimas_justificaciones": ultimas_justificaciones,
        "semestre_nombre": semestre_actual.nombre if semestre_actual else "Ninguno"
    })

    return context
