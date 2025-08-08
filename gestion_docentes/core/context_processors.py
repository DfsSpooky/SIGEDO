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

def panel_navigation_context(request):
    """
    Provides the model structure for the custom admin panel's navigation.
    """
    if not request.user.is_staff:
        return {}

    model_groups = {
        'Gestión Académica': ['Semestre', 'Carrera', 'Especialidad', 'Curso'],
        'Personal y Asistencia': ['Docente', 'Asistencia', 'Justificacion'],
        'Documentos y Anuncios': ['Documento', 'Anuncio'],
        'Configuración': ['FranjaHoraria', 'DiaEspecial', 'TipoDocumento', 'TipoJustificacion'],
    }

    panel_structure = {}
    for group, model_names in model_groups.items():
        models_info = []
        for model_name in model_names:
            try:
                model = apps.get_model('core', model_name)
                opts = model._meta
                # Check if user has permission to view the model
                if request.user.has_perm(f'core.view_{opts.model_name}'):
                    models_info.append({
                        'name': opts.model_name,
                        'verbose_name_plural': opts.verbose_name_plural,
                        'app_label': opts.app_label,
                    })
            except LookupError:
                continue # Skip if model doesn't exist

        if models_info: # Only add group if it has visible models
            panel_structure[group] = models_info

    return {'panel_nav_structure': panel_structure}
