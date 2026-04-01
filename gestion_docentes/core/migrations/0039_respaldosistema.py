from django.db import migrations, models
import django.db.models.deletion

import core.models.backups


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0038_grupo_dias_preferidos_especialidad"),
    ]

    operations = [
        migrations.CreateModel(
            name="RespaldoSistema",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(max_length=255)),
                ("descripcion", models.TextField(blank=True)),
                ("archivo", models.FileField(max_length=500, upload_to=core.models.backups.respaldo_upload_to)),
                ("origen", models.CharField(choices=[("GENERADO", "Generado por el sistema"), ("SUBIDO", "Subido manualmente"), ("PRE_RESTORE", "Previo a restauracion"), ("SINCRONIZADO", "Sincronizado desde almacenamiento")], default="GENERADO", max_length=20)),
                ("formato", models.CharField(choices=[("POSTGRES_CUSTOM", "PostgreSQL Custom"), ("POSTGRES_PLAIN", "PostgreSQL SQL"), ("SQLITE", "SQLite"), ("DESCONOCIDO", "Desconocido")], default="DESCONOCIDO", max_length=20)),
                ("estado", models.CharField(choices=[("DISPONIBLE", "Disponible"), ("RESTAURANDO", "Restaurando"), ("RESTAURADO", "Restaurado"), ("ERROR", "Error")], default="DISPONIBLE", max_length=20)),
                ("checksum_sha256", models.CharField(blank=True, db_index=True, max_length=64)),
                ("tamano_bytes", models.BigIntegerField(default=0)),
                ("fecha_creacion", models.DateTimeField(auto_now_add=True)),
                ("fecha_actualizacion", models.DateTimeField(auto_now=True)),
                ("fecha_restauracion", models.DateTimeField(blank=True, null=True)),
                ("log_restauracion", models.TextField(blank=True)),
                ("creado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="respaldos_creados", to="core.docente")),
                ("respaldo_previo", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="restauraciones_relacionadas", to="core.respaldosistema")),
                ("restaurado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="respaldos_restaurados", to="core.docente")),
            ],
            options={
                "verbose_name": "Respaldo del sistema",
                "verbose_name_plural": "Respaldos del sistema",
                "ordering": ("-fecha_creacion",),
            },
        ),
    ]
