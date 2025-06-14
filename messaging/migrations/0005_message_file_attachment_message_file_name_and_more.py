# Generated by Django 5.1.6 on 2025-04-16 14:43

import django.db.models.deletion
import messaging.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('messaging', '0004_add_content_types'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='file_attachment',
            field=models.FileField(blank=True, null=True, upload_to=messaging.models.get_attachment_path),
        ),
        migrations.AddField(
            model_name='message',
            name='file_name',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='message',
            name='file_size',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='message',
            name='file_type',
            field=models.CharField(blank=True, choices=[('image', 'Image'), ('audio', 'Audio'), ('video', 'Video'), ('document', 'Document'), ('other', 'Other')], max_length=50, null=True),
        ),
        migrations.AlterField(
            model_name='message',
            name='content',
            field=models.TextField(blank=True),
        ),
        migrations.CreateModel(
            name='MessageReadStatus',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('object_id', models.PositiveIntegerField()),
                ('is_read', models.BooleanField(default=False)),
                ('read_at', models.DateTimeField(blank=True, null=True)),
                ('content_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype')),
                ('message', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='read_statuses', to='messaging.message')),
            ],
            options={
                'unique_together': {('message', 'content_type', 'object_id')},
            },
        ),
    ]
