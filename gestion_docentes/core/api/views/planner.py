import random
from collections import defaultdict

from core.models import BloqueHorario, Curso, Especialidad, FranjaHoraria, Semestre
from core.utils.responses import success_response
from django.db import models
from django.db.models import Q
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers_planner import (
    AjustarDuracionSerializer,
    AsignarHorarioSerializer,
    AutoAsignarSerializer,
    DesasignarHorarioSerializer,
    MoverBloqueSerializer,
)


class AsignarHorarioView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        serializer = AsignarHorarioSerializer(data=request.data)
        if serializer.is_valid():
            validated_data = serializer.validated_data
            BloqueHorario.objects.create(
                curso=validated_data["curso"],
                dia=validated_data["dia"],
                franja_inicio=validated_data["franja_inicio"],
                duracion_bloques=validated_data["duracion"],
            )
            return Response(
                {"status": "success", "message": "Bloque asignado con éxito."},
                status=status.HTTP_200_OK,
            )
        return Response(
            {"status": "error", "message": next(iter(serializer.errors.values()))[0]},
            status=status.HTTP_400_BAD_REQUEST,
        )


class DesasignarHorarioView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        serializer = DesasignarHorarioSerializer(data=request.data)
        if serializer.is_valid():
            BloqueHorario.objects.filter(
                pk=serializer.validated_data["bloque_id"]
            ).delete()
            return Response(
                {"status": "success", "message": "Bloque de horario eliminado."},
                status=status.HTTP_200_OK,
            )
        return Response(
            {"status": "error", "message": next(iter(serializer.errors.values()))[0]},
            status=status.HTTP_400_BAD_REQUEST,
        )


class MoverBloqueView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        serializer = MoverBloqueSerializer(data=request.data)
        if serializer.is_valid():
            bloque = serializer.validated_data["bloque"]
            bloque.dia = serializer.validated_data["dia"]
            bloque.franja_inicio = serializer.validated_data["nueva_franja_inicio"]
            bloque.save()
            return Response(
                {"status": "success", "message": "Bloque movido con éxito."},
                status=status.HTTP_200_OK,
            )
        return Response(
            {"status": "error", "message": next(iter(serializer.errors.values()))[0]},
            status=status.HTTP_400_BAD_REQUEST,
        )


class AjustarDuracionView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        serializer = AjustarDuracionSerializer(data=request.data)
        if serializer.is_valid():
            bloque = serializer.validated_data["bloque"]
            bloque.duracion_bloques = serializer.validated_data["nueva_duracion"]
            bloque.save()
            return Response(
                {"status": "success", "message": "Duración del bloque actualizada."},
                status=status.HTTP_200_OK,
            )
        return Response(
            {"status": "error", "message": next(iter(serializer.errors.values()))[0]},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["GET"])
