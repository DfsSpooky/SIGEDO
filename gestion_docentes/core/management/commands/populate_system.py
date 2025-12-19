import random
from datetime import date, time

from core.models import (
    Carrera,
    Curso,
    Docente,
    Especialidad,
    FranjaHoraria,
    Grupo,
    Semestre,
)
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

User = get_user_model()


class Command(BaseCommand):
    help = "Puebla la base de datos con una estructura de grupos, especialidades y cursos bien definida."

    @transaction.atomic
    def handle(self, *args, **kwargs):
        self.stdout.write(
            self.style.SUCCESS("--- Iniciando la nueva población del sistema ---")
        )

        # --- 1. Limpiar la base de datos ---
        self.stdout.write("... Limpiando datos existentes...")
        Curso.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()
        Especialidad.objects.all().delete()
        Grupo.objects.all().delete()
        Carrera.objects.all().delete()
        Semestre.objects.all().delete()
        FranjaHoraria.objects.all().delete()
        self.stdout.write(self.style.SUCCESS("-> Modelos principales limpiados."))

        # --- 2. Crear usuarios clave ---
        self.stdout.write("... Creando usuarios clave...")
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser(
                "admin", "admin@example.com", "12345", dni="10000000"
            )

        secretaria, _ = User.objects.get_or_create(
            username="secretaria",
            defaults={
                "first_name": "Secretaria",
                "last_name": "Académica",
                "is_staff": True,
                "dni": "10000001",
            },
        )
        secretaria.set_password("123456")
        secretaria.save()

        director, _ = User.objects.get_or_create(
            username="director",
            defaults={
                "first_name": "Director",
                "last_name": "General",
                "is_staff": True,
                "is_superuser": True,
                "dni": "10000002",
            },
        )
        director.set_password("123456")
        director.save()
        self.stdout.write(
            self.style.SUCCESS(
                "-> Usuarios admin, secretaria y director creados/actualizados."
            )
        )

        # --- 3. Crear Carrera y Semestre ---
        carrera_edu, _ = Carrera.objects.get_or_create(nombre="EDUCACION SECUNDARIA")
        semestre, _ = Semestre.objects.get_or_create(
            nombre=f"Semestre {date.today().year}-A",
            defaults={
                "fecha_inicio": date(date.today().year, 3, 1),
                "fecha_fin": date(date.today().year, 8, 31),
                "estado": "ACTIVO",
                "tipo": "IMPAR",
            },
        )
        self.stdout.write(self.style.SUCCESS("-> Carrera y Semestre creados."))

        # --- 4. Crear Franjas Horarias ---
        franjas_data = [
            ("MANANA", time(8, 0), time(8, 50)),
            ("MANANA", time(8, 50), time(9, 40)),
            ("MANANA", time(9, 40), time(10, 30)),
            ("MANANA", time(10, 30), time(11, 20)),
            ("MANANA", time(11, 20), time(12, 10)),
            ("MANANA", time(12, 10), time(13, 0)),
            ("TARDE", time(15, 0), time(15, 50)),
            ("TARDE", time(15, 50), time(16, 40)),
            ("TARDE", time(16, 40), time(17, 30)),
            ("TARDE", time(17, 30), time(18, 20)),
            ("TARDE", time(18, 20), time(19, 10)),
        ]
        for turno, inicio, fin in franjas_data:
            FranjaHoraria.objects.get_or_create(
                turno=turno, hora_inicio=inicio, hora_fin=fin
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"-> {len(franjas_data)} Franjas Horarias creadas/verificadas."
            )
        )

        # --- 5. Crear Grupos, Especialidades, Docentes y Cursos ---
        self.stdout.write("... Creando estructura académica...")

        grupos_data = {
            "Grupo A": ["Historia", "Comunicacion", "Ingles"],
            "Grupo B": ["Filosofía", "Biologia"],
            "Grupo C": ["Matematica", "Computacion", "Quimica"],
        }

        docentes_generales = []
        for i in range(5):
            docente_gen, created = Docente.objects.get_or_create(
                username=f"general{i+1}",
                defaults={
                    "first_name": f"DocenteGeneral{i+1}",
                    "last_name": "Multi",
                    "dni": f"9000000{i}",
                },
            )
            if created:
                docente_gen.set_password("123456")
                docente_gen.save()
            docentes_generales.append(docente_gen)

        for grupo_nombre, especialidades_nombres in grupos_data.items():
            grupo, _ = Grupo.objects.get_or_create(nombre=grupo_nombre)
            for esp_nombre in especialidades_nombres:
                especialidad, _ = Especialidad.objects.get_or_create(
                    nombre=esp_nombre, defaults={"grupo": grupo}
                )

                docentes_especialidad = []
                for i in range(3):
                    docente, created = Docente.objects.get_or_create(
                        username=f"d{i+1}{esp_nombre[:4].lower()}",
                        defaults={
                            "first_name": f"Docente{i+1}",
                            "last_name": esp_nombre,
                            "dni": f"{random.randint(20000000, 89999999)}",
                        },
                    )
                    if created:
                        docente.set_password("123456")
                        docente.save()
                    docente.especialidades.add(especialidad)
                    docentes_especialidad.append(docente)

                for sem_cursado in range(1, 11):
                    # Crear 2 cursos de especialidad
                    for i in range(2):
                        Curso.objects.create(
                            nombre=f"Curso de {esp_nombre} {i+1} - Sem {sem_cursado}",
                            tipo_curso="ESPECIALIDAD",
                            docente=random.choice(docentes_especialidad),
                            carrera=carrera_edu,
                            especialidad=especialidad,
                            semestre=semestre,
                            semestre_cursado=sem_cursado,
                            horas_academicas_semanales=random.choice([2, 3, 4]),
                        )

                    # Crear 1 curso general con posible excepción
                    nombre_curso_general = f"Curso General {sem_cursado}"
                    es_excepcion = False

                    # Hacemos que el curso general del 2do semestre del primer grupo sea 'Educación Física'
                    if sem_cursado == 2 and grupo_nombre == "Grupo A":
                        nombre_curso_general = "Educación Física"
                        es_excepcion = True

                    Curso.objects.create(
                        nombre=nombre_curso_general,
                        tipo_curso="GENERAL",
                        docente=random.choice(docentes_generales),
                        carrera=carrera_edu,
                        especialidad=especialidad,
                        semestre=semestre,
                        semestre_cursado=sem_cursado,
                        horas_academicas_semanales=random.choice([2, 3]),
                        excepcion_horario=es_excepcion,
                    )

        self.stdout.write(self.style.SUCCESS("-> Estructura académica creada."))
        self.stdout.write(
            self.style.SUCCESS("--- ¡Población completa del sistema finalizada! ---")
        )
