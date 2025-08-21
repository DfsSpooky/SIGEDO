from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.core.exceptions import ValidationError
import uuid
from datetime import date
from PIL import Image

class Grupo(models.Model):
    nombre = models.CharField(max_length=100, help_text="Ej: Grupo A, Grupo B, Grupo C")
    def __str__(self):
        return self.nombre

class Carrera(models.Model):
    nombre = models.CharField(max_length=100)
    def __str__(self):
        return self.nombre

class Especialidad(models.Model):
    nombre = models.CharField(max_length=100)
    grupo = models.ForeignKey(Grupo, on_delete=models.SET_NULL, null=True, blank=True, related_name='especialidades')
    
    def __str__(self):
        return self.nombre

class TipoDocumento(models.Model):
    nombre = models.CharField(max_length=100)
    def __str__(self): return self.nombre

class Semestre(models.Model):
    ESTADOS = [('PLANIFICACION', 'En Planificación'), ('ACTIVO', 'Activo'), ('CERRADO', 'Cerrado')]
    TIPO_SEMESTRE = [('IMPAR', 'Impar (A)'), ('PAR', 'Par (B)')]
    nombre = models.CharField(max_length=100, help_text="Ej: Semestre 2025-A")
    tipo = models.CharField(max_length=10, choices=TIPO_SEMESTRE, default='IMPAR')
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    estado = models.CharField(max_length=20, choices=ESTADOS, default='PLANIFICACION')
    def __str__(self): return f"{self.nombre} ({self.get_estado_display()})"
    def save(self, *args, **kwargs):
        if self.estado == 'ACTIVO':
            Semestre.objects.filter(estado='ACTIVO').exclude(pk=self.id).update(estado='CERRADO')
        super(Semestre, self).save(*args, **kwargs)

class FranjaHoraria(models.Model):
    TURNO_CHOICES = [('MANANA', 'Mañana'), ('TARDE', 'Tarde'), ('NOCHE', 'Noche')]
    turno = models.CharField(max_length=10, choices=TURNO_CHOICES)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    class Meta:
        verbose_name = "Franja Horaria"; verbose_name_plural = "Franjas Horarias"; ordering = ['hora_inicio']
    def __str__(self): return f"{self.get_turno_display()}: {self.hora_inicio.strftime('%I:%M %p')} - {self.hora_fin.strftime('%I:%M %p')}"

class DiaEspecial(models.Model):
    TIPO_CHOICES = [('FERIADO', 'Feriado (No se labora)'), ('EVENTO', 'Evento Institucional (Se labora, sin clases)'), ('SUSPENSION', 'Suspensión de Clases')]
    fecha = models.DateField(unique=True)
    motivo = models.CharField(max_length=255)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    semestre = models.ForeignKey(Semestre, on_delete=models.CASCADE, null=True, blank=True)
    def __str__(self): return f"{self.fecha}: {self.motivo} ({self.get_tipo_display()})"

class Docente(AbstractUser):
    DISPONIBILIDAD_CHOICES = [('COMPLETO', 'Tiempo Completo (Mañana y Tarde)'), ('MANANA', 'Solo Mañana'), ('TARDE', 'Solo Tarde')]
    dni = models.CharField(max_length=8, unique=True, db_index=True)
    especialidades = models.ManyToManyField(Especialidad, related_name="docentes")
    disponibilidad = models.CharField(max_length=20, choices=DISPONIBILIDAD_CHOICES, default='COMPLETO')
    id_qr = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    rfid_uid = models.CharField(max_length=100, unique=True, null=True, blank=True, help_text="UID de la tarjeta RFID asignada al docente")
    foto = models.ImageField(upload_to='fotos_docentes/', null=True, blank=True, default='fotos_docentes/placeholder.png')

    def __str__(self): return f"{self.first_name} {self.last_name}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.foto:
            try:
                img = Image.open(self.foto.path)
                if img.height > 300 or img.width > 300:
                    output_size = (300, 300)
                    img.thumbnail(output_size)
                    img.save(self.foto.path, format='PNG', quality=85)
            except Exception as e:
                # Log the error, but don't prevent the model from saving
                print(f"Error al redimensionar la imagen para {self.username}: {e}")

