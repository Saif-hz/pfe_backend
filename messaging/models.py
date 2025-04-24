from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
import logging
from users.models import Artist, Producer
import os

logger = logging.getLogger(__name__)

# Helper function to determine the upload path for attachments
def get_attachment_path(instance, filename):
    # Create a directory structure based on the chat room ID
    room_id = instance.room.id if instance.room else 'no_room'
    return f'chat_attachments/room_{room_id}/{filename}'

class ChatRoomParticipant(models.Model):
    """
    Bridge model to allow both Artists and Producers to participate in chat rooms
    """
    chat_room = models.ForeignKey('ChatRoom', on_delete=models.CASCADE, related_name='participant_links')
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    participant = GenericForeignKey('content_type', 'object_id')

    class Meta:
        unique_together = ('chat_room', 'content_type', 'object_id')

    def __str__(self):
        return f"ChatRoomParticipant: {self.participant} in {self.chat_room}"

class ChatRoom(models.Model):
    name = models.CharField(max_length=128)
    # Use a reverse relationship from the ChatRoomParticipant model instead
    # of a direct ManyToManyField
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"ChatRoom: {self.name}"

    @property
    def participants(self):
        """
        Return all participants (Artist and Producer instances) for this chat room
        """
        participant_objects = []
        for link in self.participant_links.all():
            participant_objects.append(link.participant)
        return participant_objects

    def add_participant(self, user):
        """
        Add a participant (Artist or Producer) to this chat room
        """
        if isinstance(user, (Artist, Producer)):
            try:
                content_type = ContentType.objects.get_for_model(user)
                logger.info(f"Adding participant to chat room {self.id}: user={user.id}, type={content_type}")

                # Check if participant already exists
                exists = ChatRoomParticipant.objects.filter(
                    chat_room=self,
                    content_type=content_type,
                    object_id=user.id
                ).exists()

                if exists:
                    logger.info(f"Participant {user.id} already exists in chat room {self.id}")
                    return

                participant = ChatRoomParticipant.objects.create(
                    chat_room=self,
                    content_type=content_type,
                    object_id=user.id
                )
                logger.info(f"Added participant {user.username} (id={user.id}) to chat room {self.id}")
                return participant
            except Exception as e:
                logger.error(f"Error adding participant {user} to chat room {self.id}: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
                raise RuntimeError(f"Failed to add participant: {str(e)}")
        else:
            logger.error(f"Cannot add participant of type {type(user).__name__} to chat room {self.id}")
            logger.error(f"User details: {user}")
            raise TypeError(f"Expected Artist or Producer, got {type(user).__name__}")

    def has_participant(self, user):
        """
        Check if a user is a participant in this chat room
        """
        if isinstance(user, (Artist, Producer)):
            content_type = ContentType.objects.get_for_model(user)
            return ChatRoomParticipant.objects.filter(
                chat_room=self,
                content_type=content_type,
                object_id=user.id
            ).exists()
        return False

    @classmethod
    def get_or_create_chatroom(cls, user1, user2):
        """
        Get or create a chat room between two users, regardless of their model type
        (Artist or Producer)
        """
        # Check that both users are either Artist or Producer
        if not (isinstance(user1, (Artist, Producer)) and isinstance(user2, (Artist, Producer))):
            logger.error(f"Both users must be Artist or Producer instances")
            logger.error(f"User1: {type(user1)}, User2: {type(user2)}")
            logger.error(f"User1 ID: {getattr(user1, 'id', 'No ID')}, User2 ID: {getattr(user2, 'id', 'No ID')}")

            # Check user models specifically
            user1_model = user1.__class__.__name__ if user1 else 'None'
            user2_model = user2.__class__.__name__ if user2 else 'None'
            logger.error(f"User1 model: {user1_model}, User2 model: {user2_model}")

            raise TypeError(f"Both users must be Artist or Producer instances, got {user1_model} and {user2_model}")

        # First check if a chat room already exists with both users
        try:
            # Get content types for both users
            user1_content_type = ContentType.objects.get_for_model(user1)
            user2_content_type = ContentType.objects.get_for_model(user2)

            logger.info(f"Finding chat rooms for user1={user1.id} (type={user1_content_type}) and user2={user2.id} (type={user2_content_type})")

            # Find chat rooms that have user1 as a participant
            user1_rooms = set(ChatRoomParticipant.objects.filter(
                content_type=user1_content_type,
                object_id=user1.id
            ).values_list('chat_room_id', flat=True))

            logger.info(f"Found {len(user1_rooms)} rooms for user1: {user1_rooms}")

            # Find chat rooms that have user2 as a participant
            user2_rooms = set(ChatRoomParticipant.objects.filter(
                content_type=user2_content_type,
                object_id=user2.id
            ).values_list('chat_room_id', flat=True))

            logger.info(f"Found {len(user2_rooms)} rooms for user2: {user2_rooms}")

            # Get the intersection of rooms
            common_rooms = user1_rooms.intersection(user2_rooms)
            logger.info(f"Found {len(common_rooms)} common rooms: {common_rooms}")

            if common_rooms:
                # Return the first common room
                room_id = list(common_rooms)[0]
                room = ChatRoom.objects.get(id=room_id)
                logger.info(f"Found existing chat room: {room.id} for users {user1.id} and {user2.id}")
                return room, False
        except Exception as e:
            logger.error(f"Error finding existing chat room: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())

        # No common room found, create a new one
        try:
            # Generate a unique name based on user IDs
            room_name = f"chat_{min(user1.id, user2.id)}_{max(user1.id, user2.id)}"
            logger.info(f"Creating new room with name: {room_name}")

            # Create the room
            room = ChatRoom.objects.create(name=room_name)
            logger.info(f"Room created with id: {room.id}")

            # Add both users as participants
            try:
                room.add_participant(user1)
                logger.info(f"Added user1 (id={user1.id}) as participant")
            except Exception as e:
                logger.error(f"Error adding user1 as participant: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
                raise

            try:
                room.add_participant(user2)
                logger.info(f"Added user2 (id={user2.id}) as participant")
            except Exception as e:
                logger.error(f"Error adding user2 as participant: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
                raise

            logger.info(f"Created new chat room: {room.id} for users {user1.id} and {user2.id}")
            return room, True
        except Exception as e:
            logger.error(f"Error creating chat room: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            raise


class MessageReadStatus(models.Model):
    """
    Model to track read status of messages by each participant
    """
    message = models.ForeignKey('Message', on_delete=models.CASCADE, related_name='read_statuses')
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    reader = GenericForeignKey('content_type', 'object_id')
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('message', 'content_type', 'object_id')

    def __str__(self):
        return f"Read status: {self.message.id} by {self.reader}"


class Message(models.Model):
    ATTACHMENT_TYPE_CHOICES = (
        ('image', 'Image'),
        ('audio', 'Audio'),
        ('video', 'Video'),
        ('document', 'Document'),
        ('other', 'Other'),
    )

    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages', null=True, blank=True)
    # Use a ContentType for the sender as well
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    sender = GenericForeignKey('content_type', 'object_id')
    content = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)  # Kept for backward compatibility

    # File attachment fields
    file_attachment = models.FileField(upload_to=get_attachment_path, null=True, blank=True)
    file_type = models.CharField(max_length=50, choices=ATTACHMENT_TYPE_CHOICES, null=True, blank=True)
    file_name = models.CharField(max_length=255, null=True, blank=True)
    file_size = models.IntegerField(null=True, blank=True)  # Size in bytes

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"Message from {self.sender.username} at {self.timestamp}"

    def save(self, *args, **kwargs):
        # If this is a new message (no ID yet), set file metadata
        if self.file_attachment and not self.id:
            if not self.file_name:
                self.file_name = os.path.basename(self.file_attachment.name)
            if not self.file_size and hasattr(self.file_attachment, 'size'):
                self.file_size = self.file_attachment.size

            # Try to determine file type from extension if not provided
            if not self.file_type:
                ext = os.path.splitext(self.file_name)[1].lower()
                if ext in ['.jpg', '.jpeg', '.png', '.gif']:
                    self.file_type = 'image'
                elif ext in ['.mp3', '.wav', '.ogg']:
                    self.file_type = 'audio'
                elif ext in ['.mp4', '.mov', '.avi']:
                    self.file_type = 'video'
                elif ext in ['.pdf', '.doc', '.docx', '.txt', '.xlsx']:
                    self.file_type = 'document'
                else:
                    self.file_type = 'other'

        super().save(*args, **kwargs)

        # Create read status entries for all participants in the room
        # (except the sender)
        if self.room:
            sender_content_type = ContentType.objects.get_for_model(self.sender)
            for participant_link in self.room.participant_links.all():
                # Skip the sender
                if (participant_link.content_type == sender_content_type and
                    participant_link.object_id == self.sender.id):
                    continue

                # Create read status for this participant
                MessageReadStatus.objects.get_or_create(
                    message=self,
                    content_type=participant_link.content_type,
                    object_id=participant_link.object_id
                )


# These models seem unused, consider removing them if not needed
class Vocal(models.Model):
    content = models.TextField()


class Vocale(models.Model):
    content = models.TextField()
# Create your models here.
