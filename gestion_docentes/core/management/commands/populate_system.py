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
    BloqueNoLectivo,  # <--- Nuevo modelo importado
    TipoActivo,
    Activo,
    Reserva,
)
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.core.exceptions import ValidationError
from django.db.models import Q

User = get_user_model()


class Command(BaseCommand):
    help = "Puebla la base de datos con estructura académica, bloques de gestión, inventario y reservas."

    @transaction.atomic
    def handle(self, *args, **kwargs):
        self.stdout.write(
            self.style.SUCCESS("--- Iniciando población AVANZADA del sistema ---")
        )

        # --- 1. Limpiar la base de datos ---
        self.stdout.write("... Limpiando datos existentes...")
        Reserva.objects.all().delete()
        Activo.objects.all().delete()
        TipoActivo.objects.all().delete()
        BloqueNoLectivo.objects.all().delete() # <--- Limpieza de gestión
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

                # Crear Cursos (Semestres Impares por ser tipo IMPAR)
                semestres_a_crear = [1, 3, 5, 7, 9] 
                for sem_num in semestres_a_crear:
                    docente_asignado = random.choice(local_docentes)
                    # Variamos las horas para que algunos cursos queden pendientes en el planificador
                    horas = random.choice([2, 3, 4, 5, 6]) 
                    
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

        # --- 6. Generación de Horarios de Clase (Planificación) ---
        self.stdout.write("... Generando Bloques de Horario (Clases)...")
        bloques_clase_creados = 0
        dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]

        for curso in cursos_creados:
            horas_pendientes = curso.horas_academicas_semanales
            intentos = 0
            
            # Intentamos asignar la mayoría, pero dejamos algunos pendientes a propósito
            # para probar el drag-and-drop manual
            limit_fill = 0.8 # Llenar el 80% aprox
            if random.random() > limit_fill:
                continue 

            while horas_pendientes > 0 and intentos < 50:
                intentos += 1
                dia = random.choice(dias_semana)
                
                # Filtrar franjas por disponibilidad docente
                franjas_disponibles = list(FranjaHoraria.objects.all())
                if curso.docente.disponibilidad == "MANANA":
                    franjas_disponibles = [f for f in franjas_disponibles if f.turno == "MANANA"]
                elif curso.docente.disponibilidad == "TARDE":
                    franjas_disponibles = [f for f in franjas_disponibles if f.turno == "TARDE"]
                
                if not franjas_disponibles: continue

                franja = random.choice(franjas_disponibles)
                duracion = 2 if horas_pendientes >= 2 else 1
                
                # Check colisiones (Clases y Gestión)
                # Nota: Como aún no creamos gestión en este script, solo checamos clases,
                # pero en un sistema real checkearíamos ambos.
                ocupado_docente = BloqueHorario.objects.filter(curso__docente=curso.docente, dia=dia, franja_inicio=franja).exists()
                ocupado_grupo = BloqueHorario.objects.filter(
                    curso__especialidad__grupo=curso.especialidad.grupo,
                    curso__semestre_cursado=curso.semestre_cursado,
                    dia=dia, 
                    franja_inicio=franja
                ).exists()

                if not ocupado_docente and not ocupado_grupo:
                    try:
                        BloqueHorario.objects.create(
                            curso=curso, dia=dia, franja_inicio=franja, duracion_bloques=duracion
                        )
                        horas_pendientes -= duracion
                        bloques_clase_creados += 1
                    except ValidationError:
                        pass
        
        self.stdout.write(f"-> {bloques_clase_creados} bloques de clase creados.")

        # --- 7. Generación de Bloques de Gestión (NUEVO) ---
        self.stdout.write("... Generando Bloques de Gestión (Administrativos)...")
        bloques_gestion_creados = 0
        motivos_gestion = ["Coordinación Académica", "Tutoría de Estudiantes", "Investigación", "Reunión de Área", "Atención a Padres"]

        for docente in docentes_creados:
            # Asignar 1 o 2 bloques de gestión por docente
            for _ in range(random.randint(1, 2)):
                dia = random.choice(dias_semana)
                franjas_disponibles = list(FranjaHoraria.objects.all())
                
                # Respetar turno del docente
                if docente.disponibilidad == "MANANA":
                    franjas_disponibles = [f for f in franjas_disponibles if f.turno == "MANANA"]
                elif docente.disponibilidad == "TARDE":
                    franjas_disponibles = [f for f in franjas_disponibles if f.turno == "TARDE"]
                
                if not franjas_disponibles: continue
                
                franja = random.choice(franjas_disponibles)
                duracion = random.choice([1, 2])
                motivo = random.choice(motivos_gestion)

                # Check colisiones con Clases existentes
                # Calculamos hora fin aproximada para el filtro
                # (Simplificación para el script de populate)
                ocupado_clase = BloqueHorario.objects.filter(
                    curso__docente=docente, 
                    dia=dia, 
                    franja_inicio=franja
                ).exists()
                
                # Check colisiones con otros bloques de gestión
                ocupado_gestion = BloqueNoLectivo.objects.filter(
                    docente=docente,
                    dia=dia,
                    franja_inicio=franja
                ).exists()

                if not ocupado_clase and not ocupado_gestion:
                    try:
                        BloqueNoLectivo.objects.create(
                            docente=docente,
                            semestre=semestre,
                            dia=dia,
                            franja_inicio=franja,
                            duracion_bloques=duracion,
                            motivo=motivo
                        )
                        bloques_gestion_creados += 1
                    except Exception: 
                        pass # Si falla por validación compleja (horas intermedias), ignorar en populate

        self.stdout.write(f"-> {bloques_gestion_creados} bloques de gestión creados.")

        # --- 8. Crear Inventario (Categorías y Activos) ---
        self.stdout.write("... Creando inventario de equipos...")
        
        tipos_equipos = ["Proyectores", "Laptops", "Equipos de Sonido", "Cables y Adaptadores"]
        activos_creados = []
        for nombre in tipos_equipos:
            tipo_obj, _ = TipoActivo.objects.get_or_create(nombre=nombre)
            
            for i in range(1, random.randint(4, 6)):
                codigo_val = f"{nombre[:3].upper()}-{random.randint(1000, 9999)}"
                estado = "DISPONIBLE"
                if random.random() < 0.2: estado = "EN_MANTENIMIENTO"
                elif random.random() < 0.2: estado = "ASIGNADO"

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

        # --- 9. Crear Reservas de Equipos ---
        self.stdout.write("... Creando reservas de equipos...")
        reservas_count = 0
        if activos_creados and docentes_creados and objs_franjas:
            for _ in range(15):
                docente = random.choice(docentes_creados)
                activo = random.choice(activos_creados)
                franja = random.choice(objs_franjas)
                fecha_reserva = date.today() + timedelta(days=random.choice([0, 1]))
                
                existe = Reserva.objects.filter(activo=activo, fecha_reserva=fecha_reserva, franja_horaria_inicio=franja).exists()

                if not existe:
                    try:
                        curso_docente = Curso.objects.filter(docente=docente).first()
                        Reserva.objects.create(
                            docente=docente,
                            activo=activo,
                            fecha_reserva=fecha_reserva,
                            franja_horaria_inicio=franja,
                            franja_horaria_fin=franja,
                            curso=curso_docente,
                            estado=random.choice(["RESERVADO", "EN_USO", "FINALIZADO"])
                        )
                        reservas_count += 1
                    except Exception: pass

        self.stdout.write(self.style.SUCCESS(f"-> {reservas_count} reservas de prueba creadas."))
        self.stdout.write(self.style.SUCCESS("--- ¡Población completa del sistema finalizada! ---"))