from core.models import BloqueHorario, Curso, FranjaHoraria
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Migra los datos de horarios desde los campos deprecados de Curso hacia el nuevo modelo BloqueHorario."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS("Iniciando migración de horarios antiguos...")
        )

        cursos_a_migrar = Curso.objects.filter(
            dia__isnull=False, horario_inicio__isnull=False
        )

        if not cursos_a_migrar.exists():
            self.stdout.write(
                self.style.WARNING(
                    "No se encontraron cursos con horarios en el formato antiguo para migrar."
                )
            )
            return

        migrados_count = 0
        errores_count = 0

        # Mapear horas de inicio a objetos FranjaHoraria para eficiencia
        franjas_map = {
            franja.hora_inicio: franja for franja in FranjaHoraria.objects.all()
        }

        for curso in cursos_a_migrar:
            self.stdout.write(f"Procesando curso: {curso.nombre} ({curso.id})")

            # 1. Asignar las horas semanales totales
            # El campo `duracion_bloques` antiguo ahora se considera el total semanal
            if curso.duracion_bloques:
                curso.horas_academicas_semanales = curso.duracion_bloques
                curso.save(update_fields=["horas_academicas_semanales"])
                self.stdout.write(
                    f"  -> Asignadas {curso.horas_academicas_semanales} horas académicas semanales."
                )

            # 2. Crear el BloqueHorario para el horario existente
            franja_inicio_obj = franjas_map.get(curso.horario_inicio)

            if franja_inicio_obj:
                try:
                    # Usamos get_or_create para evitar duplicados si el script se corre varias veces
                    bloque, created = BloqueHorario.objects.get_or_create(
                        curso=curso,
                        dia=curso.dia,
                        franja_inicio=franja_inicio_obj,
                        defaults={"duracion_bloques": curso.duracion_bloques or 1},
                    )

                    if created:
                        migrados_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(f"  -> Creado BloqueHorario: {bloque}")
                        )
                    else:
                        self.stdout.write(
                            self.style.NOTICE(
                                f"  -> BloqueHorario ya existente: {bloque}"
                            )
                        )

                except Exception as e:
                    self.stderr.write(
                        self.style.ERROR(
                            f"  -> ERROR al crear BloqueHorario para el curso {curso.id}: {e}"
                        )
                    )
                    errores_count += 1
            else:
                self.stderr.write(
                    self.style.ERROR(
                        f"  -> No se encontró FranjaHoraria para la hora de inicio {curso.horario_inicio} en el curso {curso.id}."
                    )
                )
                errores_count += 1

        self.stdout.write("\n" + "=" * 50)
        if errores_count == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Migración completada con éxito. Se crearon {migrados_count} nuevos bloques de horario."
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"Migración completada con {errores_count} errores. Se crearon {migrados_count} nuevos bloques de horario."
                )
            )
        self.stdout.write("=" * 50)
