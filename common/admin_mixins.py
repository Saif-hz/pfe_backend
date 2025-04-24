from django.contrib import admin

class ReadOnlyModelAdmin(admin.ModelAdmin):
    """
    ModelAdmin class that prevents modifications through the admin.
    The changelist and detail view work, but a 403 is returned
    if one attempts to edit an object or delete it.

    Override any of the modifiable methods to customize the behavior.
    """
    actions = None  # Removes the default delete action

    def has_add_permission(self, request, obj=None):
        """Disable add permission"""
        return False

    def has_change_permission(self, request, obj=None):
        """Allow viewing objects, but not editing"""
        # Allow viewing the change page
        if request.method == 'GET' and obj is not None:
            return True
        # Allow viewing the changelist page
        if request.method == 'GET' and obj is None:
            return True
        # Disable actual changes
        return False

    def has_delete_permission(self, request, obj=None):
        """Disable delete permission"""
        return False

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        """Override to make all fields readonly"""
        extra_context = extra_context or {}
        extra_context['show_save'] = False
        extra_context['show_save_and_continue'] = False
        extra_context['show_save_and_add_another'] = False
        extra_context['show_delete'] = False
        return super().changeform_view(request, object_id, form_url, extra_context)

class ViewOnlyModelAdmin(admin.ModelAdmin):
    """
    ModelAdmin class that only allows viewing of objects.
    Similar to ReadOnlyModelAdmin but more restrictive.
    """
    actions = None  # Removes the default delete action

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        # Allow viewing the changelist and objects
        return request.method == 'GET'

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        # Make all fields readonly
        if obj:
            return [field.name for field in obj.__class__._meta.fields]
        return []

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_save'] = False
        extra_context['show_save_and_continue'] = False
        extra_context['show_save_and_add_another'] = False
        extra_context['show_delete'] = False
        return super().changeform_view(request, object_id, form_url, extra_context)