from django.utils import timezone
from datetime import date, timedelta

from ..models import Docente, Asistencia, Curso, ConfiguracionInstitucion, Justificacion, AsistenciaDiaria, Semestre, BloqueCurso
from collections import defaultdict

def _generar_datos_reporte_asistencia(filters):
    """
    Función auxiliar optimizada para generar los datos del reporte de asistencia,
    adaptada para usar el modelo BloqueCurso.
    """
    # 1. OBTENER Y PARSEAR FILTROS
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

    # 2. PRE-CARGAR DATOS DE FORMA EFICIENTE
    docentes_qs = Docente.objects.order_by('last_name', 'first_name')
    if especialidad_id:
        docentes_qs = docentes_qs.filter(especialidades__id=especialidad_id)
    if docente_id:
        docentes_qs = docentes_qs.filter(id=docente_id)

    semestre_activo = Semestre.objects.filter(estado='ACTIVO').first()
    if not semestre_activo:
        return [], docentes_qs.count()

    asistencias_en_rango = Asistencia.objects.filter(fecha__range=[fecha_inicio, fecha_fin]).select_related('docente', 'curso')
    asistencias_diarias_en_rango = AsistenciaDiaria.objects.filter(fecha__range=[fecha_inicio, fecha_fin])

    # La consulta principal ahora es sobre BloqueCurso
    bloques_programados_qs = BloqueCurso.objects.filter(curso__semestre=semestre_activo).select_related('curso__docente')

    if curso_id:
        bloques_programados_qs = bloques_programados_qs.filter(curso_id=curso_id)
        if not docente_id:
            docentes_del_curso_ids = bloques_programados_qs.values_list('curso__docente_id', flat=True).distinct()
            docentes_qs = docentes_qs.filter(id__in=docentes_del_curso_ids)

    asistencias_map = defaultdict(list)
    for asis in asistencias_en_rango:
        asistencias_map[(asis.docente_id, asis.fecha)].append(asis)

    asistencias_diarias_map = {(ad.docente_id, ad.fecha): ad for ad in asistencias_diarias_en_rango}

    # El mapa ahora es de bloques por día
    bloques_por_dia_map = defaultdict(list)
    for bloque in bloques_programados_qs:
        bloques_por_dia_map[(bloque.curso.docente_id, bloque.dia)].append(bloque)

    justificaciones_aprobadas = Justificacion.objects.filter(estado='APROBADO', fecha_inicio__lte=fecha_fin, fecha_fin__gte=fecha_inicio)
    justificaciones_set = set()
    for just in justificaciones_aprobadas:
        d = just.fecha_inicio
        while d <= just.fecha_fin:
            justificaciones_set.add((just.docente_id, d))
            d += timedelta(days=1)

    # 3. CONSTRUIR EL REPORTE
    reporte_final = []
    configuracion = ConfiguracionInstitucion.load()
    limite_tardanza = timedelta(minutes=configuracion.tiempo_limite_tardanza or 10)
    dias_del_rango = [fecha_inicio + timedelta(days=i) for i in range((fecha_fin - fecha_inicio).days + 1)]
    dias_semana_map = {0: 'Lunes', 1: 'Martes', 2: 'Miércoles', 3: 'Jueves', 4: 'Viernes', 5: 'Sábado', 6: 'Domingo'}

    for docente in docentes_qs:
        for dia_actual in dias_del_rango:
            dia_semana_str = dias_semana_map[dia_actual.weekday()]

            bloques_del_dia = bloques_por_dia_map.get((docente.id, dia_semana_str), [])

            if not bloques_del_dia:
                if estado_filtro == 'todos':
                    reporte_final.append({'docente': docente, 'fecha': dia_actual, 'estado': 'No Requerido', 'asistencias': [], 'asistencia_diaria': None})
                continue

            asistencias_del_dia = asistencias_map.get((docente.id, dia_actual), [])
            estado_dia = 'Falta'
            tiene_tardanza = False

            if asistencias_del_dia:
                estado_dia = 'Presente'
                for asis in asistencias_del_dia:
                    asis.es_tardanza = False
                    # Encontrar el bloque correspondiente a la asistencia
                    # La lógica es encontrar el último bloque que empezó ANTES de la hora de entrada.
                    bloque_asistido = None
                    for b in bloques_del_dia:
                        if b.curso_id == asis.curso_id and b.hora_inicio <= asis.hora_entrada.time():
                            if bloque_asistido is None or b.hora_inicio > bloque_asistido.hora_inicio:
                                bloque_asistido = b

                    if asis.hora_entrada and bloque_asistido:
                        hora_inicio_dt = timezone.make_aware(timezone.datetime.combine(dia_actual, bloque_asistido.hora_inicio))
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
                    'asistencias': asistencias_del_dia, 'asistencia_diaria': asistencia_diaria
                })

    return reporte_final, docentes_qs.count()
