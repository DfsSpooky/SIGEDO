from .academic import Carrera, Curso, Especialidad, Grupo, Semestre
from .attendance import Asistencia, AsistenciaDiaria, Justificacion, TipoJustificacion
from .communication import Anuncio, Notificacion
from .documents import Documento, TipoDocumento, VersionDocumento
from .inventory import Activo, Reserva, TipoActivo
from .scheduling import (
    BloqueHorario,
    BloqueNoLectivo,
    DiaEspecial,
    FranjaHoraria,
    SolicitudIntercambio,
)
from .settings import ConfiguracionInstitucion
from .users import Administrador, Docente, PersonalDocente
