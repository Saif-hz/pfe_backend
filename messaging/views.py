from django.shortcuts import render, get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from .models import ChatRoom, Message, ChatRoomParticipant, MessageReadStatus
from .serializers import ChatRoomSerializer, MessageSerializer
from django.contrib.auth import get_user_model
from django.db.models import Q
from users.models import Artist, Producer
from users.jwt_auth import CustomJWTAuthentication
import logging
from django.contrib.contenttypes.models import ContentType
import traceback
from django.utils import timezone

User = get_user_model()
logger = logging.getLogger(__name__)

class ChatRoomListCreateView(generics.ListCreateAPIView):
    """
    List all chat rooms or create a new one
    """
    serializer_class = ChatRoomSerializer
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [CustomJWTAuthentication]

    def get_serializer_context(self):
        """
        Extra context provided to the serializer class.
        """
        context = super().get_serializer_context()
        # Ensure request is included in the context
        context['request'] = self.request
        return context

    def get_queryset(self):
        # Only show chat rooms that the user is part of
        user = self.request.user
        logger.info(f"Getting chat rooms for user: {user}, type: {type(user)}")

        # Get content type for the user
        content_type = ContentType.objects.get_for_model(user)

        # Find all chat rooms where this user is a participant
        participant_rooms = ChatRoomParticipant.objects.filter(
            content_type=content_type,
            object_id=user.id
        ).values_list('chat_room_id', flat=True)

        return ChatRoom.objects.filter(id__in=participant_rooms)

    def perform_create(self, serializer):
        logger.info(f"Creating chat room, user: {self.request.user}, user type: {type(self.request.user)}")
        chat_room = serializer.save()

        # Add current user as participant
        chat_room.add_participant(self.request.user)

        # Add other participants if provided
        participants = self.request.data.get('participants', [])
        logger.info(f"Adding participants: {participants}")
        for user_id in participants:
            try:
                # Try to find the user in both Artist and Producer models
                user = None
                try:
                    user_id = int(user_id)
                    if user_id >= 1000000:  # Producer ID range
                        user = Producer.objects.get(id=user_id)
                        logger.info(f"Found producer: {user.username}")
                    else:
                        user = Artist.objects.get(id=user_id)
                        logger.info(f"Found artist: {user.username}")
                except (ValueError, Artist.DoesNotExist, Producer.DoesNotExist) as e:
                    logger.error(f"Error finding user {user_id}: {str(e)}")

                if user:
                    chat_room.add_participant(user)
                    logger.info(f"Added participant: {user.username}")
                else:
                    logger.warning(f"User not found with ID: {user_id}")
            except Exception as e:
                logger.error(f"Error adding participant {user_id}: {str(e)}")

    def post(self, request, *args, **kwargs):
        """
        Custom POST method to handle chat room creation
        """
        logger.info(f"POST request to create chat room: {request.data}")
        logger.info(f"Request headers: {request.headers}")
        logger.info(f"Request user: {request.user}, authenticated: {request.user.is_authenticated}")

        try:
            # Extract the participant_id from the request
            participant_id = request.data.get('participant_id')

            if not participant_id:
                logger.error("No participant_id provided for chat room creation")
                return Response(
                    {"error": "participant_id is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Find the participant based on ID
            logger.info(f"Looking for participant with ID: {participant_id}")
            participant = None

            try:
                participant_id = int(participant_id)
                if participant_id >= 1000000:  # Producer ID range
                    participant = Producer.objects.get(id=participant_id)
                    logger.info(f"Found producer participant: {participant.username}")
                else:
                    participant = Artist.objects.get(id=participant_id)
                    logger.info(f"Found artist participant: {participant.username}")
            except (ValueError, Artist.DoesNotExist, Producer.DoesNotExist) as e:
                logger.error(f"Error finding participant: {str(e)}")
                return Response(
                    {"error": f"Participant not found with ID: {participant_id}"},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Get or create a chat room
            current_user = request.user
            logger.info(f"Current user: {current_user.username} ({type(current_user)})")

            try:
                room, created = ChatRoom.get_or_create_chatroom(current_user, participant)
                logger.info(f"Chat room {'created' if created else 'found'}: {room.id}")

                # Return the room data
                serializer = self.get_serializer(room)

                status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
                return Response(serializer.data, status=status_code)
            except Exception as e:
                logger.error(f"Error in get_or_create_chatroom: {str(e)}")
                logger.error(traceback.format_exc())
                return Response(
                    {"error": f"Failed to create chat room: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        except Exception as e:
            logger.error(f"Error creating chat room: {str(e)}")
            logger.error(traceback.format_exc())
            return Response(
                {"error": f"Failed to create chat room: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ChatRoomDetailView(generics.RetrieveAPIView):
    """
    Retrieve a chat room
    """
    serializer_class = ChatRoomSerializer
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [CustomJWTAuthentication]

    def get_serializer_context(self):
        """
        Extra context provided to the serializer class.
        """
        context = super().get_serializer_context()
        # Ensure request is included in the context
        context['request'] = self.request
        return context

    def get_queryset(self):
        user = self.request.user
        content_type = ContentType.objects.get_for_model(user)

        # Find all chat rooms where this user is a participant
        participant_rooms = ChatRoomParticipant.objects.filter(
            content_type=content_type,
            object_id=user.id
        ).values_list('chat_room_id', flat=True)

        return ChatRoom.objects.filter(id__in=participant_rooms)


class ChatMessageListView(generics.ListCreateAPIView):
    """
    List all messages for a room or create a new one
    """
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [CustomJWTAuthentication]
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get_serializer_context(self):
        """
        Extra context provided to the serializer class.
        """
        context = super().get_serializer_context()
        # Ensure request is included in the context
        context['request'] = self.request
        return context

    def get_queryset(self):
        room_id = self.kwargs.get('room_id')
        user = self.request.user

        try:
            # Get the chat room
            room = ChatRoom.objects.get(id=room_id)

            # Verify the user is a participant of the room
            content_type = ContentType.objects.get_for_model(user)
            is_participant = ChatRoomParticipant.objects.filter(
                chat_room=room,
                content_type=content_type,
                object_id=user.id
            ).exists()

            if is_participant:
                # Automatically mark messages as read when fetching them
                messages = Message.objects.filter(room=room)

                # Mark messages from other users as read
                for message in messages:
                    if message.sender != user:
                        self.mark_message_as_read(message, user)

                return messages
            return Message.objects.none()
        except ChatRoom.DoesNotExist:
            return Message.objects.none()

    def perform_create(self, serializer):
        room_id = self.kwargs.get('room_id')
        user = self.request.user

        try:
            # Get the chat room
            room = ChatRoom.objects.get(id=room_id)

            # Verify the user is a participant of the room
            content_type = ContentType.objects.get_for_model(user)
            is_participant = ChatRoomParticipant.objects.filter(
                chat_room=room,
                content_type=content_type,
                object_id=user.id
            ).exists()

            if is_participant:
                # Create a content_type and object_id for the sender
                content_type = ContentType.objects.get_for_model(user)

                # Handle file and content
                file_attachment = self.request.data.get('file_attachment', None)
                content = self.request.data.get('content', '')

                # Validate that there's either file or content
                if not file_attachment and not content:
                    raise ValueError("Either file_attachment or content must be provided")

                # Create the message
                serializer.save(
                    content_type=content_type,
                    object_id=user.id,
                    room=room,
                    file_attachment=file_attachment
                )
        except ChatRoom.DoesNotExist:
            pass
        except ValueError as e:
            logger.error(f"Error creating message: {str(e)}")
            raise

    def mark_message_as_read(self, message, user):
        # Get content type for the user
        content_type = ContentType.objects.get_for_model(user)

        # Get or create the read status
        read_status, created = MessageReadStatus.objects.get_or_create(
            message=message,
            content_type=content_type,
            object_id=user.id
        )

        # Update the read status if it's not already read
        if not read_status.is_read:
            read_status.is_read = True
            read_status.read_at = timezone.now()
            read_status.save()

            # Also update the legacy is_read field if all participants have read the message
            if all(status.is_read for status in message.read_statuses.all()):
                message.is_read = True
                message.save(update_fields=['is_read'])


class MarkMessagesAsReadView(APIView):
    """
    Mark messages as read for the current user
    """
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [CustomJWTAuthentication]

    def post(self, request, room_id=None, message_id=None):
        user = request.user
        content_type = ContentType.objects.get_for_model(user)

        # Check if the room exists and user is a participant
        try:
            room = ChatRoom.objects.get(id=room_id)
            is_participant = ChatRoomParticipant.objects.filter(
                chat_room=room,
                content_type=content_type,
                object_id=user.id
            ).exists()

            if not is_participant:
                return Response(
                    {"error": "You are not a participant in this chat room"},
                    status=status.HTTP_403_FORBIDDEN
                )

            # If message_id is provided, mark only that message as read
            if message_id:
                try:
                    message = Message.objects.get(id=message_id, room=room)

                    # Don't mark your own messages as read
                    if message.sender == user:
                        return Response(
                            {"error": "Cannot mark your own message as read"},
                            status=status.HTTP_400_BAD_REQUEST
                        )

                    # Update or create read status
                    read_status, created = MessageReadStatus.objects.get_or_create(
                        message=message,
                        content_type=content_type,
                        object_id=user.id
                    )

                    if not read_status.is_read:
                        read_status.is_read = True
                        read_status.read_at = timezone.now()
                        read_status.save()

                    return Response({"success": True})

                except Message.DoesNotExist:
                    return Response(
                        {"error": "Message not found"},
                        status=status.HTTP_404_NOT_FOUND
                    )
            else:
                # Mark all unread messages in the room as read
                messages = Message.objects.filter(room=room).exclude(
                    # Exclude messages sent by the current user
                    content_type=content_type,
                    object_id=user.id
                )

                # Get all unread messages
                unread_message_ids = MessageReadStatus.objects.filter(
                    message__in=messages,
                    content_type=content_type,
                    object_id=user.id,
                    is_read=False
                ).values_list('message_id', flat=True)

                # Also check for messages without read status
                for message in messages:
                    read_status_exists = MessageReadStatus.objects.filter(
                        message=message,
                        content_type=content_type,
                        object_id=user.id
                    ).exists()

                    if not read_status_exists:
                        MessageReadStatus.objects.create(
                            message=message,
                            content_type=content_type,
                            object_id=user.id,
                            is_read=True,
                            read_at=timezone.now()
                        )

                # Update all unread statuses
                MessageReadStatus.objects.filter(
                    message_id__in=unread_message_ids,
                    content_type=content_type,
                    object_id=user.id
                ).update(is_read=True, read_at=timezone.now())

                return Response({"success": True, "marked_read_count": len(unread_message_ids)})

        except ChatRoom.DoesNotExist:
            return Response(
                {"error": "Chat room not found"},
                status=status.HTTP_404_NOT_FOUND
            )


class UserChatListView(APIView):
    """
    List all users the current user has chatted with
    """
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [CustomJWTAuthentication]

    def get(self, request):
        user = request.user
        logger.info(f"Getting chats for user: {user}, type: {type(user)}")

        # Get content type for the user
        content_type = ContentType.objects.get_for_model(user)

        # Find all chat rooms where this user is a participant
        participant_rooms = ChatRoomParticipant.objects.filter(
            content_type=content_type,
            object_id=user.id
        ).values_list('chat_room_id', flat=True)

        chat_rooms = ChatRoom.objects.filter(id__in=participant_rooms)
        logger.info(f"Found {chat_rooms.count()} chat rooms")

        # Get unique participants excluding the current user
        user_data = []
        for room in chat_rooms:
            # Get all participants in this room
            room_participants = ChatRoomParticipant.objects.filter(chat_room=room)

            for participant_link in room_participants:
                # Skip the current user
                if participant_link.content_type == content_type and participant_link.object_id == user.id:
                    continue

                participant = participant_link.participant
                logger.info(f"Processing participant: {participant.username}, type: {type(participant)}")

                # Get the latest message for the room
                latest_message = Message.objects.filter(room=room).order_by('-timestamp').first()
                latest_content = latest_message.content if latest_message else ""
                latest_time = latest_message.timestamp if latest_message else None

                # Check if this participant is already in user_data
                existing = next((item for item in user_data if item['id'] == participant.id), None)
                if not existing:
                    user_data.append({
                        'id': participant.id,
                        'username': participant.username,
                        'room_id': room.id,
                        'latest_message': latest_content,
                        'timestamp': latest_time,
                    })

        # Sort by latest message timestamp - handle None and type conversion
        def sort_key(x):
            timestamp = x.get('timestamp')
            if timestamp is None:
                return ""
            # Convert datetime to string if it's a datetime object
            return timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp)

        user_data.sort(key=sort_key, reverse=True)
        logger.info(f"Returning {len(user_data)} chat contacts")

        return Response(user_data)
