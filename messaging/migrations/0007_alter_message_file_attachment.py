# Generated by Django 5.1.6 on 2025-04-24 00:05

import messaging.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('messaging', '0006_alter_message_file_attachment'),
    ]

    operations = [
        migrations.AlterField(
            model_name='message',
            name='file_attachment',
            field=models.FileField(blank=True, null=True, upload_to=messaging.models.get_attachment_path),
        ),
    ]
