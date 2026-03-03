import os
import django
from datetime import time

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_docentes.settings')
django.setup()

from core.models import (
    ConfiguracionInstitucion, Carrera, Grupo, Especialidad, FranjaHoraria, Semestre
)

def create_time_slots():
    print("Creando franjas horarias...")
    FranjaHoraria.objects.all().delete()
    
    # Mañana: 8:00 - 13:50 (7 bloques de 50 min)
    manana_slots = [
        (time(8, 0), time(8, 50)),
        (time(8, 50), time(9, 40)),
        (time(9, 40), time(10, 30)),
        (time(10, 30), time(11, 20)),
        (time(11, 20), time(12, 10)),
        (time(12, 10), time(13, 0)),
        (time(13, 0), time(13, 50)),
    ]
    for start, end in manana_slots:
        FranjaHoraria.objects.create(turno="MANANA", hora_inicio=start, hora_fin=end)
        
    # Tarde: 15:00 - 20:50 (7 bloques de 50 min)
    tarde_slots = [
        (time(15, 0), time(15, 50)),
        (time(15, 50), time(16, 40)),
        (time(16, 40), time(17, 30)),
        (time(17, 30), time(18, 20)),
        (time(18, 20), time(19, 10)),
        (time(19, 10), time(20, 0)),
        (time(20, 0), time(20, 50)),
    ]
    for start, end in tarde_slots:
        FranjaHoraria.objects.create(turno="TARDE", hora_inicio=start, hora_fin=end)
        
    print(f"Creadas {FranjaHoraria.objects.count()} franjas horarias.")

def create_curriculum():
    print("Configurando institución y carrera...")
    # Configurar Institución
    config = ConfiguracionInstitucion.load()
    config.nombre_institucion = "Universidad Nacional Daniel Alcides Carrión"
    
    # Crear Programa (Carrera)
    carrera, _ = Carrera.objects.get_or_create(nombre="Educación Secundaria")
    
    config.facultad = carrera
    config.save()
    
    print("Creando grupos y especialidades...")
    Grupo.objects.all().delete()
    Especialidad.objects.all().delete()
    
    # Grupo A
    grupo_a = Grupo.objects.create(nombre="Grupo A")
    e_historia_a = Especialidad.objects.create(nombre="Historia, Ciencias Sociales y Turismo", grupo=grupo_a)
    e_ciencias_a = Especialidad.objects.create(nombre="Ciencias Sociales, Filosofía y Psicología Educativa", grupo=grupo_a)

    # Grupo B
    grupo_b = Grupo.objects.create(nombre="Grupo B")
    e_comunicacion_b = Especialidad.objects.create(nombre="Comunicación y Literatura", grupo=grupo_b)
    e_idiomas_b = Especialidad.objects.create(nombre="Idiomas Extranjeros", grupo=grupo_b)

    # Grupo C
    grupo_c = Grupo.objects.create(nombre="Grupo C")
    e_mate_c = Especialidad.objects.create(nombre="Matemática y Física", grupo=grupo_c)
    e_telecom_c = Especialidad.objects.create(nombre="Telecomunicaciones e Informática Educativa", grupo=grupo_c)
    e_biologia_c = Especialidad.objects.create(nombre="Biología y Química", grupo=grupo_c)

    print(f"Creados {Grupo.objects.count()} grupos y {Especialidad.objects.count()} especialidades.")
    
def run():
    print("Iniciando población de datos...")
    create_time_slots()
    create_curriculum()
    print("¡Finalizado exitosamente!")

if __name__ == "__main__":
    run()
