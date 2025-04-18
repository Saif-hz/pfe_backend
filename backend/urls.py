from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/feed/", include("feed.urls")),
    path("api/auth/", include("users.urls")),
    path("api/notifications/", include("users.urls")),
    path('accounts/', include('allauth.urls')),  # Django AllAuth URLs
    path('api/messaging/', include('messaging.urls')),  # Messaging URLs
]

# ✅ Serve media files in development mode
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
