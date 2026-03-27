import os
import csv
import django
from collections import defaultdict

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_docentes.settings')
django.setup()

from core.models import Docente, Curso, Carrera, Especialidad, Semestre, Grupo
from core.utils.docente_identity import normalize_docente_key


def clean_name(raw_name):
    # Remove prefix like "Dr.", "Mg.", "Dra."
    prefixes = ["Dr.", "Dra.", "Mg.", "Lic.", "Ing.", "Prof."]
    name = raw_name.strip()
    for prefix in prefixes:
        if name.startswith(prefix):
            name = name[len(prefix):].strip()
    
    if "Contrato" in name:
        return "Docente", "Contratado"
    
    parts = name.split()
    if len(parts) >= 3:
        # Assume first 1 or 2 are names, rest are last names
        # Let's just do an even split or 1st name vs rest
        first_name = parts[0]
        last_name = " ".join(parts[1:])
        return first_name, last_name
    elif len(parts) == 2:
        return parts[0], parts[1]
    else:
        return name, ""

def import_data():
    csv_file = '/app/docentes.csv'
    output_csv = '/app/accesos_docentes.csv'
    
    if not os.path.exists(csv_file):
        print(f"Error: {csv_file} no encontrado.")
        return

    carrera = Carrera.objects.get(nombre="Educación Secundaria")
    
    docentes_creados = {}
    docentes_index = {}
    dni_counter = 10000001

    for docente_existente in Docente.objects.filter(is_staff=False, is_superuser=False):
        nombre_existente = f"{docente_existente.first_name} {docente_existente.last_name}".strip()
        key = normalize_docente_key(nombre_existente)
        if key and key not in docentes_index:
            docentes_index[key] = docente_existente
    
    with open(csv_file, newline='', encoding='utf-8') as f, \
         open(output_csv, 'w', newline='', encoding='utf-8') as out_f:
        
        reader = csv.DictReader(f)
        writer = csv.writer(out_f)
        writer.writerow(['Nombre Original', 'Nombres', 'Apellidos', 'Usuario (DNI)', 'Contraseña'])
        
        for row in reader:
            raw_name = row['Nombre docente'].strip()
            curso_name = row['Nombre curso'].strip()
            programa_raw = row['Programa'].strip()
            semestre_raw = row['Semestre'].strip()
            tipo_curso_raw = row['Especialidad o general'].strip()
            
            # --- 1. DOCENTE ---
            docente_key = normalize_docente_key(raw_name)
            if docente_key and docente_key not in docentes_creados:
                first_name, last_name = clean_name(raw_name)
                dni = str(dni_counter)

                # Reusar docente existente por clave canónica para evitar duplicados.
                docente = docentes_index.get(docente_key)
                if not docente:
                    docente = Docente.objects.filter(first_name=first_name, last_name=last_name).first()

                if not docente:
                    docente = Docente.objects.create_user(
                        username=dni,
                        password='12345',
                        first_name=first_name,
                        last_name=last_name,
                        dni=dni
                    )
                    writer.writerow([raw_name, first_name, last_name, dni, '12345'])
                    dni_counter += 1

                if docente_key:
                    docentes_index[docente_key] = docente
                    docentes_creados[docente_key] = docente
                else:
                    docentes_creados[raw_name] = docente
            else:
                docente = docentes_creados.get(docente_key) if docente_key else docentes_creados[raw_name]
                
            # --- 2. ESPECIALIDAD ---
            # Try to find exactly or 'contains'
            especialidad = None
            for esp in Especialidad.objects.all():
                if esp.nombre.lower() == programa_raw.lower() or esp.nombre.lower().replace(",", "") == programa_raw.lower():
                    especialidad = esp
                    break
            
            if especialidad:
                docente.especialidades.add(especialidad)
                
            # --- 3. CURSO ---
            # Parse semester strings like "II-A / IV-A" or "VI-C"
            # Map roman to int
            roman_to_int = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10}
            
            # extract roman numerals
            parts = semestre_raw.replace('/', ' ').replace('-', ' ').split()
            semestres_ints = []
            for p in parts:
                if p in roman_to_int:
                    semestres_ints.append(roman_to_int[p])
                    
            tipo_curso = "ESPECIALIDAD" if "Especialidad" in tipo_curso_raw else "GENERAL"
            
            for sem_int in semestres_ints:
                # Create a course for each semester
                curso_identifier = f"{curso_name} - Sem {sem_int}"
                curso, created = Curso.objects.get_or_create(
                    nombre=curso_name,
                    carrera=carrera,
                    semestre_cursado=sem_int,
                    defaults={
                        'tipo_curso': tipo_curso,
                        'docente': docente,
                        'horas_academicas_semanales': 4, # default
                    }
                )
                if not created:
                    # Update just in case
                    curso.docente = docente
                    curso.save()

                if especialidad:
                    curso.especialidades.add(especialidad)
                    
    print(f"Importación completada. Se generaron accesos en {output_csv}.")


if __name__ == "__main__":
    import_data()
