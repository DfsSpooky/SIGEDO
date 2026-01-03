import os
from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from core.models import BloqueHorario, Asistencia
import firebase_admin
from firebase_admin import credentials, messaging

class Command(BaseCommand):
    help = 'Envía recordatorios Push a los docentes 10-15 minutos antes de su clase.'

    def handle(self, *args, **options):
        # 1. Inicializar Firebase (Solo si no está inicializado)
        try:
            if not firebase_admin._apps:
                # Busca el archivo en la raíz del proyecto Django
                cred_path = os.path.join(settings.BASE_DIR, 'serviceAccountKey.json')
                if os.path.exists(cred_path):
                    cred = credentials.Certificate(cred_path)
                    firebase_admin.initialize_app(cred)
                else:
                    self.stdout.write(self.style.WARNING(f"No se encontró serviceAccountKey.json en {cred_path}. No se enviarán notificaciones."))
                    return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error inicializando Firebase: {e}"))
            return

        # 2. Calcular Rango de Tiempo (Próximos 15 mins)
        now = timezone.localtime(timezone.now())
        current_time = now.time()
        # Dia de la semana (0=Lunes, 6=Domingo)
        weekday = now.weekday()

        self.stdout.write(f"Ejecutando revisión de alertas: {now}")

        # 3. Buscar Bloques que inicien pronto (y sean hoy)
        # Nota: Esto es una simplificación. En producción idealmente filtrarías por rango de minutos exacto.
        # Aquí traemos todos los del día y filtramos en Python para mayor precisión de tiempo/delta.
        bloques_hoy = BloqueHorario.objects.filter(dia_semana=weekday)

        for bloque in bloques_hoy:
            start = bloque.horario_inicio
            
            # Convertir a datetime para restar
            bloque_dt = datetime.combine(now.date(), start)
            # Hacerlo timezone-aware si Django lo usa
            bloque_dt = timezone.make_aware(bloque_dt, timezone.get_current_timezone())
            
            diff_minutes = (bloque_dt - now).total_seconds() / 60

            # Si faltan entre 5 y 15 minutos
            if 5 <= diff_minutes <= 15:
                docente = bloque.curso.docente
                if not docente or not docente.fcm_token:
                    continue

                # Validar si ya marcó asistencia
                asistencia_existe = Asistencia.objects.filter(
                    docente=docente,
                    curso=bloque.curso,
                    fecha=now.date(),
                    hora_entrada__isnull=False
                ).exists()

                if not asistencia_existe:
                    self.enviar_notificacion(docente, bloque.curso.nombre, int(diff_minutes))

    def enviar_notificacion(self, docente, curso, minutos):
        try:
            message = messaging.Message(
                notification=messaging.Notification(
                    title="⏰ Recordatorio de Clase",
                    body=f"Profe {docente.first_name}, su clase de {curso} comienza en {minutos} minutos.",
                ),
                token=docente.fcm_token,
            )
            response = messaging.send(message)
            self.stdout.write(self.style.SUCCESS(f"Notificación enviada a {docente}: {response}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error enviando FCM a {docente}: {e}"))
