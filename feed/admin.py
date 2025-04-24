from django.contrib import admin
from .models import Post, Comment, Like
from common.admin_mixins import ViewOnlyModelAdmin

class PostAdmin(ViewOnlyModelAdmin):
    list_display = ('id', 'user_type', 'user_id', 'created_at')
    list_filter = ('user_type', 'created_at')
    search_fields = ('content',)
    readonly_fields = ('created_at',)

class CommentAdmin(ViewOnlyModelAdmin):
    list_display = ('id', 'post', 'user_type', 'user_id', 'created_at')
    list_filter = ('user_type', 'created_at')
    search_fields = ('text',)
    readonly_fields = ('created_at',)

class LikeAdmin(ViewOnlyModelAdmin):
    list_display = ('id', 'post', 'user_type', 'user_id', 'created_at')
    list_filter = ('user_type', 'created_at')
    readonly_fields = ('created_at',)

admin.site.register(Post, PostAdmin)
admin.site.register(Comment, CommentAdmin)
admin.site.register(Like, LikeAdmin)


# Register your models here.
