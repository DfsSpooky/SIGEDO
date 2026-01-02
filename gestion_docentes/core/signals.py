import logging
from functools import partial

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django.urls import reverse

from .models import (
    Anuncio,
    AsistenciaDiaria,
    BloqueHorario,
    Curso,
    Docente,
    Documento,
    Justificacion,
    Notificacion,
    SolicitudIntercambio,
    VersionDocumento,
)

from django.conf import settings
import os
import firebase_admin
from firebase_admin import credentials, messaging

logger = logging.getLogger(__name__)

# --- Inicialización Lazy de Firebase ---
if not firebase_admin._apps:
    try:
        cred_path = os.path.join(settings.BASE_DIR, 'serviceAccountKey.json')
        if os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
    except Exception as e:
        logger.error(f"Error loading Firebase credentials in signals: {e}")

from django.utils.html import strip_tags

def send_fcm_notification(user, title, body, data=None):
    """Envía una notificación Push al Token FCM del usuario."""
    if not user.fcm_token:
        return
    
    try:
        if not firebase_admin._apps: 
             return # No configurado

        # Limpiar etiquetas HTML del cuerpo (e.g. <div>, <strong>)
        clean_body = strip_tags(body)

        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=clean_body,
            ),
            data=data if data else {},
            token=user.fcm_token,
        )
        response = messaging.send(message)
        logger.info(f"FCM Sent to {user.username}: {response}")
    except Exception as e:
        logger.error(f"Error sending FCM to {user.username}: {e}")


def do_broadcast(user_id, payload):
    """Helper function to broadcast a message to a user's notification channel."""
    try:
        channel_layer = get_channel_layer()
        if channel_layer:
            logger.info(f"Broadcasting notification to user {user_id}.")
            async_to_sync(channel_layer.group_send)(f"notifications_{user_id}", payload)
        else:
            logger.warning(
                "Channel layer is not available. Real-time notifications may not work."
            )
    except Exception as e:
        logger.error(
            f"Failed to broadcast notification for user {user_id}: {e}", exc_info=True
        )


@receiver(pre_save, sender=Documento)
def crear_notificacion_estado_documento(sender, instance, **kwargs):
    if instance.pk:
        try:
            old_instance = Documento.objects.get(pk=instance.pk)
            if old_instance.estado != instance.estado:
                message = None
                if instance.estado == "APROBADO":
                    message = f"Su documento '{instance.titulo}' ha sido aprobado."
                elif instance.estado == "OBSERVADO":
                    message = f"Su documento '{instance.titulo}' tiene observaciones. Por favor, revíselo."

                if message:
                    notificacion = Notificacion.objects.create(
                        destinatario=instance.docente,
                        mensaje=message,
                        url=reverse("lista_documentos"),
                    )
                    payload = {
                        "type": "send.notification",
                        "message": {
                            "id": notificacion.id,
                            "mensaje": notificacion.mensaje,
                            "url": notificacion.url,
                            "leido": notificacion.leido,
                            "fecha_creacion": notificacion.fecha_creacion.isoformat(),
                        },
                    }
                    transaction.on_commit(
                        partial(do_broadcast, instance.docente.id, payload)
                    )
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

                if instance.estado == "aprobado":
                    message = f"Tu solicitud de intercambio para el curso '{instance.curso_solicitante.nombre}' fue aprobada."
                elif instance.estado == "rechazado":
                    message = f"Tu solicitud de intercambio para el curso '{instance.curso_solicitante.nombre}' fue rechazada."

                if message:
                    notificacion = Notificacion.objects.create(
                        destinatario=destinatario,
                        mensaje=message,
                        url=reverse("ver_solicitudes"),
                    )
                    payload = {
                        "type": "send.notification",
                        "message": {
                            "id": notificacion.id,
                            "mensaje": notificacion.mensaje,
                            "url": notificacion.url,
                            "leido": notificacion.leido,
                            "fecha_creacion": notificacion.fecha_creacion.isoformat(),
                        },
                    }
                    transaction.on_commit(
                        partial(do_broadcast, destinatario.id, payload)
                    )
        except SolicitudIntercambio.DoesNotExist:
            pass


