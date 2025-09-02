from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from .models import Reserva

@admin.register(Reserva)
class ReservaAdmin(ModelAdmin):
    list_display = ('id', 'activo', 'docente', 'fecha_reserva', 'franja_horaria_inicio', 'franja_horaria_fin', 'estado', 'acciones')
    list_display_links = None
    list_filter = ('estado', 'fecha_reserva')
    search_fields = ('activo__nombre', 'docente__username', 'docente__first_name')
    search_as_command = True
    autocomplete_fields = ('activo', 'docente', 'franja_horaria_inicio', 'franja_horaria_fin')
    readonly_fields = ('fecha_creacion', 'fecha_confirmacion', 'fecha_finalizacion')
    list_per_page = 20

    @admin.display(description="Acciones")
    def acciones(self, obj):
        change_url = reverse(f'admin:{obj._meta.app_label}_{obj._meta.model_name}_change', args=[obj.pk])
        return format_html(f'<a href="{change_url}" class="button">Ver</a>')
