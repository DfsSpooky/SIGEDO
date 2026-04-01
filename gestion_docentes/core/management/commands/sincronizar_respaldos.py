from django.core.management.base import BaseCommand

from core.utils.backups import synchronize_backup_index


class Command(BaseCommand):
    help = "Sincroniza archivos de respaldo existentes en media/backups con la base de datos."

    def handle(self, *args, **options):
        sincronizados = synchronize_backup_index()
        self.stdout.write(
            self.style.SUCCESS(f"Respaldos sincronizados: {len(sincronizados)}")
        )
