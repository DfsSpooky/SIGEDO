from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db import models
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html
from django.utils import timezone
from unfold.admin import ModelAdmin, TabularInline
from unfold.contrib.forms.widgets import WysiwygWidget

from .models import (
    Grupo, Carrera, Especialidad, TipoDocumento, Docente, Curso,
    Documento, Asistencia, SolicitudIntercambio,
    PersonalDocente, Administrador, AsistenciaDiaria,
    ConfiguracionInstitucion, Semestre, FranjaHoraria, DiaEspecial, VersionDocumento,
    Notificacion, Anuncio, TipoJustificacion, Justificacion,
    Activo, TipoActivo, Reserva
)

# --- CONFIGURACIÓN DE ADMINS ---

@admin.register(Docente)
class DocenteAdmin(UserAdmin, ModelAdmin):
    model = Docente
    list_display = [
        'username', 'first_name', 'last_name', 'get_especialidades_prettified',
        'disponibilidad', 'display_is_staff', 'display_is_active'
    ]
    
    fieldsets = (
        (None, {
            'fields': ('username', 'password')
        }),
        ('Información Personal', {
            'classes': ('tab',),
            'fields': ('first_name', 'last_name', 'email', 'dni')
        }),
        ('Perfil Docente', {
            'classes': ('tab',),
            'fields': ('especialidades', 'disponibilidad', 'foto', 'vista_previa_foto')
        }),
        ('Permisos', {
            'classes': ('tab',),
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('Credenciales', {
            'classes': ('tab',),
            'fields': ('id_qr', 'rotate_qr_code_button', 'rfid_uid')
        }),
        ('Fechas Importantes', {
            'classes': ('tab',),
            'fields': ('date_joined', 'last_login')
        }),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Información Adicional', {'fields': ('dni', 'especialidades', 'disponibilidad', 'foto')}),
    )
    
    readonly_fields = ('id_qr', 'vista_previa_foto', 'rotate_qr_code_button', 'date_joined', 'last_login')
    filter_horizontal = ('especialidades', 'groups', 'user_permissions')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups', 'disponibilidad')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'dni')
    ordering = ('username',)

    @admin.display(description="Especialidades", ordering='especialidades')
    def get_especialidades_prettified(self, obj):
        html = [f'<span class="badge badge-sm badge-outline">{e.nombre}</span>' for e in obj.especialidades.all()]
        return format_html(" ".join(html))

    @admin.display(boolean=True, description="Es Staff")
    def display_is_staff(self, obj):
        return obj.is_staff

    @admin.display(boolean=True, description="Está Activo")
    def display_is_active(self, obj):
        return obj.is_active

    def rotate_qr_code_button(self, obj):
        if obj.pk:
            url = reverse('rotate_qr_code', args=[obj.pk])
            return format_html('<a class="button" href="{}">Generar Nuevo Código QR</a>', url)
        return "No disponible para nuevos docentes"
    rotate_qr_code_button.short_description = "Regenerar QR"

    def vista_previa_foto(self, obj):
        if obj.foto and hasattr(obj.foto, 'url'):
            return format_html('<img src="{}" width="150" height="150" style="object-fit: cover; border-radius: 8px;" />', obj.foto.url)
        return "(Sin foto)"
    vista_previa_foto.short_description = 'Vista Previa de la Foto'

@admin.register(PersonalDocente)
class PersonalDocenteAdmin(DocenteAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_staff=False)

@admin.register(Administrador)
class AdministradorAdmin(DocenteAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_staff=True)

@admin.register(Especialidad)
class EspecialidadAdmin(ModelAdmin):
    list_display = ('nombre', 'grupo')
    list_filter = ('grupo',)
    search_fields = ('nombre',)

@admin.register(Carrera)
class CarreraAdmin(ModelAdmin):
    search_fields = ('nombre',)

@admin.register(TipoDocumento)
class TipoDocumentoAdmin(ModelAdmin):
    search_fields = ('nombre',)

@admin.register(Semestre)
class SemestreAdmin(ModelAdmin):
    list_display = ('nombre', 'display_estado', 'tipo', 'fecha_inicio', 'fecha_fin')
    list_filter = ('estado', 'tipo')
    ordering = ('-fecha_inicio',)
    search_fields = ('nombre',)

    @admin.display(description="Estado", ordering='estado')
    def display_estado(self, obj):
        colors = {
            'PLANIFICACION': 'bg-blue-500',
            'ACTIVO': 'bg-green-500',
            'CERRADO': 'bg-gray-500',
        }
        color = colors.get(obj.estado, 'bg-gray-400')
        return format_html(f'<span class="px-2 py-1 text-xs font-semibold text-white rounded-full {color}">{obj.get_estado_display()}</span>')

@admin.register(Curso)
class CursoAdmin(ModelAdmin):
    list_display = ('nombre', 'tipo_curso', 'docente', 'especialidad', 'semestre', 'semestre_cursado')
    list_filter = ('semestre', 'tipo_curso', 'especialidad', 'semestre_cursado', 'carrera')
    search_fields = ('nombre', 'docente__first_name', 'docente__last_name')
    ordering = ('semestre', 'semestre_cursado', 'nombre')
    autocomplete_fields = ['docente', 'carrera', 'especialidad', 'semestre']
    
    fieldsets = (
        ('Información General', {
            'classes': ('tab',),
            'fields': ('nombre', 'tipo_curso', 'duracion_bloques')
        }),
        ('Organización Académica', {
            'classes': ('tab',),
            'fields': ('docente', 'carrera', 'especialidad', 'semestre', 'semestre_cursado')
        }),
        ('Horario', {
            'classes': ('tab',),
            'fields': ('dia', 'horario_inicio', 'horario_fin')
        }),
    )

@admin.register(DiaEspecial)
class DiaEspecialAdmin(ModelAdmin):
    list_display = ('fecha', 'motivo', 'tipo', 'semestre')
    list_filter = ('tipo', 'semestre')
    ordering = ('-fecha',)
    
@admin.register(FranjaHoraria)
class FranjaHorariaAdmin(ModelAdmin):
    list_display = ('__str__', 'turno', 'hora_inicio', 'hora_fin')
    list_filter = ('turno',)
    ordering = ('hora_inicio',)
    search_fields = ('turno', 'hora_inicio')

class VersionDocumentoInline(TabularInline):
    model = VersionDocumento
    extra = 1
    readonly_fields = ('fecha_version', 'numero_version')
    classes = ('collapse',)

@admin.register(Documento)
class DocumentoAdmin(ModelAdmin):
    list_display = ('titulo', 'docente', 'tipo_documento', 'display_estado', 'fecha_vencimiento')
    list_filter = ('estado', 'tipo_documento', 'docente')
    search_fields = ('titulo', 'docente__first_name', 'docente__last_name')
    readonly_fields = ('fecha_subida',)
    inlines = [VersionDocumentoInline]
    autocomplete_fields = ['docente', 'tipo_documento']

    fieldsets = (
        ("Detalles del Documento", {
            "classes": ("tab",),
            "fields": ("titulo", "tipo_documento", "docente", "fecha_vencimiento"),
        }),
        ("Revisión", {
            "classes": ("tab",),
            "fields": ("estado", "observaciones"),
        }),
    )

    @admin.display(description="Estado", ordering='estado')
    def display_estado(self, obj):
        colors = {
            'RECIBIDO': 'bg-blue-500',
            'EN_REVISION': 'bg-yellow-500',
            'APROBADO': 'bg-green-500',
            'OBSERVADO': 'bg-orange-500',
            'VENCIDO': 'bg-red-500',
        }
        color = colors.get(obj.estado, 'bg-gray-400')
        return format_html(f'<span class="px-2 py-1 text-xs font-semibold text-white rounded-full {color}">{obj.get_estado_display()}</span>')


@admin.register(VersionDocumento)
class VersionDocumentoAdmin(ModelAdmin):
    list_display = ('__str__', 'fecha_version')
    search_fields = ('documento__titulo',)

@admin.register(ConfiguracionInstitucion)
class ConfiguracionInstitucionAdmin(ModelAdmin):
    fieldsets = (
        ('Información Principal', {
            'fields': ('nombre_institucion', 'logo', 'facultad', 'nombre_dashboard')
        }),
        ('Parámetros del Sistema', {
            'fields': ('tiempo_limite_tardanza',)
        }),
        ('Datos de Contacto (Opcional)', {
            'fields': ('direccion', 'telefono', 'email_contacto'),
            'classes': ('collapse',),
        }),
    )

    def add_view(self, request, form_url='', extra_context=None):
        if ConfiguracionInstitucion.objects.exists():
            obj = ConfiguracionInstitucion.objects.first()
            return HttpResponseRedirect(reverse('admin:core_configuracioninstitucion_change', args=[obj.pk]))
        return super().add_view(request, form_url, extra_context)

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(Notificacion)
class NotificacionAdmin(ModelAdmin):
    list_display = ('destinatario', 'mensaje', 'leido', 'fecha_creacion')
    list_filter = ('leido', 'fecha_creacion')
    search_fields = ('destinatario__username', 'mensaje')

@admin.register(Anuncio)
class AnuncioAdmin(ModelAdmin):
    list_display = ('titulo', 'autor', 'fecha_publicacion')
    search_fields = ('titulo', 'contenido')
    list_filter = ('autor', 'fecha_publicacion')
    formfield_overrides = {
        models.TextField: {"widget": WysiwygWidget},
    }
    fieldsets = (
        (None, {'fields': ('titulo', 'contenido')}),
    )

    def save_model(self, request, obj, form, change):
        if not obj.autor:
            obj.autor = request.user
        super().save_model(request, obj, form, change)

@admin.register(TipoJustificacion)
class TipoJustificacionAdmin(ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)

@admin.register(Justificacion)
class JustificacionAdmin(ModelAdmin):
    list_display = ('docente', 'tipo', 'fecha_inicio', 'fecha_fin', 'display_estado')
    list_filter = ('estado', 'tipo', 'fecha_inicio')
    search_fields = ('docente__first_name', 'docente__last_name', 'motivo')
    ordering = ('-fecha_creacion',)
    readonly_fields = ('fecha_creacion', 'fecha_revision', 'revisado_por')
    autocomplete_fields = ['docente', 'tipo', 'revisado_por']

    fieldsets = (
        ("Datos de la Justificación", {
            "classes": ("tab",),
            "fields": ('docente', 'tipo', ('fecha_inicio', 'fecha_fin'), 'motivo', 'documento_adjunto'),
        }),
        ("Revisión Administrativa", {
            "classes": ("tab",),
            "fields": ('estado', 'observaciones_revision', 'revisado_por', 'fecha_revision'),
        }),
    )

    @admin.display(description="Estado", ordering='estado')
    def display_estado(self, obj):
        colors = {
            'PENDIENTE': 'bg-yellow-500',
            'APROBADO': 'bg-green-500',
            'RECHAZADO': 'bg-red-500',
        }
        color = colors.get(obj.estado, 'bg-gray-400')
        return format_html(f'<span class="px-2 py-1 text-xs font-semibold text-white rounded-full {color}">{obj.get_estado_display()}</span>')

    def save_model(self, request, obj, form, change):
        if 'estado' in form.changed_data and obj.estado != 'PENDIENTE':
            obj.revisado_por = request.user
            obj.fecha_revision = timezone.now()
        super().save_model(request, obj, form, change)

@admin.register(TipoActivo)
class TipoActivoAdmin(ModelAdmin):
    search_fields = ('nombre',)
    list_display = ('nombre',)

@admin.register(Activo)
class ActivoAdmin(ModelAdmin):
    list_display = ('nombre', 'codigo_patrimonial', 'tipo', 'estado', 'asignado_a')
    list_filter = ('estado', 'tipo')
    search_fields = ('nombre', 'codigo_patrimonial', 'asignado_a__first_name', 'asignado_a__last_name', 'asignado_a__username')
    autocomplete_fields = ('asignado_a', 'tipo')

@admin.register(Reserva)
class ReservaAdmin(ModelAdmin):
    list_display = ('id', 'activo', 'docente', 'fecha_reserva', 'franja_horaria_inicio', 'franja_horaria_fin', 'estado')
    list_filter = ('estado', 'fecha_reserva')
    search_fields = ('activo__nombre', 'docente__username', 'docente__first_name')
    autocomplete_fields = ('activo', 'docente', 'franja_horaria_inicio', 'franja_horaria_fin')
    readonly_fields = ('fecha_creacion', 'fecha_confirmacion', 'fecha_finalizacion')
    list_per_page = 20

@admin.register(Asistencia)
class AsistenciaAdmin(ModelAdmin):
    list_display = ('docente', 'curso', 'fecha', 'hora_entrada', 'hora_salida')
    list_filter = ('fecha', 'curso__semestre', 'docente')
    search_fields = ('docente__first_name', 'docente__last_name', 'curso__nombre')
    readonly_fields = ('hora_entrada', 'hora_salida', 'hora_salida_permitida', 'foto_entrada', 'foto_salida')
    autocomplete_fields = ['docente', 'curso']

@admin.register(SolicitudIntercambio)
class SolicitudIntercambioAdmin(ModelAdmin):
    list_display = ('docente_solicitante', 'curso_solicitante', 'docente_destino', 'curso_destino', 'display_estado')
    list_filter = ('estado',)
    search_fields = ('docente_solicitante__first_name', 'docente_destino__first_name')
    autocomplete_fields = ['docente_solicitante', 'curso_solicitante', 'docente_destino', 'curso_destino']

    @admin.display(description="Estado", ordering='estado')
    def display_estado(self, obj):
        colors = {
            'pendiente': 'bg-yellow-500',
            'aprobado': 'bg-green-500',
            'rechazado': 'bg-red-500',
        }
        color = colors.get(obj.estado, 'bg-gray-400')
        return format_html(f'<span class="px-2 py-1 text-xs font-semibold text-white rounded-full {color}">{obj.get_estado_display()}</span>')

# --- REGISTRO DEL RESTO DE MODELOS ---
admin.site.register(Grupo)
admin.site.register(AsistenciaDiaria)