@receiver(pre_save, sender=Curso)
def crear_notificacion_asignacion_curso(sender, instance, **kwargs):
    if instance.pk:
        try:
            old_instance = Curso.objects.get(pk=instance.pk)
            if (
                old_instance.docente != instance.docente
                and instance.docente is not None
            ):
                message = f"Se le ha asignado un nuevo curso: '{instance.nombre}'. Consulte su horario para ver los detalles."

                notificacion = Notificacion.objects.create(
                    destinatario=instance.docente,
                    mensaje=message,
                    url=reverse("ver_horarios", args=[instance.carrera.id]),
                )
                payload = {
                    "type": "send.notification",
                    "message": {
                        "id": notificacion.id,
                        "mensaje": notificacion.mensaje,
                        "url": notificacion.url,
                        "leido": notificacion.leido,
                        "fecha_creacion": notificacion.fecha_creacion.isoformat(),
                    },
                }
                transaction.on_commit(
                    partial(do_broadcast, instance.docente.id, payload)
                )
        except Curso.DoesNotExist:
            pass
    elif instance.docente is not None:
        message = f"Se le ha asignado un nuevo curso: '{instance.nombre}'."
        try:
            url = reverse("ver_horarios", args=[instance.carrera.id])
        except Exception:
            url = "/"

        notificacion = Notificacion.objects.create(
            destinatario=instance.docente, mensaje=message, url=url
        )
        payload = {
            "type": "send.notification",
            "message": {
                "id": notificacion.id,
                "mensaje": notificacion.mensaje,
                "url": notificacion.url,
                "leido": notificacion.leido,
                "fecha_creacion": notificacion.fecha_creacion.isoformat(),
            },
        }
        transaction.on_commit(partial(do_broadcast, instance.docente.id, payload))


@receiver(post_save, sender=Anuncio)
def crear_notificacion_anuncio(sender, instance, created, **kwargs):
    if created:
        message = f"Nuevo anuncio: {instance.titulo}\n\n{instance.contenido}"

        for docente in Docente.objects.all():
            notificacion = Notificacion.objects.create(
                destinatario=docente, mensaje=message, url=reverse("ver_anuncios")
            )
            payload = {
                "type": "send.notification",
                "message": {
                    "id": notificacion.id,
                    "mensaje": notificacion.mensaje,
                    "url": notificacion.url,
                    "leido": notificacion.leido,
                    "fecha_creacion": notificacion.fecha_creacion.isoformat(),
                },
            }
            # Prepare data payload for deep link
            fcm_data = {"screen": "announcements", "id": str(instance.id)}
            transaction.on_commit(partial(do_broadcast, docente.id, payload))
            transaction.on_commit(partial(send_fcm_notification, docente, "SIGEDO", message, fcm_data))


@receiver(post_save, sender=VersionDocumento)
def notificar_admin_nuevo_documento(sender, instance, created, **kwargs):
    if created:
        admins = Docente.objects.filter(is_staff=True)
        message = (
            f"Nuevo documento/versión de '{instance.documento.docente.first_name}'"
        )
        url = reverse("admin:core_documento_change", args=[instance.documento.pk])

        for admin in admins:
            notificacion = Notificacion.objects.create(
                destinatario=admin, mensaje=message, url=url
            )
            payload = {
                "type": "send.notification",
                "message": {
                    "id": notificacion.id,
                    "mensaje": notificacion.mensaje,
                    "url": notificacion.url,
                    "leido": notificacion.leido,
                    "fecha_creacion": notificacion.fecha_creacion.isoformat(),
                },
            }
            transaction.on_commit(partial(do_broadcast, admin.id, payload))


@receiver(post_save, sender=Justificacion)
def notificar_admin_nueva_justificacion(sender, instance, created, **kwargs):
    if created:
        admins = Docente.objects.filter(is_staff=True)
        message = f"Nueva justificación de '{instance.docente.first_name}' pendiente de revisión"
        url = reverse("admin:core_justificacion_change", args=[instance.pk])

        for admin in admins:
            notificacion = Notificacion.objects.create(
                destinatario=admin, mensaje=message, url=url
            )
            payload = {
                "type": "send.notification",
                "message": {
                    "id": notificacion.id,
                    "mensaje": notificacion.mensaje,
                    "url": notificacion.url,
                    "leido": notificacion.leido,
                    "fecha_creacion": notificacion.fecha_creacion.isoformat(),
                },
            }
            transaction.on_commit(partial(do_broadcast, admin.id, payload))


@receiver(post_save, sender=SolicitudIntercambio)
def notificar_nueva_solicitud_intercambio(sender, instance, created, **kwargs):
    if created:
        destinatario = instance.docente_destino
        message = f"'{instance.docente_solicitante.first_name}' te envió una solicitud de intercambio"
        url = reverse("admin:core_solicitudintercambio_change", args=[instance.pk])

        notificacion = Notificacion.objects.create(
            destinatario=destinatario, mensaje=message, url=url
        )
        payload = {
            "type": "send.notification",
            "message": {
                "id": notificacion.id,
                "mensaje": notificacion.mensaje,
                "url": notificacion.url,
                "leido": notificacion.leido,
                "fecha_creacion": notificacion.fecha_creacion.isoformat(),
            },
        }
        transaction.on_commit(partial(do_broadcast, destinatario.id, payload))


# --- Señales para el Calendario en Tiempo Real ---


