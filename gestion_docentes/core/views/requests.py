from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import SolicitudIntercambioForm
from ..models import Curso, SolicitudIntercambio


@login_required
def solicitar_intercambio(request, curso_id):
    curso_solicitante = Curso.objects.get(id=curso_id)
    if curso_solicitante.docente != request.user:
        return redirect("ver_horarios", carrera_id=curso_solicitante.carrera.id)

    if request.method == "POST":
        form = SolicitudIntercambioForm(
            request.POST, curso_solicitante=curso_solicitante
        )
        if form.is_valid():
            solicitud = form.save(commit=False)
            solicitud.docente_solicitante = request.user
            solicitud.curso_solicitante = curso_solicitante
            solicitud.save()
            messages.success(request, "La solicitud de intercambio ha sido enviada.")
            return redirect("ver_solicitudes")
    else:
        form = SolicitudIntercambioForm(curso_solicitante=curso_solicitante)

    return render(
        request,
        "solicitar_intercambio.html",
        {"form": form, "curso": curso_solicitante},
    )


@login_required
def ver_solicitudes(request):
    solicitudes_enviadas = SolicitudIntercambio.objects.filter(
        docente_solicitante=request.user
    )
    solicitudes_recibidas = SolicitudIntercambio.objects.filter(
        docente_destino=request.user, estado="pendiente"
    )
    return render(
        request,
        "ver_solicitudes.html",
        {
            "solicitudes_enviadas": solicitudes_enviadas,
            "solicitudes_recibidas": solicitudes_recibidas,
        },
    )


@login_required
def responder_solicitud(request, solicitud_id):
    solicitud = SolicitudIntercambio.objects.get(id=solicitud_id)
    if solicitud.docente_destino != request.user:
        return redirect("ver_solicitudes")

    if request.method == "POST":
        accion = request.POST.get("accion")
        if accion == "aprobar":
            # Esta lógica de intercambio es compleja y se basa en el modelo antiguo.
            # Con el nuevo modelo de BloqueHorario, un intercambio implicaría reasignar
            # todos los bloques de un docente a otro, lo cual requiere una lógica de validación
            # de conflictos mucho más compleja.
            # Por ahora, se deshabilita la aprobación para evitar inconsistencias.
            messages.error(
                request,
                "La aprobación de intercambios está temporalmente deshabilitada debido a la nueva lógica de horarios flexibles.",
            )
            return render(request, "responder_solicitud.html", {"solicitud": solicitud})

            # La lógica original está comentada abajo para referencia futura.
            # curso_solicitante = solicitud.curso_solicitante
            # curso_destino = solicitud.curso_destino
            # ... (lógica de conflicto original) ...
            # curso_solicitante.docente, curso_destino.docente = curso_destino.docente, curso_solicitante.docente
            # curso_solicitante.save()
            # curso_destino.save()
            # solicitud.estado = "aprobado"
            # solicitud.save()
            # messages.success(request, "El intercambio ha sido aprobado correctamente.")
        elif accion == "rechazar":
            solicitud.estado = "rechazado"
            solicitud.save()
            messages.info(request, "La solicitud de intercambio ha sido rechazada.")
        return redirect("ver_solicitudes")

    return render(request, "responder_solicitud.html", {"solicitud": solicitud})
