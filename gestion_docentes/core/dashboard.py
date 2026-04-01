from django.urls import reverse

from .models import (
    ConfiguracionInstitucion,
    Curso,
    Documento,
    Justificacion,
    PersonalDocente,
    Reserva,
    Semestre,
)


def dashboard_callback(request, context):
    """
    Callback to prepare custom variables for the dashboard template.
    """
    # --- KPI Calculations ---
    docentes_activos = PersonalDocente.objects.filter(is_active=True).count()
    semestre_actual = Semestre.objects.filter(estado="ACTIVO").first()
    cursos_semestre_actual = (
        Curso.objects.filter(semestre=semestre_actual).count() if semestre_actual else 0
    )
    documentos_pendientes = Documento.objects.filter(
        estado__in=["RECIBIDO", "EN_REVISION"]
    ).count()
    justificaciones_pendientes = Justificacion.objects.filter(
        estado="PENDIENTE"
    ).count()
    reservas_activas = Reserva.objects.filter(estado__in=["PENDIENTE", "APROBADA"]).count()
    configuracion = ConfiguracionInstitucion.objects.first()
    nombre_institucion = (
        configuracion.nombre_institucion if configuracion else "Gestión de Docentes"
    )

    # --- Data for Tracker Component ---
    tracker_data = [
        {
            "title": "Docentes Activos",
            "metric": docentes_activos,
            "icon": "group",
            "color": "primary",
            "link": reverse("admin:core_personaldocente_changelist"),
            "description": "Personal docente habilitado en el sistema.",
        },
        {
            "title": "Cursos del Semestre",
            "metric": cursos_semestre_actual,
            "icon": "book",
            "color": "success",
            "link": reverse("admin:core_curso_changelist"),
            "description": "Carga académica registrada para el semestre activo.",
        },
        {
            "title": "Documentos Pendientes",
            "metric": documentos_pendientes,
            "icon": "folder_open",
            "color": "warning",
            "link": reverse("admin:core_documento_changelist")
            + "?estado__exact=RECIBIDO",
            "description": "Documentos por revisar o validar.",
        },
        {
            "title": "Justificaciones Pendientes",
            "metric": justificaciones_pendientes,
            "icon": "assignment_late",
            "color": "danger",
            "link": reverse("admin:core_justificacion_changelist")
            + "?estado__exact=PENDIENTE",
            "description": "Solicitudes que requieren respuesta.",
        },
    ]

    summary_cards = [
        {
            "label": "Semestre activo",
            "value": semestre_actual.nombre if semestre_actual else "Sin semestre",
            "tone": "slate",
        },
        {
            "label": "Reservas activas",
            "value": reservas_activas,
            "tone": "amber",
        },
        {
            "label": "Institución",
            "value": nombre_institucion,
            "tone": "blue",
        },
    ]

    # --- Data for Tables ---
    ultimos_documentos = Documento.objects.filter(
        estado__in=["RECIBIDO", "EN_REVISION"]
    ).order_by("-fecha_subida")[:5]
    ultimas_justificaciones = Justificacion.objects.filter(estado="PENDIENTE").order_by(
        "-fecha_creacion"
    )[:5]

    context.update(
        {
            "tracker_data": tracker_data,
            "ultimos_documentos": ultimos_documentos,
            "ultimas_justificaciones": ultimas_justificaciones,
            "semestre_nombre": semestre_actual.nombre if semestre_actual else "Ninguno",
            "nombre_institucion": nombre_institucion,
            "summary_cards": summary_cards,
        }
    )

    return context
