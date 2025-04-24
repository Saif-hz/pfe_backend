from django.contrib import admin
from django import forms
from django.contrib.auth.hashers import make_password
from .models import Artist, Producer, CollaborationRequest, Notification
from common.admin_mixins import ViewOnlyModelAdmin

# 🔥 Custom Form for Artist to Show Password Field
class ArtistAdminForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, required=True)  # 🔥 Show password field

    class Meta:
        model = Artist
        fields = '__all__'  # Show all fields, including password

    def clean_password(self):
        password = self.cleaned_data.get('password')
        return make_password(password)  # 🔐 Hash password before saving


class ArtistAdmin(ViewOnlyModelAdmin):
    form = ArtistAdminForm
    list_display = ('email', 'nom', 'prenom', 'talents', 'genres')
    fields = ('email', 'nom', 'prenom', 'password', 'profile_picture', 'bio', 'talents', 'genres')

    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return self.fields
        return []


# Custom Form for Producer to Show Password Field
class ProducerAdminForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, required=True)  # 🔥 Show password field

    class Meta:
        model = Producer
        fields = '__all__'

    def clean_password(self):
        password = self.cleaned_data.get('password')
        return make_password(password)  # 🔐 Hash password before saving


class ProducerAdmin(ViewOnlyModelAdmin):
    form = ProducerAdminForm
    list_display = ('email', 'nom', 'prenom', 'studio_name', 'website', 'genres')
    fields = ('email', 'nom', 'prenom', 'password', 'profile_picture', 'bio', 'studio_name', 'website', 'genres')

    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return self.fields
        return []

admin.site.register(Artist, ArtistAdmin)
admin.site.register(Producer, ProducerAdmin)

# Register other models with read-only permissions if they exist in the app
try:
    admin.site.register(CollaborationRequest, ViewOnlyModelAdmin)
    admin.site.register(Notification, ViewOnlyModelAdmin)
except admin.sites.AlreadyRegistered:
    pass  # Models already registered



