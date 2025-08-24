import logging
from django.db import transaction
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.urls import reverse
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from functools import partial
from .models import Documento, Notificacion, SolicitudIntercambio, Curso, Anuncio, Docente, VersionDocumento, Justificacion

logger = logging.getLogger(__name__)

def do_broadcast(user_id, payload):
    """Helper function to broadcast a message to a user's notification channel."""
    try:
        channel_layer = get_channel_layer()
        if channel_layer:
            logger.info(f"Broadcasting notification to user {user_id}.")
            async_to_sync(channel_layer.group_send)(
                f'notifications_{user_id}',
                payload
            )
        else:
            logger.warning("Channel layer is not available. Real-time notifications may not work.")
    except Exception as e:
        logger.error(f"Failed to broadcast notification for user {user_id}: {e}", exc_info=True)

@receiver(pre_save, sender=Documento)
def crear_notificacion_estado_documento(sender, instance, **kwargs):
    if instance.pk:
        try:
            old_instance = Documento.objects.get(pk=instance.pk)
            if old_instance.estado != instance.estado:
                message = None
                if instance.estado == 'APROBADO':
                    message = f"Su documento '{instance.titulo}' ha sido aprobado."
                elif instance.estado == 'OBSERVADO':
                    message = f"Su documento '{instance.titulo}' tiene observaciones. Por favor, revíselo."

                if message:
                    notificacion = Notificacion.objects.create(
                        destinatario=instance.docente,
                        mensaje=message,
                        url=reverse('lista_documentos')
                    )
                    payload = {'type': 'send.notification', 'message': { 'id': notificacion.id, 'mensaje': notificacion.mensaje, 'url': notificacion.url, 'leido': notificacion.leido, 'fecha_creacion': notificacion.fecha_creacion.isoformat() }}
                    transaction.on_commit(partial(do_broadcast, instance.docente.id, payload))
        except Documento.DoesNotExist:
            pass

@receiver(pre_save, sender=SolicitudIntercambio)
def crear_notificacion_estado_solicitud(sender, instance, **kwargs):
    if instance.pk:
        try:
            old_instance = SolicitudIntercambio.objects.get(pk=instance.pk)
            if old_instance.estado != instance.estado:
                message = None
                destinatario = instance.docente_solicitante

                if instance.estado == 'aprobado':
                    message = f"Tu solicitud de intercambio para el curso '{instance.curso_solicitante.nombre}' fue aprobada."
                elif instance.estado == 'rechazado':
                    message = f"Tu solicitud de intercambio para el curso '{instance.curso_solicitante.nombre}' fue rechazada."

                if message:
                    notificacion = Notificacion.objects.create(
                        destinatario=destinatario,
                        mensaje=message,
                        url=reverse('ver_solicitudes')
                    )
                    payload = {'type': 'send.notification', 'message': { 'id': notificacion.id, 'mensaje': notificacion.mensaje, 'url': notificacion.url, 'leido': notificacion.leido, 'fecha_creacion': notificacion.fecha_creacion.isoformat() }}
                    transaction.on_commit(partial(do_broadcast, destinatario.id, payload))
        except SolicitudIntercambio.DoesNotExist:
            pass

@receiver(pre_save, sender=Curso)
def crear_notificacion_asignacion_curso(sender, instance, **kwargs):
    if instance.pk:
        try:
            old_instance = Curso.objects.get(pk=instance.pk)
            if old_instance.docente != instance.docente and instance.docente is not None:
                message = f"Se le ha asignado un nuevo curso: '{instance.nombre}' en el horario de {instance.dia} de {instance.horario_inicio} a {instance.horario_fin}."

                notificacion = Notificacion.objects.create(
                    destinatario=instance.docente,
                    mensaje=message,
                    url=reverse('ver_horarios', args=[instance.carrera.id])
                )
                payload = {'type': 'send.notification', 'message': { 'id': notificacion.id, 'mensaje': notificacion.mensaje, 'url': notificacion.url, 'leido': notificacion.leido, 'fecha_creacion': notificacion.fecha_creacion.isoformat() }}
                transaction.on_commit(partial(do_broadcast, instance.docente.id, payload))
        except Curso.DoesNotExist:
            pass
    elif instance.docente is not None:
        message = f"Se le ha asignado un nuevo curso: '{instance.nombre}'."
        try:
            url = reverse('ver_horarios', args=[instance.carrera.id])
        except Exception:
            url = "/"

        notificacion = Notificacion.objects.create(
            destinatario=instance.docente,
            mensaje=message,
            url=url
        )
        payload = {'type': 'send.notification', 'message': { 'id': notificacion.id, 'mensaje': notificacion.mensaje, 'url': notificacion.url, 'leido': notificacion.leido, 'fecha_creacion': notificacion.fecha_creacion.isoformat() }}
        transaction.on_commit(partial(do_broadcast, instance.docente.id, payload))


