from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from ..models import Anuncio, Notificacion


@login_required
def ver_notificaciones(request):
    # Get all notifications for the user
    notificaciones = request.user.notificaciones.all()

    context = {"notificaciones": notificaciones}

    # Mark all unread notifications as read
    request.user.notificaciones.filter(leido=False).update(leido=True)

    return render(request, "ver_notificaciones.html", context)


@login_required
def ver_anuncios(request):
    anuncios = Anuncio.objects.all()
    context = {"anuncios": anuncios}
    return render(request, "ver_anuncios.html", context)
