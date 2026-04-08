from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from .utils import exports

urlpatterns = [
    path('subir_documento/', views.subir_documento, name='subir_documento'),
    path('documentos/<int:documento_id>/subir_version/', views.subir_nueva_version, name='subir_nueva_version'),
    path('documentos/', views.lista_documentos, name='lista_documentos'),
    path('asistencia/', views.registrar_asistencia, name='asistencia'),
    path('', views.dashboard, name='dashboard'),
    path('perfil/', views.perfil, name='perfil'),
    path('horarios/<int:carrera_id>/', views.ver_horarios, name='ver_horarios'),
    path('horarios/<int:carrera_id>/generar/', views.generar_horarios, name='generar_horarios'),
    path('intercambio/<int:curso_id>/', views.solicitar_intercambio, name='solicitar_intercambio'),
    path('solicitudes/', views.ver_solicitudes, name='ver_solicitudes'),
    path('solicitudes/<int:solicitud_id>/responder/', views.responder_solicitud, name='responder_solicitud'),
    
    # --- Custom Login/Logout Views ---
    path('accounts/login/', views.custom_login_view, name='login'),
    # Django's built-in logout view is fine, as settings.py handles the redirect
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),

    # --- URLS PARA EL KIOSCO ---
    # Esta ruta mostrará la página del kiosco
    path('kiosco/', views.kiosco_page, name='kiosco_page'),
    
    # APIs que usará el JavaScript del kiosco
    path('api/get-teacher-info/', views.get_teacher_info, name='api_get_teacher_info'),
    path('api/mark-attendance/', views.mark_attendance_kiosk, name='api_mark_attendance'),

        # --- INICIO DE URLS PARA CREDENCIALES ---
    path('credenciales/', views.lista_docentes_credenciales, name='lista_credenciales'),
    path('credenciales/<int:docente_id>/', views.generar_credencial_docente, name='generar_credencial'),
    # --- FIN DE URLS PARA CREDENCIALES ---
    path('reportes/asistencia/', views.reporte_asistencia, name='reporte_asistencia'),

    path('planificador/', views.planificador_horarios, name='planificador_horarios'),
    path('api/asignar-horario/', views.api_asignar_horario, name='api_asignar_horario'),
    path('api/desasignar-horario/', views.api_desasignar_horario, name='api_desasignar_horario'),
    path('api/get-teacher-conflicts/', views.api_get_teacher_conflicts, name='api_get_teacher_conflicts'),
    path('api/auto-asignar/', views.api_auto_asignar, name='api_auto_asignar'),
    path('api/get-cursos-no-asignados/', views.api_get_cursos_no_asignados, name='api_get_cursos_no_asignados'),

    path('horarios/ver/', views.vista_publica_horarios, name='vista_publica_horarios'),

    path('reporte-asistencia/', views.reporte_asistencia, name='reporte_asistencia'),
    # Las URLs de exportación ahora apuntan al nuevo módulo
    path('reporte-asistencia/excel/', exports.exportar_reporte_excel, name='exportar_excel'),
    path('reporte-asistencia/pdf/', exports.exportar_reporte_pdf, name='exportar_pdf'),
    path('reporte-asistencia/detalle/<int:docente_id>/', views.detalle_asistencia_docente_ajax, name='detalle_asistencia_docente_ajax'),
    path('api/reporte/chart-data/', views.api_get_report_chart_data, name='api_report_chart_data'),
]