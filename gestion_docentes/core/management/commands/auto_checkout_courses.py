from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime
from core.models import Asistencia, BloqueCurso

class Command(BaseCommand):
    help = 'Automatically checks out courses where the end time has passed but no exit has been marked.'

    def handle(self, *args, **options):
        self.stdout.write("Starting auto-checkout process...")

        now = timezone.now()
        open_attendances = Asistencia.objects.filter(hora_entrada__isnull=False, hora_salida__isnull=True)

        checked_out_count = 0
        DIAS_MAP = {0: 'Lunes', 1: 'Martes', 2: 'Miércoles', 3: 'Jueves', 4: 'Viernes', 5: 'Sábado', 6: 'Domingo'}

        for a in open_attendances:
            if not a.curso:
                continue

            # Find the corresponding block for the attendance
            dia_semana_str = DIAS_MAP.get(a.fecha.weekday())

            # Fetch all blocks for the given day and find the correct one in Python
            # This is more robust against DB-specific time comparison issues.
            bloques_del_dia = BloqueCurso.objects.filter(
                curso=a.curso,
                dia=dia_semana_str
            )

            bloque_asistido = None
            for bloque in bloques_del_dia:
                if bloque.hora_inicio <= a.hora_entrada.time() and a.hora_entrada.time() < bloque.hora_fin:
                    bloque_asistido = bloque
                    break

            if bloque_asistido:
                end_time_naive = datetime.combine(a.fecha, bloque_asistido.hora_fin)
                end_time_aware = timezone.make_aware(end_time_naive, timezone.get_current_timezone())

                if now > end_time_aware:
                    a.hora_salida = end_time_aware
                    a.save()
                    checked_out_count += 1
                    self.stdout.write(self.style.SUCCESS(f"Checked out {a.docente} from {a.curso} for {a.fecha}."))

        self.stdout.write(self.style.SUCCESS(f"Auto-checkout process finished. {checked_out_count} attendances were closed."))
