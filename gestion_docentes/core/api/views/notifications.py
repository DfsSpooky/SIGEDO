from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from core.models import Notificacion


@login_required
def notificaciones_json(request):
    """
    API view to get the user's notifications in JSON format.
    """
    notifications = Notificacion.objects.filter(destinatario=request.user).order_by(
        "-fecha_creacion"
    )[:10]
    unread_count = Notificacion.objects.filter(
        destinatario=request.user, leido=False
    ).count()

    notifications_data = [
        {
            "id": n.id,
            "mensaje": n.mensaje,
            "url": n.url,
            "leido": n.leido,
            "fecha_creacion": n.fecha_creacion.isoformat(),
        }
        for n in notifications
    ]

    return JsonResponse(
        {"notifications": notifications_data, "unread_count": unread_count}
    )


@login_required
def marcar_notificacion_como_leida(request, notificacion_id):
    """
    API view to mark a single notification as read.
    """
    notificacion = get_object_or_404(
        Notificacion, id=notificacion_id, destinatario=request.user
    )
    if not notificacion.leido:
        notificacion.leido = True
        notificacion.save()
    return JsonResponse({"status": "success"})


@login_required
def marcar_todas_como_leidas(request):
    """
    API view to mark all unread notifications as read.
    """
    Notificacion.objects.filter(destinatario=request.user, leido=False).update(
        leido=True
    )
    return JsonResponse({"status": "success"})