def broadcast_horario_update(docente_id):
    """
    Helper function to broadcast a schedule update message to a user's calendar channel.
    """
    try:
        channel_layer = get_channel_layer()
        if channel_layer and docente_id:
            logger.info(f"Broadcasting schedule update to user {docente_id}.")
            async_to_sync(channel_layer.group_send)(
                f"horario_{docente_id}",
                {
                    "type": "horario.update",
                    "message": "Tu horario ha sido actualizado.",
                },
            )
        else:
            logger.warning(
                f"Channel layer not available or no docente_id provided for schedule update."
            )
    except Exception as e:
        logger.error(
            f"Failed to broadcast schedule update for user {docente_id}: {e}",
            exc_info=True,
        )


@receiver(post_save, sender=BloqueHorario)
def notificar_cambio_horario_on_save(sender, instance, **kwargs):
    """
    Notifica al docente cuando un bloque de su horario es creado o modificado.
    """
    if instance.curso and instance.curso.docente:
        # Usamos on_commit para asegurar que la transacción se haya completado
        # antes de enviar la notificación. Esto evita race conditions.
        transaction.on_commit(
            partial(broadcast_horario_update, instance.curso.docente.id)
        )


@receiver(post_delete, sender=BloqueHorario)
def notificar_cambio_horario_on_delete(sender, instance, **kwargs):
    """
    Notifica al docente cuando un bloque de su horario es eliminado.
    """
    if instance.curso and instance.curso.docente:
        transaction.on_commit(
            partial(broadcast_horario_update, instance.curso.docente.id)
        )

@receiver(post_save, sender=Notificacion)
def enviar_push_al_crear_notificacion(sender, instance, created, **kwargs):
    """
    Cada vez que se crea una Notificación interna (BD), se intenta enviar como Push.
    """
    if created and instance.destinatario.fcm_token:
        # Usamos on_commit para no bloquear la transacción DB con la llamada de red
        transaction.on_commit(
            # Título genérico o personalizado según contexto
            partial(send_fcm_notification, instance.destinatario, "SIGEDO", instance.mensaje)
        )

# --- Dashboard Real-time Signal ---
from .models import Asistencia

def broadcast_dashboard_update(data):
    try:
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                "dashboard_feed",
                {
                    "type": "attendance.update",
                    "data": data,
                },
            )
    except Exception as e:
        logger.error(f"Failed to broadcast dashboard update: {e}", exc_info=True)

@receiver(post_save, sender=Asistencia)
def notificar_dashboard_asistencia(sender, instance, created, **kwargs):
    # Determinar tipo de evento
    tipo = None
    if created:
        tipo = "entrada"
    elif instance.hora_salida:
        # Si ya tiene salida y NO es creado, asumimos que es el evento de salida.
        # (Nota: esto enviará 'salida' también en ediciones posteriores, lo cual es aceptable para refrescar la UI)
        tipo = "salida"
    # Si no es creado y no tiene hora_salida, es una edición de entrada (no notificamos o notificamos entrada)
    # Por ahora, solo notificamos si hay un cambio relevante de estado.

    if tipo:
        data = {
            "id": instance.id,
            "docente_nombre": f"{instance.docente.first_name} {instance.docente.last_name}",
            "curso": instance.curso.nombre,
            "hora_entrada": instance.hora_entrada.strftime("%H:%M") if instance.hora_entrada else "--:--",
            "hora_salida": instance.hora_salida.strftime("%H:%M") if instance.hora_salida else "--:--",
            "foto_url": instance.foto_entrada.url if instance.foto_entrada else None,
            "estado": "Finalizado" if instance.hora_salida else "En curso",
            "tipo": tipo,
            "es_general": False
        }
        transaction.on_commit(partial(broadcast_dashboard_update, data))


@receiver(post_save, sender=AsistenciaDiaria)
def notificar_dashboard_asistencia_diaria(sender, instance, created, **kwargs):
    tipo = None
    if created:
        tipo = "entrada_general"
    elif instance.hora_salida:
        tipo = "salida_general"

    if tipo:
        data = {
            "id": f"gen_{instance.id}",
            "docente_nombre": f"{instance.docente.first_name} {instance.docente.last_name}",
            "curso": "Control General",  # Etiqueta distintiva
            "hora_entrada": instance.hora_entrada.strftime("%H:%M") if instance.hora_entrada else "--:--",
            "hora_salida": instance.hora_salida.strftime("%H:%M") if instance.hora_salida else "--:--",
            "foto_url": instance.foto_verificacion.url if instance.foto_verificacion else None,
            "estado": "Jornada Finalizada" if instance.hora_salida else "En Campus",
            "tipo": tipo,
            "es_general": True
        }
        transaction.on_commit(partial(broadcast_dashboard_update, data))
