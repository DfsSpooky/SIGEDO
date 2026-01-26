from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.db.models import Q

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

    # Lógica POST para Aprobar/Rechazar (Solo Admin)
    if request.method == "POST" and is_admin and user.has_perm("core.change_justificacion"):
        justificacion_id = request.POST.get("justificacion_id")
        accion = request.POST.get("accion")
        
        if justificacion_id and accion:
            justificacion = get_object_or_404(Justificacion, id=justificacion_id)

            if accion == "aprobar":
                justificacion.estado = "APROBADO"
                messages.success(request, f"Se aprobó la justificación de {justificacion.docente}.")
            elif accion == "rechazar":
                justificacion.estado = "RECHAZADO"
                messages.warning(request, f"Se rechazó la justificación de {justificacion.docente}.")

            justificacion.revisado_por = user
            justificacion.fecha_revision = timezone.now()
            justificacion.save()
            return redirect("lista_justificaciones")

    # 1. Obtener QuerySet base según rol
    if is_admin:
        qs = Justificacion.objects.select_related("docente", "tipo").order_by("-fecha_creacion")
    else:
        qs = Justificacion.objects.filter(docente=user).select_related("tipo").order_by("-fecha_creacion")

    # 2. Serializar datos para React
    justificaciones_data = []
    for j in qs:
        # Calcular duración en días
        dias = (j.fecha_fin - j.fecha_inicio).days + 1
        
        justificaciones_data.append({
            "id": j.id,
            "docente_nombre": f"{j.docente.first_name} {j.docente.last_name}",
            "docente_avatar": j.docente.foto.url if j.docente.foto else None,
            "tipo": j.tipo.nombre,
            "motivo": j.motivo,
            "estado": j.estado,
            "fecha_inicio": j.fecha_inicio.strftime("%d/%m/%Y"),
            "fecha_fin": j.fecha_fin.strftime("%d/%m/%Y"),
            "dias_duracion": dias,
            "fecha_solicitud": j.fecha_creacion.strftime("%d %b, %H:%M"),
            "adjunto_url": j.documento_adjunto.url if j.documento_adjunto else None,
            "adjunto_nombre": j.documento_adjunto.name.split('/')[-1] if j.documento_adjunto else None
        })

    # 3. Contadores para las pestañas
    stats = {
        "total": qs.count(),
        "pendientes": qs.filter(estado="PENDIENTE").count(),
        "aprobados": qs.filter(estado="APROBADO").count(),
        "rechazados": qs.filter(estado="RECHAZADO").count(),
    }

    context = {
        "justificaciones_data": justificaciones_data,
        "stats": stats,
        "is_admin": is_admin,
        "can_manage": is_admin and user.has_perm("core.change_justificacion"),
    }

    return render(request, "lista_justificaciones.html", context)