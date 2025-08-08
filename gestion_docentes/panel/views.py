from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.apps import apps

@login_required
@staff_member_required
def dashboard(request):
    # Agrupamos los modelos de la app 'core' por categoría para mostrarlos en el panel.
    model_groups = {
        'Gestión Académica': ['Semestre', 'Carrera', 'Especialidad', 'Curso'],
        'Personal y Asistencia': ['Docente', 'Asistencia', 'Justificacion'],
        'Documentos y Anuncios': ['Documento', 'Anuncio'],
        'Configuración': ['FranjaHoraria', 'DiaEspecial', 'TipoDocumento', 'TipoJustificacion'],
    }

    app_structure = {}
    for group, model_names in model_groups.items():
        models_info = []
        for model_name in model_names:
            model = apps.get_model('core', model_name)
            opts = model._meta
            models_info.append({
                'name': opts.model_name,
                'verbose_name_plural': opts.verbose_name_plural,
                'app_label': opts.app_label,
                'has_add_perm': request.user.has_perm(f'{opts.app_label}.add_{opts.model_name}'),
            })
        app_structure[group] = models_info

    context = {
        'app_structure': app_structure
    }

    return render(request, 'panel/dashboard.html', context)

@login_required
def model_list_view(request, app_label, model_name):
    try:
        model = apps.get_model(app_label, model_name)
    except LookupError:
        return render(request, 'panel/404.html')

    opts = model._meta
    queryset = model.objects.all()

    # Verificar permisos
    has_add_permission = request.user.has_perm(f'{app_label}.add_{model_name}')
    has_change_permission = request.user.has_perm(f'{app_label}.change_{model_name}')
    has_delete_permission = request.user.has_perm(f'{app_label}.delete_{model_name}')

    context = {
        'queryset': queryset,
        'opts': opts,
        'has_add_permission': has_add_permission,
        'has_change_permission': has_change_permission,
        'has_delete_permission': has_delete_permission,
    }
    return render(request, 'panel/model_list.html', context)
