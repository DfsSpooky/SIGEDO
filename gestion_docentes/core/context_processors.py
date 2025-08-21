from .models import Notificacion, ConfiguracionInstitucion

def unread_notifications_context(request):
    if request.user.is_authenticated:
        unread_count = Notificacion.objects.filter(destinatario=request.user, leido=False).count()
        return {'unread_notifications_count': unread_count}
    return {'unread_notifications_count': 0}

from django.apps import apps

def site_configuration_context(request):
    """
    Makes the institution's configuration available in all templates.
    """
    return {'configuracion': ConfiguracionInstitucion.load()}

