import json

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from ..models import (
    Asistencia,
    BloqueHorario,
    Carrera,
    ConfiguracionInstitucion,
    Documento,
    Semestre,
    VersionDocumento,
)


@login_required
def dashboard(request):
    docente = request.user
    now = timezone.localtime(timezone.now())
    today = now.date()

    # --- LÓGICA MEJORADA PARA EL NUEVO DASHBOARD ---

    # 1. Datos para las tarjetas de métricas
    documentos_qs = Documento.objects.filter(docente=docente)
    documentos_observados_count = documentos_qs.filter(estado="OBSERVADO").count()
    asistencias_count = Asistencia.objects.filter(docente=docente, fecha=today).count()

    dia_actual_str = [
        "Lunes",
        "Martes",
        "Miércoles",
        "Jueves",
        "Viernes",
        "Sábado",
        "Domingo",
    ][today.weekday()]

    # Lógica actualizada para usar BloqueHorario
    bloques_hoy_qs = BloqueHorario.objects.filter(
        curso__docente=docente, dia=dia_actual_str, curso__semestre__estado="ACTIVO"
    ).select_related("curso")

    cursos_hoy_count = bloques_hoy_qs.values("curso").distinct().count()

    # 2. Encontrar el próximo curso del día
    proximo_bloque = (
        bloques_hoy_qs.filter(horario_inicio__gte=now.time())
        .order_by("horario_inicio")
        .first()
    )
    proximo_curso = proximo_bloque.curso if proximo_bloque else None

    # 3. Crear la línea de tiempo de actividad reciente (últimas 3 acciones)
    asistencias_recientes = Asistencia.objects.filter(docente=docente).order_by(
        "-hora_entrada"
    )[:3]
    versiones_recientes = (
        VersionDocumento.objects.filter(documento__docente=docente)
        .select_related("documento")
        .order_by("-fecha_version")[:3]
    )

    actividad_reciente = []
    for asistencia in asistencias_recientes:
        if asistencia.hora_entrada:
            actividad_reciente.append(
                {
                    "fecha": asistencia.hora_entrada,
                    "texto": f"Marcó entrada en '{asistencia.curso.nombre}'",
                    "tipo": "asistencia",
                }
            )
    for version in versiones_recientes:
        actividad_reciente.append(
            {
                "fecha": version.fecha_version,
                "texto": f"Subió el documento '{version.documento.titulo}'",
                "tipo": "documento",
            }
        )

    # Ordenamos la actividad combinada por fecha y tomamos los 3 más recientes
    actividad_reciente.sort(key=lambda item: item["fecha"], reverse=True)

    # 4. Encontrar las carreras asociadas al docente en el semestre activo
    semestre_activo = Semestre.objects.filter(estado="ACTIVO").first()
    carreras = []
    if semestre_activo:
        carreras = Carrera.objects.filter(
            curso__docente=docente, curso__semestre=semestre_activo
        ).distinct()

    configuracion = ConfiguracionInstitucion.load()

    context = {
        "asistencias_count": asistencias_count,
        "documentos_observados_count": documentos_observados_count,
        "cursos_hoy_count": cursos_hoy_count,
        "proximo_curso": proximo_curso,
        "actividad_reciente": actividad_reciente[
            :3
        ],  # Pasamos solo los 3 últimos eventos
        "configuracion": configuracion,
        "carreras": carreras,
    }
    return render(request, "dashboard.html", context)


@login_required
def perfil(request):
    docente = request.user

    # --- PREPARACIÓN DE DATOS PARA EL NUEVO PERFIL ---

    # 1. Datos para el Gráfico de Documentos
    documentos = Documento.objects.filter(docente=docente)
    status_counts = {
        "APROBADO": documentos.filter(estado="APROBADO").count(),
        "EN_REVISION": documentos.filter(estado="EN_REVISION").count(),
        "OBSERVADO": documentos.filter(estado="OBSERVADO").count(),
        "RECIBIDO": documentos.filter(estado="RECIBIDO").count(),
    }
    # Convertimos a JSON para pasarlo al JavaScript del gráfico
    documentos_status_json = json.dumps(list(status_counts.values()))
    documentos_labels_json = json.dumps(list(status_counts.keys()))

    # 2. Creación de la Línea de Tiempo (Timeline)
    # Combinamos las asistencias de hoy y las versiones de documentos recientes

    today = timezone.localtime(timezone.now()).date()
    asistencias_hoy = Asistencia.objects.filter(docente=docente, fecha=today)
    versiones_recientes = (
        VersionDocumento.objects.filter(documento__docente=docente)
        .select_related("documento")
        .order_by("-fecha_version")[:10]
    )

    timeline = []

    # Añadimos las asistencias de hoy a la línea de tiempo
    for asistencia in asistencias_hoy:
        if asistencia.hora_entrada:
            timeline.append(
                {
                    "tipo": "asistencia_entrada",
                    "fecha": asistencia.hora_entrada,
                    "texto": f"Marcó entrada en el curso '{asistencia.curso.nombre}'.",
                }
            )
        if asistencia.hora_salida:
            timeline.append(
                {
                    "tipo": "asistencia_salida",
                    "fecha": asistencia.hora_salida,
                    "texto": f"Marcó salida del curso '{asistencia.curso.nombre}'.",
                }
            )

    # Añadimos las subidas de documentos a la línea de tiempo
    for version in versiones_recientes:
        timeline.append(
            {
                "tipo": "documento",
                "fecha": version.fecha_version,
                "texto": f"Subió una nueva versión (v{version.numero_version}) del documento '{version.documento.titulo}'.",
                "documento": version.documento,  # Pasamos el objeto para crear enlaces
            }
        )

    # Ordenamos la línea de tiempo por fecha, de más reciente a más antiguo
    timeline.sort(key=lambda item: item["fecha"], reverse=True)

    context = {
        "timeline": timeline[:10],  # Mostramos los 10 eventos más recientes
        "documentos_status_json": documentos_status_json,
        "documentos_labels_json": documentos_labels_json,
        "total_documentos": documentos.count(),
    }

    return render(request, "perfil.html", context)