class Curso(models.Model):
    TIPO_CURSO_CHOICES = [('ESPECIALIDAD', 'Especialidad'), ('GENERAL', 'General')]
    SEMESTRE_CURSADO_CHOICES = [(1, 'Semestre I'), (2, 'Semestre II'), (3, 'Semestre III'), (4, 'Semestre IV'), (5, 'Semestre V'), (6, 'Semestre VI'), (7, 'Semestre VII'), (8, 'Semestre VIII'), (9, 'Semestre IX'), (10, 'Semestre X')]
    nombre = models.CharField(max_length=100)
    tipo_curso = models.CharField(max_length=20, choices=TIPO_CURSO_CHOICES, default='ESPECIALIDAD')
    docente = models.ForeignKey(Docente, on_delete=models.SET_NULL, null=True, blank=True)
    carrera = models.ForeignKey(Carrera, on_delete=models.CASCADE)
    especialidad = models.ForeignKey(Especialidad, on_delete=models.SET_NULL, null=True, related_name='cursos')
    semestre = models.ForeignKey(Semestre, on_delete=models.SET_NULL, null=True, related_name='cursos')
    semestre_cursado = models.IntegerField(choices=SEMESTRE_CURSADO_CHOICES, null=True, blank=True)
    horario_inicio = models.TimeField(null=True, blank=True)
    horario_fin = models.TimeField(null=True, blank=True)
    dia = models.CharField(max_length=20, choices=[('Lunes', 'Lunes'), ('Martes', 'Martes'), ('Miércoles', 'Miércoles'), ('Jueves', 'Jueves'), ('Viernes', 'Viernes')], null=True, blank=True)
    duracion_bloques = models.IntegerField(default=2, help_text="Número de bloques de 50 minutos que dura el curso.")

    class Meta:
        permissions = [
            ("view_planificador", "Puede ver el planificador de horarios"),
        ]

    def __str__(self): return f"{self.nombre} ({self.especialidad.nombre if self.especialidad else 'N/A'})"

class Documento(models.Model):
    ESTADOS_DOCUMENTO = [
        ('RECIBIDO', 'Recibido'),
        ('EN_REVISION', 'En Revisión'),
        ('APROBADO', 'Aprobado'),
        ('OBSERVADO', 'Observado'),
        ('VENCIDO', 'Vencido'),
    ]

    titulo = models.CharField(max_length=200)
    tipo_documento = models.ForeignKey(TipoDocumento, on_delete=models.CASCADE)
    docente = models.ForeignKey(Docente, on_delete=models.CASCADE, related_name='documentos')
    fecha_subida = models.DateTimeField(auto_now_add=True)
    fecha_vencimiento = models.DateField(null=True, blank=True, help_text="Opcional: Dejar en blanco si el documento no vence.")
    estado = models.CharField(max_length=20, choices=ESTADOS_DOCUMENTO, default='RECIBIDO')
    observaciones = models.TextField(blank=True, help_text="Notas internas para la administración.")

    def __str__(self): 
        return self.titulo
    
class VersionDocumento(models.Model):
    documento = models.ForeignKey(Documento, on_delete=models.CASCADE, related_name='versiones')
    archivo = models.FileField(upload_to='documentos/%Y/%m/%d/')
    fecha_version = models.DateTimeField(auto_now_add=True)
    numero_version = models.PositiveIntegerField(editable=False)

    class Meta:
        ordering = ['-fecha_version']

    def save(self, *args, **kwargs):
        if not self.pk:
            ultima_version = VersionDocumento.objects.filter(documento=self.documento).order_by('-numero_version').first()
            self.numero_version = (ultima_version.numero_version + 1) if ultima_version else 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.documento.titulo} (v{self.numero_version})"

class Asistencia(models.Model):
    docente = models.ForeignKey(Docente, on_delete=models.CASCADE)
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE)
    fecha = models.DateField(default=timezone.now)
    hora_entrada = models.DateTimeField(null=True, blank=True)
    hora_salida = models.DateTimeField(null=True, blank=True)
    hora_salida_permitida = models.DateTimeField(null=True, blank=True, help_text="Hora mínima a la que se puede marcar la salida.")
    foto_entrada = models.ImageField(upload_to='verificacion_cursos/entradas/%Y/%m/%d/', null=True, blank=True)
    foto_salida = models.ImageField(upload_to='verificacion_cursos/salidas/%Y/%m/%d/', null=True, blank=True)

    class Meta:
        permissions = [
            ("view_reporte", "Puede ver reportes de asistencia"),
        ]

    def __str__(self): return f"Asistencia {self.docente} - {self.curso} ({self.fecha})"

class AsistenciaDiaria(models.Model):
    docente = models.ForeignKey(Docente, on_delete=models.CASCADE)
    fecha = models.DateField(default=date.today)
    hora_entrada = models.DateTimeField(auto_now_add=True)
    foto_verificacion = models.ImageField(upload_to='verificacion_diaria/%Y/%m/%d/', null=True, blank=True)
    def __str__(self): return f"Asistencia Diaria de {self.docente} - {self.fecha}"

class SolicitudIntercambio(models.Model):
    docente_solicitante = models.ForeignKey(Docente, on_delete=models.CASCADE, related_name='solicitudes_enviadas')
    curso_solicitante = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='solicitudes_solicitante')
    docente_destino = models.ForeignKey(Docente, on_delete=models.CASCADE, related_name='solicitudes_recibidas')
    curso_destino = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='solicitudes_destino')
    estado = models.CharField(max_length=20, choices=[('pendiente', 'Pendiente'), ('aprobado', 'Aprobado'), ('rechazado', 'Rechazado')], default='pendiente')
    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    def __str__(self): return f"Solicitud {self.docente_solicitante} -> {self.docente_destino} ({self.estado})"

