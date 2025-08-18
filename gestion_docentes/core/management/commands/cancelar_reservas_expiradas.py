# Este comando debe ser ejecutado periódicamente usando un cron job o un programador de tareas similar.
# Ejemplo de cron job para ejecutarlo cada 5 minutos:
# */5 * * * * /ruta/a/tu/entorno/python /ruta/a/tu/proyecto/manage.py cancelar_reservas_expiradas

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from ...models import Reserva

class Command(BaseCommand):
    help = 'Busca y cancela las reservas que han expirado (no confirmadas después de 15 minutos).'

    def handle(self, *args, **options):
        now = timezone.now()
        expiration_window = timedelta(minutes=15)

        # Buscamos reservas que están en estado 'RESERVADO' y cuya fecha ya pasó o es hoy.
        # Esto es una optimización para no iterar sobre reservas futuras.
        reservas_pendientes = Reserva.objects.filter(
            estado='RESERVADO',
            fecha_reserva__lte=now.date()
        ).select_related('activo', 'franja_horaria')

        reservas_expiradas_count = 0

        self.stdout.write(f"Verificando reservas a las {now.strftime('%Y-%m-%d %H:%M:%S')}...")

        for reserva in reservas_pendientes:
            # Combinamos la fecha de la reserva con la hora de inicio de la franja horaria
            # Es crucial asegurarse de que la hora se interprete en la zona horaria correcta
            hora_inicio_reserva = timezone.make_aware(
                timezone.datetime.combine(reserva.fecha_reserva, reserva.franja_horaria.hora_inicio),
                timezone.get_current_timezone()
            )

            # Calculamos el momento exacto en que la reserva expira
            momento_expiracion = hora_inicio_reserva + expiration_window

            # Si la hora actual ha pasado el momento de expiración, la cancelamos
            if now > momento_expiracion:
                reserva.estado = 'EXPIRADO'
                reserva.save()
                reservas_expiradas_count += 1
                self.stdout.write(self.style.WARNING(f'Reserva ID {reserva.id} para "{reserva.activo.nombre}" ha expirado y fue cancelada.'))

        if reservas_expiradas_count > 0:
            self.stdout.write(self.style.SUCCESS(f'Proceso finalizado. Se cancelaron {reservas_expiradas_count} reservas expiradas.'))
        else:
            self.stdout.write(self.style.SUCCESS('No se encontraron reservas expiradas para cancelar.'))
