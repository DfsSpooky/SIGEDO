from jet.dashboard import modules
from jet.dashboard.dashboard import Dashboard, AppIndexDashboard

from django.utils import timezone
from datetime import timedelta
from django.db.models import Count
import json
from .models import Docente, Curso, Justificacion, Documento, Asistencia

class CustomDashboardModule(modules.DashboardModule):
    title = 'Estadísticas y Atajos'
    template = 'admin_dashboard.html'
    collapsible = False

    def init_with_context(self, context):
        super(CustomDashboardModule, self).init_with_context(context)

        today = timezone.now().date()
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)

        # KPIs
        kpis = {
            'total_docentes': Docente.objects.filter(is_staff=False, is_active=True).count(),
            'cursos_hoy': Curso.objects.filter(dia=today.strftime('%A').capitalize(), semestre__estado='ACTIVO').count(),
            'justificaciones_pendientes': Justificacion.objects.filter(estado='PENDIENTE').count(),
            'documentos_observados': Documento.objects.filter(estado='OBSERVADO').count(),
        }

        # Chart Data
        asistencia_labels = [(start_of_week + timedelta(days=i)).strftime('%a %d') for i in range(7)]
        asistencias_semana = Asistencia.objects.filter(fecha__range=[start_of_week, end_of_week])
        presentes_por_dia = [asistencias_semana.filter(fecha=start_of_week + timedelta(days=i)).values('docente').distinct().count() for i in range(7)]
        faltas_por_dia = [0] * 7
        tardanzas_por_dia = [0] * 7

        asistencia_semanal_data = {
            'labels': asistencia_labels, 'presentes': presentes_por_dia,
            'faltas': faltas_por_dia, 'tardanzas': tardanzas_por_dia,
        }

        doc_status_counts = Documento.objects.values('estado').annotate(count=Count('id')).order_by('estado')
        documentos_status_data = {
            'labels': [item['estado'] for item in doc_status_counts],
            'data': [item['count'] for item in doc_status_counts],
        }

        # Quick Access Lists
        justificaciones_recientes = Justificacion.objects.filter(estado='PENDIENTE').order_by('-fecha_creacion')[:5]
        documentos_recientes = Documento.objects.filter(estado='EN_REVISION').order_by('-fecha_subida')[:5]

        self.children.append({
            'kpis': kpis,
            'charts_data': {
                'asistencia_semanal_json': json.dumps(asistencia_semanal_data),
                'documentos_status_json': json.dumps(documentos_status_data),
            },
            'justificaciones_recientes': justificaciones_recientes,
            'documentos_recientes': documentos_recientes,
        })

class CustomIndexDashboard(Dashboard):
    columns = 3

    def init_with_context(self, context):
        self.available_children.append(CustomDashboardModule(
            'Panel de Control Principal',
            column=0,
            order=0
        ))
        self.available_children.append(modules.AppList(
            'Aplicaciones',
            column=1,
            order=0
        ))
        self.available_children.append(modules.RecentActions(
            'Acciones Recientes',
            10,
            column=2,
            order=0
        ))
