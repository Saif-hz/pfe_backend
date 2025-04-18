# Setup logging
import logging
logger = logging.getLogger(__name__)

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.core.exceptions import ObjectDoesNotExist
from users.models import Artist, Producer, Notification
from .models import Post, Comment, Like
from .serializers import PostSerializer, CommentSerializer
from rest_framework import status
from users.jwt_auth import CustomJWTAuthentication  # Import our custom JWT auth class

# Create a New Post (Debugging Version)
class CreatePostView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomJWTAuthentication]  # Use our custom JWT auth class

    def post(self, request):
        try:
            # Log authentication information for debugging
            logger.info(f"Request user: {request.user}")
            logger.info(f"Request auth: {request.auth}")
            logger.info(f"User ID: {getattr(request.user, 'id', 'No ID')}")
            logger.info(f"Username: {getattr(request.user, 'username', 'No username')}")
            
            user = request.user
            
            # Check if user exists
            if not user or not hasattr(user, 'id'):
                logger.error(f"User not found or invalid: {user}")
                return Response({"error": "User not authenticated properly"}, status=status.HTTP_401_UNAUTHORIZED)
            
            # Determine user type with extra validation
            try:
                # Get user ID from token claims if available
                user_id_from_token = getattr(request.auth, 'payload', {}).get('user_id', user.id)
                logger.info(f"User ID from token: {user_id_from_token}")
                
                # Check if IDs match
                if user_id_from_token != user.id:
                    logger.warning(f"User ID mismatch: token={user_id_from_token}, user={user.id}")
                
                # Use the ID from the authenticated user object
                user_id = user.id
                
                # Get user_type from token first
                user_type = getattr(request.auth, 'payload', {}).get('user_type', '').lower()
                logger.info(f"User type from token: {user_type}")
                
                # If user_type not in token or empty, determine from database
                if not user_type:
                    # Check Producer first since we know the ID exists there
                    if Producer.objects.filter(id=user_id).exists():
                        user_type = "producer"
                        producer = Producer.objects.get(id=user_id)
                        logger.info(f"Creating post for producer: {producer.username} (ID: {producer.id})")
                        
                        # Verify username matches
                        if producer.username != user.username:
                            logger.warning(f"Username mismatch: producer.username={producer.username}, user.username={user.username}")
                            
                    elif Artist.objects.filter(id=user_id).exists():
                        user_type = "artist"
                        artist = Artist.objects.get(id=user_id)
                        logger.info(f"Creating post for artist: {artist.username} (ID: {artist.id})")
                        
                        # Verify username matches
                        if artist.username != user.username:
                            logger.warning(f"Username mismatch: artist.username={artist.username}, user.username={user.username}")
                    else:
                        logger.error(f"User {user_id} is neither Artist nor Producer")
                        return Response({"error": "Invalid user type"}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                logger.error(f"Error determining user type: {str(e)}")
                return Response({"error": f"Error determining user type: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            content = request.data.get("content", "").strip()

            # Check if post has any content (text, image, video, or audio)
            if (not content and 
                not request.FILES.get("image") and 
                not request.FILES.get("video") and 
                not request.FILES.get("audio")):
                return Response({"error": "Post cannot be empty!"}, status=status.HTTP_400_BAD_REQUEST)

            # Log media information
            if request.FILES.get("audio"):
                logger.info(f"Audio file received: {request.FILES.get('audio').name}")
            if request.FILES.get("image"):
                logger.info(f"Image file received: {request.FILES.get('image').name}")
            if request.FILES.get("video"):
                logger.info(f"Video file received: {request.FILES.get('video').name}")

            post = Post.objects.create(
                user_id=user.id,
                user_type=user_type,
                content=content,
                image=request.FILES.get("image"),
                video=request.FILES.get("video"),
                audio=request.FILES.get("audio"),
            )

            return Response({"message": "Post created successfully!", "post_id": post.id}, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Error creating post: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Get All Posts for Feed
class GetPostsView(APIView):
    permission_classes = [AllowAny]  # Public access
    authentication_classes = []  # No authentication required

    def get(self, request):
        try:
            # Log request information
            logger.info(f"GetPostsView: Fetching posts for feed")
            
            # Get all posts ordered by creation date (newest first)
            posts = Post.objects.all().order_by("-created_at")
            logger.info(f"GetPostsView: Found {posts.count()} posts")
            
            # Serialize the posts with the request context for absolute URLs
            serializer = PostSerializer(posts, many=True, context={"request": request})
            
            # Return the serialized data
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"GetPostsView Error: {str(e)}")
            return Response(
                {"error": "An error occurred while fetching posts."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# Get User's Posts
class GetUserPostsView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomJWTAuthentication]

    def get(self, request, user_id=None):
        try:
            # If no user_id provided, use the authenticated user's ID
            if user_id is None:
                user_id = request.user.id

            # Get user type
            user_type = None
            if Producer.objects.filter(id=user_id).exists():
                user_type = "producer"
            elif Artist.objects.filter(id=user_id).exists():
                user_type = "artist"
            
            if not user_type:
                return Response(
                    {"error": "User not found"},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Get all posts by this user
            posts = Post.objects.filter(
                user_id=user_id,
                user_type=user_type
            ).order_by('-created_at')

            # Serialize the posts
            serializer = PostSerializer(posts, many=True, context={"request": request})
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error fetching user posts: {str(e)}")
            return Response(
                {"error": "Failed to fetch user posts"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# Like a Post
class LikePostView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomJWTAuthentication]  # Use our custom JWT auth class

    def post(self, request, post_id):
        try:
            # Log request information
            logger.info(f"LikePostView: User {request.user.username} (ID: {request.user.id}) attempting to like post {post_id}")
            
            # Check if post exists
            try:
                post = Post.objects.get(id=post_id)
                logger.info(f"LikePostView: Found post {post_id}")
            except Post.DoesNotExist:
                logger.warning(f"LikePostView: Post {post_id} not found")
                return Response({"error": "Post not found"}, status=status.HTTP_404_NOT_FOUND)
            
            user = request.user
            
            # Try to get user_type from token payload first (most reliable)
            if hasattr(request.auth, 'payload') and 'user_type' in request.auth.payload:
                user_type = request.auth.payload.get('user_type')
                logger.info(f"LikePostView: Got user_type from token: {user_type}")
            # Fallback method: check the user model type
            else:
                if Producer.objects.filter(id=user.id).exists():
                    user_type = "producer"
                    logger.info(f"LikePostView: Determined user is a producer")
                elif Artist.objects.filter(id=user.id).exists():
                    user_type = "artist"
                    logger.info(f"LikePostView: Determined user is an artist")
                else:
                    logger.error(f"LikePostView: User {user.id} is neither Artist nor Producer")
                    return Response({"error": "Invalid user type"}, status=status.HTTP_400_BAD_REQUEST)

            # Try to find existing like
            existing_like = Like.objects.filter(
                post=post,
                user_id=user.id,
                user_type=user_type
            ).first()
            
            if existing_like:
                # Unlike the post (toggle behavior)
                logger.info(f"LikePostView: User {user.id} unliking post {post_id}")
                existing_like.delete()
                return Response({
                    "message": "Like removed",
                    "liked": False,
                    "likes_count": Like.objects.filter(post=post).count()
                }, status=status.HTTP_200_OK)
            else:
                # Like the post
                try:
                    logger.info(f"LikePostView: User {user.id} liking post {post_id}")
                    like = Like.objects.create(
                        post=post,
                        user_id=user.id,
                        user_type=user_type,
                    )
                    
                    # Create notification only if the post owner is not the same as the liker
                    if post.user_id != user.id:
                        try:
                            # Determine post owner (artist or producer)
                            post_owner_artist = None
                            post_owner_producer = None
                            if post.user_type == "artist":
                                post_owner_artist = Artist.objects.get(id=post.user_id)
                                logger.info(f"LikePostView: Post owner is artist {post_owner_artist.username}")
                            elif post.user_type == "producer":
                                post_owner_producer = Producer.objects.get(id=post.user_id)
                                logger.info(f"LikePostView: Post owner is producer {post_owner_producer.username}")
                                
                            # Determine sender (artist or producer)
                            sender_artist = None
                            sender_producer = None
                            if user_type == "artist":
                                sender_artist = Artist.objects.get(id=user.id)
                            elif user_type == "producer":
                                sender_producer = Producer.objects.get(id=user.id)
                            
                            # Get sender username for notification message
                            sender_username = user.username
                                
                            # Create notification
                            notification = Notification.objects.create(
                                artist=post_owner_artist,
                                producer=post_owner_producer,
                                sender_artist=sender_artist,
                                sender_producer=sender_producer,
                                notification_type="like",
                                message=f"{sender_username} liked your post.",
                                related_id=post.id,
                                read=False
                            )
                            logger.info(f"LikePostView: Created notification {notification.id} for post owner")
                            
                        except Exception as notif_error:
                            # Log error but don't fail the like operation if notification fails
                            logger.error(f"LikePostView: Error creating notification: {str(notif_error)}")
                    
                    return Response({
                        "message": "Post liked successfully",
                        "liked": True,
                        "likes_count": Like.objects.filter(post=post).count()
                    }, status=status.HTTP_201_CREATED)
                    
                except Exception as like_error:
                    logger.error(f"LikePostView: Error creating like: {str(like_error)}")
                    # Check for IntegrityError (duplicate like)
                    if "unique constraint" in str(like_error).lower():
                        return Response({"error": "You have already liked this post"}, status=status.HTTP_400_BAD_REQUEST)
                    return Response({"error": str(like_error)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            logger.error(f"LikePostView Error: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Add a Comment
class AddCommentView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomJWTAuthentication]

    def post(self, request, post_id):
        try:
            post = Post.objects.get(id=post_id)
            user = request.user
            
            # Get user type from token or determine from database
            user_type = getattr(user, 'user_type', None)
            
            # If not in token, determine from database
            if not user_type:
                if Producer.objects.filter(id=user.id).exists():
                    user_type = "producer"
                elif Artist.objects.filter(id=user.id).exists():
                    user_type = "artist"
                else:
                    logger.error(f"User {user.id} is neither Artist nor Producer")
                    return Response({"error": "Invalid user type"}, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate text is not empty
            text = request.data.get("text", "").strip()
            if not text:
                return Response(
                    {"error": "Comment text cannot be empty"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create the comment
            comment = Comment.objects.create(
                post=post,
                user_id=user.id,
                user_type=user_type,
                text=text,
            )
            
            # Create notification only if the post owner is not the commenter
            if post.user_id != user.id:
                try:
                    # Determine post owner (artist or producer)
                    post_owner_artist = None
                    post_owner_producer = None
                    if post.user_type == "artist":
                        post_owner_artist = Artist.objects.get(id=post.user_id)
                    elif post.user_type == "producer":
                        post_owner_producer = Producer.objects.get(id=post.user_id)
                        
                    # Determine sender (artist or producer)
                    sender_artist = None
                    sender_producer = None
                    if user_type == "artist":
                        sender_artist = Artist.objects.get(id=user.id)
                    elif user_type == "producer":
                        sender_producer = Producer.objects.get(id=user.id)
                    
                    # Get sender username for notification message
                    sender_username = user.username
                        
                    # Create notification
                    notification = Notification.objects.create(
                        artist=post_owner_artist,
                        producer=post_owner_producer,
                        sender_artist=sender_artist,
                        sender_producer=sender_producer,
                        notification_type="comment",
                        message=f"{sender_username} commented on your post: \"{text[:50]}{'...' if len(text) > 50 else ''}\"",
                        post_id=post.id,
                        read=False
                    )
                    
                    logger.info(f"Created comment notification {notification.id} for post {post_id}")
                except Exception as e:
                    # Log error but don't fail the whole request if notification creation fails
                    logger.error(f"Failed to create comment notification: {str(e)}")
            
            # Serialize the created comment
            serializer = CommentSerializer(comment, context={"request": request})
            
            return Response(
                {"message": "Comment added successfully", "comment": serializer.data}, 
                status=status.HTTP_201_CREATED
            )

        except Post.DoesNotExist:
            return Response({"error": "Post not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error adding comment: {str(e)}")
            return Response(
                {"error": f"Failed to add comment: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# Get Comments for a Post
class GetCommentsView(APIView):
    permission_classes = [AllowAny]  # Public access
    authentication_classes = []  # No authentication required

    def get(self, request, post_id):
        try:
            # Check if post exists
            post = Post.objects.get(id=post_id)
            
            # Get all comments for this post
            comments = Comment.objects.filter(post=post).order_by('-created_at')
            
            # Serialize the comments
            serializer = CommentSerializer(comments, many=True, context={"request": request})
            
            # Return the serialized data
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Post.DoesNotExist:
            return Response(
                {"error": "Post not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error fetching comments: {str(e)}")
            return Response(
                {"error": "Failed to fetch comments"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# Update a Post
class UpdatePostView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomJWTAuthentication]

    def patch(self, request, post_id):
        try:
            # Get the post
            post = Post.objects.get(id=post_id)
            
            # Check if the user is the owner of the post
            if request.user.id != post.user_id:
                return Response(
                    {"error": "You don't have permission to edit this post"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Update fields that are present in the request
            content = request.data.get("content")
            if content is not None:
                post.content = content.strip()
            
            # Handle media updates if provided
            if 'image' in request.FILES:
                # Delete old image if it exists
                if post.image:
                    post.image.delete(save=False)
                post.image = request.FILES.get("image")
                
            if 'video' in request.FILES:
                # Delete old video if it exists
                if post.video:
                    post.video.delete(save=False)
                post.video = request.FILES.get("video")
                
            if 'audio' in request.FILES:
                # Delete old audio if it exists
                if post.audio:
                    post.audio.delete(save=False)
                post.audio = request.FILES.get("audio")
            
            # Check if post still has any content after update
            if (not post.content and 
                not post.image and 
                not post.video and 
                not post.audio):
                return Response(
                    {"error": "Post cannot be empty!"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Save the updated post
            post.save()
            
            # Serialize and return the updated post
            serializer = PostSerializer(post, context={"request": request})
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Post.DoesNotExist:
            return Response(
                {"error": "Post not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error updating post: {str(e)}")
            return Response(
                {"error": f"Failed to update post: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# Delete a Post
class DeletePostView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomJWTAuthentication]

    def delete(self, request, post_id):
        try:
            # Get the post
            post = Post.objects.get(id=post_id)
            
            # Check if the user is the owner of the post
            if request.user.id != post.user_id:
                return Response(
                    {"error": "You don't have permission to delete this post"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Delete associated likes, comments, and notifications
            # This is handled by the on_delete=models.CASCADE in the models
            
            # Delete the post
            post.delete()
            
            return Response(
                {"message": "Post deleted successfully"},
                status=status.HTTP_200_OK
            )
            
        except Post.DoesNotExist:
            return Response(
                {"error": "Post not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error deleting post: {str(e)}")
            return Response(
                {"error": f"Failed to delete post: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
