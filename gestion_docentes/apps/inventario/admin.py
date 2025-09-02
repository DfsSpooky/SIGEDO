from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from .models import TipoActivo, Activo

@admin.register(TipoActivo)
class TipoActivoAdmin(ModelAdmin):
    list_display = ('nombre', 'acciones')
    list_display_links = None
    search_fields = ('nombre',)
    search_as_command = True

    @admin.display(description="Acciones")
    def acciones(self, obj):
        change_url = reverse(f'admin:{obj._meta.app_label}_{obj._meta.model_name}_change', args=[obj.pk])
        return format_html(f'<a href="{change_url}" class="button">Editar</a>')

@admin.register(Activo)
class ActivoAdmin(ModelAdmin):
    list_display = ('nombre', 'codigo_patrimonial', 'tipo', 'estado', 'asignado_a', 'acciones')
    list_display_links = None
    list_filter = ('estado', 'tipo')
    search_fields = ('nombre', 'codigo_patrimonial', 'asignado_a__first_name', 'asignado_a__last_name', 'asignado_a__username')
    search_as_command = True
    autocomplete_fields = ('asignado_a', 'tipo')

    @admin.display(description="Acciones")
    def acciones(self, obj):
        change_url = reverse(f'admin:{obj._meta.app_label}_{obj._meta.model_name}_change', args=[obj.pk])
        return format_html(f'<a href="{change_url}" class="button">Editar</a>')