class ConfiguracionInstitucion(models.Model):
    nombre_institucion = models.CharField(max_length=255, help_text="El nombre oficial de la institución.")
    logo = models.ImageField(upload_to='configuracion/', help_text="Logo que aparecerá en las credenciales y reportes.")
    direccion = models.CharField(max_length=255, blank=True, help_text="Dirección física de la institución.")
    telefono = models.CharField(max_length=20, blank=True, help_text="Teléfono de contacto.")
    email_contacto = models.EmailField(blank=True, help_text="Email de contacto oficial.")
    facultad = models.ForeignKey(
        Carrera, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        help_text="Seleccione la facultad o carrera principal para la cual se está configurando el sistema."
    )
    tiempo_limite_tardanza = models.PositiveIntegerField(default=10, help_text="Minutos de tolerancia para considerar una asistencia como tardanza.")
    nombre_dashboard = models.CharField(max_length=100, default="Gestión Docente", help_text="El nombre que se mostrará en el dashboard.")
    
    class Meta:
        verbose_name = "Configuración de la Institución"; verbose_name_plural = "Configuración de la Institución"
        
    def __str__(self): return self.nombre_institucion
    
    @classmethod
    def load(cls):
        obj = cls.objects.first()
        if obj is None:
            obj = cls.objects.create()
        return obj

class PersonalDocente(Docente):
    class Meta:
        proxy = True; verbose_name = 'Personal Docente'; verbose_name_plural = 'Personal Docente'

class Administrador(Docente):
    class Meta:
        proxy = True; verbose_name = 'Administrador'; verbose_name_plural = 'Administradores'

class Notificacion(models.Model):
    destinatario = models.ForeignKey(Docente, on_delete=models.CASCADE, related_name='notificaciones')
    mensaje = models.CharField(max_length=255)
    leido = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    url = models.CharField(max_length=255, blank=True, help_text="URL a la que la notificación debe dirigir.")

    class Meta:
        ordering = ['-fecha_creacion']
        verbose_name = "Notificación"
        verbose_name_plural = "Notificaciones"

    def __str__(self):
        return f"Notificación para {self.destinatario.username}: {self.mensaje[:30]}..."

class Anuncio(models.Model):
    titulo = models.CharField(max_length=200)
    contenido = models.TextField()
    fecha_publicacion = models.DateTimeField(auto_now_add=True)
    autor = models.ForeignKey(Docente, on_delete=models.SET_NULL, null=True, limit_choices_to={'is_staff': True})

    class Meta:
        ordering = ['-fecha_publicacion']
        verbose_name = "Anuncio"
        verbose_name_plural = "Anuncios"

    def __str__(self):
        return self.titulo

class TipoJustificacion(models.Model):
    nombre = models.CharField(max_length=100, unique=True, help_text="Ej: Licencia Médica, Comisión de Servicio, Permiso Personal")

    def __str__(self):
        return self.nombre

class Justificacion(models.Model):
    ESTADOS_APROBACION = [
        ('PENDIENTE', 'Pendiente'),
        ('APROBADO', 'Aprobado'),
        ('RECHAZADO', 'Rechazado'),
    ]

    docente = models.ForeignKey(Docente, on_delete=models.CASCADE, related_name='justificaciones')
    tipo = models.ForeignKey(TipoJustificacion, on_delete=models.PROTECT, related_name='justificaciones')
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    motivo = models.TextField(help_text="Explique brevemente el motivo de su ausencia.")
    documento_adjunto = models.FileField(upload_to='justificaciones/', blank=True, null=True, help_text="Opcional: Adjunte un documento que respalde su solicitud (PDF, imagen, etc.)")
    estado = models.CharField(max_length=20, choices=ESTADOS_APROBACION, default='PENDIENTE')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_revision = models.DateTimeField(null=True, blank=True)
    revisado_por = models.ForeignKey(Docente, on_delete=models.SET_NULL, null=True, blank=True, related_name='justificaciones_revisadas', limit_choices_to={'is_staff': True})
    observaciones_revision = models.TextField(blank=True, help_text="Notas internas del administrador que revisa la solicitud.")

    def __str__(self):
        return f"Justificación de {self.docente} ({self.fecha_inicio} al {self.fecha_fin}) - {self.get_estado_display()}"

    def clean(self):
        if self.fecha_inicio > self.fecha_fin:
            raise ValidationError("La fecha de inicio no puede ser posterior a la fecha de fin.")

    class Meta:
        ordering = ['-fecha_creacion']

# Importar modelos de módulos separados para mantener el código organizado
from .models_inventario import *
