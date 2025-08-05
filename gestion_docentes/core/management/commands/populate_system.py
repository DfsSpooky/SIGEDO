import random
from django.core.management.base import BaseCommand
from datetime import date, timedelta, time
from core.models import (
    Carrera, Especialidad, Docente, Curso, Semestre, ConfiguracionInstitucion, FranjaHoraria, Grupo
)

class Command(BaseCommand):
    help = 'Puebla la base de datos con un escenario específico para probar los cursos generales por grupo.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('--- Iniciando la población del sistema para la prueba de Cursos Generales ---'))
        
        # Limpiar datos para un inicio fresco
        Curso.objects.all().delete()
        Docente.objects.filter(is_superuser=False).delete()
        Especialidad.objects.all().delete()
        Carrera.objects.all().delete()
        Semestre.objects.all().delete()
        ConfiguracionInstitucion.objects.all().delete()
        FranjaHoraria.objects.all().delete()
        Grupo.objects.all().delete()
        self.stdout.write('... Datos antiguos eliminados.')

        # 1. Crear Configuración y Carrera
        ConfiguracionInstitucion.objects.get_or_create(
            pk=1, defaults={'nombre_institucion': 'UNIVERSIDAD NACIONAL DANIEL ALCIDES CARRIÓN'}
        )
        carrera, _ = Carrera.objects.get_or_create(nombre="EDUCACION SECUNDARIA")
        self.stdout.write('-> Configuración y Carrera creadas.')

        # 2. Crear Franjas Horarias
        franjas_data = [
            ('MANANA', time(8, 0), time(8, 50)), ('MANANA', time(8, 50), time(9, 40)),
            ('MANANA', time(9, 40), time(10, 30)), ('MANANA', time(10, 30), time(11, 20)),
        ]
        for turno, inicio, fin in franjas_data:
            FranjaHoraria.objects.get_or_create(turno=turno, hora_inicio=inicio, hora_fin=fin)
        self.stdout.write(f'-> {len(franjas_data)} Franjas Horarias creadas.')

        # 3. Crear Grupo y Especialidades
        grupo_c, _ = Grupo.objects.get_or_create(nombre='Grupo C')
        self.stdout.write('-> Grupo C creado.')

        especialidades_data = ['Matemática', 'Biología', 'Computacion']
        for esp_nombre in especialidades_data:
            Especialidad.objects.get_or_create(nombre=esp_nombre, grupo=grupo_c)
        self.stdout.write('-> Especialidades creadas y asignadas a Grupo C.')

        # 4. Crear Docentes
        docentes_data = {
            'Matemática': 'SOTO MATEO Hernán',
            'Biología': 'ATENCIO CARHUARICRA Graciela',
            'Computacion': 'CANDIOTTI PACHECO, Cesar',
            'General': 'ROJAS CALDERON Rocio Pilar'
        }
        todos_los_docentes = {}
        for nombre, nombre_completo in docentes_data.items():
            partes = nombre_completo.replace(',', '').split()
            primer_nombre = partes[-1].capitalize() if partes else ''
            apellido_paterno = partes[0].capitalize() if partes else ''
            username = f"{primer_nombre[0].lower()}{apellido_paterno.lower()}"
            docente, created = Docente.objects.get_or_create(
                username=username,
                defaults={'first_name': primer_nombre, 'last_name': " ".join(partes[0:-1]), 'dni': f"{random.randint(10000000, 99999999)}"}
            )
            if created: docente.set_password('password123'); docente.save()
            todos_los_docentes[nombre] = docente
            if nombre != 'General':
                especialidad = Especialidad.objects.get(nombre=nombre)
                docente.especialidades.add(especialidad)
        
        # 5. Crear Semestre Activo
        semestre_activo, _ = Semestre.objects.get_or_create(
            nombre=f'Semestre {date.today().year}-A',
            defaults={'fecha_inicio': date(date.today().year, 3, 17), 'fecha_fin': date(date.today().year, 7, 11), 'estado': 'ACTIVO', 'tipo': 'IMPAR'}
        )

        # 6. Crear Cursos de Especialidad y Generales
        # Cursos Generales para el Grupo C (vinculados a una especialidad, pero con tipo 'GENERAL')
        general_docente = todos_los_docentes.get('General')
        especialidad_base_general = Especialidad.objects.get(nombre='Matemática')
        if general_docente:
            Curso.objects.get_or_create(
                nombre='Filosofía y Lógica', semestre_cursado=1, especialidad=especialidad_base_general, semestre=semestre_activo,
                defaults={'carrera': carrera, 'docente': general_docente, 'tipo_curso': 'GENERAL', 'duracion_bloques': 2}
            )
            Curso.objects.get_or_create(
                nombre='Inglés Básico I', semestre_cursado=1, especialidad=especialidad_base_general, semestre=semestre_activo,
                defaults={'carrera': carrera, 'docente': general_docente, 'tipo_curso': 'GENERAL', 'duracion_bloques': 2}
            )

        # Cursos de Especialidad
        cursos_especialidad_data = {
            'Matemática': [('Cálculo I', 'SOTO MATEO Hernán'), ('Álgebra Superior', 'SOTO MATEO Hernán')],
            'Biología': [('Biología Celular', 'ATENCIO CARHUARICRA Graciela'), ('Química Orgánica', 'ATENCIO CARHUARICRA Graciela')],
            'Computacion': [('Algoritmos', 'CANDIOTTI PACHECO, Cesar'), ('Estructuras de Datos', 'CANDIOTTI PACHECO, Cesar')],
        }
        for esp_nombre, cursos_data in cursos_especialidad_data.items():
            especialidad = Especialidad.objects.get(nombre=esp_nombre)
            for nombre_curso, nombre_docente in cursos_data:
                docente_obj = Docente.objects.get(first_name=nombre_docente.split()[-1])
                if docente_obj:
                    Curso.objects.get_or_create(
                        nombre=nombre_curso, semestre_cursado=1, especialidad=especialidad, semestre=semestre_activo,
                        defaults={'carrera': carrera, 'docente': docente_obj, 'tipo_curso': 'ESPECIALIDAD', 'duracion_bloques': 2}
                    )
        
        self.stdout.write(self.style.SUCCESS('--- ¡Población del sistema para prueba completada! ---'))