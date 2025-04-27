from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProjectViewSet, debug_user, debug_project_permission, check_producer_1000000, fix_producer_1000000

# Create a router and register our viewsets with it
router = DefaultRouter()
router.register(r'projects', ProjectViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('debug-user/', debug_user, name='debug-user'),
    path('debug-project-permission/', debug_project_permission, name='debug-project-permission'),
    path('check-producer-1000000/', check_producer_1000000, name='check-producer-1000000'),
    path('fix-producer-1000000/', fix_producer_1000000, name='fix-producer-1000000'),
]  