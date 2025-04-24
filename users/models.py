from django.db import models
from django.contrib.auth.hashers import make_password
from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError
import os
import logging

logger = logging.getLogger(__name__)

def validate_image_size(value):
    filesize = value.size
    if filesize > 5 * 1024 * 1024:  # 5MB limit
        raise ValidationError("The maximum file size that can be uploaded is 5MB")

def profile_pic_path(instance, filename):
    # Get the file extension while keeping the original filename
    ext = filename.split('.')[-1]
    # Create a new filename with user_id
    filename = f"{instance.username}_{instance.id}.{ext}"
    return os.path.join('profile_pics', filename)

def cover_photo_path(instance, filename):
    # Get the file extension while keeping the original filename
    ext = filename.split('.')[-1]
    # Create a new filename with user_id
    filename = f"cover_{instance.username}_{instance.id}.{ext}"
    return os.path.join('cover_photos', filename)

# Custom model managers to handle ID-based lookups
class ArtistManager(models.Manager):
    def get_by_user_id(self, user_id):
        """Get an artist by user_id, returns None if the ID is in the producer range"""
        try:
            user_id = int(user_id)
            if user_id >= 1000000:  # This is a producer ID
                return None
            return self.get(id=user_id)
        except (ValueError, self.model.DoesNotExist):
            return None

class ProducerManager(models.Manager):
    def get_by_user_id(self, user_id):
        """Get a producer by user_id, returns None if the ID is in the artist range"""
        try:
            user_id = int(user_id)
            if user_id < 1000000:  # This is an artist ID
                return None
            return self.get(id=user_id)
        except (ValueError, self.model.DoesNotExist):
            return None

# Utility function to get a user by ID without knowing the type
def get_user_by_id(user_id):
    """
    Get a user (artist or producer) by ID.
    Returns a tuple of (user, user_type) where user_type is 'artist' or 'producer'.
    Returns (None, None) if no user is found.
    """
    try:
        user_id = int(user_id)
        if user_id >= 1000000:  # Producer range
            producer = Producer.objects.get(id=user_id)
            return producer, 'producer'
        else:  # Artist range
            artist = Artist.objects.get(id=user_id)
            return artist, 'artist'
    except (ValueError, Artist.DoesNotExist, Producer.DoesNotExist):
        logger.warning(f"User not found with ID: {user_id}")
        return None, None

class Artist(models.Model):
    id = models.BigAutoField(primary_key=True)
    username = models.CharField(max_length=50, unique=True)
    nom = models.CharField(max_length=50)
    prenom = models.CharField(max_length=50)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)
    date_de_naissance = models.DateField(blank=True, null=True)
    profile_picture = models.ImageField(
        upload_to=profile_pic_path,
        validators=[
            FileExtensionValidator(['jpg', 'jpeg', 'png', 'webp']),
            validate_image_size
        ],
        blank=True,
        null=True
    )
    cover_photo = models.ImageField(
        upload_to=cover_photo_path,
        validators=[
            FileExtensionValidator(['jpg', 'jpeg', 'png', 'webp']),
            validate_image_size
        ],
        blank=True,
        null=True
    )
    bio = models.TextField(blank=True, null=True)
    talents = models.TextField(blank=True, null=True)
    genres = models.TextField(blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)  # Added location
    followers = models.ManyToManyField("self", symmetrical=False, related_name="user_followers", blank=True)  # Followers system
    following = models.ManyToManyField("self", symmetrical=False, related_name="user_following", blank=True)  # Following system
    created_at = models.DateTimeField(auto_now_add=True)
    reset_code = models.CharField(max_length=6, blank=True, null=True)
    collaboration_count = models.PositiveIntegerField(default=0)  # Track number of successful collaborations

    # Use custom manager
    objects = ArtistManager()

    def save(self, *args, **kwargs):
        if self.password and not self.password.startswith("pbkdf2_sha256$"):
            self.password = make_password(self.password)

        # Delete old profile picture if it exists
        if self.pk:
            old_instance = Artist.objects.get(pk=self.pk)
            if old_instance.profile_picture and self.profile_picture != old_instance.profile_picture:
                old_instance.profile_picture.delete(save=False)
            if hasattr(old_instance, 'cover_photo') and old_instance.cover_photo and self.cover_photo != old_instance.cover_photo:
                old_instance.cover_photo.delete(save=False)

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.username} (Artist)"

