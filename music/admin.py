from django.contrib import admin
from .models import Project


class ProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'deadline', 'get_creator', 'created_at')
    list_filter = ('deadline', 'created_at')
    search_fields = ('title', 'description')
    date_hierarchy = 'created_at'
    
    def get_creator(self, obj):
        if obj.created_by_producer:
            return f"{obj.created_by_producer.username} (Producer)"
        elif obj.created_by_artist:
            return f"{obj.created_by_artist.username} (Artist)"
        return "Unknown"
    get_creator.short_description = 'Created By'


admin.site.register(Project, ProjectAdmin) 