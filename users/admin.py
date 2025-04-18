from django.contrib import admin
from django import forms
from django.contrib.auth.hashers import make_password
from .models import Artist, Producer

# 🔥 Custom Form for Artist to Show Password Field
class ArtistAdminForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, required=True)  # 🔥 Show password field

    class Meta:
        model = Artist
        fields = '__all__'  # Show all fields, including password

    def clean_password(self):
        password = self.cleaned_data.get('password')
        return make_password(password)  # 🔐 Hash password before saving


class ArtistAdmin(admin.ModelAdmin):
    form = ArtistAdminForm
    list_display = ('email', 'nom', 'prenom', 'talents', 'genres')
    fields = ('email', 'nom', 'prenom', 'password', 'profile_picture', 'bio', 'talents', 'genres')  # 🔥 Added password field

admin.site.register(Artist, ArtistAdmin)


#  Custom Form for Producer to Show Password Field
class ProducerAdminForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, required=True)  # 🔥 Show password field

    class Meta:
        model = Producer
        fields = '__all__'

    def clean_password(self):
        password = self.cleaned_data.get('password')
        return make_password(password)  # 🔐 Hash password before saving


class ProducerAdmin(admin.ModelAdmin):
    form = ProducerAdminForm
    list_display = ('email', 'nom', 'prenom', 'studio_name', 'website', 'genres')
    fields = ('email', 'nom', 'prenom', 'password', 'profile_picture', 'bio', 'studio_name', 'website', 'genres')  # 🔥 Added password field

admin.site.register(Producer, ProducerAdmin)


from rest_framework_simplejwt.tokens import AccessToken

token_string = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzQxNDAzMDIzLCJpYXQiOjE3NDE0MDIxMjMsImp0aSI6ImY1M2FiMDJlZWI5NDRmNTU5ZmY1ZmE3YWFmMDE3OTMyIiwidXNlcl9pZCI6MjQsInVzZXJfdHlwZSI6ImFydGlzdCJ9.Mh7qOIoGXhqpNg3nVmymj6oz4zlwKVoo38Etviuvx4w"
try:
    token = AccessToken(token_string)
    print("User ID:", token["user_id"])
    print("User Type:", token["user_type"])
except Exception as e:
    print("Invalid Token:", str(e))


 
