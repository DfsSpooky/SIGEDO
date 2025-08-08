from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.apps import apps
from django import forms
from django.views.generic import CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import PermissionRequiredMixin
from .forms import DocenteCreationForm, DocenteChangeForm, SemestreForm, CursoForm
from core.models import Docente, Curso, Justificacion, Semestre

@login_required
@staff_member_required
def dashboard(request):
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

    kpis = {
        'total_docentes': Docente.objects.count(),
        'cursos_activos': Curso.objects.filter(semestre__estado='ACTIVO').count(),
        'justificaciones_pendientes': Justificacion.objects.filter(estado='PENDIENTE').count(),
        'semestres_activos': Semestre.objects.filter(estado='ACTIVO').count(),
    }

    context = {
        'app_structure': app_structure,
        'kpis': kpis,
    }
    return render(request, 'panel/dashboard.html', context)

MODEL_LIST_FIELDS = {
    'docente': ['dni', 'first_name', 'last_name', 'email', 'disponibilidad'],
    'semestre': ['nombre', 'fecha_inicio', 'fecha_fin', 'estado'],
    'curso': ['nombre', 'docente', 'carrera', 'semestre'],
    'justificacion': ['docente', 'tipo', 'fecha_inicio', 'fecha_fin', 'estado'],
}

@login_required
@staff_member_required
def model_list_view(request, app_label, model_name):
    try:
        model = apps.get_model(app_label, model_name)
    except LookupError:
        return render(request, 'panel/404.html')

    opts = model._meta
    queryset = model.objects.all()

    list_display = MODEL_LIST_FIELDS.get(model_name, ['__str__'])

    list_headers = []
    for field_name in list_display:
        if field_name == '__str__':
            list_headers.append(opts.verbose_name)
        else:
            list_headers.append(model._meta.get_field(field_name).verbose_name)

    object_list = []
    for obj in queryset:
        row = []
        for field_name in list_display:
            if field_name == '__str__':
                row.append(str(obj))
            else:
                row.append(getattr(obj, field_name))
        object_list.append({'pk': obj.pk, 'fields': row})


    has_add_permission = request.user.has_perm(f'{app_label}.add_{model_name}')
    has_change_permission = request.user.has_perm(f'{app_label}.change_{model_name}')
    has_delete_permission = request.user.has_perm(f'{app_label}.delete_{model_name}')

    context = {
        'object_list': object_list,
        'list_headers': list_headers,
        'opts': opts,
        'has_add_permission': has_add_permission,
        'has_change_permission': has_change_permission,
        'has_delete_permission': has_delete_permission,
    }
    return render(request, 'panel/model_list.html', context)

MODEL_FORMS = {
    'docente': DocenteChangeForm,
    'semestre': SemestreForm,
    'curso': CursoForm,
}

MODEL_ADD_FORMS = {
    'docente': DocenteCreationForm,
}

class ModelCreateView(PermissionRequiredMixin, CreateView):
    template_name = 'panel/model_form.html'

    def get_model(self):
        return apps.get_model(self.kwargs['app_label'], self.kwargs['model_name'])

    def get_permission_required(self):
        model = self.get_model()
        return [f"{model._meta.app_label}.add_{model._meta.model_name}"]

    def get_form_class(self):
        self.model = self.get_model()
        model_name = self.model._meta.model_name

        form_class = MODEL_ADD_FORMS.get(model_name)
        if not form_class:
            form_class = MODEL_FORMS.get(model_name)

        if form_class:
            return form_class

        class ModelForm(forms.ModelForm):
            class Meta:
                model = self.model
                fields = '__all__'
        return ModelForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['opts'] = self.get_model()._meta
        return context

    def get_success_url(self):
        return reverse_lazy('panel:model_list', kwargs={'app_label': self.kwargs['app_label'], 'model_name': self.kwargs['model_name']})

class ModelUpdateView(PermissionRequiredMixin, UpdateView):
    template_name = 'panel/model_form.html'

    def get_model(self):
        return apps.get_model(self.kwargs['app_label'], self.kwargs['model_name'])

    def get_queryset(self):
        model = self.get_model()
        return model.objects.all()

    def get_permission_required(self):
        model = self.get_model()
        return [f"{model._meta.app_label}.change_{model._meta.model_name}"]

    def get_form_class(self):
        self.model = self.get_model()
        form_class = MODEL_FORMS.get(self.model._meta.model_name)
        if form_class:
            return form_class

        class ModelForm(forms.ModelForm):
            class Meta:
                model = self.model
                fields = '__all__'
        return ModelForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['opts'] = self.get_model()._meta
        return context

    def get_success_url(self):
        return reverse_lazy('panel:model_list', kwargs={'app_label': self.kwargs['app_label'], 'model_name': self.kwargs['model_name']})

class ModelDeleteView(PermissionRequiredMixin, DeleteView):
    template_name = 'panel/model_confirm_delete.html'

    def get_model(self):
        return apps.get_model(self.kwargs['app_label'], self.kwargs['model_name'])

    def get_queryset(self):
        model = self.get_model()
        return model.objects.all()

    def get_permission_required(self):
        model = self.get_model()
        return [f"{model._meta.app_label}.delete_{model._meta.model_name}"]

    def get_success_url(self):
        return reverse_lazy('panel:model_list', kwargs={'app_label': self.kwargs['app_label'], 'model_name': self.kwargs['model_name']})
