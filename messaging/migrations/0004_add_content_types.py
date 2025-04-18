# Generated manually

from django.db import migrations, models
import django.db.models.deletion
from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.conf import settings

def forwards_func(apps, schema_editor):
    """
    Forward migration: Create ChatRoomParticipant model and transfer data from ChatRoom.participants
    """
    ChatRoom = apps.get_model("messaging", "ChatRoom")
    Message = apps.get_model("messaging", "Message")
    ChatRoomParticipant = apps.get_model("messaging", "ChatRoomParticipant")
    
    # Get ContentType for User model
    User = apps.get_model(settings.AUTH_USER_MODEL)
    User_ct = ContentType.objects.get_for_model(User)
    
    # Migrate ChatRoom participants
    for room in ChatRoom.objects.all():
        for user in room.participants.all():
            # Create participant link
            ChatRoomParticipant.objects.create(
                chat_room=room,
                content_type=User_ct,
                object_id=user.id
            )
    
    # Migrate Message senders
    for message in Message.objects.all():
        if message.sender:
            message.content_type = User_ct
            message.object_id = message.sender.id
            message.save()

def reverse_func(apps, schema_editor):
    """
    Reverse migration: Copy content_type and object_id back to the original fields
    """
    ChatRoom = apps.get_model("messaging", "ChatRoom")
    Message = apps.get_model("messaging", "Message")
    ChatRoomParticipant = apps.get_model("messaging", "ChatRoomParticipant")
    
    # Migrate ChatRoomParticipant objects back to ChatRoom.participants
    for participant in ChatRoomParticipant.objects.all():
        if participant.content_type.model_class() == apps.get_model(settings.AUTH_USER_MODEL):
            try:
                user = apps.get_model(settings.AUTH_USER_MODEL).objects.get(id=participant.object_id)
                participant.chat_room.participants.add(user)
            except:
                pass
    
    # Migrate Message content_type/object_id back to sender
    for message in Message.objects.all():
        if message.content_type.model_class() == apps.get_model(settings.AUTH_USER_MODEL):
            try:
                user = apps.get_model(settings.AUTH_USER_MODEL).objects.get(id=message.object_id)
                message.sender = user
                message.save()
            except:
                pass

class Migration(migrations.Migration):

    dependencies = [
        ('messaging', '0003_alter_message_options_message_is_read_and_more'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        # Add ChatRoomParticipant model
        migrations.CreateModel(
            name='ChatRoomParticipant',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('object_id', models.PositiveIntegerField()),
                ('chat_room', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='participant_links', to='messaging.chatroom')),
                ('content_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype')),
            ],
            options={
                'unique_together': {('chat_room', 'content_type', 'object_id')},
            },
        ),
        # Add content_type and object_id to Message
        migrations.AddField(
            model_name='message',
            name='content_type',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='message',
            name='object_id',
            field=models.PositiveIntegerField(null=True),
            preserve_default=False,
        ),
        # Apply data migration
        migrations.RunPython(forwards_func, reverse_func),
        # Make fields required
        migrations.AlterField(
            model_name='message',
            name='content_type',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype'),
        ),
        migrations.AlterField(
            model_name='message',
            name='object_id',
            field=models.PositiveIntegerField(),
        ),
        # Remove old fields
        migrations.RemoveField(
            model_name='message',
            name='sender',
        ),
        migrations.RemoveField(
            model_name='chatroom',
            name='participants',
        ),
    ] 