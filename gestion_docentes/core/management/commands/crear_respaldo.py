from django.core.management.base import BaseCommand, CommandError

from core.models import Docente
from core.utils.backups import BackupError, create_system_backup


class Command(BaseCommand):
    help = "Crea un respaldo completo de la base de datos actual."

    def add_arguments(self, parser):
        parser.add_argument("--nombre", dest="nombre")
        parser.add_argument("--descripcion", dest="descripcion", default="")
        parser.add_argument("--user-id", dest="user_id", type=int)
        parser.add_argument("--origen", dest="origen", default="GENERADO")

    def handle(self, *args, **options):
        user = None
        if options.get("user_id"):
            user = Docente.objects.filter(pk=options["user_id"]).first()

        try:
            respaldo = create_system_backup(
                created_by=user,
                nombre=options.get("nombre"),
                descripcion=options.get("descripcion", ""),
                origen=options.get("origen", "GENERADO"),
            )
        except BackupError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Respaldo creado: #{respaldo.pk} - {respaldo.nombre_archivo}"
            )
        )