class Producer(models.Model):
    id = models.BigAutoField(primary_key=True)
    username = models.CharField(max_length=50, unique=True)
    nom = models.CharField(max_length=50)
    prenom = models.CharField(max_length=50)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)
    date_de_naissance = models.DateField(blank=True, null=True)
    profile_picture = models.ImageField(
        upload_to=profile_pic_path,
        validators=[
            FileExtensionValidator(['jpg', 'jpeg', 'png', 'webp']),
            validate_image_size
        ],
        blank=True,
        null=True
    )
    cover_photo = models.ImageField(
        upload_to=cover_photo_path,
        validators=[
            FileExtensionValidator(['jpg', 'jpeg', 'png', 'webp']),
            validate_image_size
        ],
        blank=True,
        null=True
    )
    bio = models.TextField(blank=True, null=True)
    studio_name = models.CharField(max_length=255, blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    genres = models.TextField(blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)  # Added location
    followers = models.ManyToManyField("self", symmetrical=False, related_name="producer_followers", blank=True)  # Followers system
    following = models.ManyToManyField("self", symmetrical=False, related_name="producer_following", blank=True)  # Following system
    created_at = models.DateTimeField(auto_now_add=True)
    reset_code = models.CharField(max_length=6, blank=True, null=True)
    collaboration_count = models.PositiveIntegerField(default=0)  # Track number of successful collaborations

    # Use custom manager
    objects = ProducerManager()

    def save(self, *args, **kwargs):
        self.email = self.email.lower()  # Always store emails in lowercase

        if self.password and not self.password.startswith("pbkdf2_sha256$"):
            self.password = make_password(self.password)

        # Ensure new producers get IDs starting from 1,000,000
        if not self.pk:
            # Check if we're adding a new record
            last_id = Producer.objects.all().order_by('-id').values_list('id', flat=True).first() or 0
            if last_id < 1000000:
                # If we haven't yet reached the 1M range, explicitly set the ID
                from django.db import connection
                db_engine = connection.settings_dict['ENGINE']
                if 'sqlite' in db_engine:
                    # For SQLite
                    self.id = 1000000
                # For PostgreSQL, the migration will handle this via sequence

        # Delete old profile picture if it exists
        if self.pk:
            old_instance = Producer.objects.get(pk=self.pk)
            if old_instance.profile_picture and self.profile_picture != old_instance.profile_picture:
                old_instance.profile_picture.delete(save=False)
            if hasattr(old_instance, 'cover_photo') and old_instance.cover_photo and self.cover_photo != old_instance.cover_photo:
                old_instance.cover_photo.delete(save=False)

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.username} (Producer)"

class CollaborationRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected')
    ]

    # Update relationship fields to handle both user types
    sender_artist = models.ForeignKey('Artist', on_delete=models.CASCADE, related_name='sent_requests', null=True, blank=True)
    sender_producer = models.ForeignKey('Producer', on_delete=models.CASCADE, related_name='sent_requests', null=True, blank=True)
    receiver_artist = models.ForeignKey('Artist', on_delete=models.CASCADE, related_name='received_requests', null=True, blank=True)
    receiver_producer = models.ForeignKey('Producer', on_delete=models.CASCADE, related_name='received_requests', null=True, blank=True)

    message = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def sender(self):
        return self.sender_artist or self.sender_producer

    @property
    def receiver(self):
        return self.receiver_artist or self.receiver_producer

    def __str__(self):
        sender_name = self.sender.username if self.sender else "Unknown"
        receiver_name = self.receiver.username if self.receiver else "Unknown"
        return f"Collaboration request from {sender_name} to {receiver_name}"

class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('collaboration_request', 'Collaboration Request'),
        ('collaboration_update', 'Collaboration Update'),
        ('system', 'System Notification'),
        ('like', 'Post Like'),
        ('comment', 'Post Comment')
    ]

    # Can be linked to either an Artist or Producer
    artist = models.ForeignKey('Artist', on_delete=models.CASCADE, related_name='notifications', null=True, blank=True)
    producer = models.ForeignKey('Producer', on_delete=models.CASCADE, related_name='notifications', null=True, blank=True)

    # Sender information - can be either artist or producer
    sender_artist = models.ForeignKey('Artist', on_delete=models.CASCADE, related_name='sent_notifications', null=True, blank=True)
    sender_producer = models.ForeignKey('Producer', on_delete=models.CASCADE, related_name='sent_notifications', null=True, blank=True)

    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    message = models.TextField()
    related_id = models.IntegerField(null=True, blank=True)  # ID of the related object (e.g., collaboration request ID)
    post_id = models.IntegerField(null=True, blank=True)  # ID of the related post
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def user(self):
        """Get the user (artist or producer) this notification belongs to"""
        return self.artist or self.producer

    @property
    def sender(self):
        """Get the user (artist or producer) who sent this notification"""
        return self.sender_artist or self.sender_producer

    def __str__(self):
        user_name = self.user.username if self.user else "Unknown"
        return f"Notification for {user_name}: {self.message[:50]}..."
