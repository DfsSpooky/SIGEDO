import random
from django.core.management.base import BaseCommand
from datetime import date, time
from django.contrib.auth import get_user_model
from core.models import (
    Carrera, Especialidad, Curso, Semestre, ConfiguracionInstitucion,
    FranjaHoraria, Grupo, Documento, TipoDocumento, Anuncio
)

User = get_user_model()

class Command(BaseCommand):
    help = 'Puebla la base de datos con un conjunto de datos de prueba completo.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('--- Iniciando la población completa del sistema ---'))

        # Limpiar datos para un inicio fresco
        self.stdout.write('... Limpiando la base de datos...')
        Anuncio.objects.all().delete()
        Documento.objects.all().delete()
        TipoDocumento.objects.all().delete()
        Curso.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()
        Especialidad.objects.all().delete()
        Carrera.objects.all().delete()
        Semestre.objects.all().delete()
        ConfiguracionInstitucion.objects.all().delete()
        FranjaHoraria.objects.all().delete()
        Grupo.objects.all().delete()
        self.stdout.write(self.style.SUCCESS('... Base de datos limpiada.'))

        # --- 1. Crear Superuser si no existe ---
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@example.com', 'adminpassword', dni='00000000')
            self.stdout.write(self.style.SUCCESS('-> Superusuario "admin" creado.'))

        # --- 2. Crear Configuración y Carrera ---
        ConfiguracionInstitucion.objects.create(nombre_institucion='Universidad de Pruebas')
        carrera_edu = Carrera.objects.create(nombre="Educación Secundaria")
        carrera_salud = Carrera.objects.create(nombre="Ciencias de la Salud")
        self.stdout.write(self.style.SUCCESS('-> Configuración y Carreras creadas.'))

        # --- 3. Crear Grupos y Especialidades ---
        grupo_a = Grupo.objects.create(nombre='Grupo A')
        grupo_b = Grupo.objects.create(nombre='Grupo B')
        esp_mat = Especialidad.objects.create(nombre='Matemática', grupo=grupo_a)
        esp_bio = Especialidad.objects.create(nombre='Biología', grupo=grupo_a)
        esp_enf = Especialidad.objects.create(nombre='Enfermería', grupo=grupo_b)
        esp_obs = Especialidad.objects.create(nombre='Obstetricia', grupo=grupo_b)
        self.stdout.write(self.style.SUCCESS('-> Grupos y Especialidades creados.'))

        # --- 4. Crear Docentes y Administradores ---
        self.stdout.write('... Creando usuarios...')
        admin1 = User.objects.create_user(username='admin1', password='password', first_name='Admin', last_name='Uno', dni='11111111', is_staff=True)
        admin2 = User.objects.create_user(username='admin2', password='password', first_name='Admin', last_name='Dos', dni='22222222', is_staff=True)

        docentes_data = [
            {'first_name': 'Carlos', 'last_name': 'Soto', 'dni': '33333333', 'especialidades': [esp_mat]},
            {'first_name': 'Maria', 'last_name': 'Rojas', 'dni': '44444444', 'especialidades': [esp_bio, esp_mat]},
            {'first_name': 'Luis', 'last_name': 'Gonzales', 'dni': '55555555', 'especialidades': [esp_enf]},
            {'first_name': 'Ana', 'last_name': 'Torres', 'dni': '66666666', 'especialidades': [esp_obs]},
            {'first_name': 'Pedro', 'last_name': 'Perez', 'dni': '77777777', 'especialidades': []},
        ]
        docentes = []
        for data in docentes_data:
            username = f"{data['first_name'][0].lower()}{data['last_name'].lower()}"
            docente = User.objects.create_user(username=username, password='password', **{k:v for k,v in data.items() if k != 'especialidades'})
            docente.especialidades.set(data['especialidades'])
            docentes.append(docente)
        self.stdout.write(self.style.SUCCESS('-> 2 administradores y 5 docentes creados.'))

        # --- 5. Crear Semestre Activo ---
        semestre = Semestre.objects.create(
            nombre=f'Semestre {date.today().year}-I',
            fecha_inicio=date(date.today().year, 3, 1),
            fecha_fin=date(date.today().year, 7, 31),
            estado='ACTIVO'
        )
        self.stdout.write(self.style.SUCCESS('-> Semestre activo creado.'))

        # --- 6. Crear Cursos ---
        Curso.objects.create(nombre='Cálculo I', tipo_curso='ESPECIALIDAD', docente=docentes[0], carrera=carrera_edu, especialidad=esp_mat, semestre=semestre, semestre_cursado=1)
        Curso.objects.create(nombre='Biología Celular', tipo_curso='ESPECIALIDAD', docente=docentes[1], carrera=carrera_edu, especialidad=esp_bio, semestre=semestre, semestre_cursado=1)
        Curso.objects.create(nombre='Anatomía Humana', tipo_curso='ESPECIALIDAD', docente=docentes[2], carrera=carrera_salud, especialidad=esp_enf, semestre=semestre, semestre_cursado=3)
        Curso.objects.create(nombre='Ginecología Básica', tipo_curso='ESPECIALIDAD', docente=docentes[3], carrera=carrera_salud, especialidad=esp_obs, semestre=semestre, semestre_cursado=5)
        Curso.objects.create(nombre='Redacción y Comunicación', tipo_curso='GENERAL', docente=docentes[4], carrera=carrera_edu, especialidad=esp_mat, semestre=semestre, semestre_cursado=1)
        self.stdout.write(self.style.SUCCESS('-> Cursos de ejemplo creados.'))

        # --- 7. Crear Tipos de Documento y Documentos ---
        td_silabo = TipoDocumento.objects.create(nombre='Sílabo')
        td_informe = TipoDocumento.objects.create(nombre='Informe Mensual')
        td_cv = TipoDocumento.objects.create(nombre='CV Actualizado')

        # Documentos para Carlos Soto
        doc1 = Documento.objects.create(titulo='Sílabo de Cálculo I', tipo_documento=td_silabo, docente=docentes[0], estado='APROBADO')
        doc2 = Documento.objects.create(titulo='Informe Mensual - Marzo', tipo_documento=td_informe, docente=docentes[0], estado='EN_REVISION')
        
        # Documentos para Maria Rojas
        doc3 = Documento.objects.create(titulo='CV 2025', tipo_documento=td_cv, docente=docentes[1], estado='RECIBIDO')
        # Este cambio de estado debería generar una notificación
        doc3.estado = 'OBSERVADO'
        doc3.save()
        self.stdout.write(self.style.SUCCESS('-> Tipos de documento y documentos de ejemplo creados.'))

        # --- 8. Crear Anuncios ---
        Anuncio.objects.create(titulo='Inicio del Semestre Académico', contenido='Se les recuerda a todos los docentes que el semestre académico inicia el próximo lunes. Por favor, asegúrense de tener sus sílabos actualizados en la plataforma.', autor=admin1)
        Anuncio.objects.create(titulo='Capacitación sobre Nuevo Sistema', contenido='El próximo viernes se realizará una capacitación sobre el uso de la nueva plataforma de gestión docente. La asistencia es obligatoria.', autor=admin2)
        self.stdout.write(self.style.SUCCESS('-> Anuncios de ejemplo creados.'))

        self.stdout.write(self.style.SUCCESS('--- ¡Población completa del sistema finalizada! ---'))