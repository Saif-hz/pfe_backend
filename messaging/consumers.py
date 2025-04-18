import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Message, ChatRoom, ChatRoomParticipant, MessageReadStatus
from django.contrib.auth.models import AnonymousUser
from urllib.parse import parse_qs
import jwt
from django.conf import settings
from users.models import Artist, Producer
import logging
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

logger = logging.getLogger(__name__)

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'chat_{self.room_name}'

        # Get query parameters
        query_string = self.scope.get('query_string', b'').decode()
        query_params = parse_qs(query_string)

        # Try to authenticate with token from query params
        token = query_params.get('token', [''])[0]
        user = await self.get_user_from_token(token)

        if user is None or isinstance(user, AnonymousUser):
            # Reject the connection if no valid token
            logger.error(f"WebSocket connection rejected: Invalid token")
            await self.close()
            return

        # Store user in scope
        self.scope['user'] = user
        logger.info(f"WebSocket connected: user={user.username}, type={type(user)}")

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # Receive message from WebSocket
    async def receive(self, text_data):
        data = json.loads(text_data)
        message_content = data.get('message', '')
        message_type = data.get('type', 'text')
        username = self.scope['user'].username

        # Check if this is a message about a file upload notification
        if message_type == 'file_notification':
            file_info = data.get('file_info', {})
            message_id = file_info.get('message_id')

            # Validate file info contains necessary data
            if not message_id:
                await self.send(text_data=json.dumps({
                    'error': 'File notification missing message_id',
                }))
                return

            # Get file information from the database message
            file_data = await self.get_file_data(message_id)

            if file_data:
                # Send notification about the file to the room
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'file_message',
                        'message_id': message_id,
                        'username': username,
                        'file_data': file_data,
                    }
                )
            else:
                await self.send(text_data=json.dumps({
                    'error': 'File not found',
                }))
        else:
            # This is a regular text message
            # Save message to database
            message_obj = await self.save_message(username, message_content)

            # Send message to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message_content,
                    'username': username,
                    'message_id': message_obj.id if message_obj else None,
                }
            )

    # Receive message from room group
    async def chat_message(self, event):
        message = event['message']
        username = event['username']
        message_id = event.get('message_id')

        # Send message to WebSocket
        response = {
            'message': message,
            'username': username,
            'type': 'text'
        }

        if message_id:
            response['message_id'] = message_id

        await self.send(text_data=json.dumps(response))

    # Handle file messages
    async def file_message(self, event):
        username = event['username']
        message_id = event['message_id']
        file_data = event['file_data']

        # Send file info to WebSocket
        await self.send(text_data=json.dumps({
            'username': username,
            'message_id': message_id,
            'type': 'file',
            'file_data': file_data
        }))

    @database_sync_to_async
    def save_message(self, username, message):
        try:
            user = self.scope['user']
            room, _ = ChatRoom.objects.get_or_create(name=self.room_name)

            # Get content type for the user
            content_type = ContentType.objects.get_for_model(user)

            # Ensure user is a participant in the room by checking ChatRoomParticipant
            participant_exists = ChatRoomParticipant.objects.filter(
                chat_room=room,
                content_type=content_type,
                object_id=user.id
            ).exists()

            if not participant_exists:
                # Add user as participant using the new method
                room.add_participant(user)
                logger.info(f"Added user {user.username} to chat room {room.name}")

            # Create the message using ContentType
            new_message = Message.objects.create(
                room=room,
                content_type=content_type,
                object_id=user.id,
                content=message
            )
            logger.info(f"Saved message: {new_message.id} from {user.username}")

            # Create read statuses for all other participants
            for participant_link in room.participant_links.all():
                # Skip the sender
                if (participant_link.content_type == content_type and
                    participant_link.object_id == user.id):
                    continue

                # Create read status for this participant
                MessageReadStatus.objects.create(
                    message=new_message,
                    content_type=participant_link.content_type,
                    object_id=participant_link.object_id,
                    is_read=False
                )

            return new_message
        except Exception as e:
            logger.error(f"Error saving message: {e}")
            return None

    @database_sync_to_async
    def get_file_data(self, message_id):
        try:
            # Get the message
            message = Message.objects.get(id=message_id)

            # Check if message has a file attachment
            if not message.file_attachment:
                return None

            # Return file data
            return {
                'url': message.file_attachment.url,
                'name': message.file_name,
                'type': message.file_type,
                'size': message.file_size,
            }
        except Message.DoesNotExist:
            logger.error(f"Message not found: {message_id}")
            return None
        except Exception as e:
            logger.error(f"Error getting file data: {e}")
            return None

    @database_sync_to_async
    def get_user_from_token(self, token):
        if not token:
            logger.warning("No token provided for WebSocket authentication")
            return AnonymousUser()

        try:
            # Decode the token
            decoded_token = jwt.decode(
                token,
                settings.SIMPLE_JWT['SIGNING_KEY'],
                algorithms=[settings.SIMPLE_JWT['ALGORITHM']]
            )

            # Extract user info
            user_id = decoded_token.get('user_id')
            user_type = decoded_token.get('user_type', '')

            logger.info(f"WebSocket auth: Token contains user_id={user_id}, user_type={user_type}")

            if not user_id:
                logger.error("Token missing user_id claim")
                return AnonymousUser()

            # Find the user based on type
            user = None
            if user_type == 'artist':
                try:
                    user = Artist.objects.get(id=user_id)
                    logger.info(f"Found Artist with id={user_id}")
                except Artist.DoesNotExist:
                    logger.warning(f"Artist with id={user_id} not found")
            elif user_type == 'producer':
                try:
                    user = Producer.objects.get(id=user_id)
                    logger.info(f"Found Producer with id={user_id}")
                except Producer.DoesNotExist:
                    logger.warning(f"Producer with id={user_id} not found")
            else:
                # Try both models if user_type not specified
                try:
                    # Check ID range to determine type
                    if user_id >= 1000000:
                        user = Producer.objects.get(id=user_id)
                        logger.info(f"Found Producer with id={user_id} based on ID range")
                    else:
                        user = Artist.objects.get(id=user_id)
                        logger.info(f"Found Artist with id={user_id} based on ID range")
                except (Artist.DoesNotExist, Producer.DoesNotExist):
                    logger.warning(f"User not found with id={user_id}")

            if user:
                # Add authentication flag for compatibility
                user.is_authenticated = True
                return user

            logger.error(f"No user found for token with user_id={user_id}, user_type={user_type}")
            return AnonymousUser()

        except Exception as e:
            logger.error(f"Invalid token: {e}")
            return AnonymousUser()