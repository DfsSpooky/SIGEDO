from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.urls import reverse
from django.utils.html import format_html
from django.utils import timezone
from unfold.admin import ModelAdmin, TabularInline

from .models import (
    Grupo, Carrera, Especialidad, TipoDocumento, Docente, Curso,
    Documento, Asistencia, SolicitudIntercambio,
    PersonalDocente, Administrador, AsistenciaDiaria,
    ConfiguracionInstitucion, Semestre, FranjaHoraria, DiaEspecial, VersionDocumento,
    Notificacion, Anuncio, TipoJustificacion, Justificacion
)

# --- CONFIGURACIÓN DE ADMINS ---

class DocenteAdmin(UserAdmin, ModelAdmin):
    model = Docente
    list_display = ['username', 'first_name', 'last_name', 'get_especialidades', 'disponibilidad', 'is_staff']
    
    fieldsets = UserAdmin.fieldsets + (
        ('Información Adicional', {'fields': ('dni', 'especialidades', 'disponibilidad', 'id_qr', 'foto', 'vista_previa_foto', 'rotate_qr_code_button')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Información Adicional', {'fields': ('dni', 'especialidades', 'disponibilidad', 'foto')}),
    )
    
    readonly_fields = ('id_qr', 'vista_previa_foto', 'rotate_qr_code_button',)
    filter_horizontal = ('especialidades',)

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

    def get_especialidades(self, obj):
        return ", ".join([e.nombre for e in obj.especialidades.all()])
    get_especialidades.short_description = 'Especialidades'


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

@admin.register(Semestre)
class SemestreAdmin(ModelAdmin):
    list_display = ('nombre', 'estado', 'tipo', 'fecha_inicio', 'fecha_fin')
    list_filter = ('estado', 'tipo')
    ordering = ('-fecha_inicio',)

@admin.register(Curso)
class CursoAdmin(ModelAdmin):
    list_display = ('nombre', 'tipo_curso', 'docente', 'especialidad', 'semestre', 'semestre_cursado')
    list_filter = ('semestre', 'tipo_curso', 'especialidad', 'semestre_cursado')
    search_fields = ('nombre', 'docente__first_name', 'docente__last_name')
    ordering = ('semestre', 'semestre_cursado', 'nombre')
    
    fieldsets = (
        (None, {'fields': ('nombre', 'tipo_curso', 'docente')}),
        ('Organización Académica', {'fields': ('carrera', 'especialidad', 'semestre', 'semestre_cursado')}),
        ('Horario', {'fields': ('dia', 'horario_inicio', 'horario_fin', 'duracion_bloques')}),
    )

@admin.register(DiaEspecial)
class DiaEspecialAdmin(ModelAdmin):
    list_display = ('fecha', 'motivo', 'tipo', 'semestre')
    list_filter = ('tipo', 'semestre')
    ordering = ('-fecha',)
    
@admin.register(FranjaHoraria)
class FranjaHorariaAdmin(ModelAdmin):
    list_display = ('turno', 'hora_inicio', 'hora_fin')
    list_filter = ('turno',)
    ordering = ('hora_inicio',)

class VersionDocumentoInline(TabularInline):
    model = VersionDocumento
    extra = 1
    readonly_fields = ('fecha_version', 'numero_version')

@admin.register(Documento)
class DocumentoAdmin(ModelAdmin):
    list_display = ('titulo', 'docente', 'tipo_documento', 'estado', 'fecha_vencimiento')
    list_filter = ('estado', 'tipo_documento', 'docente')
    search_fields = ('titulo', 'docente__first_name', 'docente__last_name')
    readonly_fields = ('fecha_subida',)
    inlines = [VersionDocumentoInline]

@admin.register(VersionDocumento)
class VersionDocumentoAdmin(ModelAdmin):
    list_display = ('__str__', 'fecha_version')

@admin.register(ConfiguracionInstitucion)
class ConfiguracionInstitucionAdmin(ModelAdmin):
    """
    Panel de administración personalizado para la Configuración de la Institución.
    """
    fieldsets = (
        ('Información Principal', {
            'fields': ('nombre_institucion', 'logo', 'facultad')
        }),
        ('Parámetros del Sistema', {
            'fields': ('tiempo_limite_tardanza',)
        }),
        ('Datos de Contacto (Opcional)', {
            'fields': ('direccion', 'telefono', 'email_contacto'),
            'classes': ('collapse',),
        }),
    )

    def has_add_permission(self, request):
        return not ConfiguracionInstitucion.objects.exists()

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
    list_display = ('docente', 'tipo', 'fecha_inicio', 'fecha_fin', 'estado')
    list_filter = ('estado', 'tipo', 'fecha_inicio')
    search_fields = ('docente__first_name', 'docente__last_name', 'motivo')
    ordering = ('-fecha_creacion',)
    readonly_fields = ('fecha_creacion', 'fecha_revision', 'revisado_por')

    fieldsets = (
        (None, {'fields': ('docente', 'tipo', 'fecha_inicio', 'fecha_fin', 'motivo')}),
        ('Documentación', {'fields': ('documento_adjunto',)}),
        ('Estado de la Solicitud', {'fields': ('estado', 'observaciones_revision', 'revisado_por', 'fecha_revision')}),
    )

    def save_model(self, request, obj, form, change):
        if 'estado' in form.changed_data:
            obj.revisado_por = request.user
            obj.fecha_revision = timezone.now()
        super().save_model(request, obj, form, change)

# --- REGISTRO DEL RESTO DE MODELOS ---
admin.site.register(Grupo)
admin.site.register(Carrera)
admin.site.register(TipoDocumento)
admin.site.register(Asistencia)
admin.site.register(SolicitudIntercambio)
admin.site.register(AsistenciaDiaria)