from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.mail import send_mail
from rest_framework import status, views
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
import random
import logging

User = get_user_model()
logger = logging.getLogger(__name__)

class RequestPasswordResetView(views.APIView):
    permission_classes = [AllowAny]
    throttle_scope = 'anon' # Limit attempts

    @extend_schema(
        summary="Solicitar código de recuperación",
        description="Envía un código OTP de 6 dígitos al correo registrado.",
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "email": {"type": "string", "format": "email"}
                },
                "required": ["email"]
            }
        },
        responses={200: {"description": "Código enviado (si el correo existe)"}}
    )
    def post(self, request):
        email = request.data.get("email")
        if not email:
            return Response({"error": "Email requerido"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Return 200 to prevent email enumeration, but log it
            logger.info(f"Password reset requested for non-existent email: {email}")
            return Response({"message": "Si el correo existe, se ha enviado un código."}, status=status.HTTP_200_OK)

        # Generate 6-digit OTP
        otp = f"{random.randint(100000, 999999)}"
        
        # Store in Cache (5 minutes)
        cache_key = f"reset_otp_{email}"
        cache.set(cache_key, otp, timeout=300)

        # Send Email (Console Backend in Dev)
        try:
            send_mail(
                subject="[SIGEDO] Código de Recuperación de Contraseña",
                message=f"Hola {user.first_name},\n\nTu código de recuperación es: {otp}\n\nEste código expira en 5 minutos.",
                from_email="no-reply@sigedo.com",
                recipient_list=[email],
                fail_silently=False,
            )
            logger.info(f"OTP sent to {email}: {otp}") # Log for dev convenience
        except Exception as e:
            logger.error(f"Error sending email to {email}: {e}")
            return Response({"error": "Error enviando correo"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({"message": "Si el correo existe, se ha enviado un código."}, status=status.HTTP_200_OK)


class ResetPasswordView(views.APIView):
    permission_classes = [AllowAny]
    throttle_scope = 'anon'

    @extend_schema(
        summary="Restablecer contraseña con código",
        description="Verifica el OTP y actualiza la contraseña del usuario.",
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "email": {"type": "string", "format": "email"},
                    "otp": {"type": "string", "minLength": 6, "maxLength": 6},
                    "new_password": {"type": "string", "minLength": 6}
                },
                "required": ["email", "otp", "new_password"]
            }
        },
        responses={
            200: {"description": "Contraseña actualizada exitosamente"},
            400: {"description": "Código inválido o expirado"}
        }
    )
    def post(self, request):
        email = request.data.get("email")
        otp = request.data.get("otp")
        new_password = request.data.get("new_password")

        if not all([email, otp, new_password]):
            return Response({"error": "Faltan datos"}, status=status.HTTP_400_BAD_REQUEST)

        # Verify OTP
        cache_key = f"reset_otp_{email}"
        stored_otp = cache.get(cache_key)

        if not stored_otp or stored_otp != otp:
             return Response({"error": "Código inválido o expirado"}, status=status.HTTP_400_BAD_REQUEST)

        # Change Password
        try:
            user = User.objects.get(email=email)
            user.set_password(new_password)
            user.save()
            
            # Invalidate OTP
            cache.delete(cache_key)
            
            return Response({"message": "Contraseña actualizada exitosamente"}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
             return Response({"error": "Usuario no encontrado"}, status=status.HTTP_400_BAD_REQUEST)
