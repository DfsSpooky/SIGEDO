from .models import Notificacion

def unread_notifications_context(request):
    if request.user.is_authenticated:
        unread_count = Notificacion.objects.filter(destinatario=request.user, leido=False).count()
        return {'unread_notifications_count': unread_count}
    return {'unread_notifications_count': 0}
