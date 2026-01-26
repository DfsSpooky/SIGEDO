from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import Asistencia, BloqueHorario, Notificacion, ConfiguracionInstitucion, Semestre

class Command(BaseCommand):
    help = "Registra inasistencias para bloques que ya pasaron su tolerancia y no tienen marca."

    def handle(self, *args, **options):
        now = timezone.localtime(timezone.now())
        today = now.date()
        
        semestre_activo = Semestre.objects.filter(
            estado="ACTIVO", 
            fecha_inicio__lte=today, 
            fecha_fin__gte=today
        ).first()

        if not semestre_activo:
            self.stdout.write("No hay semestre activo.")
            return

        dias_semana = {
            0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves",
            4: "Viernes", 5: "Sábado", 6: "Domingo",
        }
        dia_actual_str = dias_semana.get(now.weekday())
        
        # Obtener bloques del día que ya deberían haber empezado
        bloques = BloqueHorario.objects.filter(
            curso__semestre=semestre_activo,
            dia=dia_actual_str,
            horario_inicio__lt=now.time()
        ).select_related('curso', 'curso__docente')

        config = ConfiguracionInstitucion.load()
        count = 0

        for bloque in bloques:
            if not bloque.curso.docente:
                continue

            # Calcular límite de tolerancia
            # Usamos la tolerancia del curso o la institucional
            tolerancia = bloque.curso.tolerancia_tardanza_minutos
            if tolerancia is None:
                tolerancia = config.tiempo_limite_tardanza
            
            # Definimos "Falta" si han pasado más de 'tolerancia + 15' minutos desde el inicio
            inicio_dt = timezone.make_aware(datetime.combine(today, bloque.horario_inicio))
            limite_falta_dt = inicio_dt + timedelta(minutes=tolerancia + 15)
            
            if now < limite_falta_dt:
                continue

            # Verificar si existe asistencia (incluso si es solo entrada)
            asistencia_exists = Asistencia.objects.filter(
                docente=bloque.curso.docente,
                curso=bloque.curso,
                fecha=today
            ).exists()

            if not asistencia_exists:
                # Crear registro de falta
                Asistencia.objects.create(
                    docente=bloque.curso.docente,
                    curso=bloque.curso,
                    fecha=today,
                    estado="FALTA"
                )
                
                # Notificar al docente
                Notificacion.objects.create(
                    destinatario=bloque.curso.docente,
                    mensaje=f"Se ha registrado una inasistencia automática para el curso {bloque.curso.nombre} (Bloque {bloque.horario_inicio}).",
                    url="/asistencia/"
                )
                count += 1
                self.stdout.write(self.style.WARNING(f"Falta registrada para {bloque.curso.docente} en {bloque.curso}"))

        self.stdout.write(self.style.SUCCESS(f"Proceso completado. {count} faltas registradas."))
