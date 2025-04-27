from django.db import models
from django.conf import settings
from django.contrib.auth.models import User
from users.models import Artist, Producer


class UserProfile(models.Model):
    ROLE_CHOICES = (
        ('producer', 'Producer'),
        ('artist', 'Artist'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='music_profile')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='artist')

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"


class Project(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    deadline = models.DateField()
    image = models.ImageField(upload_to='project_images/', null=True, blank=True)
    
    # The creator can be either an Artist or a Producer
    created_by_artist = models.ForeignKey(Artist, on_delete=models.CASCADE, 
                                         related_name='projects', null=True, blank=True)
    created_by_producer = models.ForeignKey(Producer, on_delete=models.CASCADE, 
                                           related_name='projects', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def created_by(self):
        """Returns the user (artist or producer) who created this project"""
        return self.created_by_artist or self.created_by_producer
    
    def __str__(self):
        return self.title 