from django.db.models import Q
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin

from .models import Activo

class ActivoListView(LoginRequiredMixin, ListView):
    model = Activo
    template_name = 'inventario/lista_activos.html'
    context_object_name = 'activos'
    paginate_by = 15

    def get_queryset(self):
        queryset = super().get_queryset().select_related('tipo', 'asignado_a')
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(nombre__icontains=query) |
                Q(codigo_patrimonial__icontains=query) |
                Q(asignado_a__first_name__icontains=query) |
                Q(asignado_a__last_name__icontains=query)
            )
        return queryset

class ActivoDetailView(LoginRequiredMixin, DetailView):
    model = Activo
    template_name = 'inventario/detalle_activo.html'
    context_object_name = 'activo'

class ActivoCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Activo
    template_name = 'inventario/form_activo.html'
    fields = ['nombre', 'descripcion', 'codigo_patrimonial', 'tipo', 'estado', 'asignado_a', 'fecha_adquisicion', 'observaciones']
    success_url = reverse_lazy('inventario:lista')
    permission_required = 'core.add_activo'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Crear Nuevo Activo'
        return context

class ActivoUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Activo
    template_name = 'inventario/form_activo.html'
    fields = ['nombre', 'descripcion', 'codigo_patrimonial', 'tipo', 'estado', 'asignado_a', 'fecha_adquisicion', 'observaciones']
    success_url = reverse_lazy('inventario:lista')
    permission_required = 'core.change_activo'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Editar Activo'
        return context

class ActivoDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Activo
    template_name = 'inventario/confirmar_eliminacion_activo.html'
    success_url = reverse_lazy('inventario:lista')
    permission_required = 'core.delete_activo'
