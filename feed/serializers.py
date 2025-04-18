from rest_framework import serializers
from django.conf import settings
import logging
from .models import Post, Comment, Like
from users.models import Artist, Producer
import time
logger = logging.getLogger(__name__)

class PostSerializer(serializers.ModelSerializer):
    comments_count = serializers.SerializerMethodField()
    likes_count = serializers.SerializerMethodField()
    liked = serializers.SerializerMethodField()  # Add this field to indicate if current user liked the post
    user = serializers.SerializerMethodField()  # Return a user object
    image = serializers.SerializerMethodField()
    video = serializers.SerializerMethodField() 
    audio = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = ["id", "user", "content", "image", "video", "audio", "created_at", "comments_count", "likes_count", "liked"]

    def get_comments_count(self, obj):
        return obj.comments.count()

    def get_likes_count(self, obj):
        return obj.likes.count()

    def get_liked(self, obj):
        """Check if the current user has liked this post"""
        request = self.context.get("request")
        
        # If no request or not authenticated, return False
        if not request or not request.user or not request.user.is_authenticated:
            return False
            
        user = request.user
        user_id = user.id
        
        # Determine user type
        user_type = None
        if hasattr(request.auth, 'payload') and 'user_type' in request.auth.payload:
            user_type = request.auth.payload.get('user_type')
        else:
            # Fallback to database check
            if Producer.objects.filter(id=user_id).exists():
                user_type = "producer"
            elif Artist.objects.filter(id=user_id).exists():
                user_type = "artist"
                
        # If we couldn't determine user type, user can't have liked the post
        if not user_type:
            return False
            
        # Check if this user has liked this post
        return Like.objects.filter(
            post=obj,
            user_id=user_id,
            user_type=user_type
        ).exists()

    def get_user(self, obj):
        """Return a user object with name, avatar, and role"""
        request = self.context.get("request")  # Ensure absolute URL
        base_url = request.build_absolute_uri('/').rstrip('/') if request else ""

        logger.info(f"Getting user info for post {obj.id} - User ID: {obj.user_id}, User Type: {obj.user_type}")
        
        # Get authenticated user if available
        auth_user = getattr(request, 'user', None)
        auth_user_id = getattr(auth_user, 'id', None)
        auth_username = getattr(auth_user, 'username', None)
        
        # Log authentication information
        if auth_user and auth_user.is_authenticated:
            logger.info(f"Auth user: ID={auth_user_id}, username={auth_username}")
            
            # If this post belongs to the authenticated user, use their info directly
            if auth_user_id == obj.user_id:
                logger.info(f"Post belongs to authenticated user: {auth_username}")
                avatar_url = None
                
                # Get profile picture if available
                if hasattr(auth_user, 'profile_picture') and auth_user.profile_picture:
                    avatar_url = f"{base_url}{auth_user.profile_picture.url}"
                    # Add timestamp to prevent caching
                    avatar_url = f"{avatar_url}?_={int(time.time())}"
                    
                return {
                    "name": auth_username,
                    "avatar": avatar_url,
                    "role": obj.user_type,
                }
        
        # If not the authenticated user or not authenticated, fetch from database
        if obj.user_type == "artist":
            try:
                # Use get() instead of filter().first() to ensure we get the exact user
                artist = Artist.objects.get(id=obj.user_id)
                avatar_url = None
                if artist.profile_picture:
                    avatar_url = f"{base_url}{artist.profile_picture.url}"
                    # Add timestamp to prevent caching
                    avatar_url = f"{avatar_url}?_={int(time.time())}"
                    logger.debug(f"Artist avatar URL: {avatar_url}")
                
                logger.info(f"Found artist: {artist.username} (ID: {artist.id})")
                return {
                    "name": artist.username,
                    "avatar": avatar_url,
                    "role": "artist",
                }
            except Artist.DoesNotExist:
                logger.warning(f"Artist with ID {obj.user_id} not found")
        elif obj.user_type == "producer":
            try:
                # Use get() instead of filter().first() to ensure we get the exact user
                producer = Producer.objects.get(id=obj.user_id)
                avatar_url = None
                if producer.profile_picture:
                    avatar_url = f"{base_url}{producer.profile_picture.url}"
                    # Add timestamp to prevent caching
                    avatar_url = f"{avatar_url}?_={int(time.time())}"
                    logger.debug(f"Producer avatar URL: {avatar_url}")
                
                logger.info(f"Found producer: {producer.username} (ID: {producer.id})")
                return {
                    "name": producer.username,
                    "avatar": avatar_url,
                    "role": "producer",
                }
            except Producer.DoesNotExist:
                logger.warning(f"Producer with ID {obj.user_id} not found")
        
        logger.warning(f"No user found for post {obj.id} - User ID: {obj.user_id}, User Type: {obj.user_type}")
        return {"name": "Unknown", "avatar": None, "role": "user"}


    def get_image(self, obj):
        request = self.context.get("request")
        if obj.image:
            base_url = request.build_absolute_uri('/').rstrip('/') if request else ""
            image_url = f"{base_url}{obj.image.url}"
            logger.debug(f"Post image URL: {image_url}")
            return image_url
        return None
    

    def get_video(self, obj):
        """Ensure correct absolute video URL without duplicates"""
        request = self.context.get("request")
    
        if obj.video:
            base_url = request.build_absolute_uri('/').rstrip('/') if request else ""
            video_url = f"{base_url}{obj.video.url}"
            logger.debug(f"Post video URL: {video_url}")
            return video_url
    
        return None

    def get_audio(self, obj):
        """Ensure correct absolute audio URL without duplicates"""
        request = self.context.get("request")
        
        if obj.audio:
            base_url = request.build_absolute_uri('/').rstrip('/') if request else ""
            audio_url = f"{base_url}{obj.audio.url}"
            logger.debug(f"Post audio URL: {audio_url}")
            return audio_url
            
        return None


class CommentSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    
    class Meta:
        model = Comment
        fields = ["id", "user", "text", "created_at"]
    
    def get_user(self, obj):
        """Return a user object with name, avatar, and role"""
        request = self.context.get("request")  # Ensure absolute URL
        base_url = request.build_absolute_uri('/').rstrip('/') if request else ""
        logger.info(f"Getting user info for comment {obj.id} - User ID: {obj.user_id}, User Type: {obj.user_type}")
        
        # Get user information based on type
        if obj.user_type == "artist":
            try:
                artist = Artist.objects.get(id=obj.user_id)
                avatar_url = None
                if artist.profile_picture:
                    avatar_url = f"{base_url}{artist.profile_picture.url}"
                    # Add timestamp to prevent caching
                    avatar_url = f"{avatar_url}?_={int(time.time())}"
                    logger.debug(f"Artist avatar URL: {avatar_url}")

                logger.info(f"Found artist: {artist.username} (ID: {artist.id})")
                return {
                    "name": artist.username,
                    "avatar": avatar_url,
                    "role": "artist",
                }
            except Artist.DoesNotExist:
                logger.warning(f"Artist with ID {obj.user_id} not found")
                
        elif obj.user_type == "producer":
            try:
                producer = Producer.objects.get(id=obj.user_id)
                avatar_url = None
                if producer.profile_picture:
                    avatar_url = f"{base_url}{producer.profile_picture.url}"
                    # Add timestamp to prevent caching
                    avatar_url = f"{avatar_url}?_={int(time.time())}"
                    logger.debug(f"Producer avatar URL: {avatar_url}")

                logger.info(f"Found producer: {producer.username} (ID: {producer.id})")
                return {
                    "name": producer.username,
                    "avatar": avatar_url,
                    "role": "producer",
                }
            except Producer.DoesNotExist:
                logger.warning(f"Producer with ID {obj.user_id} not found")
        
        logger.warning(f"No user found for comment {obj.id}")
        return {"name": "Unknown", "avatar": None, "role": "user"}
