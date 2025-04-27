from rest_framework import serializers
from .models import Project
from users.models import Artist, Producer


class ArtistSerializer(serializers.ModelSerializer):
    class Meta:
        model = Artist
        fields = ['id', 'username', 'email']
        read_only_fields = ['id']


class ProducerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Producer
        fields = ['id', 'username', 'email']
        read_only_fields = ['id']


class ProjectSerializer(serializers.ModelSerializer):
    created_by_artist = ArtistSerializer(read_only=True)
    created_by_producer = ProducerSerializer(read_only=True)
    
    class Meta:
        model = Project
        fields = ['id', 'title', 'description', 'deadline', 'image', 
                 'created_by_artist', 'created_by_producer', 'created_at']
        read_only_fields = ['created_by_artist', 'created_by_producer', 'created_at'] 