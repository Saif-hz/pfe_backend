from rest_framework import serializers
from .models import Artist, Producer, CollaborationRequest, Notification
from django.conf import settings
import logging
import time

logger = logging.getLogger(__name__)

# Artist Serializer
class ArtistSerializer(serializers.ModelSerializer):
    profile_picture = serializers.SerializerMethodField()
    cover_photo = serializers.SerializerMethodField()
    genres = serializers.SerializerMethodField()
    talents = serializers.SerializerMethodField()
    profile_url = serializers.SerializerMethodField()
    user_type = serializers.SerializerMethodField()

    def get_profile_picture(self, obj):
        if obj.profile_picture:
            return obj.profile_picture.url
        return None

    def get_cover_photo(self, obj):
        if obj.cover_photo:
            return obj.cover_photo.url
        return None

    def get_genres(self, obj):
        if obj.genres:
            return [g.strip() for g in obj.genres.split(',') if g.strip()]
        return []

    def get_talents(self, obj):
        if obj.talents:
            return [t.strip() for t in obj.talents.split(',') if t.strip()]
        return []

    def get_profile_url(self, obj):
        return f"/profile/artist/{obj.id}/"

    def get_user_type(self, obj):
        return "artist"

    class Meta:
        model = Artist
        fields = [
            'id', 'username', 'nom', 'prenom', 'email', 'profile_picture',
            'cover_photo', 'bio', 'talents', 'genres', 'location', 'created_at',
            'profile_url', 'user_type', 'collaboration_count'
        ]
        extra_kwargs = {'password': {'write_only': True}}  # Hide password in API responses

# Producer Serializer
class ProducerSerializer(serializers.ModelSerializer):
    profile_picture = serializers.SerializerMethodField()
    cover_photo = serializers.SerializerMethodField()
    genres = serializers.SerializerMethodField()
    profile_url = serializers.SerializerMethodField()
    user_type = serializers.SerializerMethodField()

    def get_profile_picture(self, obj):
        if obj.profile_picture:
            return obj.profile_picture.url
        return None

    def get_cover_photo(self, obj):
        if obj.cover_photo:
            return obj.cover_photo.url
        return None

    def get_genres(self, obj):
        if obj.genres:
            return [g.strip() for g in obj.genres.split(',') if g.strip()]
        return []

    def get_profile_url(self, obj):
        return f"/profile/producer/{obj.id}/"

    def get_user_type(self, obj):
        return "producer"

    class Meta:
        model = Producer
        fields = [
            'id', 'username', 'nom', 'prenom', 'email', 'profile_picture',
            'cover_photo', 'bio', 'studio_name', 'website', 'genres',
            'location', 'created_at', 'profile_url', 'user_type', 'collaboration_count'
        ]
        extra_kwargs = {'password': {'write_only': True}}  # Hide password in API responses

# Collaboration Request Serializer
class CollaborationRequestSerializer(serializers.ModelSerializer):
    sender_details = serializers.SerializerMethodField()
    receiver_details = serializers.SerializerMethodField()
    sender_type = serializers.SerializerMethodField()
    receiver_type = serializers.SerializerMethodField()

    class Meta:
        model = CollaborationRequest
        fields = [
            'id', 'message', 'status', 'created_at', 'updated_at',
            'sender_type', 'receiver_type', 'sender_details', 'receiver_details'
        ]
        read_only_fields = ['id', 'status', 'created_at', 'updated_at']

    def get_sender_type(self, obj):
        return 'artist' if obj.sender_artist else 'producer'

    def get_receiver_type(self, obj):
        return 'artist' if obj.receiver_artist else 'producer'

    def get_sender_details(self, obj):
        sender = obj.sender_artist or obj.sender_producer
        if not sender:
            return None

        if obj.sender_artist:
            serializer = ArtistSerializer(sender)
        else:
            serializer = ProducerSerializer(sender)
        return serializer.data

    def get_receiver_details(self, obj):
        receiver = obj.receiver_artist or obj.receiver_producer
        if not receiver:
            return None

        if obj.receiver_artist:
            serializer = ArtistSerializer(receiver)
        else:
            serializer = ProducerSerializer(receiver)
        return serializer.data

