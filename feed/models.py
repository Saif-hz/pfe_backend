from django.db import models
from users.models import Artist, Producer
from django.core.exceptions import ValidationError

class Post(models.Model):
    user_id = models.PositiveIntegerField()  
    user_type = models.CharField(max_length=10, choices=[("artist", "Artist"), ("producer", "Producer")])

    content = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to="posts/images/", blank=True, null=True)
    video = models.FileField(upload_to="posts/videos/", blank=True, null=True)
    audio = models.FileField(upload_to="posts/audio/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Post by {self.user_type} {self.user_id} on {self.created_at}"


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    user_id = models.PositiveIntegerField()
    user_type = models.CharField(max_length=10, choices=[("artist", "Artist"), ("producer", "Producer")])
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comment by {self.user_type} {self.user_id} on {self.post.id}"


class Like(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="likes")
    user_id = models.PositiveIntegerField()
    user_type = models.CharField(max_length=10, choices=[("artist", "Artist"), ("producer", "Producer")])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Prevent duplicate likes from the same user on the same post
        unique_together = ('post', 'user_id', 'user_type')

    def __str__(self):
        return f"Like by {self.user_type} {self.user_id} on {self.post.id}"
