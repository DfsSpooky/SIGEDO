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
        # El frontend espera un payload con una clave 'type' y 'message'.
        # Reconstruimos el payload aquí para que coincida con las expectativas del cliente.
        await self.send(text_data=json.dumps({
            'type': 'send_notification',
            'message': event['message']
        }))


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


from channels.db import database_sync_to_async

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        if not self.user.is_authenticated:
            await self.close()
            return

        await self.accept()

        self.conversation_groups = []
        conversations = await self.get_user_conversations()
        for conv in conversations:
            group_name = f'chat_{conv.id}'
            self.conversation_groups.append(group_name)
            await self.channel_layer.group_add(group_name, self.channel_name)

    async def disconnect(self, close_code):
        for group_name in self.conversation_groups:
            await self.channel_layer.group_discard(group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type')

        if message_type == 'chat.new_message':
            conversation_id = data.get('conversation_id')
            content = data.get('content')

            if not conversation_id or not content:
                return

            message = await self.create_chat_message(conversation_id, content)
            if not message:
                # No se pudo crear el mensaje (p. ej., usuario no es participante)
                return

            from .api.serializers import ChatMessageSerializer
            serializer = ChatMessageSerializer(message)

            await self.channel_layer.group_send(
                f'chat_{conversation_id}',
                {
                    'type': 'chat.broadcast_message',
                    'message': serializer.data
                }
            )

    async def chat_broadcast_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'new_message', # El cliente espera este tipo
            'message': event['message']
        }))

    @database_sync_to_async
    def get_user_conversations(self):
        from .models import ChatConversation
        return list(self.user.chat_conversations.all())

    @database_sync_to_async
    def create_chat_message(self, conversation_id, content):
        from .models import ChatConversation, ChatMessage
        try:
            conversation = ChatConversation.objects.get(id=conversation_id)
            if self.user not in conversation.participants.all():
                return None

            message = ChatMessage.objects.create(
                conversation=conversation,
                sender=self.user,
                content=content
            )
            message.read_by.add(self.user)
            return message
        except ChatConversation.DoesNotExist:
            return None
