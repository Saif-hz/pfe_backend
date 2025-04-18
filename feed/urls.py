from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings
from .views import CreatePostView, GetPostsView, LikePostView, AddCommentView, GetUserPostsView, GetCommentsView, UpdatePostView, DeletePostView
from users.views import NotificationView, MarkNotificationReadView, DeleteNotificationView

urlpatterns = [
    path("posts/", GetPostsView.as_view(), name="get_posts"),
    path("posts/create/", CreatePostView.as_view(), name="create_post"),  # ✅ Ensure this exists
    path("posts/<int:post_id>/like/", LikePostView.as_view(), name="like_post"),
    path("posts/<int:post_id>/comment/", AddCommentView.as_view(), name="add_comment"),
    path("posts/<int:post_id>/comments/", GetCommentsView.as_view(), name="get_comments"),
    path('user/posts/', GetUserPostsView.as_view(), name='get_user_posts'),
    path('user/<int:user_id>/posts/', GetUserPostsView.as_view(), name='get_specific_user_posts'),
    
    # New endpoints for updating and deleting posts
    path('posts/<int:post_id>/update/', UpdatePostView.as_view(), name='update_post'),
    path('posts/<int:post_id>/', DeletePostView.as_view(), name='delete_post'),
    
    # Use direct include for notification endpoints - this redirects to users URLs
    path('notifications/', include('users.urls')),
]
