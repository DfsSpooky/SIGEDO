from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.apps import apps

@login_required
def dashboard(request):
    # Agrupamos los modelos de la app 'core' por categoría para mostrarlos en el panel.
    # En el futuro, esto puede ser más dinámico.
    app_models = {
        'Gestión Académica': [
            apps.get_model('core', 'Semestre'),
            apps.get_model('core', 'Carrera'),
            apps.get_model('core', 'Especialidad'),
            apps.get_model('core', 'Curso'),
        ],
        'Personal y Asistencia': [
            apps.get_model('core', 'Docente'),
            apps.get_model('core', 'Asistencia'),
            apps.get_model('core', 'Justificacion'),
        ],
        'Documentos y Anuncios': [
            apps.get_model('core', 'Documento'),
            apps.get_model('core', 'Anuncio'),
        ],
        'Configuración': [
            apps.get_model('core', 'FranjaHoraria'),
            apps.get_model('core', 'DiaEspecial'),
            apps.get_model('core', 'TipoDocumento'),
            apps.get_model('core', 'TipoJustificacion'),
        ]
    }

    context = {
        'app_models': app_models
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
