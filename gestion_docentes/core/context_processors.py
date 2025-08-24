from .models import Notificacion, ConfiguracionInstitucion

def unread_notifications_context(request):
    """
    Provides notification data to all templates for the logged-in user.
    """
    if request.user.is_authenticated and request.user.is_staff:
        notifications = Notificacion.objects.filter(destinatario=request.user, leido=False)
        unread_count = notifications.count()
        # Fetch the 7 most recent unread notifications for the dropdown
        recent_notifications = notifications.order_by('-fecha_creacion')[:7]

        return {
            'unread_notifications_count': unread_count,
            'recent_notifications': recent_notifications
        }

    return {
        'unread_notifications_count': 0,
        'recent_notifications': []
    }

def site_configuration_context(request):
    """
    Makes the institution's configuration available in all templates.
    """
    # Using .first() and creating a default if it does not exist
    # is safer than a custom .load() method if it's not present on all branches.
    config = ConfiguracionInstitucion.objects.first()
    if not config:
        # In case the config object does not exist yet.
        config = ConfiguracionInstitucion.objects.create(nombre_institucion="Institución por Defecto")

    return {'configuracion': config}
