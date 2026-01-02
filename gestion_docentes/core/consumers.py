import json
from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

User = get_user_model()

class NotificationConsumer(AsyncWebsocketConsumer):
    @database_sync_to_async
    def get_user_from_token(self, token):
        try:
            access_token = AccessToken(token)
            user_id = access_token['user_id']
            return User.objects.get(id=user_id)
        except (InvalidToken, TokenError, User.DoesNotExist):
            return None

    async def connect(self):
        self.user = self.scope["user"]
        
        # Try Token Auth if Anonymous (e.g. Mobile App)
        if not self.user.is_authenticated:
            query_string = self.scope.get('query_string', b'').decode()
            params = parse_qs(query_string)
            token = params.get('token', [None])[0]
            if token:
                self.user = await self.get_user_from_token(token)

        if not self.user or not self.user.is_authenticated:
            await self.close()
            return

        self.room_group_name = f"notifications_{self.user.id}"

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def send_notification(self, event):
        # El frontend espera un payload con una clave 'type' y 'message'.
        await self.send(
            text_data=json.dumps(
                {"type": "send_notification", "message": event["message"]}
            )
        )


class KioskConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        """
        Se llama cuando el websocket es conectado por un cliente.
        """
        self.room_group_name = "kiosk_group"

        # Unirse al grupo de la sala
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        await self.accept()
        print(f"WebSocket Kiosk client connected: {self.channel_name}")

    async def disconnect(self, close_code):
        """
        Se llama cuando el websocket se desconecta.
        """
        # Salir del grupo de la sala
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        print(f"WebSocket Kiosk client disconnected: {self.channel_name}")

    # Este método no se usará para recibir mensajes de los clientes,
    # ya que la comunicación es unidireccional desde el servidor.
    # async def receive(self, text_data):
    #     pass

    async def kiosk_update(self, event):
        """
        Recibe un mensaje del grupo de la sala y lo envía al cliente.
        Este es el "manejador de eventos" que será llamado desde la vista de Django.
        """
        message_data = event["data"]

        # Enviar el mensaje al WebSocket
        await self.send(
            text_data=json.dumps({"type": "kiosk.update", "data": message_data})
        )
        print(f"Sent message to {self.channel_name}: {message_data}")


class CalendarConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        if not self.user.is_authenticated:
            await self.close()
            return

        self.room_group_name = f"horario_{self.user.id}"

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def horario_update(self, event):
        """
        Envía un mensaje al cliente indicando que el horario ha sido actualizado.
        """
        await self.send(
            text_data=json.dumps(
                {
                    "type": "horario.update",
                    "message": event.get("message", "Tu horario ha sido actualizado."),
                }
            )
        )


class DashboardConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        # Solo permitir admin o staff
        if not self.user.is_authenticated or not self.user.is_staff:
            await self.close()
            return

        self.room_group_name = "dashboard_feed"
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def attendance_update(self, event):
        # El frontend espera { type: 'attendance.update', data: ... }
        await self.send(text_data=json.dumps({
            "type": "attendance.update",
            "data": event["data"]
        }))
