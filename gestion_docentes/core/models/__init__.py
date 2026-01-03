from .academic import Carrera, Curso, Especialidad, Grupo, Semestre
from .attendance import AdelantoClase, Asistencia, AsistenciaDiaria, Justificacion, TipoJustificacion, RecuperacionClase
from .communication import Anuncio, Notificacion
from .documents import Documento, TipoDocumento, VersionDocumento
from .inventory import Activo, Reserva, TipoActivo
from .scheduling import (
    Aula,
    BloqueHorario,
    BloqueNoLectivo,
    DiaEspecial,
    FranjaHoraria,
    SolicitudIntercambio,
)
from .settings import ConfiguracionInstitucion
from .users import Administrador, Docente, PersonalDocente
