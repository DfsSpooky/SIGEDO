from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0035_alter_adelantoclase_unique_together_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="configuracioninstitucion",
            name="max_horas_diarias_docente",
            field=models.PositiveIntegerField(
                default=10,
                help_text="Máximo de bloques que un docente puede dictar por día en el planificador.",
            ),
        ),
        migrations.AddField(
            model_name="configuracioninstitucion",
            name="max_horas_diarias_especialidad",
            field=models.PositiveIntegerField(
                default=10,
                help_text="Máximo de bloques que una especialidad/grupo de estudiantes puede llevar por día en el planificador.",
            ),
        ),
    ]
