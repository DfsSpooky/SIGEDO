from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import Notificacion

class Command(BaseCommand):
    help = 'Verifies that a notification was created for the test admin user.'

    def handle(self, *args, **options):
        User = get_user_model()
        self.stdout.write('Checking for notifications for the admin user...')

        try:
            admin_user = User.objects.get(username='admin_test')
            notifications = Notificacion.objects.filter(destinatario=admin_user)

            if notifications.exists():
                self.stdout.write(self.style.SUCCESS(f'SUCCESS: Found {notifications.count()} notification(s) for {admin_user.username}.'))
                for notif in notifications:
                    self.stdout.write(f'  - "{notif.mensaje}"')
            else:
                self.stdout.write(self.style.WARNING('WARNING: No notifications found for the admin user.'))

        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR('ERROR: Test admin user "admin_test" not found. Run create_test_document first.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'An unexpected error occurred: {e}'))
