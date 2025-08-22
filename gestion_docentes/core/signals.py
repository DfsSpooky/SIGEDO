from django.db import transaction
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.urls import reverse
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import Documento, Notificacion, SolicitudIntercambio, Curso, Anuncio, Docente


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

                    def broadcast():
                        channel_layer = get_channel_layer()
                        async_to_sync(channel_layer.group_send)(
                            f'notifications_{instance.docente.id}',
                            {
                                'type': 'send_notification',
                                'message': { 'id': notificacion.id, 'mensaje': notificacion.mensaje, 'url': notificacion.url, 'leido': notificacion.leido, 'fecha_creacion': notificacion.fecha_creacion.isoformat() }
                            }
                        )
                    transaction.on_commit(broadcast)
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

                    def broadcast():
                        channel_layer = get_channel_layer()
                        async_to_sync(channel_layer.group_send)(
                            f'notifications_{destinatario.id}',
                            {
                                'type': 'send_notification',
                                'message': { 'id': notificacion.id, 'mensaje': notificacion.mensaje, 'url': notificacion.url, 'leido': notificacion.leido, 'fecha_creacion': notificacion.fecha_creacion.isoformat() }
                            }
                        )
                    transaction.on_commit(broadcast)
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

                def broadcast():
                    channel_layer = get_channel_layer()
                    async_to_sync(channel_layer.group_send)(
                        f'notifications_{instance.docente.id}',
                        {
                            'type': 'send_notification',
                            'message': { 'id': notificacion.id, 'mensaje': notificacion.mensaje, 'url': notificacion.url, 'leido': notificacion.leido, 'fecha_creacion': notificacion.fecha_creacion.isoformat() }
                        }
                    )
                transaction.on_commit(broadcast)
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

        def broadcast():
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'notifications_{instance.docente.id}',
                {
                    'type': 'send_notification',
                    'message': { 'id': notificacion.id, 'mensaje': notificacion.mensaje, 'url': notificacion.url, 'leido': notificacion.leido, 'fecha_creacion': notificacion.fecha_creacion.isoformat() }
                }
            )
        transaction.on_commit(broadcast)

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

            def broadcast_to_user(user_id, notif_id, msg, url_path, read_status, creation_date):
                def broadcast():
                    channel_layer = get_channel_layer()
                    async_to_sync(channel_layer.group_send)(
                        f'notifications_{user_id}',
                        {
                            'type': 'send_notification',
                            'message': { 'id': notif_id, 'mensaje': msg, 'url': url_path, 'leido': read_status, 'fecha_creacion': creation_date }
                        }
                    )
                transaction.on_commit(broadcast)

            broadcast_to_user(docente.id, notificacion.id, notificacion.mensaje, notificacion.url, notificacion.leido, notificacion.fecha_creacion.isoformat())