class NotificationSerializer(serializers.ModelSerializer):
    sender = serializers.SerializerMethodField()
    recipient = serializers.SerializerMethodField()
    post = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ['id', 'recipient', 'sender', 'notification_type', 'message', 'post', 'read', 'created_at']

    def get_sender(self, obj):
        """Return sender information"""
        request = self.context.get('request')
        base_url = request.build_absolute_uri('/').rstrip('/') if request else ""

        sender = obj.sender
        if not sender:
            logger.warning(f"Notification {obj.id}: No sender found")
            return None

        logger.info(f"Notification {obj.id}: Sender is {sender.username} ({sender.id})")

        avatar_url = None
        if hasattr(sender, 'profile_picture') and sender.profile_picture:
            # Check if the profile picture actually exists
            if sender.profile_picture and hasattr(sender.profile_picture, 'url'):
                # Make sure we're using the full absolute URL
                avatar_url = request.build_absolute_uri(sender.profile_picture.url)
                logger.info(f"Notification {obj.id}: Found profile picture at {avatar_url}")
            else:
                logger.warning(f"Notification {obj.id}: Sender has profile_picture attribute but no URL")
        else:
            logger.warning(f"Notification {obj.id}: Sender has no profile_picture")

        result = {
            'id': sender.id,
            'username': sender.username,
            'role': 'artist' if obj.sender_artist else 'producer',
            'avatar': avatar_url
        }

        logger.info(f"Notification {obj.id}: Returning sender data: {result}")
        return result

    def get_recipient(self, obj):
        """Return recipient information"""
        request = self.context.get('request')
        base_url = request.build_absolute_uri('/').rstrip('/') if request else ""

        user = obj.user
        if not user:
            logger.warning(f"Notification {obj.id}: No recipient found")
            return None

        logger.info(f"Notification {obj.id}: Recipient is {user.username} ({user.id})")

        avatar_url = None
        if hasattr(user, 'profile_picture') and user.profile_picture:
            # Check if the profile picture actually exists
            if user.profile_picture and hasattr(user.profile_picture, 'url'):
                # Make sure we're using the full absolute URL
                avatar_url = request.build_absolute_uri(user.profile_picture.url)
                logger.info(f"Notification {obj.id}: Found recipient profile picture at {avatar_url}")
            else:
                logger.warning(f"Notification {obj.id}: Recipient has profile_picture attribute but no URL")
        else:
            logger.warning(f"Notification {obj.id}: Recipient has no profile_picture")

        result = {
            'id': user.id,
            'username': user.username,
            'role': 'artist' if obj.artist else 'producer',
            'avatar': avatar_url
        }

        logger.info(f"Notification {obj.id}: Returning recipient data: {result}")
        return result

    def get_post(self, obj):
        """Return post information if this is a post-related notification"""
        if not obj.post_id:
            return None

        from feed.models import Post  # Import here to avoid circular imports

        try:
            post = Post.objects.get(id=obj.post_id)

            request = self.context.get('request')
            base_url = request.build_absolute_uri('/').rstrip('/') if request else ""

            post_data = {
                'id': post.id,
                'content': post.content[:100] + ('...' if len(post.content) > 100 else '') if post.content else None,
            }

            # Add post image if available
            if post.image and hasattr(post.image, 'url'):
                post_data['image'] = request.build_absolute_uri(post.image.url)

            # Add post video if available
            if post.video and hasattr(post.video, 'url'):
                post_data['video'] = request.build_absolute_uri(post.video.url)

            return post_data
        except Post.DoesNotExist:
            logger.warning(f"Post {obj.post_id} referenced in notification {obj.id} does not exist")
            return {'id': obj.post_id, 'deleted': True}
        except Exception as e:
            logger.error(f"Error getting post data for notification: {str(e)}")
            return {'id': obj.post_id, 'error': True}
