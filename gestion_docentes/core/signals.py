from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.urls import reverse
from .models import Documento, Notificacion, SolicitudIntercambio


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
                    Notificacion.objects.create(
                        destinatario=instance.docente,
                        mensaje=message,
                        url=reverse('lista_documentos')
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
                if instance.estado == 'aprobado':
                    message = f"Tu solicitud de intercambio para el curso '{instance.curso_solicitante.nombre}' fue aprobada."
                elif instance.estado == 'rechazado':
                    message = f"Tu solicitud de intercambio para el curso '{instance.curso_solicitante.nombre}' fue rechazada."

                if message:
                    Notificacion.objects.create(
                        destinatario=instance.docente_solicitante,
                        mensaje=message,
                        url=reverse('ver_solicitudes')
                    )
        except SolicitudIntercambio.DoesNotExist:
            pass
