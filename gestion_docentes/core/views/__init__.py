from .attendance import registrar_asistencia
from .auth import custom_login_view
from .credentials import (
    generar_credencial_docente,
    lista_docentes_credenciales,
    rotate_qr_code,
)
from .dashboard import dashboard, perfil
from .documents import lista_documentos, subir_documento, subir_nueva_version
from .inventory import (
    ActivoCreateView,
    ActivoDeleteView,
    ActivoDetailView,
    ActivoListView,
    ActivoUpdateView,
)
from .justifications import lista_justificaciones, solicitar_justificacion
from .kiosk import kiosco_page
from .notifications import ver_anuncios, ver_notificaciones
from .reports import analytics_dashboard, generar_ficha_docente, reporte_asistencia
from .requests import responder_solicitud, solicitar_intercambio, ver_solicitudes, ver_recuperaciones, solicitar_recuperacion
from .reservations import DisponibilidadEquiposView, MisReservasView, cancelar_reserva
from .schedules import (
    calendario_view,
    generar_horarios,
    planificador_horarios,
    ver_horarios,
    vista_publica_horarios,
)
from .utils import remove_accents
