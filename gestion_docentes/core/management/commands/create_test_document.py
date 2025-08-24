from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import Docente, TipoDocumento, Documento

class Command(BaseCommand):
    help = 'Creates a test document to trigger a notification.'

    def handle(self, *args, **options):
        User = get_user_model()

        # Ensure an admin user exists to receive the notification
        admin_user, created = User.objects.get_or_create(
            username='admin_test',
            defaults={
                'first_name': 'Admin',
                'last_name': 'Test',
                'email': 'admin@test.com',
                'is_staff': True,
                'is_superuser': True,
            }
        )
        if created:
            admin_user.set_password('password')
            admin_user.save()
            self.stdout.write(self.style.SUCCESS('Created test admin user.'))

        # Create a dummy teacher to be the author
        teacher, created = Docente.objects.get_or_create(
            username='teacher_test',
            dni='12345678',
            defaults={'first_name': 'Test', 'last_name': 'Teacher'}
        )
        if created:
            self.stdout.write(self.style.SUCCESS('Created test teacher.'))

        # Create a document type
        doc_type, created = TipoDocumento.objects.get_or_create(nombre='Declaración Jurada')
        if created:
            self.stdout.write(self.style.SUCCESS('Created document type.'))

        # Create the document
        self.stdout.write('Creating a new document...')
        Documento.objects.create(
            titulo='Test Document for Notification',
            tipo_documento=doc_type,
            docente=teacher,
            estado='RECIBIDO'
        )

        self.stdout.write(self.style.SUCCESS('Successfully created a test document.'))
        self.stdout.write('This should have triggered a notification for the admin user.')
