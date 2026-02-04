from datetime import datetime

from core.models import Asistencia, BloqueHorario
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Automatically checks out courses where the end time has passed but no exit has been marked."

    def handle(self, *args, **options):
        self.stdout.write("Starting auto-checkout process...")

        now = timezone.now()
        open_attendances = Asistencia.objects.filter(
            hora_entrada__isnull=False, hora_salida__isnull=True
        ).select_related("curso")

        checked_out_count = 0
        dias_semana = {
            0: "Lunes",
            1: "Martes",
            2: "Miércoles",
            3: "Jueves",
            4: "Viernes",
            5: "Sábado",
            6: "Domingo",
        }

        for a in open_attendances:
            if not a.curso:
                continue

            # Find the schedule block for this course on the day of attendance
            dia_asistencia = dias_semana.get(a.fecha.weekday())
            if not dia_asistencia:
                continue

            bloque_del_dia = BloqueHorario.objects.filter(
                curso=a.curso, dia=dia_asistencia
            ).first()

            if bloque_del_dia:
                # Combine the attendance date with the block's end time
                end_time_naive = datetime.combine(a.fecha, bloque_del_dia.horario_fin)
                # Make it timezone-aware
                end_time_aware = timezone.make_aware(
                    end_time_naive, timezone.get_current_timezone()
                )

                # If the current time is past the scheduled end time
                if now > end_time_aware:
                    a.hora_salida = end_time_aware
                    a.save()
                    checked_out_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Checked out {a.docente} from {a.curso} for {a.fecha}."
                        )
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"Auto-checkout process finished. {checked_out_count} attendances were closed."
            )
        )
