from core.models import TipoActivo, Activo, FranjaHoraria
from datetime import time

# Create TipoActivo
tipo, created = TipoActivo.objects.get_or_create(nombre="Proyector Multimedia")
if created:
    print(f"Created TipoActivo: {tipo.nombre}")

# Create Activo
activo, created = Activo.objects.get_or_create(
    nombre="Proyector Epson A",
    codigo_patrimonial="EPSON-001",
    tipo=tipo
)
if created:
    print(f"Created Activo: {activo.nombre}")

# Create FranjaHoraria for the morning
franjas_manana = [
    ("MANANA", time(8, 0), time(8, 50)),
    ("MANANA", time(8, 50), time(9, 40)),
    ("MANANA", time(9, 40), time(10, 30)),
    ("MANANA", time(10, 30), time(11, 20)),
    ("MANANA", time(11, 20), time(12, 10)),
    ("MANANA", time(12, 10), time(13, 0)),
]

for turno, inicio, fin in franjas_manana:
    franja, created = FranjaHoraria.objects.get_or_create(
        turno=turno,
        hora_inicio=inicio,
        hora_fin=fin
    )
    if created:
        print(f"Created FranjaHoraria: {franja}")

# Create FranjaHoraria for the afternoon
franjas_tarde = [
    ("TARDE", time(14, 0), time(14, 50)),
    ("TARDE", time(14, 50), time(15, 40)),
    ("TARDE", time(15, 40), time(16, 30)),
    ("TARDE", time(16, 30), time(17, 20)),
    ("TARDE", time(17, 20), time(18, 10)),
]

for turno, inicio, fin in franjas_tarde:
    franja, created = FranjaHoraria.objects.get_or_create(
        turno=turno,
        hora_inicio=inicio,
        hora_fin=fin
    )
    if created:
        print(f"Created FranjaHoraria: {franja}")

print("Database seeded with initial data.")
