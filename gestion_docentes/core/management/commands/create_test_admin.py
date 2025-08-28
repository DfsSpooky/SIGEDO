from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = 'Creates a test admin user for development.'

    def handle(self, *args, **options):
        User = get_user_model()
        if not User.objects.filter(username='testadmin').exists():
            User.objects.create_superuser('testadmin', 'admin@example.com', 'testpassword', dni='99999999')
            self.stdout.write(self.style.SUCCESS('Successfully created test admin user.'))
        else:
            self.stdout.write(self.style.WARNING('Test admin user already exists.'))
