from .models import PersonalDocente, Semestre, Curso, Documento, Justificacion

def dashboard_callback(request, context):
    """
    Callback to prepare custom variables for the dashboard template.
    """
    # KPI: Número de docentes activos
    docentes_activos = PersonalDocente.objects.filter(is_active=True).count()

    # KPI: Total de cursos en el semestre actual
    semestre_actual = Semestre.objects.filter(estado='ACTIVO').first()
    cursos_semestre_actual = 0
    if semestre_actual:
        cursos_semestre_actual = Curso.objects.filter(semestre=semestre_actual).count()

    # KPI: Documentos pendientes de revisión
    documentos_pendientes = Documento.objects.filter(estado__in=['RECIBIDO', 'EN_REVISION']).count()

    # KPI: Justificaciones por aprobar
    justificaciones_pendientes = Justificacion.objects.filter(estado='PENDIENTE').count()

    context.update({
        "docentes_activos": docentes_activos,
        "cursos_semestre_actual": cursos_semestre_actual,
        "documentos_pendientes": documentos_pendientes,
        "justificaciones_pendientes": justificaciones_pendientes,
        "semestre_nombre": semestre_actual.nombre if semestre_actual else "Ninguno"
    })

    return context
