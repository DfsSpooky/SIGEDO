import json
from channels.generic.websocket import AsyncWebsocketConsumer

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        if not self.user.is_authenticated:
            await self.close()
            return

        self.room_group_name = f'notifications_{self.user.id}'

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def send_notification(self, event):
        message = event['message']
        await self.send(text_data=json.dumps(message))


class KioskConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        """
        Se llama cuando el websocket es conectado por un cliente.
        """
        self.room_group_name = 'kiosk_group'

        # Unirse al grupo de la sala
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()
        print(f"WebSocket Kiosk client connected: {self.channel_name}")

    async def disconnect(self, close_code):
        """
        Se llama cuando el websocket se desconecta.
        """
        # Salir del grupo de la sala
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
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
        message_data = event['data']

        # Enviar el mensaje al WebSocket
        await self.send(text_data=json.dumps({
            'type': 'kiosk.update',
            'data': message_data
        }))
        print(f"Sent message to {self.channel_name}: {message_data}")
