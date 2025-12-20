import random
from datetime import date, time, timedelta

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
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.core.exceptions import ValidationError

User = get_user_model()


class Command(BaseCommand):
    help = "Puebla la base de datos con estructura académica, inventario y reservas de prueba (CORREGIDO)."

    @transaction.atomic
    def handle(self, *args, **kwargs):
        self.stdout.write(
            self.style.SUCCESS("--- Iniciando población COMPLETA del sistema ---")
        )

        # --- 1. Limpiar la base de datos ---
        self.stdout.write("... Limpiando datos existentes...")
        Reserva.objects.all().delete()
        Activo.objects.all().delete()
        TipoActivo.objects.all().delete()
        BloqueHorario.objects.all().delete()
        Curso.objects.all().delete()
        User.objects.filter(is_superuser=False).exclude(username="admin").delete()
        Especialidad.objects.all().delete()
        Grupo.objects.all().delete()
        Carrera.objects.all().delete()
        Semestre.objects.all().delete()
        FranjaHoraria.objects.all().delete()
        self.stdout.write(self.style.SUCCESS("-> Base de datos limpia."))

        # --- 2. Crear usuarios clave ---
        self.stdout.write("... Creando usuarios administrativos...")
        
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
        if _: secretaria.set_password("123456"); secretaria.save()

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
        if _: director.set_password("123456"); director.save()

        # --- 3. Estructura Académica Básica ---
        carrera_edu, _ = Carrera.objects.get_or_create(nombre="EDUCACION SECUNDARIA")
        
        semestre, _ = Semestre.objects.get_or_create(
            nombre=f"Semestre {date.today().year}-A",
            defaults={
                "fecha_inicio": date(date.today().year, 3, 1),
                "fecha_fin": date(date.today().year, 7, 31),
                "estado": "ACTIVO",
                "tipo": "IMPAR",
            },
        )

        # --- 4. Franjas Horarias ---
        franjas_data = [
            ("MANANA", time(8, 0), time(8, 50)),
            ("MANANA", time(8, 50), time(9, 40)),
            ("MANANA", time(9, 40), time(10, 30)),
            ("MANANA", time(10, 30), time(11, 20)),
            ("MANANA", time(11, 20), time(12, 10)),
            ("MANANA", time(12, 10), time(13, 0)),
            ("TARDE", time(14, 0), time(14, 50)),
            ("TARDE", time(14, 50), time(15, 40)),
            ("TARDE", time(15, 40), time(16, 30)),
            ("TARDE", time(16, 30), time(17, 20)),
            ("TARDE", time(17, 20), time(18, 10)),
        ]
        
        objs_franjas = []
        for turno, inicio, fin in franjas_data:
            f, _ = FranjaHoraria.objects.get_or_create(
                turno=turno, hora_inicio=inicio, hora_fin=fin
            )
            objs_franjas.append(f)

        # --- 5. Grupos, Especialidades y Docentes ---
        self.stdout.write("... Configurando Grupos y Especialidades...")

        grupos_config = {
            "Grupo A": ["Computación", "Educación Física"], 
            "Grupo B": ["Historia", "Filosofía", "Comunicación", "Inglés"], 
            "Grupo C": ["Telecomunicaciones", "Matemática", "Biología"],    
        }

        docentes_creados = []
        
        def crear_docente(nombre_base, especialidad_obj, i):
            disponibilidad = random.choice(["MANANA", "TARDE", "COMPLETO"])
            dni = f"{random.randint(10000000, 99999999)}"
            # Generar un UID simple para pruebas
            uid_rfid = f"RFID-{nombre_base[:3].upper()}-{i}-{random.randint(100,999)}"
            
            user = Docente.objects.create_user(
                username=f"docente_{nombre_base.lower()}_{i}",
                password="123",
                first_name=f"Profesor {i}",
                last_name=nombre_base,
                dni=dni,
                disponibilidad=disponibilidad,
                rfid_uid=uid_rfid
            )
            user.especialidades.add(especialidad_obj)
            return user

        cursos_creados = []

        for grupo_nom, especialidades in grupos_config.items():
            grupo, _ = Grupo.objects.get_or_create(nombre=grupo_nom)
            for esp_nom in especialidades:
                especialidad, _ = Especialidad.objects.get_or_create(
                    nombre=esp_nom, defaults={"grupo": grupo}
                )
                
                local_docentes = []
                for i in range(1, 3):
                    doc = crear_docente(esp_nom, especialidad, i)
                    local_docentes.append(doc)
                    docentes_creados.append(doc)

                # Crear Cursos
                semestres_a_crear = [1, 3, 5, 7, 9] 
                for sem_num in semestres_a_crear:
                    docente_asignado = random.choice(local_docentes)
                    horas = random.choice([2, 4, 6])
                    
                    curso = Curso.objects.create(
                        nombre=f"{esp_nom} {sem_num}",
                        tipo_curso="ESPECIALIDAD",
                        docente=docente_asignado,
                        carrera=carrera_edu,
                        especialidad=especialidad,
                        semestre=semestre,
                        semestre_cursado=sem_num,
                        horas_academicas_semanales=horas,
                        excepcion_horario=(docente_asignado.disponibilidad == 'TARDE')
                    )
                    cursos_creados.append(curso)

        # --- 6. Generación de Horarios (Planificación) ---
        self.stdout.write("... Generando Bloques de Horario...")
        bloques_creados = 0
        dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]

        for curso in cursos_creados:
            horas_pendientes = curso.horas_academicas_semanales
            intentos = 0
            while horas_pendientes > 0 and intentos < 50:
                intentos += 1
                dia = random.choice(dias_semana)
                
                franjas_disponibles = list(FranjaHoraria.objects.all())
                if curso.docente.disponibilidad == "MANANA":
                    franjas_disponibles = [f for f in franjas_disponibles if f.turno == "MANANA"]
                elif curso.docente.disponibilidad == "TARDE":
                    franjas_disponibles = [f for f in franjas_disponibles if f.turno == "TARDE"]
                
                if not franjas_disponibles: continue

                franja = random.choice(franjas_disponibles)
                duracion = 2 if horas_pendientes >= 2 else 1
                
                # Check colisiones simples
                ocupado_docente = BloqueHorario.objects.filter(curso__docente=curso.docente, dia=dia, franja_inicio=franja).exists()
                ocupado_curso = BloqueHorario.objects.filter(curso=curso, dia=dia, franja_inicio=franja).exists()

                if not ocupado_docente and not ocupado_curso:
                    try:
                        BloqueHorario.objects.create(
                            curso=curso, dia=dia, franja_inicio=franja, duracion_bloques=duracion
                        )
                        horas_pendientes -= duracion
                        bloques_creados += 1
                    except ValidationError:
                        pass

        # --- 7. Crear Inventario (Categorías y Activos) ---
        self.stdout.write("... Creando inventario de equipos (Tipos y Activos)...")
        
        tipos_equipos = ["Proyectores", "Laptops", "Equipos de Sonido", "Cables y Adaptadores"]
        
        activos_creados = []
        for nombre in tipos_equipos:
            # CORRECCIÓN 1: Eliminamos 'defaults' con 'descripcion' que no existe
            tipo_obj, _ = TipoActivo.objects.get_or_create(nombre=nombre)
            
            # Crear entre 3 y 5 activos por tipo
            for i in range(1, random.randint(4, 6)):
                codigo_val = f"{nombre[:3].upper()}-{random.randint(1000, 9999)}"
                
                estado = "DISPONIBLE"
                if random.random() < 0.2: estado = "EN_MANTENIMIENTO" # Corregido para coincidir con choices
                elif random.random() < 0.2: estado = "ASIGNADO"

                # CORRECCIÓN 2: Cambiamos 'codigo' por 'codigo_patrimonial'
                activo, _ = Activo.objects.get_or_create(
                    codigo_patrimonial=codigo_val,
                    defaults={
                        "nombre": f"{nombre[:-1]} {i} (Marca Genérica)",
                        "tipo": tipo_obj,
                        "estado": estado,
                        "descripcion": f"Activo de prueba {codigo_val}. Perfecto estado.",
                        "fecha_adquisicion": date.today() - timedelta(days=random.randint(100, 1000))
                    }
                )
                if estado == "DISPONIBLE":
                    activos_creados.append(activo)

        self.stdout.write(self.style.SUCCESS(f"-> Inventario creado: {len(activos_creados)} activos disponibles."))

        # --- 8. Crear Reservas de Equipos ---
        self.stdout.write("... Creando reservas de equipos...")
        
        reservas_count = 0
        if activos_creados and docentes_creados and objs_franjas:
            for _ in range(15): # Crear 15 reservas aleatorias
                docente = random.choice(docentes_creados)
                activo = random.choice(activos_creados)
                franja = random.choice(objs_franjas)
                fecha_reserva = date.today() + timedelta(days=random.choice([0, 1]))
                
                # Verificar que no exista reserva
                existe = Reserva.objects.filter(
                    activo=activo, 
                    fecha_reserva=fecha_reserva, 
                    franja_horaria_inicio=franja
                ).exists()

                if not existe:
                    try:
                        estado_reserva = random.choice(["RESERVADO", "EN_USO", "FINALIZADO"])
                        
                        # Buscar cursos del docente si existen (manualmente para evitar errores de relación)
                        curso_docente = Curso.objects.filter(docente=docente).first()
                        
                        # CORRECCIÓN 3: Eliminamos 'motivo' que no existe en el modelo Reserva
                        Reserva.objects.create(
                            docente=docente,
                            activo=activo,
                            fecha_reserva=fecha_reserva,
                            franja_horaria_inicio=franja,
                            franja_horaria_fin=franja, # Asumimos 1 bloque de duración
                            curso=curso_docente,
                            estado=estado_reserva
                        )
                        reservas_count += 1
                    except Exception as e:
                        # Si algo falla en la reserva específica, continuamos con la siguiente
                        pass

        self.stdout.write(self.style.SUCCESS(f"-> {reservas_count} reservas de prueba creadas."))
        self.stdout.write(self.style.SUCCESS("--- ¡Población completa del sistema finalizada! ---"))