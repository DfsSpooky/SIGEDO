
import random
import time
from datetime import date, timedelta, time as datetime_time

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.contrib.auth import get_user_model
from core.models import (
    Carrera,
    Curso,
    Docente,
    Especialidad,
    FranjaHoraria,
    Grupo,
    Semestre,
    BloqueHorario,
    TipoActivo,
    Activo,
    Reserva,
)

# Docente is our custom User model
User = get_user_model()

class Command(BaseCommand):
    help = "Puebla la base de datos con estructura académica completa, incluyendo cursos generales y docentes válidos."

    @transaction.atomic
    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS("--- Iniciando población COMPLETA DEL SISTEMA ---"))

        # --- 1. Limpieza ---
        self.stdout.write("... Limpiando base de datos...")
        Reserva.objects.all().delete()
        Activo.objects.all().delete()
        TipoActivo.objects.all().delete()
        BloqueHorario.objects.all().delete()
        Curso.objects.all().delete()
        Especialidad.objects.all().delete()
        Grupo.objects.all().delete()
        Carrera.objects.all().delete()
        Semestre.objects.all().delete()
        FranjaHoraria.objects.all().delete()
        # Delete non-superuser/non-admin users
        User.objects.filter(is_superuser=False, is_staff=False).delete()
        
        # --- 2. Usuarios Clave ---
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser("admin", "admin@example.com", "12345", dni="10000000")
            self.stdout.write("Usuario 'admin' creado.")

        # --- 3. Semestre ---
        semestre, _ = Semestre.objects.get_or_create(
            nombre=f"Semestre {date.today().year}-A",
            defaults={
                "fecha_inicio": date(date.today().year, 3, 1),
                "fecha_fin": date(date.today().year, 7, 31),
                "estado": "ACTIVO",
                "tipo": "IMPAR",
            },
        )
        self.stdout.write(f"Semestre {semestre} creado.")

        # --- 4. Franjas Horarias ---
        franjas_data = [
            ("MANANA", datetime_time(8, 0), datetime_time(8, 50)),
            ("MANANA", datetime_time(8, 50), datetime_time(9, 40)),
            ("MANANA", datetime_time(9, 40), datetime_time(10, 30)),
            ("MANANA", datetime_time(10, 30), datetime_time(11, 20)),
            ("MANANA", datetime_time(11, 20), datetime_time(12, 10)),
            ("MANANA", datetime_time(12, 10), datetime_time(13, 0)),
            ("TARDE", datetime_time(14, 0), datetime_time(14, 50)),
            ("TARDE", datetime_time(14, 50), datetime_time(15, 40)),
            ("TARDE", datetime_time(15, 40), datetime_time(16, 30)),
            ("TARDE", datetime_time(16, 30), datetime_time(17, 20)),
            ("TARDE", datetime_time(17, 20), datetime_time(18, 10)),
        ]
        for turno, inicio, fin in franjas_data:
            FranjaHoraria.objects.get_or_create(turno=turno, hora_inicio=inicio, hora_fin=fin)

        # --- 5. Estructura Académica (Carrera, Grupos, Especialidades) ---
        carrera, _ = Carrera.objects.get_or_create(nombre="EDUCACION SECUNDARIA")
        
        grupos_data = {
            "Grupo A": ["Computación", "Educación Física"],
            "Grupo B": ["Historia", "Filosofía", "Comunicación"],
            "Grupo C": ["Biología", "Matemática", "Telecomunicaciones"],
        }
        
        especialidades_objs = {} # {nombre: obj}
        grupo_objs = {} # {nombre: obj}

        for g_nombre, esps in grupos_data.items():
            g, _ = Grupo.objects.get_or_create(nombre=g_nombre)
            grupo_objs[g_nombre] = g
            for e_nombre in esps:
                e, _ = Especialidad.objects.get_or_create(nombre=e_nombre, grupo=g)
                especialidades_objs[e_nombre] = e

        # --- 6. Helper Docentes ---
        nombres = ["Juan", "Maria", "Carlos", "Ana", "Luis", "Elena", "Pedro", "Sofia", "Miguel", "Lucia"]
        apellidos = ["Perez", "Gomez", "Rodriguez", "Lopez", "Garcia", "Martinez", "Sanchez", "Fernandez", "Diaz", "Torres"]
        
        def crear_docente():
            # Retry logic for uniqueness
            for _ in range(10):
                nombre = random.choice(nombres)
                apellido = random.choice(apellidos)
                ts = int(time.time() * 10000)
                username = f"{nombre.lower()}{random.randint(10,99)}.{ts}"[-20:]
                email = f"{username}@example.com"
                base_dni = str(random.randint(10000000, 99999999))
                
                if not User.objects.filter(dni=base_dni).exists():
                    try:
                        d = User.objects.create_user(
                            username=username,
                            email=email,
                            password='12345',
                            first_name=nombre,
                            last_name=apellido,
                            dni=base_dni,
                            celular=f"9{random.randint(10000000, 99999999)}",
                            rfid_uid=f"RFID-{base_dni}",
                            disponibilidad=random.choice(["MANANA", "TARDE", "COMPLETO"])
                        )
                        return d
                    except Exception:
                        continue
            return None

        # --- 7. Creación de Cursos y Asignación ---
        self.stdout.write("... Creando Cursos y Asignando Docentes...")
        
        # Lista de cursos ESPECIALIDAD por nombre base
        cursos_especialidad_nombres = [
            "Práctica Docente", "Didáctica Específica", "Taller de Investigación", 
            "Programación Curricular", "Evaluación del Aprendizaje"
        ]
        
        # Lista de cursos GENERALES (compartidos por grupo)
        cursos_generales_nombres = [
            "Investigación I", "Realidad Nacional", "Psicología Educativa", "Ética Profesional"
        ]

        semestres_impares = [1, 3, 5, 7, 9]

        count_cursos = 0

        # A. Cursos de Especialidad (Uno por cada especialidad)
        for esp_nombre, esp_obj in especialidades_objs.items():
            for sem in semestres_impares:
                # Elegir nombre aleatorio o fijo
                nombre_base = random.choice(cursos_especialidad_nombres)
                nombre_curso = f"{nombre_base} ({esp_nombre}) {sem}"
                
                docente = crear_docente()
                if not docente: continue

                c = Curso.objects.create(
                    nombre=nombre_curso,
                    tipo_curso="ESPECIALIDAD",
                    docente=docente,
                    carrera=carrera,
                    semestre=semestre,
                    semestre_cursado=sem,
                    horas_academicas_semanales=random.choice([4, 6]),
                    excepcion_horario=(docente.disponibilidad == 'TARDE')
                )
                c.especialidades.add(esp_obj)
                count_cursos += 1

        # B. Cursos Generales (Uno por GRUPO, con TODAS sus especialidades)
        for g_nombre, grupo_obj in grupo_objs.items():
            esps_del_grupo = Especialidad.objects.filter(grupo=grupo_obj)
            
            for sem in semestres_impares[:3]: # Solo primeros semestres
                nombre_base = random.choice(cursos_generales_nombres)
                nombre_curso = f"{nombre_base} (General {g_nombre}) {sem}"
                
                docente = crear_docente()
                if not docente: continue

                c = Curso.objects.create(
                    nombre=nombre_curso,
                    tipo_curso="GENERAL",
                    docente=docente,
                    carrera=carrera,
                    semestre=semestre,
                    semestre_cursado=sem,
                    horas_academicas_semanales=2,
                    excepcion_horario=(docente.disponibilidad == 'TARDE')
                )
                # Agregar TODAS las especialidades del grupo
                c.especialidades.set(esps_del_grupo)
                count_cursos += 1

        self.stdout.write(f"-> {count_cursos} cursos creados (Especialidad y Generales).")

        # --- 8. Inventario y Reservas ---
        self.stdout.write("... Creando Inventario Básico...")
        t_laptop, _ = TipoActivo.objects.get_or_create(nombre="Laptops")
        t_proyector, _ = TipoActivo.objects.get_or_create(nombre="Proyectores")
        
        for i in range(5):
            Activo.objects.create(
                nombre=f"Laptop Dell {i+1}",
                codigo_patrimonial=f"LP-{100+i}",
                tipo=t_laptop,
                estado="DISPONIBLE",
                descripcion="Laptop de prueba"
            )
            Activo.objects.create(
                nombre=f"Proyector Epson {i+1}",
                codigo_patrimonial=f"PR-{100+i}",
                tipo=t_proyector,
                estado="DISPONIBLE",
                descripcion="Proyector de prueba"
            )

        self.stdout.write(self.style.SUCCESS("--- Población Finalizada Correctamente ---"))