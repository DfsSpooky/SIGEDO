import random
from django.core.management.base import BaseCommand
from datetime import date
from django.contrib.auth import get_user_model
from core.models import (
    Carrera, Especialidad, Curso, Semestre, ConfiguracionInstitucion,
    Grupo, Documento, TipoDocumento, Anuncio
)

User = get_user_model()

class Command(BaseCommand):
    help = 'Puebla la base de datos con un escenario específico para la carrera de Educación Secundaria.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('--- Iniciando la población específica para Educación Secundaria ---'))

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
        Grupo.objects.all().delete()
        self.stdout.write(self.style.SUCCESS('... Base de datos limpiada.'))

        # --- 1. Crear Superuser si no existe ---
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@example.com', 'adminpassword', dni='00000000')
            self.stdout.write(self.style.SUCCESS('-> Superusuario "admin" creado.'))

        # --- 2. Crear Configuración y Carrera ---
        ConfiguracionInstitucion.objects.create(nombre_institucion='Universidad de Pruebas')
        carrera_edu = Carrera.objects.create(nombre="EDUCACION SECUNDARIA")
        self.stdout.write(self.style.SUCCESS('-> Carrera "Educación Secundaria" creada.'))

        # --- 3. Crear Grupos y Especialidades ---
        grupo_c = Grupo.objects.create(nombre='Grupo C')
        esp_mat = Especialidad.objects.create(nombre='MATEMATICA', grupo=grupo_c)
        esp_bio = Especialidad.objects.create(nombre='BIOLOGIA', grupo=grupo_c)
        esp_comp = Especialidad.objects.create(nombre='COMPUTACION', grupo=grupo_c)

        grupo_b = Grupo.objects.create(nombre='Grupo B')
        esp_hist = Especialidad.objects.create(nombre='HISTORIA', grupo=grupo_b)
        esp_com = Especialidad.objects.create(nombre='COMUNICACION', grupo=grupo_b)
        esp_fil = Especialidad.objects.create(nombre='FILOSOFIA', grupo=grupo_b)
        self.stdout.write(self.style.SUCCESS('-> Grupos y Especialidades creados según especificaciones.'))

        # --- 4. Crear Docentes ---
        self.stdout.write('... Creando docentes...')
        docentes = {
            'mat': User.objects.create_user(username='h.soto', first_name='Hernán', last_name='Soto', dni='11111111', password='password'),
            'bio': User.objects.create_user(username='g.atencio', first_name='Graciela', last_name='Atencio', dni='22222222', password='password'),
            'comp': User.objects.create_user(username='c.candiotti', first_name='César', last_name='Candiotti', dni='33333333', password='password'),
            'hist': User.objects.create_user(username='j.perez', first_name='Juan', last_name='Perez', dni='44444444', password='password'),
            'com': User.objects.create_user(username='a.gomez', first_name='Ana', last_name='Gomez', dni='55555555', password='password'),
            'fil': User.objects.create_user(username='l.martinez', first_name='Luis', last_name='Martinez', dni='66666666', password='password'),
            'gen1': User.objects.create_user(username='r.rojas', first_name='Rocio', last_name='Rojas', dni='77777777', password='password'),
            'gen2': User.objects.create_user(username='m.diaz', first_name='Mario', last_name='Diaz', dni='88888888', password='password'),
        }

        docentes['mat'].especialidades.add(esp_mat)
        docentes['bio'].especialidades.add(esp_bio)
        docentes['comp'].especialidades.add(esp_comp)
        docentes['hist'].especialidades.add(esp_hist)
        docentes['com'].especialidades.add(esp_com)
        docentes['fil'].especialidades.add(esp_fil)
        self.stdout.write(self.style.SUCCESS('-> Docentes creados y asignados a especialidades.'))

        # --- 5. Crear Semestre Activo ---
        semestre = Semestre.objects.create(
            nombre=f'Semestre {date.today().year}-A',
            fecha_inicio=date(date.today().year, 3, 1),
            fecha_fin=date(date.today().year, 7, 31),
            estado='ACTIVO',
            tipo='IMPAR'
        )
        self.stdout.write(self.style.SUCCESS('-> Semestre activo creado.'))

        # --- 6. Crear Cursos ---
        self.stdout.write('... Creando cursos...')
        # Grupo C
        Curso.objects.create(nombre='Cálculo I', tipo_curso='ESPECIALIDAD', docente=docentes['mat'], carrera=carrera_edu, especialidad=esp_mat, semestre=semestre, semestre_cursado=1)
        Curso.objects.create(nombre='Álgebra Lineal', tipo_curso='ESPECIALIDAD', docente=docentes['mat'], carrera=carrera_edu, especialidad=esp_mat, semestre=semestre, semestre_cursado=3)
        Curso.objects.create(nombre='Biología Celular', tipo_curso='ESPECIALIDAD', docente=docentes['bio'], carrera=carrera_edu, especialidad=esp_bio, semestre=semestre, semestre_cursado=1)
        Curso.objects.create(nombre='Genética', tipo_curso='ESPECIALIDAD', docente=docentes['bio'], carrera=carrera_edu, especialidad=esp_bio, semestre=semestre, semestre_cursado=3)
        Curso.objects.create(nombre='Algoritmos y Programación', tipo_curso='ESPECIALIDAD', docente=docentes['comp'], carrera=carrera_edu, especialidad=esp_comp, semestre=semestre, semestre_cursado=1)
        Curso.objects.create(nombre='Bases de Datos', tipo_curso='ESPECIALIDAD', docente=docentes['comp'], carrera=carrera_edu, especialidad=esp_comp, semestre=semestre, semestre_cursado=3)
        Curso.objects.create(nombre='Estadística Aplicada', tipo_curso='GENERAL', docente=docentes['gen1'], carrera=carrera_edu, especialidad=esp_mat, semestre=semestre, semestre_cursado=1)

        # Grupo B
        Curso.objects.create(nombre='Historia Universal', tipo_curso='ESPECIALIDAD', docente=docentes['hist'], carrera=carrera_edu, especialidad=esp_hist, semestre=semestre, semestre_cursado=1)
        Curso.objects.create(nombre='Historia del Perú', tipo_curso='ESPECIALIDAD', docente=docentes['hist'], carrera=carrera_edu, especialidad=esp_hist, semestre=semestre, semestre_cursado=3)
        Curso.objects.create(nombre='Teoría de la Comunicación', tipo_curso='ESPECIALIDAD', docente=docentes['com'], carrera=carrera_edu, especialidad=esp_com, semestre=semestre, semestre_cursado=1)
        Curso.objects.create(nombre='Redacción Creativa', tipo_curso='ESPECIALIDAD', docente=docentes['com'], carrera=carrera_edu, especialidad=esp_com, semestre=semestre, semestre_cursado=3)
        Curso.objects.create(nombre='Introducción a la Filosofía', tipo_curso='ESPECIALIDAD', docente=docentes['fil'], carrera=carrera_edu, especialidad=esp_fil, semestre=semestre, semestre_cursado=1)
        Curso.objects.create(nombre='Ética y Deontología', tipo_curso='ESPECIALIDAD', docente=docentes['fil'], carrera=carrera_edu, especialidad=esp_fil, semestre=semestre, semestre_cursado=3)
        Curso.objects.create(nombre='Realidad Nacional', tipo_curso='GENERAL', docente=docentes['gen2'], carrera=carrera_edu, especialidad=esp_hist, semestre=semestre, semestre_cursado=1)
        self.stdout.write(self.style.SUCCESS('-> Cursos de especialidad y generales creados.'))

        self.stdout.write(self.style.SUCCESS('--- ¡Población específica del sistema finalizada! ---'))