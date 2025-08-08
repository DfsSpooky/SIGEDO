from django.shortcuts import render
from django.contrib.auth.decorators import login_required, permission_required
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count
import json

from core.models import Docente, Curso, Justificacion, Documento, Asistencia

@login_required
def dashboard(request):
    today = timezone.now().date()
    start_of_week = today - timedelta(days=today.weekday())

    # KPIs
    kpis = {
        'total_docentes': Docente.objects.filter(is_staff=False, is_active=True).count(),
        'cursos_hoy': Curso.objects.filter(dia=today.strftime('%A').capitalize(), semestre__estado='ACTIVO').count(),
        'justificaciones_pendientes': Justificacion.objects.filter(estado='PENDIENTE').count(),
        'documentos_observados': Documento.objects.filter(estado='OBSERVADO').count(),
    }

    # Chart Data
    asistencia_labels = [(start_of_week + timedelta(days=i)).strftime('%a %d') for i in range(7)]
    asistencias_semana = Asistencia.objects.filter(fecha__range=[start_of_week, start_of_week + timedelta(days=6)])
    presentes_por_dia = [asistencias_semana.filter(fecha=start_of_week + timedelta(days=i)).values('docente').distinct().count() for i in range(7)]

    asistencia_semanal_data = {
        'labels': asistencia_labels,
        'presentes': presentes_por_dia,
        'faltas': [kpis['total_docentes'] - p for p in presentes_por_dia],
        'tardanzas': [0] * 7, # Simplificado por ahora
    }

    doc_status_counts = Documento.objects.values('estado').annotate(count=Count('id')).order_by('estado')
    documentos_status_data = {
        'labels': [item['get_estado_display'] for item in Documento.ESTADOS_DOCUMENTO if Documento.objects.filter(estado=item[0]).exists()],
        'data': [doc_status_counts.filter(estado=item[0]).first()['count'] if doc_status_counts.filter(estado=item[0]).exists() else 0 for item in Documento.ESTADOS_DOCUMENTO if Documento.objects.filter(estado=item[0]).exists()],
    }

    context = {
        'kpis': kpis,
        'charts_data': {
            'asistencia_semanal_json': json.dumps(asistencia_semanal_data),
            'documentos_status_json': json.dumps(documentos_status_data),
        },
        'justificaciones_recientes': Justificacion.objects.filter(estado='PENDIENTE').order_by('-fecha_creacion')[:5],
        'documentos_recientes': Documento.objects.filter(estado='EN_REVISION').order_by('-fecha_subida')[:5],
    }

    return render(request, 'panel/dashboard.html', context)
