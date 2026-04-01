from django.core.management.base import BaseCommand, CommandError

from core.models import Docente, RespaldoSistema
from core.utils.backups import BackupError, restore_system_backup


class Command(BaseCommand):
    help = "Restaura un respaldo registrado en el sistema."

    def add_arguments(self, parser):
        parser.add_argument("backup_id", type=int)
        parser.add_argument("--user-id", dest="user_id", type=int)

    def handle(self, *args, **options):
        respaldo = RespaldoSistema.objects.filter(pk=options["backup_id"]).first()
        if respaldo is None:
            raise CommandError("No existe el respaldo indicado.")

        user = None
        if options.get("user_id"):
            user = Docente.objects.filter(pk=options["user_id"]).first()

        try:
            restaurado, previo = restore_system_backup(respaldo, restored_by=user)
        except BackupError as exc:
            raise CommandError(str(exc)) from exc

        mensaje = f"Respaldo restaurado: #{restaurado.pk}"
        if previo:
            mensaje += f" | respaldo previo: #{previo.pk}"
        self.stdout.write(self.style.SUCCESS(mensaje))
