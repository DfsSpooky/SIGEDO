from core.models import BloqueHorario, Curso, Especialidad, FranjaHoraria, Semestre
from django.db import models
from rest_framework import serializers


class AsignarHorarioSerializer(serializers.Serializer):
    curso_id = serializers.IntegerField()
    franja_id = serializers.IntegerField()
    dia = serializers.CharField(max_length=20)
    duracion = serializers.IntegerField(default=2, min_value=1)

    def validate(self, data):
        try:
            curso = Curso.objects.get(pk=data["curso_id"])
            data["curso"] = curso
        except Curso.DoesNotExist:
            raise serializers.ValidationError({"curso_id": "Curso no encontrado."})

        try:
            franja = FranjaHoraria.objects.get(pk=data["franja_id"])
            data["franja_inicio"] = franja
        except FranjaHoraria.DoesNotExist:
            raise serializers.ValidationError(
                {"franja_id": "Franja horaria no encontrada."}
            )

        # Validar horas semanales
        horas_asignadas = (
            curso.bloques_horario.aggregate(total=models.Sum("duracion_bloques"))[
                "total"
            ]
            or 0
        )
        if horas_asignadas + data["duracion"] > curso.horas_academicas_semanales:
            raise serializers.ValidationError(
                f"No se puede asignar: excede las horas semanales del curso ({curso.horas_academicas_semanales})."
            )

        return data


class DesasignarHorarioSerializer(serializers.Serializer):
    bloque_id = serializers.IntegerField()

    def validate_bloque_id(self, value):
        if not BloqueHorario.objects.filter(pk=value).exists():
            raise serializers.ValidationError("El bloque de horario no existe.")
        return value


class MoverBloqueSerializer(serializers.Serializer):
    bloque_id = serializers.IntegerField()
    dia = serializers.CharField(max_length=20)
    franja_id = serializers.IntegerField()

    def validate(self, data):
        try:
            bloque = BloqueHorario.objects.select_related(
                "curso__docente", "curso__especialidad__grupo"
            ).get(pk=data["bloque_id"])
            data["bloque"] = bloque
        except BloqueHorario.DoesNotExist:
            raise serializers.ValidationError(
                {"bloque_id": "El bloque a mover no existe."}
            )

        try:
            franja = FranjaHoraria.objects.get(pk=data["franja_id"])
            data["nueva_franja_inicio"] = franja
        except FranjaHoraria.DoesNotExist:
            raise serializers.ValidationError(
                {"franja_id": "La nueva franja horaria no existe."}
            )

        return data


class AjustarDuracionSerializer(serializers.Serializer):
    bloque_id = serializers.IntegerField()
    accion = serializers.ChoiceField(choices=["increase", "decrease"])

    def validate(self, data):
        try:
            bloque = BloqueHorario.objects.select_related("curso").get(
                pk=data["bloque_id"]
            )
            data["bloque"] = bloque
        except BloqueHorario.DoesNotExist:
            raise serializers.ValidationError(
                {"bloque_id": "El bloque de horario no existe."}
            )

        nueva_duracion = bloque.duracion_bloques
        if data["accion"] == "increase":
            nueva_duracion += 1
        else:
            nueva_duracion -= 1

        if nueva_duracion < 1:
            raise serializers.ValidationError(
                "La duración no puede ser menor a 1 bloque."
            )

        data["nueva_duracion"] = nueva_duracion

        # Validar maximo de horas solo si aumentamos
        if data["accion"] == "increase":
            horas_asignadas = (
                bloque.curso.bloques_horario.exclude(pk=bloque.id).aggregate(
                    total=models.Sum("duracion_bloques")
                )["total"]
                or 0
            )
            if (
                horas_asignadas + nueva_duracion
                > bloque.curso.horas_academicas_semanales
            ):
                raise serializers.ValidationError(
                    "La duración excede las horas semanales del curso."
                )

        return data


class AutoAsignarSerializer(serializers.Serializer):
    especialidad_id = serializers.IntegerField()
    semestre_cursado = serializers.IntegerField()

    def validate_especialidad_id(self, value):
        if not Especialidad.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Especialidad no encontrada.")
        return value

    def validate(self, data):
        semestre_activo = Semestre.objects.filter(estado="ACTIVO").first()
        if not semestre_activo:
            raise serializers.ValidationError("No hay un semestre activo.")
        data["semestre_activo"] = semestre_activo
        return data
