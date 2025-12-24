from .calendar import api_horario_docente
from .kiosk import MarkAttendanceView, RegistrarAsistenciaRfidView, TeacherInfoView
from .notifications import (
    marcar_notificacion_como_leida,
    marcar_todas_como_leidas,
    notificaciones_json,
)
from .planner import (
    AjustarDuracionView,
    AsignarHorarioView,
    AutoAsignarView,
    DesasignarHorarioView,
    MoverBloqueView,
    api_get_cursos_no_asignados,
    api_get_teacher_conflicts,
    generar_horario_automatico,
)
from .schedules import export_schedule_ics
from .reports import api_get_report_chart_data, detalle_asistencia_docente_ajax
