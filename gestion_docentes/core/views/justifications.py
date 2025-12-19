from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from ..forms import JustificacionForm
from ..models import Justificacion


@login_required
def solicitar_justificacion(request):
    if request.method == "POST":
        form = JustificacionForm(request.POST, request.FILES)
        if form.is_valid():
            justificacion = form.save(commit=False)
            justificacion.docente = request.user
            justificacion.save()
            messages.success(
                request, "Su solicitud de justificación ha sido enviada correctamente."
            )
            return redirect("lista_justificaciones")
    else:
        form = JustificacionForm()

    return render(request, "solicitar_justificacion.html", {"form": form})


@login_required
def lista_justificaciones(request):
    user = request.user
    is_admin = user.is_staff

    # Lógica para aprobar/rechazar (solo para staff con permisos)
    if (
        request.method == "POST"
        and is_admin
        and user.has_perm("core.change_justificacion")
    ):
        justificacion_id = request.POST.get("justificacion_id")
        accion = request.POST.get("accion")
        justificacion = get_object_or_404(Justificacion, id=justificacion_id)

        if accion == "aprobar":
            justificacion.estado = "APROBADO"
            messages.success(
                request, f"Se aprobó la justificación de {justificacion.docente}."
            )
        elif accion == "rechazar":
            justificacion.estado = "RECHAZADO"
            messages.warning(
                request, f"Se rechazó la justificación de {justificacion.docente}."
            )

        justificacion.revisado_por = user
        justificacion.fecha_revision = timezone.now()
        justificacion.save()
        return redirect("lista_justificaciones")

    # Preparar el contexto
    if is_admin:
        # Para el admin, separamos las justificaciones por estado para las pestañas
        base_qs = Justificacion.objects.select_related("docente", "tipo").order_by(
            "-fecha_creacion"
        )
        context = {
            "justificaciones": {
                "pending": base_qs.filter(estado="PENDIENTE"),
                "approved": base_qs.filter(estado="APROBADO"),
                "rejected": base_qs.filter(estado="RECHAZADO"),
                "pending_count": base_qs.filter(estado="PENDIENTE").count(),
            },
            "is_admin_view": True,
        }
    else:
        # Para el docente, solo una lista de sus propias justificaciones
        context = {
            "justificaciones": Justificacion.objects.filter(docente=user)
            .select_related("tipo")
            .order_by("-fecha_creacion"),
            "is_admin_view": False,
        }

    return render(request, "lista_justificaciones.html", context)
