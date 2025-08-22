from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.urls import reverse
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import Documento, Notificacion, SolicitudIntercambio, Curso, Anuncio, Docente


@receiver(pre_save, sender=Documento)
def crear_notificacion_estado_documento(sender, instance, **kwargs):
    """
    Crea una notificación cuando el estado de un documento cambia a 'APROBADO' o 'OBSERVADO'.
    """
    if instance.pk:  # Solo para objetos que ya existen
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

                    channel_layer = get_channel_layer()
                    async_to_sync(channel_layer.group_send)(
                        f'notifications_{instance.docente.id}',
                        {
                            'type': 'send_notification',
                            'message': {
                                'id': notificacion.id,
                                'mensaje': notificacion.mensaje,
                                'url': notificacion.url,
                                'leido': notificacion.leido,
                                'fecha_creacion': notificacion.fecha_creacion.isoformat()
                            }
                        }
                    )
        except Documento.DoesNotExist:
            pass # No hacer nada si el objeto es nuevo


@receiver(pre_save, sender=SolicitudIntercambio)
def crear_notificacion_estado_solicitud(sender, instance, **kwargs):
    """
    Crea una notificación cuando el estado de una solicitud de intercambio cambia.
    """
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

                    channel_layer = get_channel_layer()
                    async_to_sync(channel_layer.group_send)(
                        f'notifications_{destinatario.id}',
                        {
                            'type': 'send_notification',
                            'message': {
                                'id': notificacion.id,
                                'mensaje': notificacion.mensaje,
                                'url': notificacion.url,
                                'leido': notificacion.leido,
                                'fecha_creacion': notificacion.fecha_creacion.isoformat()
                            }
                        }
                    )
        except SolicitudIntercambio.DoesNotExist:
            pass


@receiver(pre_save, sender=Curso)
def crear_notificacion_asignacion_curso(sender, instance, **kwargs):
    """
    Crea una notificación cuando un curso es asignado a un docente.
    """
    if instance.pk: # Solo para cursos que ya existen
        try:
            old_instance = Curso.objects.get(pk=instance.pk)
            # Notificar si el docente ha cambiado y el nuevo docente no es nulo
            if old_instance.docente != instance.docente and instance.docente is not None:
                message = f"Se le ha asignado un nuevo curso: '{instance.nombre}' en el horario de {instance.dia} de {instance.horario_inicio} a {instance.horario_fin}."

                notificacion = Notificacion.objects.create(
                    destinatario=instance.docente,
                    mensaje=message,
                    url=reverse('ver_horarios', args=[instance.carrera.id]) # Asumiendo que quieres que el link vaya a la vista de horarios
                )

                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    f'notifications_{instance.docente.id}',
                    {
                        'type': 'send_notification',
                        'message': {
                            'id': notificacion.id,
                            'mensaje': notificacion.mensaje,
                            'url': notificacion.url,
                            'leido': notificacion.leido,
                            'fecha_creacion': notificacion.fecha_creacion.isoformat()
                        }
                    }
                )
        except Curso.DoesNotExist:
            pass # No hacer nada si el curso es nuevo
    elif instance.docente is not None: # Para cursos nuevos que se crean con un docente ya asignado
        message = f"Se le ha asignado un nuevo curso: '{instance.nombre}'."

        # Necesitamos un delay o algo para asegurar que la carrera está asignada si es un curso nuevo
        # Pero por ahora, asumimos que la carrera existe para generar el URL
        try:
            url = reverse('ver_horarios', args=[instance.carrera.id])
        except Exception:
            url = "/" # URL de fallback

        notificacion = Notificacion.objects.create(
            destinatario=instance.docente,
            mensaje=message,
            url=url
        )

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'notifications_{instance.docente.id}',
            {
                'type': 'send_notification',
                'message': {
                    'id': notificacion.id,
                    'mensaje': notificacion.mensaje,
                    'url': notificacion.url,
                    'leido': notificacion.leido,
                    'fecha_creacion': notificacion.fecha_creacion.isoformat()
                }
            }
        )

@receiver(post_save, sender=Anuncio)
def crear_notificacion_anuncio(sender, instance, created, **kwargs):
    """
    Crea una notificación para todos los usuarios cuando se publica un nuevo anuncio.
    """
    if created:
        channel_layer = get_channel_layer()
        message = f"Nuevo anuncio publicado: '{instance.titulo}'"

        # Iterar sobre todos los docentes para crear y enviar notificaciones
        for docente in Docente.objects.all():
            notificacion = Notificacion.objects.create(
                destinatario=docente,
                mensaje=message,
                url=reverse('ver_anuncios')
            )

            async_to_sync(channel_layer.group_send)(
                f'notifications_{docente.id}',
                {
                    'type': 'send_notification',
                    'message': {
                        'id': notificacion.id,
                        'mensaje': notificacion.mensaje,
                        'url': notificacion.url,
                        'leido': notificacion.leido,
                        'fecha_creacion': notificacion.fecha_creacion.isoformat()
                    }
                }
            )
