from django.urls import path
from . import views

# Define el espacio de nombres para estas URLs de API
app_name = 'api'

urlpatterns = [
    # --- URLs para el Kiosco ---
    path('get-teacher-info/', views.get_teacher_info, name='get_teacher_info'),
    path('mark-attendance/', views.mark_attendance_kiosk, name='mark_attendance'),
    path('asistencia_rfid/', views.registrar_asistencia_rfid, name='asistencia_rfid'),

    # --- URLs para el Planificador de Horarios ---
    path('asignar-horario/', views.api_asignar_horario, name='asignar_horario'),
    path('desasignar-horario/', views.api_desasignar_horario, name='desasignar_horario'),
    path('get-teacher-conflicts/', views.api_get_teacher_conflicts, name='get_teacher_conflicts'),
    path('auto-asignar/', views.api_auto_asignar, name='auto_asignar'),
    path('generar-horario-automatico/', views.generar_horario_automatico, name='generar_horario_automatico'),
    path('get-cursos-no-asignados/', views.api_get_cursos_no_asignados, name='get_cursos_no_asignados'),

    # --- URLs para la API de Reportes ---
    path('reporte/chart-data/', views.api_get_report_chart_data, name='report_chart_data'),
    path('reporte/detalle/<int:docente_id>/', views.detalle_asistencia_docente_ajax, name='detalle_asistencia_docente_ajax'),
]
