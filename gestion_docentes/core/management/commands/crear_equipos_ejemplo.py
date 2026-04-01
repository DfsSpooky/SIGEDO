from django.core.management.base import BaseCommand

from core.models import Activo, TipoActivo

class Command(BaseCommand):
    help = "Crea 3 equipos de ejemplo para probar la funcionalidad de reservas"

    def handle(self, *args, **options):
        laptop_tipo, _ = TipoActivo.objects.get_or_create(nombre="Laptop")
        proyector_tipo, _ = TipoActivo.objects.get_or_create(nombre="Proyector")
        tablet_tipo, _ = TipoActivo.objects.get_or_create(nombre="Tablet")

        equipos = [
            {
                "nombre": "Laptop Dell Inspiron 15",
                "descripcion": "Laptop para uso docente, 8GB RAM, 256GB SSD, Windows 11",
                "codigo_patrimonial": "LAPTOP-001",
                "tipo": laptop_tipo,
                "estado": "DISPONIBLE",
                "observaciones": "En buen estado. Cargador incluido.",
            },
            {
                "nombre": "Proyector Epson PowerLite",
                "descripcion": "Proyector 3000 lumenes, resolucion WXGA, cable HDMI incluido",
                "codigo_patrimonial": "PROY-001",
                "tipo": proyector_tipo,
                "estado": "DISPONIBLE",
                "observaciones": "Control remoto incluido. Requiere 10 min de calentamiento.",
            },
            {
                "nombre": "Tablet Samsung Galaxy Tab A",
                "descripcion": "Tablet 10.5 pulgadas, 64GB, Wi-Fi, ideal para presentaciones",
                "codigo_patrimonial": "TAB-001",
                "tipo": tablet_tipo,
                "estado": "DISPONIBLE",
                "observaciones": "Funda protectora incluida. Cargador USB-C incluido.",
            },
        ]

        creados = 0
        for equipo_data in equipos:
            codigo = equipo_data["codigo_patrimonial"]
            if not Activo.objects.filter(codigo_patrimonial=codigo).exists():
                Activo.objects.create(**equipo_data)
                self.stdout.write(
                    self.style.SUCCESS(f"  ✓ Creado: {equipo_data['nombre']}")
                )
                creados += 1
            else:
                self.stdout.write(
                    f"  - Ya existe: {equipo_data['nombre']} ({codigo})"
                )

        self.stdout.write("")
        if creados > 0:
            self.stdout.write(
                self.style.SUCCESS(f"{creados} equipo(s) creado(s) exitosamente.")
            )
        else:
            self.stdout.write("Todos los equipos de ejemplo ya existen.")

        self.stdout.write("")
        self.stdout.write("Inventario actual:")
        for activo in Activo.objects.all().select_related("tipo"):
            self.stdout.write(
                f"  [{activo.estado}] {activo.nombre} ({activo.tipo.nombre}) - {activo.codigo_patrimonial}"
            )
