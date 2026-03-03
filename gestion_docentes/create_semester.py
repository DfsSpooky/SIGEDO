import os
import django
from datetime import date, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_docentes.settings')
django.setup()

from core.models import Semestre, Curso

def create_active_semester():
    # Creamos un semestre "PAR" (ya que los semestres cursados de los profes son II, IV, VI, VIII, X)
    nombre_semestre = "2026-II"
    fecha_inicio = date.today()
    fecha_fin = date.today() + timedelta(days=120)  # Aprox 4 meses de duración

    semestre, created = Semestre.objects.get_or_create(
        nombre=nombre_semestre,
        defaults={
            'tipo': 'PAR',
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
            'estado': 'ACTIVO'
        }
    )
    
    if not created and semestre.estado != 'ACTIVO':
        semestre.estado = 'ACTIVO'
        semestre.save()
        
    print(f"✅ Semestre '{semestre.nombre}' configurado y marcado como ACTIVO.")
    
    # Asignar todos los cursos a este semestre para poder probar el sistema
    cursos_actualizados = Curso.objects.filter(semestre__isnull=True).update(semestre=semestre)
    
    print(f"✅ Se han asignado {cursos_actualizados} cursos al semestre '{semestre.nombre}'.")

if __name__ == "__main__":
    create_active_semester()
