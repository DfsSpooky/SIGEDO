from django.utils import timezone
from datetime import date, timedelta

from ..models import Docente, Asistencia, Curso, ConfiguracionInstitucion, Justificacion, AsistenciaDiaria, Semestre

def _generar_datos_reporte_asistencia(filters):
    """
    Función auxiliar para generar los datos del reporte de asistencia.
    Esta función centraliza la lógica para ser reutilizada por la vista principal y las exportaciones.
    """
    fecha_inicio_str = filters.get('fecha_inicio')
    fecha_fin_str = filters.get('fecha_fin')
    estado_filtro = filters.get('estado', 'todos')
    curso_id = filters.get('curso')
    especialidad_id = filters.get('especialidad')
    docente_id = filters.get('docente')

    try:
        fecha_inicio = timezone.datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date() if fecha_inicio_str else date.today()
        fecha_fin = timezone.datetime.strptime(fecha_fin_str, '%Y-%m-%d').date() if fecha_fin_str else date.today()
    except (ValueError, TypeError):
        fecha_inicio = fecha_fin = date.today()

    docentes_qs = Docente.objects.all().order_by('last_name', 'first_name')
    if especialidad_id:
        docentes_qs = docentes_qs.filter(especialidades__id=especialidad_id)
    if docente_id:
        docentes_qs = docentes_qs.filter(id=docente_id)

    asistencias_qs = Asistencia.objects.filter(fecha__range=[fecha_inicio, fecha_fin]).select_related('docente', 'curso')
    asistencias_diarias_map = {
        (ad.docente_id, ad.fecha): ad for ad in AsistenciaDiaria.objects.filter(fecha__range=[fecha_inicio, fecha_fin]).select_related('docente')
    }

    semestre_activo = Semestre.objects.filter(estado='ACTIVO').first()
    cursos_programados_qs = Curso.objects.filter(semestre=semestre_activo, dia__isnull=False)
    if curso_id:
        cursos_programados_qs = cursos_programados_qs.filter(id=curso_id)
        if not docente_id:
            docente_del_curso_id = cursos_programados_qs.first().docente_id
            docentes_qs = docentes_qs.filter(id=docente_del_curso_id)

    reporte_final = []
    configuracion = ConfiguracionInstitucion.load()
    limite_tardanza = timedelta(minutes=configuracion.tiempo_limite_tardanza or 10)

    justificaciones_aprobadas = Justificacion.objects.filter(estado='APROBADO', fecha_inicio__lte=fecha_fin, fecha_fin__gte=fecha_inicio)
    justificaciones_set = set()
    for just in justificaciones_aprobadas:
        d = just.fecha_inicio
        while d <= just.fecha_fin:
            justificaciones_set.add((just.docente_id, d))
            d += timedelta(days=1)

    dias_del_rango = [fecha_inicio + timedelta(days=i) for i in range((fecha_fin - fecha_inicio).days + 1)]
    dias_semana_map = {0: 'Lunes', 1: 'Martes', 2: 'Miércoles', 3: 'Jueves', 4: 'Viernes', 5: 'Sábado', 6: 'Domingo'}

    for docente in docentes_qs:
        for dia_actual in dias_del_rango:
            dia_semana_str = dias_semana_map[dia_actual.weekday()]
            cursos_del_dia = cursos_programados_qs.filter(docente=docente, dia=dia_semana_str)
            if not cursos_del_dia.exists():
                if estado_filtro == 'todos':
                    reporte_final.append({'docente': docente, 'fecha': dia_actual, 'estado': 'No Requerido', 'asistencias': [], 'cursos_programados': [], 'asistencia_diaria': None})
                continue

            asistencias_del_dia = asistencias_qs.filter(docente=docente, fecha=dia_actual)
            estado_dia = 'Falta'
            tiene_tardanza = False

            if asistencias_del_dia.exists():
                estado_dia = 'Presente'
                for asis in asistencias_del_dia:
                    asis.es_tardanza = False
                    if asis.hora_entrada and asis.curso.horario_inicio:
                        hora_inicio_dt = timezone.make_aware(timezone.datetime.combine(dia_actual, asis.curso.horario_inicio))
                        if (asis.hora_entrada - hora_inicio_dt) > limite_tardanza:
                            asis.es_tardanza = tiene_tardanza = True
                if tiene_tardanza:
                    estado_dia = 'Tardanza'

            if estado_dia == 'Falta' and (docente.id, dia_actual) in justificaciones_set:
                estado_dia = 'Justificado'

            if estado_filtro == 'todos' or estado_dia.lower() == estado_filtro:
                asistencia_diaria = asistencias_diarias_map.get((docente.id, dia_actual))
                reporte_final.append({
                    'docente': docente, 'fecha': dia_actual, 'estado': estado_dia,
                    'asistencias': asistencias_del_dia, 'cursos_programados': cursos_del_dia, 'asistencia_diaria': asistencia_diaria
                })
    return reporte_final, docentes_qs.count()
