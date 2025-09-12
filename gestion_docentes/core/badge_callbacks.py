from .models import Documento, Justificacion, SolicitudIntercambio, Notificacion

def documentos_badge_callback(request):
    """
    Returns the number of documents in 'RECIBIDO' state.
    """
    if request.user.is_staff:
        return Documento.objects.filter(estado='RECIBIDO').count()
    return 0

def justificaciones_badge_callback(request):
    """
    Returns the number of justifications in 'PENDIENTE' state.
    """
    if request.user.is_staff:
        return Justificacion.objects.filter(estado='PENDIENTE').count()
    return 0

def solicitudes_intercambio_badge_callback(request):
    """
    Returns the number of exchange requests in 'pendiente' state.
    This is visible to staff.
    """
    if request.user.is_staff:
        return SolicitudIntercambio.objects.filter(estado='pendiente').count()
    return 0

def notificaciones_badge_callback(request):
    """
    Returns the number of unread notifications for the current user.
    """
    if request.user.is_authenticated:
        return Notificacion.objects.filter(destinatario=request.user, leido=False).count()
    return 0
