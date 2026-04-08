from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime
from core.models import Asistencia

class Command(BaseCommand):
    help = 'Automatically checks out courses where the end time has passed but no exit has been marked.'

    def handle(self, *args, **options):
        self.stdout.write("Starting auto-checkout process...")

        now = timezone.now()
        open_attendances = Asistencia.objects.filter(hora_entrada__isnull=False, hora_salida__isnull=True)

        checked_out_count = 0

        for a in open_attendances:
            if a.curso and a.curso.horario_fin:
                # Combine the attendance date with the course's end time
                end_time_naive = datetime.combine(a.fecha, a.curso.horario_fin)
                # Make it timezone-aware
                end_time_aware = timezone.make_aware(end_time_naive, timezone.get_current_timezone())

                # If the current time is past the scheduled end time
                if now > end_time_aware:
                    a.hora_salida = end_time_aware
                    a.save()
                    checked_out_count += 1
                    self.stdout.write(self.style.SUCCESS(f"Checked out {a.docente} from {a.curso} for {a.fecha}."))

        self.stdout.write(self.style.SUCCESS(f"Auto-checkout process finished. {checked_out_count} attendances were closed."))
