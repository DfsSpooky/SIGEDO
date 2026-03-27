from django.contrib.auth import views as auth_views
from django.urls import include, path

from . import urls_inventario, urls_reservas, views
from .utils import exports

# Importamos las vistas específicas del planificador desde la API
from core.api.views import planner
from core.views.realtime_dashboard import RealTimeDashboardView

urlpatterns = [
    path("health/", views.health_check, name="health_check"),
    # --- Gestión de Documentos ---
    path("subir_documento/", views.subir_documento, name="subir_documento"),
    path(
        "documentos/<int:documento_id>/subir_version/",
        views.subir_nueva_version,
        name="subir_nueva_version",
    ),
    path("documentos/", views.lista_documentos, name="lista_documentos"),
    
    # --- Asistencia y Dashboard ---
    path("asistencia/", views.registrar_asistencia, name="asistencia"),
    path("", views.dashboard, name="dashboard"),
    path("dashboard-feed/", RealTimeDashboardView.as_view(), name="dashboard_feed"),
    path("perfil/", views.perfil, name="perfil"),
    
    # --- Calendario y Horarios (Vistas Tradicionales) ---
    path("calendario/", views.calendario_view, name="calendario"),
    path("horarios/<int:carrera_id>/", views.ver_horarios, name="ver_horarios"),
    # Vista Admin Nueva para Horario Docente Detallado
    path("horarios/docente/<int:docente_id>/", views.ver_horario_docente_admin, name="ver_horario_docente_admin"),
    path(
        "horarios/<int:carrera_id>/generar/",
        views.generar_horarios,
        name="generar_horarios",
    ),
    
    # --- Solicitudes e Intercambios ---
    path(
        "intercambio/<int:curso_id>/",
        views.solicitar_intercambio,
        name="solicitar_intercambio",
    ),
    path("solicitudes/", views.ver_solicitudes, name="ver_solicitudes"),
    path(
        "solicitudes/<int:solicitud_id>/responder/",
        views.responder_solicitud,
        name="responder_solicitud",
    ),
    
    
    # --- Recuperación de Clases ---
    path("recuperaciones/", views.ver_recuperaciones, name="ver_recuperaciones"),
    path("recuperaciones/solicitar/", views.solicitar_recuperacion, name="solicitar_recuperacion"),
    
    # --- Justificaciones ---
    path("justificaciones/", views.lista_justificaciones, name="lista_justificaciones"),
    path(
        "justificaciones/solicitar/",
        views.solicitar_justificacion,
        name="solicitar_justificacion",
    ),
    
    # --- Módulos Incluidos (Inventario y Reservas) ---
    path("inventario/", include(urls_inventario)),
    path("reservas/", include(urls_reservas)),
    
    # --- Autenticación ---
    path("accounts/login/", views.custom_login_view, name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    
    # --- Kiosco ---
    path("kiosco/", views.kiosco_page, name="kiosco_page"),

    # ==========================================
    # --- RUTAS API DEL PLANIFICADOR (NUEVO) ---
    # ==========================================
    # Estas rutas deben ir ANTES del include('api/') general para asegurar prioridad
    path('api/get-cursos-no-asignados/', planner.api_get_cursos_no_asignados, name='api_get_cursos_no_asignados'),
    path('api/asignar-horario/', planner.api_asignar_horario, name='api_asignar_horario'),
    path('api/mover-bloque/', planner.api_mover_bloque, name='api_mover_bloque'),
    path('api/desasignar-horario/', planner.api_desasignar_horario, name='api_desasignar_horario'),
    path('api/ajustar-duracion/', planner.api_ajustar_duracion, name='api_ajustar_duracion'),
    path('api/auto-asignar/', planner.api_auto_asignar, name='api_auto_asignar'),
    path('api/generar-horario-automatico/', planner.generar_horario_automatico, name='api_generar_horario_automatico'),
    path('api/get-teacher-conflicts/', planner.api_get_teacher_conflicts, name='api_get_teacher_conflicts'),
    path('api/exportar-horario/', planner.api_exportar_horario, name='api_exportar_horario'),
    path('api/get-placement-suggestions/', planner.api_get_placement_suggestions, name='api_get_placement_suggestions'),

    # --- Resto de la API ---
    path("api/", include("core.api.urls", namespace="api")),
    
    # --- Credenciales ---
    path("credenciales/", views.lista_docentes_credenciales, name="lista_credenciales"),
    path(
        "credenciales/<str:encrypted_id>/",
        views.generar_credencial_docente,
        name="generar_credencial",
    ),
    path(
        "credenciales/<int:docente_id>/rotate-qr/",
        views.rotate_qr_code,
        name="rotate_qr_code",
    ),
    
    # --- Reportes y Planificador (Vistas de Template) ---
    path("reportes/asistencia/", views.reporte_asistencia, name="reporte_asistencia"),
    path("planificador/", views.planificador_horarios, name="planificador_horarios"),
    path("horarios/ver/", views.vista_publica_horarios, name="vista_publica_horarios"),
    path("reporte-asistencia/", views.reporte_asistencia, name="reporte_asistencia"),
    path("reportes/analiticas/", views.analytics_dashboard, name="analytics_dashboard"),
    
    # --- Exportaciones Generales ---
    path(
        "reporte-asistencia/excel/",
        exports.exportar_reporte_excel,
        name="exportar_excel",
    ),
    path("reporte-asistencia/pdf/", exports.exportar_reporte_pdf, name="exportar_pdf"),
    
    # --- Notificaciones y Varios ---
    path("notificaciones/", views.ver_notificaciones, name="ver_notificaciones"),
    path("anuncios/", views.ver_anuncios, name="ver_anuncios"),
    path(
        "docente/<int:docente_id>/ficha/",
        views.generar_ficha_docente,
        name="generar_ficha_docente",
    ),
]
