from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0037_configuracioninstitucion_max_bloques_consecutivos_docente"),
    ]

    operations = [
        migrations.AddField(
            model_name="grupo",
            name="dia_preferido_especialidad_1",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Primer día preferido para programar cursos de especialidad.",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="grupo",
            name="dia_preferido_especialidad_2",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Segundo día preferido para programar cursos de especialidad.",
                max_length=20,
            ),
        ),
    ]
