from django.urls import path
from . import views

urlpatterns = [
    path('rooms/', views.ChatRoomListCreateView.as_view(), name='chat-room-list'),
    path('rooms/<int:pk>/', views.ChatRoomDetailView.as_view(), name='chat-room-detail'),
    path('rooms/<int:room_id>/messages/', views.ChatMessageListView.as_view(), name='chat-messages'),
    path('rooms/<int:room_id>/mark-read/', views.MarkMessagesAsReadView.as_view(), name='mark-messages-read'),
    path('rooms/<int:room_id>/messages/<int:message_id>/mark-read/', views.MarkMessagesAsReadView.as_view(), name='mark-message-read'),
    path('chats/', views.UserChatListView.as_view(), name='user-chats'),
    path('chats/create/', views.ChatRoomListCreateView.as_view(), name='create-chat'),
    path('create-chat/', views.ChatRoomListCreateView.as_view(), name='explicit-create-chat'),
]