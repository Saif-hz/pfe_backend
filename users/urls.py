from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    LoginView, SignupView, GetProfileView, UpdateProfileView, GetAllUsersView,
    ForgotPasswordView, ResetPasswordView, ValidateTokenView, CustomTokenRefreshView,
    DiscoverView, CollaborationRequestView, CollaborationRequestActionView, ExploreFeedView,
    TestCollaborationRequestsView, NotificationView, MarkNotificationReadView, DeleteNotificationView,
    GoogleLoginView
)

urlpatterns = [
    # Authentication endpoints
    path('login/', LoginView.as_view(), name='login'),
    path('signup/', SignupView.as_view(), name='signup'),
    path('token/refresh/', CustomTokenRefreshView.as_view(), name='token-refresh'),
    path('validate-token/', ValidateTokenView.as_view(), name='validate-token'),
    path('google-login/', GoogleLoginView.as_view(), name='google_login'),
    
    # Profile endpoints
    path('profile/<str:email>/', GetProfileView.as_view(), name='get_profile'),
    # User ID endpoints with required user_type
    path('profile/artist/<int:user_id>/', GetProfileView.as_view(), {'user_type_param': 'artist'}, name='get_artist_profile_by_id'),
    path('profile/producer/<int:user_id>/', GetProfileView.as_view(), {'user_type_param': 'producer'}, name='get_producer_profile_by_id'),
    # New simplified endpoint using ID ranges - doesn't require user_type
    path('profile/id/<int:user_id>/', GetProfileView.as_view(), name='get_profile_by_id'),
    # Legacy endpoint - requires explicit user_type parameter in query string
    path('profile/id/legacy/<int:user_id>/', GetProfileView.as_view(), name='get_profile_by_id_legacy'),
    path('profile/update/<str:email>/', UpdateProfileView.as_view(), name='update_profile'),
    path('users/', GetAllUsersView.as_view(), name='get_all_users'),
    
    # Password management
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot_password'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset_password'),
    
    # Feed and discovery
    path('explore/', ExploreFeedView.as_view(), name='explore_feed'),
    path('discover/', DiscoverView.as_view(), name='discover'),
    
    # Collaboration requests
    path('collaboration-requests/', CollaborationRequestView.as_view(), name='collaboration_requests'),
    path('collaboration-requests/<int:request_id>/', CollaborationRequestView.as_view(), name='collaboration_request_detail'),
    path('collaboration-requests/<int:request_id>/action/', CollaborationRequestActionView.as_view(), name='collaboration_request_action'),
    
    # Notifications
    path('notifications/', NotificationView.as_view(), name='notifications'),
    path('notifications/<int:notification_id>/read/', MarkNotificationReadView.as_view(), name='mark_notification_read'),
    path('notifications/<int:notification_id>/', DeleteNotificationView.as_view(), name='delete_notification'),
    
    # Test endpoints
    path('test/collaboration-requests/', TestCollaborationRequestsView.as_view(), name='test_collaboration_requests'),
]
