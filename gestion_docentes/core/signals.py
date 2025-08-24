import logging
from django.db import transaction
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.urls import reverse
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from functools import partial
from django.contrib.auth import get_user_model

# Import all necessary models at once for clarity
from .models import (
    Documento, Justificacion, Reserva, Notificacion,
    SolicitudIntercambio, Curso, Anuncio, Docente
)

logger = logging.getLogger(__name__)
User = get_user_model()


def do_broadcast(user_id, payload):
    """Helper function to broadcast a message to a user's notification channel."""
    try:
        channel_layer = get_channel_layer()
        if channel_layer:
            # logger.info(f"Broadcasting notification to user {user_id}.")
            async_to_sync(channel_layer.group_send)(
                f'notifications_{user_id}',
                payload
            )
        else:
            logger.warning("Channel layer is not available. Real-time notifications may not work.")
    except Exception as e:
        logger.error(f"Failed to broadcast notification for user {user_id}: {e}", exc_info=True)

def crear_notificacion_para_admins(mensaje, url):
    """
    Creates a notification for all admin users and broadcasts it via WebSocket.
    """
    admins = User.objects.filter(is_staff=True, is_active=True)
    for admin in admins:
        notificacion = Notificacion.objects.create(
            destinatario=admin,
            mensaje=mensaje,
            url=url
        )
        payload = {
            'type': 'send_notification', # Use a more descriptive type name
            'message': {
                'id': notificacion.id,
                'mensaje': notificacion.mensaje,
                'url': notificacion.url,
                'leido': notificacion.leido,
                'fecha_creacion': notificacion.fecha_creacion.isoformat()
            }
        }
        # Schedule the broadcast to happen after the database transaction is committed
        transaction.on_commit(partial(do_broadcast, admin.id, payload))


# --- SIGNALS FOR ADMINS (when a new item is submitted) ---

@receiver(post_save, sender=Documento)
def notificar_nuevo_documento(sender, instance, created, **kwargs):
    """Notifies admins when a new document is uploaded."""
    if created:
        mensaje = f"Nuevo documento de {instance.docente.get_full_name()}: '{instance.titulo}'."
        url = reverse('admin:core_documento_change', args=[instance.pk])
        crear_notificacion_para_admins(mensaje, url)

@receiver(post_save, sender=Justificacion)
def notificar_nueva_justificacion(sender, instance, created, **kwargs):
    """Notifies admins when a new justification is requested."""
    if created:
        mensaje = f"{instance.docente.get_full_name()} ha solicitado una justificación."
        url = reverse('admin:core_justificacion_change', args=[instance.pk])
        crear_notificacion_para_admins(mensaje, url)

@receiver(post_save, sender=Reserva)
def notificar_nueva_reserva(sender, instance, created, **kwargs):
    """Notifies admins when a new PENDING reservation is made."""
    # Only notify for reservations that require approval
    if created and getattr(instance, 'estado', None) == 'PENDIENTE':
        mensaje = f"{instance.docente.get_full_name()} ha solicitado la reserva de '{instance.activo.nombre}'."
        url = reverse('admin:core_reserva_change', args=[instance.pk])
        crear_notificacion_para_admins(mensaje, url)


# --- SIGNALS FOR TEACHERS (when an admin changes an item's state) ---

@receiver(pre_save, sender=Documento)
def notificar_cambio_estado_documento(sender, instance, **kwargs):
    """Notifies a user when the status of their document changes."""
    if not instance.pk: return # Only on updates
    try:
        old_instance = Documento.objects.get(pk=instance.pk)
        if old_instance.estado != instance.estado:
            message = None
            if instance.estado == 'APROBADO':
                message = f"Su documento '{instance.titulo}' ha sido aprobado."
            elif instance.estado == 'OBSERVADO':
                message = f"Su documento '{instance.titulo}' tiene observaciones. Por favor, revíselo."

            if message:
                notificacion = Notificacion.objects.create(destinatario=instance.docente, mensaje=message, url=reverse('lista_documentos'))
                payload = {'type': 'send_notification', 'message': { 'id': notificacion.id, 'mensaje': notificacion.mensaje, 'url': notificacion.url, 'leido': notificacion.leido, 'fecha_creacion': notificacion.fecha_creacion.isoformat() }}
                transaction.on_commit(partial(do_broadcast, instance.docente.id, payload))
    except Documento.DoesNotExist:
        pass

@receiver(pre_save, sender=SolicitudIntercambio)
def notificar_cambio_estado_solicitud(sender, instance, **kwargs):
    """Notifies a user when the status of their exchange request changes."""
    if not instance.pk: return # Only on updates
    try:
        old_instance = SolicitudIntercambio.objects.get(pk=instance.pk)
        if old_instance.estado != instance.estado:
            message, destinatario = None, instance.docente_solicitante
            if instance.estado == 'aprobado': message = f"Su solicitud de intercambio para '{instance.curso_solicitante.nombre}' fue aprobada."
            elif instance.estado == 'rechazado': message = f"Su solicitud de intercambio para '{instance.curso_solicitante.nombre}' fue rechazada."

            if message:
                notificacion = Notificacion.objects.create(destinatario=destinatario, mensaje=message, url=reverse('ver_solicitudes'))
                payload = {'type': 'send_notification', 'message': { 'id': notificacion.id, 'mensaje': notificacion.mensaje, 'url': notificacion.url, 'leido': notificacion.leido, 'fecha_creacion': notificacion.fecha_creacion.isoformat() }}
                transaction.on_commit(partial(do_broadcast, destinatario.id, payload))
    except SolicitudIntercambio.DoesNotExist:
        pass

@receiver(pre_save, sender=Curso)
def notificar_asignacion_curso(sender, instance, **kwargs):
    """Notifies a teacher when they are assigned to a course."""
    if not instance.pk: return # Only on updates
    try:
        old_instance = Curso.objects.get(pk=instance.pk)
        if old_instance.docente != instance.docente and instance.docente is not None:
            message = f"Se le ha asignado un nuevo curso: '{instance.nombre}'."
            url = reverse('ver_horarios', args=[instance.carrera.id])
            notificacion = Notificacion.objects.create(destinatario=instance.docente, mensaje=message, url=url)
            payload = {'type': 'send_notification', 'message': { 'id': notificacion.id, 'mensaje': notificacion.mensaje, 'url': notificacion.url, 'leido': notificacion.leido, 'fecha_creacion': notificacion.fecha_creacion.isoformat() }}
            transaction.on_commit(partial(do_broadcast, instance.docente.id, payload))
    except Curso.DoesNotExist:
        pass

@receiver(post_save, sender=Anuncio)
def notificar_nuevo_anuncio(sender, instance, created, **kwargs):
    """Notifies all users when a new announcement is published."""
    if created:
        message = f"Nuevo anuncio publicado: '{instance.titulo}'"
        for docente in Docente.objects.filter(is_active=True):
            notificacion = Notificacion.objects.create(destinatario=docente, mensaje=message, url=reverse('ver_anuncios'))
            payload = {'type': 'send_notification', 'message': { 'id': notificacion.id, 'mensaje': notificacion.mensaje, 'url': notificacion.url, 'leido': notificacion.leido, 'fecha_creacion': notificacion.fecha_creacion.isoformat() }}
            transaction.on_commit(partial(do_broadcast, docente.id, payload))