@receiver(post_save, sender=Anuncio)
def crear_notificacion_anuncio(sender, instance, created, **kwargs):
    if created:
        message = f"Nuevo anuncio publicado: '{instance.titulo}'"

        for docente in Docente.objects.all():
            notificacion = Notificacion.objects.create(
                destinatario=docente,
                mensaje=message,
                url=reverse('ver_anuncios')
            )
            payload = {'type': 'send.notification', 'message': { 'id': notificacion.id, 'mensaje': notificacion.mensaje, 'url': notificacion.url, 'leido': notificacion.leido, 'fecha_creacion': notificacion.fecha_creacion.isoformat() }}
            transaction.on_commit(partial(do_broadcast, docente.id, payload))

@receiver(post_save, sender=VersionDocumento)
def notificar_admin_nuevo_documento(sender, instance, created, **kwargs):
    if created:
        admins = Docente.objects.filter(is_staff=True)
        message = f"Nuevo documento/versión de '{instance.documento.docente.first_name}'"
        url = reverse('admin:core_documento_change', args=[instance.documento.pk])

        for admin in admins:
            notificacion = Notificacion.objects.create(
                destinatario=admin,
                mensaje=message,
                url=url
            )
            payload = {'type': 'send.notification', 'message': { 'id': notificacion.id, 'mensaje': notificacion.mensaje, 'url': notificacion.url, 'leido': notificacion.leido, 'fecha_creacion': notificacion.fecha_creacion.isoformat() }}
            transaction.on_commit(partial(do_broadcast, admin.id, payload))

@receiver(post_save, sender=Justificacion)
def notificar_admin_nueva_justificacion(sender, instance, created, **kwargs):
    if created:
        admins = Docente.objects.filter(is_staff=True)
        message = f"Nueva justificación de '{instance.docente.first_name}' pendiente de revisión"
        url = reverse('admin:core_justificacion_change', args=[instance.pk])

        for admin in admins:
            notificacion = Notificacion.objects.create(
                destinatario=admin,
                mensaje=message,
                url=url
            )
            payload = {'type': 'send.notification', 'message': { 'id': notificacion.id, 'mensaje': notificacion.mensaje, 'url': notificacion.url, 'leido': notificacion.leido, 'fecha_creacion': notificacion.fecha_creacion.isoformat() }}
            transaction.on_commit(partial(do_broadcast, admin.id, payload))

@receiver(post_save, sender=SolicitudIntercambio)
def notificar_nueva_solicitud_intercambio(sender, instance, created, **kwargs):
    if created:
        destinatario = instance.docente_destino
        message = f"'{instance.docente_solicitante.first_name}' te envió una solicitud de intercambio"
        url = reverse('admin:core_solicitudintercambio_change', args=[instance.pk])

        notificacion = Notificacion.objects.create(
            destinatario=destinatario,
            mensaje=message,
            url=url
        )
        payload = {'type': 'send.notification', 'message': { 'id': notificacion.id, 'mensaje': notificacion.mensaje, 'url': notificacion.url, 'leido': notificacion.leido, 'fecha_creacion': notificacion.fecha_creacion.isoformat() }}
        transaction.on_commit(partial(do_broadcast, destinatario.id, payload))
