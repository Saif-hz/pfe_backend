from django.contrib import admin
from .models import Message, ChatRoom, ChatRoomParticipant, MessageReadStatus
from common.admin_mixins import ViewOnlyModelAdmin

class MessageReadStatusInline(admin.TabularInline):
    model = MessageReadStatus
    extra = 0
    readonly_fields = ('is_read', 'read_at')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

class MessageAdmin(ViewOnlyModelAdmin):
    list_display = ('id', 'sender_display', 'content', 'room', 'timestamp', 'has_attachment', 'is_read')
    list_filter = ('timestamp', 'is_read', 'file_type')
    search_fields = ('content',)
    readonly_fields = ('timestamp',)
    inlines = [MessageReadStatusInline]

    def sender_display(self, obj):
        if hasattr(obj.sender, 'username'):
            return obj.sender.username
        return "Unknown"
    sender_display.short_description = 'Sender'

    def has_attachment(self, obj):
        return bool(obj.file_attachment)
    has_attachment.boolean = True
    has_attachment.short_description = 'Has Attachment'

class ChatRoomParticipantInline(admin.TabularInline):
    model = ChatRoomParticipant
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

class ChatRoomAdmin(ViewOnlyModelAdmin):
    list_display = ('id', 'name', 'participant_count', 'created_at')
    search_fields = ('name',)
    inlines = [ChatRoomParticipantInline]

    def participant_count(self, obj):
        return obj.participant_links.count()
    participant_count.short_description = 'Participants'

class ChatRoomParticipantAdmin(ViewOnlyModelAdmin):
    list_display = ('id', 'chat_room', 'participant_display')

    def participant_display(self, obj):
        if hasattr(obj.participant, 'username'):
            return obj.participant.username
        return "Unknown"
    participant_display.short_description = 'Participant'

class MessageReadStatusAdmin(ViewOnlyModelAdmin):
    list_display = ('id', 'message', 'reader_display', 'is_read', 'read_at')
    list_filter = ('is_read', 'read_at')

    def reader_display(self, obj):
        if hasattr(obj.reader, 'username'):
            return obj.reader.username
        return "Unknown"
    reader_display.short_description = 'Reader'

admin.site.register(Message, MessageAdmin)
admin.site.register(ChatRoom, ChatRoomAdmin)
admin.site.register(ChatRoomParticipant, ChatRoomParticipantAdmin)
admin.site.register(MessageReadStatus, MessageReadStatusAdmin)

# Register your models here.
