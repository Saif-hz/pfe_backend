from rest_framework import serializers
from .models import ChatRoom, Message, ChatRoomParticipant, MessageReadStatus
from users.models import Artist, Producer
import logging
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

logger = logging.getLogger(__name__)

class UserSerializer(serializers.ModelSerializer):
    """
    Generic serializer for both Artist and Producer models
    """
    class Meta:
        model = None  # This will be set dynamically
        fields = ['id', 'username']

    def to_representation(self, instance):
        # Set the model dynamically based on the instance type
        if isinstance(instance, Artist):
            self.Meta.model = Artist
        elif isinstance(instance, Producer):
            self.Meta.model = Producer
        else:
            logger.warning(f"Unknown user type: {type(instance)}")

        return super().to_representation(instance)


class MessageReadStatusSerializer(serializers.ModelSerializer):
    reader_username = serializers.SerializerMethodField()
    reader_id = serializers.SerializerMethodField()
    reader_type = serializers.SerializerMethodField()

    class Meta:
        model = MessageReadStatus
        fields = ['id', 'reader_id', 'reader_username', 'reader_type', 'is_read', 'read_at']

    def get_reader_id(self, obj):
        if hasattr(obj.reader, 'id'):
            return obj.reader.id
        return None

    def get_reader_username(self, obj):
        if hasattr(obj.reader, 'username'):
            return obj.reader.username
        return "Unknown"

    def get_reader_type(self, obj):
        if isinstance(obj.reader, Artist):
            return "artist"
        elif isinstance(obj.reader, Producer):
            return "producer"
        return "unknown"


class MessageSerializer(serializers.ModelSerializer):
    sender_username = serializers.SerializerMethodField()
    sender_type = serializers.SerializerMethodField()
    sender = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()
    read_status = serializers.SerializerMethodField()
    is_current_user = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            'id', 'sender', 'sender_username', 'sender_type',
            'content', 'timestamp', 'is_read', 'is_current_user',
            'file_attachment', 'file_url', 'file_type',
            'file_name', 'file_size', 'read_status'
        ]
        read_only_fields = ['sender', 'timestamp', 'file_url', 'read_status', 'is_current_user']

    def get_sender(self, obj):
        """
        Return the sender's ID, formatted according to frontend convention:
        - For messages sent by the current user, return the actual user ID
        - For messages received from others, return -1
        This helps the frontend correctly position messages in the UI.
        """
        request = self.context.get('request')
        if not request or not hasattr(request, 'user') or not hasattr(obj.sender, 'id'):
            return None

        current_user = request.user
        if obj.sender.id == current_user.id:
            # Current user is the sender, return actual ID
            return obj.sender.id
        else:
            # Message is from another user, return -1 as expected by frontend
            return -1

    def get_sender_username(self, obj):
        if hasattr(obj.sender, 'username'):
            return obj.sender.username
        return "Unknown"

    def get_sender_type(self, obj):
        if isinstance(obj.sender, Artist):
            return "artist"
        elif isinstance(obj.sender, Producer):
            return "producer"
        return "unknown"

    def get_is_current_user(self, obj):
        """
        Determine if the current user is the sender of this message
        """
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            current_user = request.user
            # Check if the sender's ID matches the current user's ID
            if hasattr(obj.sender, 'id') and hasattr(current_user, 'id'):
                return obj.sender.id == current_user.id
        return False

    def get_file_url(self, obj):
        if obj.file_attachment and hasattr(obj.file_attachment, 'url'):
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file_attachment.url)
            return obj.file_attachment.url
        return None

    def get_read_status(self, obj):
        read_statuses = obj.read_statuses.all()
        if read_statuses:
            return MessageReadStatusSerializer(read_statuses, many=True).data
        return []

    def create(self, validated_data):
        # Set is_read to False for new messages
        validated_data['is_read'] = False
        return super().create(validated_data)


class ChatRoomSerializer(serializers.ModelSerializer):
    participants = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = ChatRoom
        fields = ['id', 'name', 'participants', 'created_at', 'last_message', 'unread_count']

    def get_participants(self, obj):
        participants_data = []

        # Get all participant links for this chat room
        participant_links = ChatRoomParticipant.objects.filter(chat_room=obj)

        for link in participant_links:
            participant = link.participant
            serializer = UserSerializer()
            # Set model dynamically based on instance type
            serializer.Meta.model = participant.__class__
            participants_data.append(serializer.to_representation(participant))

        return participants_data

    def get_last_message(self, obj):
        last_message = obj.messages.order_by('-timestamp').first()
        if last_message:
            # Ensure the request context is passed to properly identify the sender
            return MessageSerializer(last_message, context=self.context).data
        return None

    def get_unread_count(self, obj):
        # Get the current user from the context
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            user = request.user

            # Get content type for the user
            content_type = ContentType.objects.get_for_model(user)

            # Count unread messages for this user in this room
            unread_count = MessageReadStatus.objects.filter(
                message__room=obj,
                content_type=content_type,
                object_id=user.id,
                is_read=False
            ).count()

            return unread_count
        return 0