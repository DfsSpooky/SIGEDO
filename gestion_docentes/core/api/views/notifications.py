from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from core.models import Notificacion


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def notificaciones_json(request):
    """
    API view to get the user's notifications in JSON format.
    Compatible with both Web (Session) and Mobile (JWT).
    """
    notifications = Notificacion.objects.filter(destinatario=request.user).order_by(
        "-fecha_creacion"
    )[:20] # Increased limit
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

    return Response(
        {"notifications": notifications_data, "unread_count": unread_count}
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
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
    return Response({"status": "success"})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def marcar_todas_como_leidas(request):
    """
    API view to mark all unread notifications as read.
    """
    Notificacion.objects.filter(destinatario=request.user, leido=False).update(
        leido=True
    )
    return Response({"status": "success"})
