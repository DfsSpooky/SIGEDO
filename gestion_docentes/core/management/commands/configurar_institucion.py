from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model
from core.models.academic import Carrera, Grupo, Especialidad, Semestre, Curso
from core.models.scheduling import FranjaHoraria, BloqueHorario
from core.models.settings import ConfiguracionInstitucion
from datetime import time, date

User = get_user_model()

class Command(BaseCommand):
    help = "Limpia y configura la institución, carrera, grupos, especialidades, semestre activo y franjas horarias."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Limpiando la base de datos..."))
        
        # 0. Limpieza
        BloqueHorario.objects.all().delete()
        Curso.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()
        FranjaHoraria.objects.all().delete()
        Especialidad.objects.all().delete()
        Grupo.objects.all().delete()
        Carrera.objects.all().delete()
        Semestre.objects.all().delete()
        ConfiguracionInstitucion.objects.all().delete()

        self.stdout.write(self.style.SUCCESS("Base de datos limpia."))

        # 1. Institución
        self.stdout.write("Configurando Institución...")
        institucion = ConfiguracionInstitucion.objects.create(
            nombre_institucion="UNIVERSIDAD NACIONAL DANIEL ALCIDES CARRIÓN"
        )
        
        # 2. Carrera
        self.stdout.write("Creando Carrera...")
        carrera = Carrera.objects.create(
            nombre="ESCUELA PROFESIONAL DE EDUCACIÓN SECUNDARIA"
        )
        institucion.facultad = carrera
        institucion.save()

        # 3. Grupos
        self.stdout.write("Creando Grupos...")
        grupo_a = Grupo.objects.create(nombre="Grupo A")
        grupo_b = Grupo.objects.create(nombre="Grupo B")
        grupo_c = Grupo.objects.create(nombre="Grupo C")

        # 4. Especialidades
        self.stdout.write("Asignando Especialidades a Grupos...")
        
        # Grupo A
        esp_grupo_a = [
            "HISTORIA CCSS Y TURISMO",
            "CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA"
        ]
        for esp_nombre in esp_grupo_a:
            Especialidad.objects.create(nombre=esp_nombre, grupo=grupo_a)

        # Grupo B
        esp_grupo_b = [
            "COMUNICACIÓN Y LITERATURA",
            "LENGUAS EXTRANJERAS: INGLÉS FRANCÉS" 
        ]
        for esp_nombre in esp_grupo_b:
            Especialidad.objects.create(nombre=esp_nombre, grupo=grupo_b)
            
        # Grupo C
        esp_grupo_c = [
            "BIOLOGIA Y QUIMICA",
            "MATEMATICA - FISICA",
            "TECNOLOGIA INFORMATICA Y TELECOMUNICACIONES"
        ]
        for esp_nombre in esp_grupo_c:
            Especialidad.objects.create(nombre=esp_nombre, grupo=grupo_c)

        # 5. Semestre Activo
        self.stdout.write("Creando Semestre Activo...")
        Semestre.objects.create(
            nombre="2026-A",
            tipo="IMPAR",
            estado="ACTIVO",
            fecha_inicio=date(2026, 3, 1),
            fecha_fin=date(2026, 7, 31)
        )

        # 6. Franjas Horarias
        self.stdout.write("Creando Franjas Horarias...")
        # Mañana
        FranjaHoraria.objects.create(hora_inicio=time(7, 0), hora_fin=time(7, 50), turno='MANANA')
        FranjaHoraria.objects.create(hora_inicio=time(7, 50), hora_fin=time(8, 40), turno='MANANA')
        FranjaHoraria.objects.create(hora_inicio=time(8, 40), hora_fin=time(9, 30), turno='MANANA')
        FranjaHoraria.objects.create(hora_inicio=time(9, 30), hora_fin=time(10, 20), turno='MANANA')
        FranjaHoraria.objects.create(hora_inicio=time(10, 20), hora_fin=time(11, 10), turno='MANANA')
        FranjaHoraria.objects.create(hora_inicio=time(11, 10), hora_fin=time(12, 0), turno='MANANA')
        FranjaHoraria.objects.create(hora_inicio=time(12, 0), hora_fin=time(12, 50), turno='MANANA')
        FranjaHoraria.objects.create(hora_inicio=time(12, 50), hora_fin=time(13, 40), turno='MANANA')
        
        # Tarde
        FranjaHoraria.objects.create(hora_inicio=time(14, 0), hora_fin=time(14, 50), turno='TARDE')
        FranjaHoraria.objects.create(hora_inicio=time(14, 50), hora_fin=time(15, 40), turno='TARDE')
        FranjaHoraria.objects.create(hora_inicio=time(15, 40), hora_fin=time(16, 30), turno='TARDE')
        FranjaHoraria.objects.create(hora_inicio=time(16, 30), hora_fin=time(17, 20), turno='TARDE')
        FranjaHoraria.objects.create(hora_inicio=time(17, 20), hora_fin=time(18, 10), turno='TARDE')
        FranjaHoraria.objects.create(hora_inicio=time(18, 10), hora_fin=time(19, 0), turno='TARDE')
        FranjaHoraria.objects.create(hora_inicio=time(19, 0), hora_fin=time(19, 50), turno='TARDE')
        FranjaHoraria.objects.create(hora_inicio=time(19, 50), hora_fin=time(20, 40), turno='TARDE')

        self.stdout.write(self.style.SUCCESS("¡Configuración institucional completada exitosamente! Ya puede ejecutar el importador principal."))
