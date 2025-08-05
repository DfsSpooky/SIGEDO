import random
from django.core.management.base import BaseCommand
from faker import Faker
from core.models import Docente, Especialidad

class Command(BaseCommand):
    help = 'Crea 25 docentes de prueba en la base de datos'

    def handle(self, *args, **kwargs):
        self.stdout.write('Iniciando la creación de 25 docentes de prueba...')

        # Usamos Faker para generar datos falsos en español de Perú
        faker = Faker('es')

        # 1. Crear o asegurar que existan algunas especialidades
        especialidades_nombres = [
            'Ingeniería de Sistemas', 'Contabilidad', 'Derecho', 
            'Administración', 'Marketing Digital'
        ]
        especialidades = []
        for nombre in especialidades_nombres:
            esp, created = Especialidad.objects.get_or_create(nombre=nombre)
            especialidades.append(esp)
            if created:
                self.stdout.write(f'Especialidad creada: {nombre}')

        # 2. Bucle para crear 25 docentes
        for i in range(25):
            first_name = faker.first_name()
            last_name = faker.last_name()
            
            # Generar un nombre de usuario único
            username = f"{first_name.lower().split(' ')[0]}.{last_name.lower().split(' ')[0]}{i}"
            email = f"{username}@test.com"
            dni = faker.unique.random_number(digits=8, fix_len=True)
            
            # Asegurarse que el username no exista ya
            if Docente.objects.filter(username=username).exists():
                continue

            try:
                # Usamos create_user para que la contraseña se guarde de forma segura (hasheada)
                docente = Docente.objects.create_user(
                    username=username,
                    password='password123', # Contraseña simple para todos los usuarios de prueba
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    dni=str(dni),
                    especialidad=random.choice(especialidades)
                )
                self.stdout.write(self.style.SUCCESS(f'Docente creado: {docente.username} (DNI: {docente.dni})'))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error al crear docente {username}: {e}'))

        self.stdout.write(self.style.SUCCESS('¡Proceso finalizado! Se crearon los docentes de prueba.'))