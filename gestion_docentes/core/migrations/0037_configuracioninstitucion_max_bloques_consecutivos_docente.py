from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0036_configuracioninstitucion_scheduler_limits"),
    ]

    operations = [
        migrations.AddField(
            model_name="configuracioninstitucion",
            name="max_bloques_consecutivos_docente",
            field=models.PositiveIntegerField(
                default=5,
                help_text="Máximo de bloques consecutivos que un docente puede dictar sin descanso en el planificador.",
            ),
        ),
    ]
