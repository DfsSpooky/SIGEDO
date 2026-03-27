from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from . import views

# Define el espacio de nombres para estas URLs de API
app_name = "api"

urlpatterns = [
    # --- URLs para el Kiosco ---
    path("get-teacher-info/", views.TeacherInfoView.as_view(), name="get_teacher_info"),
    path(
        "mark-attendance/", views.MarkAttendanceView.as_view(), name="mark_attendance"
    ),
    path(
        "asistencia_rfid/",
        views.RegistrarAsistenciaRfidView.as_view(),
        name="asistencia_rfid",
    ),
    # --- URLs para el Planificador de Horarios ---
    path("asignar-horario/", views.api_asignar_horario, name="asignar_horario"),
    path(
        "desasignar-horario/", views.api_desasignar_horario, name="desasignar_horario"
    ),
    path(
        "get-teacher-conflicts/",
        views.api_get_teacher_conflicts,
        name="get_teacher_conflicts",
    ),
    path("mover-bloque/", views.api_mover_bloque, name="mover_bloque"),
    path("ajustar-duracion/", views.api_ajustar_duracion, name="ajustar_duracion"),
    path("auto-asignar/", views.api_auto_asignar, name="auto_asignar"),
    path(
        "generar-horario-automatico/",
        views.generar_horario_automatico,
        name="generar_horario_automatico",
    ),
    path("clear-horario/", views.clear_horario, name="clear_horario"),
    path("planner-chat/", views.api_planner_chat, name="planner_chat"),
    path(
        "get-cursos-no-asignados/",
        views.api_get_cursos_no_asignados,
        name="get_cursos_no_asignados",
    ),
    # --- URLs para la API de Reportes ---
    path(
        "reporte/chart-data/", views.api_get_report_chart_data, name="report_chart_data"
    ),
    path(
        "reporte/detalle/<int:docente_id>/",
        views.detalle_asistencia_docente_ajax,
        name="detalle_asistencia_docente_ajax",
    ),
    # --- URLs para Notificaciones ---
    path("notificaciones/json/", views.notificaciones_json, name="notificaciones_json"),
    path(
        "notificaciones/<int:notificacion_id>/marcar-leida/",
        views.marcar_notificacion_como_leida,
        name="marcar_notificacion_leida",
    ),
    path(
        "notificaciones/marcar-todas-leidas/",
        views.marcar_todas_como_leidas,
        name="marcar_todas_leidas",
    ),
    # --- URL para el Calendario del Docente ---
    path("horario-docente/", views.api_horario_docente, name="horario_docente"),
    path(
        "exportar-horario/<int:docente_id>/",
        views.export_schedule_ics,
        name="export_schedule_ics",
    ),
    path(
        "exportar-horario/mis-horarios/",
        views.export_schedule_ics,
        name="export_my_schedule_ics",
    ),
    # --- Autenticación JWT ---
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    # --- API Móvil ---
    path("mobile/profile/update/", views.MobileUpdateProfileView.as_view(), name="mobile_profile_update"),
    path("mobile/public-config/", views.MobilePublicConfigView.as_view(), name="mobile_public_config"),
    path("mobile/status/", views.MobileStatusView.as_view(), name="mobile_status"),
    path("mobile/attendance/", views.MobileMarkAttendanceView.as_view(), name="mobile_attendance"),
    path("mobile/fcm-token/", views.UpdateFCMTokenView.as_view(), name="mobile_fcm_token"),
    path("mobile/documents/", views.MobileDocumentsView.as_view(), name="mobile_documents"),
    path("mobile/documents/upload/", views.MobileUploadDocumentView.as_view(), name="mobile_documents_upload"),
    path("mobile/adelanto-clase/", views.MobileAdelantoClaseView.as_view(), name="mobile_adelanto_clase"),
    path("mobile/director/attendance/", views.MobileDirectorAttendanceView.as_view(), name="mobile_director_attendance"),
    path("mobile/director/stats/", views.MobileDirectorStatsView.as_view(), name="mobile_director_stats"),
    path("mobile/history/", views.MobileAttendanceHistoryView.as_view(), name="mobile_attendance_history"),
    path("mobile/recuperacion-clase/", views.MobileRecuperacionClaseView.as_view(), name="mobile_recuperacion_clase"),
    
    # --- Justificaciones ---
    # --- Justificaciones ---
    path("justificaciones/", views.JustificationListView.as_view(), name="justification_list"),
    path("tipo-justificaciones/", views.TipoJustificacionListView.as_view(), name="tipo_justification_list"),

    # --- Autenticación y Recuperación ---
    path("auth/request-reset/", views.RequestPasswordResetView.as_view(), name="request_reset"),
    path("auth/reset-password/", views.ResetPasswordView.as_view(), name="reset_password"),
]