@permission_classes([permissions.IsAdminUser])
def api_get_teacher_conflicts(request):
    curso_id = request.GET.get("curso_id")
    if not curso_id:
        return Response(
            {"status": "error", "message": "Falta el ID del curso."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        curso_a_asignar = Curso.objects.select_related(
            "docente", "especialidad__grupo"
        ).get(pk=curso_id)
        docente = curso_a_asignar.docente
        semestre = curso_a_asignar.semestre
        grupo_del_curso = (
            curso_a_asignar.especialidad.grupo if curso_a_asignar.especialidad else None
        )
        semestre_cursado_a_asignar = curso_a_asignar.semestre_cursado

        conflictos = {}
        todas_las_franjas = list(FranjaHoraria.objects.order_by("hora_inicio"))

        bloques_asignados = BloqueHorario.objects.filter(
            curso__semestre=semestre
        ).select_related(
            "curso__docente", "curso__especialidad__grupo", "curso__especialidad"
        )

        # 1. Conflictos del propio docente
        if docente:
            bloques_docente = bloques_asignados.filter(curso__docente=docente).exclude(
                curso=curso_a_asignar
            )
            for bloque in bloques_docente:
                try:
                    franja_idx = todas_las_franjas.index(bloque.franja_inicio)
                    for i in range(bloque.duracion_bloques):
                        if franja_idx + i < len(todas_las_franjas):
                            franja_actual = todas_las_franjas[franja_idx + i]
                            key = (bloque.dia, franja_actual.id)
                            if key not in conflictos:
                                conflictos[key] = (
                                    f"Docente Ocupado: {bloque.curso.nombre}"
                                )
                except ValueError:
                    continue

        # 2. Conflictos del grupo de estudiantes
        if grupo_del_curso and semestre_cursado_a_asignar:
            q_grupo = Q(
                curso__especialidad__grupo=grupo_del_curso,
                curso__semestre_cursado=semestre_cursado_a_asignar,
            )
            bloques_grupo = bloques_asignados.filter(q_grupo).exclude(
                curso=curso_a_asignar
            )
            for bloque in bloques_grupo:
                try:
                    franja_idx = todas_las_franjas.index(bloque.franja_inicio)
                    for i in range(bloque.duracion_bloques):
                        if franja_idx + i < len(todas_las_franjas):
                            franja_actual = todas_las_franjas[franja_idx + i]
                            key = (bloque.dia, franja_actual.id)
                            if key not in conflictos:
                                conflictos[key] = (
                                    f"Grupo Ocupado: {bloque.curso.nombre}"
                                )
                except ValueError:
                    continue

        # 3. Conflictos de disponibilidad del docente
        if docente and docente.disponibilidad != "COMPLETO":
            turno_no_disponible = (
                "TARDE" if docente.disponibilidad == "MANANA" else "MANANA"
            )
            franjas_no_disponibles_ids = set(
                FranjaHoraria.objects.filter(turno=turno_no_disponible).values_list(
                    "id", flat=True
                )
            )
            if franjas_no_disponibles_ids:
                dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
                for dia in dias_semana:
                    for franja_id in franjas_no_disponibles_ids:
                        key = (dia, franja_id)
                        if key not in conflictos:
                            conflictos[key] = (
                                f"No disponible en turno de {turno_no_disponible.title()}"
                            )

        response_data = [
            {"dia": k[0], "franja_id": k[1], "razon": v} for k, v in conflictos.items()
        ]

        return Response({"status": "success", "data": {"conflicts": response_data}})

    except Curso.DoesNotExist:
        return Response(
            {"status": "error", "message": "Curso no encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"status": "error", "message": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


def _get_planner_data(especialidad_id, semestre_cursado):
    try:
        semestre_activo = Semestre.objects.get(estado="ACTIVO")
    except Semestre.DoesNotExist:
        raise ValueError("No hay un semestre activo configurado.")

    cursos_asignados_json = []
    cursos_pendientes_generales = []
    cursos_pendientes_especialidad = []

    if especialidad_id and semestre_cursado:
        try:
            especialidad_obj = Especialidad.objects.get(id=especialidad_id)
        except Especialidad.DoesNotExist:
            return {}  # Should handle gracefully

        grupo_obj = especialidad_obj.grupo

        q_cursos_del_plan = Q(
            semestre=semestre_activo, semestre_cursado=semestre_cursado
        ) & (
            Q(especialidad_id=especialidad_id)
            | Q(especialidad__grupo=grupo_obj, tipo_curso="GENERAL")
        )

        cursos_del_plan = (
            Curso.objects.filter(q_cursos_del_plan)
            .annotate(
                horas_asignadas=models.Sum(
                    "bloques_horario__duracion_bloques", default=0
                )
            )
            .select_related("docente", "especialidad")
            .prefetch_related("bloques_horario")
        )

        for curso in cursos_del_plan:
            # Lógica para cursos pendientes
            if curso.horas_asignadas < curso.horas_academicas_semanales:
                curso_data = {
                    "id": curso.id,
                    "nombre": curso.nombre,
                    "docente_nombre": (
                        f"{curso.docente.first_name} {curso.docente.last_name}"
                        if curso.docente
                        else "N/A"
                    ),
                    "horas_pendientes": curso.horas_academicas_semanales
                    - curso.horas_asignadas,
                    "horas_totales": curso.horas_academicas_semanales,
                    "tipo_curso": curso.tipo_curso,
                    "semestre_cursado": curso.semestre_cursado,
                    "excepcion_horario": curso.excepcion_horario,
                }
                if curso.tipo_curso == "GENERAL":
                    cursos_pendientes_generales.append(curso_data)
                else:
                    cursos_pendientes_especialidad.append(curso_data)

            # Lógica para bloques ya asignados
            for bloque in curso.bloques_horario.all():
                cursos_asignados_json.append(
                    {
                        "bloque_id": bloque.id,
                        "curso_id": curso.id,
                        "nombre": curso.nombre,
                        "docente_nombre": (
                            f"{curso.docente.first_name} {curso.docente.last_name}"
                            if curso.docente
                            else "N/A"
                        ),
                        "dia": bloque.dia,
                        "franja_id_inicio": bloque.franja_inicio.id,
                        "duracion_bloques": bloque.duracion_bloques,
                        "tipo_curso": curso.tipo_curso,
                        "semestre_cursado": curso.semestre_cursado,
                        "excepcion_horario": curso.excepcion_horario,
                    }
                )

    return {
        "cursos_pendientes": {
            "generales": cursos_pendientes_generales,
            "especialidad": cursos_pendientes_especialidad,
        },
        "cursos_asignados": cursos_asignados_json,
    }


class AutoAsignarView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        serializer = AutoAsignarSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "status": "error",
                    "message": next(iter(serializer.errors.values()))[0],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = serializer.validated_data
        especialidad_id = data.get("especialidad_id")
        semestre_cursado_num = data.get("semestre_cursado")
        semestre_activo = data.get("semestre_activo")

        try:
            # 1. Identificar los cursos con horas pendientes
            especialidad_obj = Especialidad.objects.get(id=especialidad_id)
            grupo_obj = especialidad_obj.grupo
            q_cursos_del_plan = Q(
                semestre=semestre_activo, semestre_cursado=semestre_cursado_num
            ) & (
                Q(especialidad_id=especialidad_id)
                | Q(especialidad__grupo=grupo_obj, tipo_curso="GENERAL")
            )

            cursos_a_planificar = (
                Curso.objects.filter(q_cursos_del_plan)
                .annotate(
                    horas_asignadas=models.Sum(
                        "bloques_horario__duracion_bloques", default=0
                    )
                )
                .select_related("docente", "especialidad__grupo")
            )

            cursos_con_pendientes = [
                c
                for c in cursos_a_planificar
                if c.horas_asignadas < c.horas_academicas_semanales
            ]

            if not cursos_con_pendientes:
                planner_data = _get_planner_data(especialidad_id, semestre_cursado_num)
                return Response(
                    {
                        "status": "success",
                        "data": {"plannerData": planner_data},
                        "message": "Todos los cursos para esta selección ya están completamente asignados.",
                    },
                    status=status.HTTP_200_OK,
                )

            # 2. Construir el mapa de horarios ocupados
            franjas_horarias = list(FranjaHoraria.objects.order_by("hora_inicio"))
            horarios_ocupados = defaultdict(set)

            todos_los_bloques = BloqueHorario.objects.filter(
                curso__semestre=semestre_activo
            ).select_related("curso__docente", "curso__especialidad__grupo")
            for bloque in todos_los_bloques:
                try:
                    franja_idx = franjas_horarias.index(bloque.franja_inicio)
                    for i in range(bloque.duracion_bloques):
                        if franja_idx + i < len(franjas_horarias):
                            franja_ocupada = franjas_horarias[franja_idx + i]
                            if bloque.curso.docente:
                                horarios_ocupados["docente"].add(
                                    (
                                        bloque.curso.docente.id,
                                        bloque.dia,
                                        franja_ocupada.id,
                                    )
                                )
                            if (
                                bloque.curso.especialidad
                                and bloque.curso.especialidad.grupo
                            ):
                                horarios_ocupados["grupo"].add(
                                    (
                                        bloque.curso.especialidad.grupo.id,
                                        bloque.curso.semestre_cursado,
                                        bloque.dia,
                                        franja_ocupada.id,
                                    )
                                )
                except ValueError:
                    continue

            # 3. Lógica de asignación
            cursos_asignados_ahora = 0
            dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
            posibles_duraciones = [3, 2, 1]

            for curso in cursos_con_pendientes:
                horas_pendientes = (
                    curso.horas_academicas_semanales - curso.horas_asignadas
                )
                docente = curso.docente
                grupo = (
                    curso.especialidad.grupo
                    if curso.especialidad and curso.especialidad.grupo
                    else None
                )
                semestre_cursado = curso.semestre_cursado
                random.shuffle(dias_semana)

                while horas_pendientes > 0:
                    bloque_asignado_en_iteracion = False
                    duracion_a_intentar = next(
                        (d for d in posibles_duraciones if d <= horas_pendientes), None
                    )
                    if not duracion_a_intentar:
                        break

                    for dia in dias_semana:
                        for i in range(len(franjas_horarias) - duracion_a_intentar + 1):
                            franja_inicio = franjas_horarias[i]
                            franjas_del_bloque = franjas_horarias[
                                i : i + duracion_a_intentar
                            ]
                            bloque_valido = True
                            for franja in franjas_del_bloque:
                                if (
                                    docente.disponibilidad == "MANANA"
                                    and franja.turno != "MANANA"
                                ) or (
                                    docente.disponibilidad == "TARDE"
                                    and franja.turno != "TARDE"
                                ):
                                    bloque_valido = False
                                    break
                                if (docente.id, dia, franja.id) in horarios_ocupados[
                                    "docente"
                                ]:
                                    bloque_valido = False
                                    break
                                if grupo and semestre_cursado:
                                    if (
                                        grupo.id,
                                        semestre_cursado,
                                        dia,
                                        franja.id,
                                    ) in horarios_ocupados["grupo"]:
                                        bloque_valido = False
                                        break
                            if not bloque_valido:
                                continue

                            BloqueHorario.objects.create(
                                curso=curso,
                                dia=dia,
                                franja_inicio=franja_inicio,
                                duracion_bloques=duracion_a_intentar,
                            )
                            for franja in franjas_del_bloque:
                                horarios_ocupados["docente"].add(
                                    (docente.id, dia, franja.id)
                                )
                                if grupo and semestre_cursado:
                                    horarios_ocupados["grupo"].add(
                                        (grupo.id, semestre_cursado, dia, franja.id)
                                    )
                            horas_pendientes -= duracion_a_intentar
                            bloque_asignado_en_iteracion = True
                            break
                        if bloque_asignado_en_iteracion:
                            break
                    if not bloque_asignado_en_iteracion:
                        break

                if horas_pendientes == 0:
                    cursos_asignados_ahora += 1

            message = f"Proceso finalizado. Se completó la asignación para {cursos_asignados_ahora} cursos."
            planner_data = _get_planner_data(especialidad_id, semestre_cursado_num)
            return Response(
                {
                    "status": "success",
                    "data": {"plannerData": planner_data},
                    "message": message,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            import traceback

            traceback.print_exc()
            return Response(
                {"status": "error", "message": f"Ocurrió un error inesperado: {e}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def generar_horario_automatico(request):
    try:
        semestre_activo = Semestre.objects.filter(estado="ACTIVO").first()
        if not semestre_activo:
            return Response(
                {
                    "status": "error",
                    "message": "No hay un semestre activo configurado.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 1. Reset
        BloqueHorario.objects.filter(curso__semestre=semestre_activo).delete()

        # 2. Obtener recursos
        cursos_a_asignar = list(
            Curso.objects.filter(semestre=semestre_activo, docente__isnull=False)
            .select_related("docente", "especialidad__grupo")
            .order_by("-horas_academicas_semanales")
        )
        franjas_horarias = list(FranjaHoraria.objects.order_by("hora_inicio"))
        dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
        horarios_ocupados = defaultdict(set)
        cursos_completados = 0
        cursos_no_asignados_completamente = []

        # 3. Iterar
        for curso in cursos_a_asignar:
            horas_pendientes = curso.horas_academicas_semanales
            docente = curso.docente
            grupo = (
                curso.especialidad.grupo
                if curso.especialidad and curso.especialidad.grupo
                else None
            )
            semestre_cursado = curso.semestre_cursado
            posibles_duraciones = [3, 2, 1]
            random.shuffle(dias_semana)

            while horas_pendientes > 0:
                bloque_asignado_en_iteracion = False
                duracion_a_intentar = next(
                    (d for d in posibles_duraciones if d <= horas_pendientes), None
                )
                if not duracion_a_intentar:
                    break

                for dia in dias_semana:
                    for i in range(len(franjas_horarias) - duracion_a_intentar + 1):
                        franja_inicio = franjas_horarias[i]
                        franjas_del_bloque = franjas_horarias[
                            i : i + duracion_a_intentar
                        ]
                        bloque_valido = True
                        for franja in franjas_del_bloque:
                            if (
                                docente.disponibilidad == "MANANA"
                                and franja.turno != "MANANA"
                            ) or (
                                docente.disponibilidad == "TARDE"
                                and franja.turno != "TARDE"
                            ):
                                bloque_valido = False
                                break
                            if (docente.id, dia, franja.id) in horarios_ocupados[
                                "docente"
                            ]:
                                bloque_valido = False
                                break
                            if grupo and semestre_cursado:
                                if (
                                    grupo.id,
                                    semestre_cursado,
                                    dia,
                                    franja.id,
                                ) in horarios_ocupados["grupo"]:
                                    bloque_valido = False
                                    break

                        if not bloque_valido:
                            continue

                        BloqueHorario.objects.create(
                            curso=curso,
                            dia=dia,
                            franja_inicio=franja_inicio,
                            duracion_bloques=duracion_a_intentar,
                        )

                        for franja in franjas_del_bloque:
                            horarios_ocupados["docente"].add(
                                (docente.id, dia, franja.id)
                            )
                            if grupo and semestre_cursado:
                                horarios_ocupados["grupo"].add(
                                    (grupo.id, semestre_cursado, dia, franja.id)
                                )

                        horas_pendientes -= duracion_a_intentar
                        bloque_asignado_en_iteracion = True
                        break
                    if bloque_asignado_en_iteracion:
                        break

                if not bloque_asignado_en_iteracion:
                    break

            if horas_pendientes == 0:
                cursos_completados += 1
            else:
                cursos_no_asignados_completamente.append(
                    f"{curso.nombre} ({horas_pendientes}h pendientes)"
                )

        total_cursos = len(cursos_a_asignar)
        message = f"Proceso completado. Se asignaron completamente {cursos_completados} de {total_cursos} cursos planificables."
        if cursos_no_asignados_completamente:
            message += f" Cursos no asignados completamente: {', '.join(cursos_no_asignados_completamente)}."

        cursos_sin_docente = Curso.objects.filter(
            semestre=semestre_activo, docente__isnull=True
        ).count()
        if cursos_sin_docente > 0:
            message += f" Hay {cursos_sin_docente} cursos sin docente asignado que no pudieron ser planificados."

        return Response(
            {"status": "success", "message": message}, status=status.HTTP_200_OK
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return Response(
            {"status": "error", "message": f"Ocurrió un error inesperado: {e}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([permissions.IsAdminUser])
def api_get_cursos_no_asignados(request):
    try:
        especialidad_id = request.GET.get("especialidad_id")
        semestre_cursado = request.GET.get("semestre_cursado")
        planner_data = _get_planner_data(especialidad_id, semestre_cursado)
        return success_response(data=planner_data)
    except ValueError as e:
        return Response(
            {"status": "error", "message": str(e)}, status=status.HTTP_404_NOT_FOUND
        )
