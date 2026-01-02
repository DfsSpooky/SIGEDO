from .calendar import api_horario_docente
from .kiosk import MarkAttendanceView, RegistrarAsistenciaRfidView, TeacherInfoView
from .mobile import (
    MobileMarkAttendanceView, 
    MobileStatusView, 
    UpdateFCMTokenView, 
    MobileDocumentsView,
    MobileUploadDocumentView,
    MobilePublicConfigView,
    MobileAdelantoClaseView,
    MobileDirectorAttendanceView,
    MobileDirectorStatsView,
)
from .notifications import (
    marcar_notificacion_como_leida,
    marcar_todas_como_leidas,
    notificaciones_json,
)
from .planner import (
    api_ajustar_duracion,
    api_asignar_horario,
    api_auto_asignar,
    api_desasignar_horario,
    api_get_cursos_no_asignados,
    api_get_teacher_conflicts,
    api_mover_bloque,
    generar_horario_automatico,
)
from .schedules import export_schedule_ics
from .reports import api_get_report_chart_data, detalle_asistencia_docente_ajax
from .justifications import JustificationListView, TipoJustificacionListView
from .auth import RequestPasswordResetView, ResetPasswordView
