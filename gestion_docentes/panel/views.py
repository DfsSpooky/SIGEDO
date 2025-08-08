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
        # Handle model not found error
        return render(request, 'panel/404.html') # O una plantilla de error personalizada

    queryset = model.objects.all()

    context = {
        'model': model,
        'queryset': queryset,
        'opts': model._meta,
    }
    return render(request, 'panel/model_list.html', context)
