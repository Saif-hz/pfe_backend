from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from django.contrib.auth.hashers import check_password, make_password
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.views import TokenRefreshView as BaseTokenRefreshView
from rest_framework.parsers import MultiPartParser, FormParser
from .models import Artist, Producer, CollaborationRequest, Notification
from django.db import models
import logging
import json
from django.core.mail import send_mail
from django.utils.crypto import get_random_string
from django.utils import timezone
from .jwt_auth import CustomJWTAuthentication  # Import our custom JWT auth class
from .serializers import ArtistSerializer, ProducerSerializer, CollaborationRequestSerializer, NotificationSerializer
from rest_framework.pagination import PageNumberPagination
from django.template.loader import render_to_string
from django.conf import settings
from django.db.models import Q
import datetime
import random
import re
import secrets
import time
import uuid
import os
import traceback
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from allauth.socialaccount.models import SocialApp, SocialAccount
from allauth.socialaccount.helpers import complete_social_login
from django.contrib.auth import login
import jwt

# Setup logging
logger = logging.getLogger(__name__)

def get_tokens_for_user(user):
    try:
        # Don't use RefreshToken.for_user directly as it tries to create OutstandingToken records
        # that expect a User model instance
        user_type = "artist" if isinstance(user, Artist) else "producer"

        # Create a token payload manually
        token_payload = {
            "user_type": user_type,
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            # Add standard JWT claims
            "token_type": "access",
            "exp": datetime.datetime.utcnow() + settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'],
            "iat": datetime.datetime.utcnow(),
            "jti": uuid.uuid4().hex
        }

        # Create a refresh token with longer expiration
        refresh_payload = {
            "user_type": user_type,
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            # Add standard JWT claims
            "token_type": "refresh",
            "exp": datetime.datetime.utcnow() + settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'],
            "iat": datetime.datetime.utcnow(),
            "jti": uuid.uuid4().hex
        }

        # Encode tokens with your secret key
        access_token = jwt.encode(
            token_payload,
            settings.SIMPLE_JWT['SIGNING_KEY'],
            algorithm=settings.SIMPLE_JWT['ALGORITHM']
        )

        refresh_token = jwt.encode(
            refresh_payload,
            settings.SIMPLE_JWT['SIGNING_KEY'],
            algorithm=settings.SIMPLE_JWT['ALGORITHM']
        )

        logger.debug(f"Generated new tokens for user: {user.username}")
        return {
            "refresh": refresh_token,
            "access": access_token,
            "user_type": user_type,
            "user_id": user.id,
            "username": user.username,
            "email": user.email
        }
    except Exception as e:
        logger.error(f"Error generating tokens: {str(e)}")
        raise


# Login View
class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            logger.debug(f"Login request received - DATA: {request.data}")
            email = request.data.get("email")
            password = request.data.get("password")

            if not email or not password:
                logger.warning(f"Missing credentials - Email: {email is not None}, Password: {password is not None}")
                return Response({"error": "Email and password are required."}, status=status.HTTP_400_BAD_REQUEST)

            user = None
            user_type = None

            # Check both Artist and Producer models
            user = Artist.objects.filter(email=email).first()
            if user:
                user_type = "artist"
                logger.info(f"Found artist user: {user.username} (email: {email})")
            else:
                user = Producer.objects.filter(email=email).first()
                if user:
                    user_type = "producer"
                    logger.info(f"Found producer user: {user.username} (email: {email})")
                else:
                    logger.warning(f"No user found with email: {email}")

            if not user or not check_password(password, user.password):
                logger.warning(f"Invalid credentials for email: {email}")
                return Response({"error": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)

            # Generate JWT Token
            tokens = get_tokens_for_user(user)

            # Log successful login
            logger.info(f"Successful login for user: {user.username} ({user_type})")
            logger.debug(f"Login response tokens: {tokens}")

            # Build absolute URLs for media files
            base_url = request.build_absolute_uri('/').rstrip('/')  # Get base URL like http://192.168.1.47:8000

            # Prepare profile picture URL with full domain
            profile_picture_url = None
            if user.profile_picture:
                profile_picture_url = f"{base_url}{user.profile_picture.url}"
                logger.debug(f"LoginView: Full profile picture URL: {profile_picture_url}")

            response_data = {
                "refresh": tokens["refresh"],
                "access": tokens["access"],
                "username": user.username,
                "email": user.email,
                "user_type": user_type,
                "profile_picture": profile_picture_url,
            }

            logger.info(f"LoginView: Sending login response with email: {response_data['email']}")
            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Login Error: {str(e)}")
            return Response(
                {"error": "An error occurred during login."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# Signup View
class SignupView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            data = request.data
            username = data.get("username")
            email = data.get("email")
            password = data.get("password")
            user_type = data.get("user_type")

            # Validate required fields
            if not username or not email or not password or not user_type:
                return Response({"error": "Missing required fields"}, status=status.HTTP_400_BAD_REQUEST)

            # Check username uniqueness across both models
            if Artist.objects.filter(username=username).exists() or Producer.objects.filter(username=username).exists():
                return Response({"error": "Username already taken"}, status=status.HTTP_400_BAD_REQUEST)

            # Check email uniqueness across both models
            if Artist.objects.filter(email=email).exists() or Producer.objects.filter(email=email).exists():
                return Response({"error": "Email already registered"}, status=status.HTTP_400_BAD_REQUEST)

            # Validate user type
            if user_type not in ["artist", "producer"]:
                return Response({"error": "Invalid user type"}, status=status.HTTP_400_BAD_REQUEST)

            # Create user based on type
            if user_type == "artist":
                user = Artist.objects.create(
                    username=username,
                    email=email,
                    password=make_password(password),
                    nom=data.get("nom", ""),
                    prenom=data.get("prenom", ""),
                    bio=data.get("bio", ""),
                    date_de_naissance=data.get("date_de_naissance", None),
                    talents=data.get("talents", ""),
                    genres=data.get("genres", ""),
                )
            else:
                user = Producer.objects.create(
                    username=username,
                    email=email,
                    password=make_password(password),
                    nom=data.get("nom", ""),
                    prenom=data.get("prenom", ""),
                    bio=data.get("bio", ""),
                    date_de_naissance=data.get("date_de_naissance", None),
                    studio_name=data.get("studio_name", ""),
                    website=data.get("website", ""),
                    genres=data.get("genres", ""),
                )

            # Generate tokens for the new user
            tokens = get_tokens_for_user(user)

            return Response({
                "message": f"{user_type.capitalize()} account created successfully.",
                "tokens": tokens,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "user_type": user_type
                }
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Signup Error: {str(e)}")
            return Response({"error": "Something went wrong during signup."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Get User Profile by Email
class GetProfileView(APIView):
    permission_classes = [AllowAny]  # Change to AllowAny to allow public access to profiles
    authentication_classes = [CustomJWTAuthentication]

    def get(self, request, email=None, user_id=None, user_type_param=None):
        """
        Get a user's profile by email or user_id.
        """
        try:
            logger.info(f"GetProfileView: Fetching profile for email: {email} or user_id: {user_id}, user_type_param: {user_type_param}")

            user = None

            if email:
                # Clean email for case-insensitive comparison
                email = email.strip().lower()

                # Search for user in both models regardless of authentication status
                user = Artist.objects.filter(email__iexact=email).first()
                if user:
                    logger.info(f"GetProfileView: Found artist: {user.email}")
                    user_type = "artist"
                else:
                    user = Producer.objects.filter(email__iexact=email).first()
                    if user:
                        logger.info(f"GetProfileView: Found producer: {user.email}")
                        user_type = "producer"
                    else:
                        logger.warning(f"GetProfileView: No user found with email: '{email}'")
                        return Response(
                            {"code": "user_not_found", "detail": "User not found"},
                            status=status.HTTP_404_NOT_FOUND
                        )

            elif user_id:
                # Use the ID range to determine the user type - simplifies the logic
                from .models import get_user_by_id
                user, user_type = get_user_by_id(user_id)

                # If the ID-based lookup failed but we have a user_type_param, try the specific lookup
                if user is None and user_type_param:
                    logger.info(f"GetProfileView: ID-based lookup failed, trying with user_type_param: {user_type_param}")

                    if user_type_param == 'artist':
                        user = Artist.objects.filter(id=user_id).first()
                        if user:
                            logger.info(f"GetProfileView: Found artist with ID: {user_id}")
                            user_type = "artist"
                        else:
                            logger.warning(f"GetProfileView: No artist found with ID: {user_id}")
                            return Response({"error": "Artist not found"}, status=status.HTTP_404_NOT_FOUND)

                    elif user_type_param == 'producer':
                        user = Producer.objects.filter(id=user_id).first()
                        if user:
                            logger.info(f"GetProfileView: Found producer with ID: {user_id}")
                            user_type = "producer"
                        else:
                            logger.warning(f"GetProfileView: No producer found with ID: {user_id}")
                            return Response({"error": "Producer not found"}, status=status.HTTP_404_NOT_FOUND)

                # If we still don't have a user, return error
                if user is None:
                    logger.warning(f"GetProfileView: No user found with ID: {user_id}")
                    return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

                logger.info(f"GetProfileView: Found user type: {user_type} with ID: {user_id}")

            else:
                return Response({"error": "Email or user_id required"}, status=status.HTTP_400_BAD_REQUEST)

            # Build absolute URLs for media files
            request_obj = self.request  # Get the request object
            base_url = request_obj.build_absolute_uri('/').rstrip('/')  # Get base URL like http://192.168.1.47:8000

            # Fetch user's posts - import inside method to avoid circular imports
            try:
                from feed.models import Post
                from feed.serializers import PostSerializer

                # Get posts for this user
                logger.info(f"GetProfileView: Fetching posts for user {user.id} of type {user_type}")
                posts = Post.objects.filter(user_id=user.id, user_type=user_type).order_by('-created_at')
                posts_serialized = PostSerializer(posts, many=True, context={'request': request}).data
                logger.info(f"GetProfileView: Found {len(posts_serialized)} posts for user {user.username}")
            except Exception as post_error:
                logger.error(f"GetProfileView: Error fetching posts: {str(post_error)}")
                posts_serialized = []

            # Prepare response data
            response_data = {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "user_type": user_type,
                "profile_picture": f"{base_url}{user.profile_picture.url}" if user.profile_picture else None,
                "cover_photo": f"{base_url}{user.cover_photo.url}" if hasattr(user, 'cover_photo') and user.cover_photo else None,
                "nom": user.nom if hasattr(user, 'nom') else None,
                "prenom": user.prenom if hasattr(user, 'prenom') else None,
                "bio": user.bio if hasattr(user, 'bio') else None,
                "location": user.location if hasattr(user, 'location') else None,
                "genres": user.genres.split(',') if hasattr(user, 'genres') and user.genres else [],
                "followers": 0,  # TODO: Implement followers count
                "following": 0,  # TODO: Implement following count
                "posts": posts_serialized  # Include the serialized posts in the response
            }

            # Add user type specific fields
            if user_type == 'artist':
                response_data["talents"] = user.talents.split(',') if hasattr(user, 'talents') and user.talents else []
            elif user_type == 'producer':
                response_data["studio_name"] = user.studio_name if hasattr(user, 'studio_name') else None
                response_data["website"] = user.website if hasattr(user, 'website') else None

            logger.info(f"GetProfileView: Sending response for user: {response_data['email']} with {len(posts_serialized)} posts")

            # Check if collaborations are requested
            if request.query_params.get('include_collaborations') == 'true':
                # Find accepted collaboration requests for this user
                collaborations = []

                if isinstance(user, Artist):
                    # Get collaborations as sender
                    sender_collabs = CollaborationRequest.objects.filter(
                        sender_artist=user,
                        status='accepted'
                    ).order_by('-updated_at')

                    # Get collaborations as receiver
                    receiver_collabs = CollaborationRequest.objects.filter(
                        receiver_artist=user,
                        status='accepted'
                    ).order_by('-updated_at')
                else:
                    # Get collaborations as sender
                    sender_collabs = CollaborationRequest.objects.filter(
                        sender_producer=user,
                        status='accepted'
                    ).order_by('-updated_at')

                    # Get collaborations as receiver
                    receiver_collabs = CollaborationRequest.objects.filter(
                        receiver_producer=user,
                        status='accepted'
                    ).order_by('-updated_at')

                # Combine and serialize
                all_collabs = list(sender_collabs) + list(receiver_collabs)
                all_collabs.sort(key=lambda x: x.updated_at, reverse=True)

                # Limit to most recent 5
                recent_collabs = all_collabs[:5]

                response_data['recent_collaborations'] = CollaborationRequestSerializer(
                    recent_collabs,
                    many=True,
                    context={'request': request}
                ).data

                logger.info(f"Added {len(recent_collabs)} recent collaborations to profile response")

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"GetProfileView Error: {str(e)}")
            return Response(
                {"error": "An error occurred while fetching the profile."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# Update User Profile
class UpdateProfileView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomJWTAuthentication]  # Use custom JWT auth
    parser_classes = [MultiPartParser, FormParser]

    def patch(self, request, email):
        try:
            # Clean up email
            email = email.strip().lower()

            logger.info(f"UpdateProfileView: Received update request for email: '{email}'")
            logger.info(f"UpdateProfileView: Authenticated user's email is: '{request.user.email}'")

            # Verify user has permission to update this profile
            if email != request.user.email.strip().lower():
                logger.warning(f"UpdateProfileView: User {request.user.email} attempted to update profile of {email}")
                return Response(
                    {"error": "You do not have permission to update this profile"},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Find the user
            user = Artist.objects.filter(email__iexact=email).first()
            if not user:
                user = Producer.objects.filter(email__iexact=email).first()

            if not user:
                logger.warning(f"UpdateProfileView: No user found with email: '{email}'")
                return Response(
                    {"error": "User not found"},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Process profile picture if provided
            if 'profile_picture' in request.FILES:
                try:
                    file = request.FILES['profile_picture']
                    if file.size > 5 * 1024 * 1024:  # 5MB limit
                        return Response(
                            {"error": "Profile picture must be less than 5MB"},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    user.profile_picture = file
                    logger.info(f"UpdateProfileView: Updated profile picture for {email}")
                except Exception as e:
                    logger.error(f"UpdateProfileView: Error processing profile picture: {str(e)}")
                    return Response(
                        {"error": "Failed to process profile picture"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Process cover photo if provided
            if 'cover_photo' in request.FILES:
                try:
                    file = request.FILES['cover_photo']
                    if file.size > 10 * 1024 * 1024:  # 10MB limit
                        return Response(
                            {"error": "Cover photo must be less than 10MB"},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    user.cover_photo = file
                    logger.info(f"UpdateProfileView: Updated cover photo for {email}")
                except Exception as e:
                    logger.error(f"UpdateProfileView: Error processing cover photo: {str(e)}")
                    return Response(
                        {"error": "Failed to process cover photo"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Update basic fields
            for field in ['username', 'nom', 'prenom', 'bio', 'location']:
                if field in request.data:
                    # Check for username uniqueness if it's being updated
                    if field == 'username' and request.data[field] != user.username:
                        # Check if the new username already exists in either model
                        username = request.data[field]
                        if Artist.objects.filter(username=username).exclude(id=user.id).exists() or \
                           Producer.objects.filter(username=username).exclude(id=user.id).exists():
                            return Response(
                                {"error": "Username already taken"},
                                status=status.HTTP_400_BAD_REQUEST
                            )
                    setattr(user, field, request.data[field])
                    logger.info(f"UpdateProfileView: Updated {field} for {email}")

            # Update genres
            if 'genres' in request.data:
                try:
                    genres = request.data['genres']
                    if isinstance(genres, str):
                        # Try to parse as JSON if it's a string
                        try:
                            genres = json.loads(genres)
                        except json.JSONDecodeError:
                            # If not valid JSON, treat as comma-separated string
                            genres = [g.strip() for g in genres.split(',') if g.strip()]

                    if isinstance(genres, list):
                        user.genres = ','.join(genres)
                    else:
                        return Response(
                            {"error": "Genres must be a list or comma-separated string"},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    logger.info(f"UpdateProfileView: Updated genres for {email}")
                except Exception as e:
                    logger.error(f"UpdateProfileView: Error processing genres: {str(e)}")
                    return Response(
                        {"error": "Invalid genres format"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Update talents for artists
            if 'talents' in request.data and isinstance(user, Artist):
                try:
                    talents = request.data['talents']
                    if isinstance(talents, str):
                        # Try to parse as JSON if it's a string
                        try:
                            talents = json.loads(talents)
                        except json.JSONDecodeError:
                            # If not valid JSON, treat as comma-separated string
                            talents = [t.strip() for t in talents.split(',') if t.strip()]

                    if isinstance(talents, list):
                        user.talents = ','.join(talents)
                    else:
                        return Response(
                            {"error": "Talents must be a list or comma-separated string"},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    logger.info(f"UpdateProfileView: Updated talents for {email}")
                except Exception as e:
                    logger.error(f"UpdateProfileView: Error processing talents: {str(e)}")
                    return Response(
                        {"error": "Invalid talents format"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Update producer-specific fields
            if isinstance(user, Producer):
                if 'studio_name' in request.data:
                    user.studio_name = request.data['studio_name']
                if 'website' in request.data:
                    user.website = request.data['website']

            user.save()
            logger.info(f"UpdateProfileView: Successfully updated profile for {email}")

            # Return updated user data
            if isinstance(user, Artist):
                serializer = ArtistSerializer(user, context={'request': request})
            else:
                serializer = ProducerSerializer(user, context={'request': request})

            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"UpdateProfileView Error: {str(e)}")
            return Response(
                {"error": "An error occurred while updating the profile"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# Get All Users
class GetAllUsersView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        artists = Artist.objects.all()
        producers = Producer.objects.all()

        users = []

        for user in artists:
            users.append({
                "id": user.id,
                "username": user.username,
                "nom": user.nom,
                "prenom": user.prenom,
                "email": user.email,
                "profile_picture": user.profile_picture.url if user.profile_picture else None,
                "bio": user.bio,
                "talents": user.talents.split(", ") if user.talents else [],
                "genres": user.genres.split(", ") if user.genres else [],
                "user_type": "artist"
            })

        for user in producers:
            users.append({
                "id": user.id,
                "username": user.username,
                "nom": user.nom,
                "prenom": user.prenom,
                "email": user.email,
                "profile_picture": user.profile_picture.url if user.profile_picture else None,
                "bio": user.bio,
                "studio_name": user.studio_name,
                "website": user.website,
                "genres": user.genres.split(", ") if user.genres else [],
                "user_type": "producer"
            })

        return Response(users, status=200)


from django.core.mail import send_mail
from django.contrib.auth.hashers import make_password
from django.utils.crypto import get_random_string
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.contrib.auth import authenticate
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import get_object_or_404
from .models import Artist, Producer
from .serializers import ArtistSerializer, ProducerSerializer
from rest_framework.parsers import MultiPartParser, FormParser
import logging

logger = logging.getLogger(__name__)

from rest_framework_simplejwt.views import TokenRefreshView as BaseTokenRefreshView

class CustomTokenRefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        try:
            logger.info("TokenRefreshView: Attempting to refresh token")

            # Check if refresh token is provided
            refresh_token = request.data.get('refresh')
            if not refresh_token:
                logger.error("TokenRefreshView: No refresh token provided")
                return Response(
                    {"error": "No refresh token provided", "code": "token_not_provided"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Log token info for debugging (don't log the full token in production)
            logger.info(f"TokenRefreshView: Refresh token provided (first 10 chars): {refresh_token[:10]}...")

            # Decode the refresh token
            try:
                # Decode token manually without token verification (we'll verify it in the next step)
                decoded_token = jwt.decode(
                    refresh_token,
                    settings.SIMPLE_JWT['SIGNING_KEY'],
                    algorithms=[settings.SIMPLE_JWT['ALGORITHM']]
                )

                # Verify token type
                if decoded_token.get('token_type') != 'refresh':
                    logger.error("TokenRefreshView: Invalid token type - not a refresh token")
                    return Response(
                        {"error": "Invalid token type", "code": "invalid_token_type"},
                        status=status.HTTP_401_UNAUTHORIZED
                    )

                # Check if token is expired
                exp = decoded_token.get('exp')
                now = datetime.datetime.utcnow().timestamp()
                if exp is None or now > exp:
                    logger.error("TokenRefreshView: Refresh token has expired")
                    return Response(
                        {"error": "Refresh token expired", "code": "token_expired"},
                        status=status.HTTP_401_UNAUTHORIZED
                    )

                # Extract user info from token
                user_id = decoded_token.get('user_id')
                user_type = decoded_token.get('user_type')
                username = decoded_token.get('username')
                email = decoded_token.get('email')

                if not user_id or not user_type:
                    logger.error("TokenRefreshView: Missing required claims in token")
                    return Response(
                        {"error": "Invalid token - missing required claims", "code": "invalid_token"},
                        status=status.HTTP_401_UNAUTHORIZED
                    )

                # Get the user to verify they exist
                user = None
                if user_type == 'artist':
                    user = Artist.objects.filter(id=user_id).first()
                else:
                    user = Producer.objects.filter(id=user_id).first()

                if not user:
                    logger.error(f"TokenRefreshView: User not found - ID: {user_id}, Type: {user_type}")
                    return Response(
                        {"error": "User not found", "code": "user_not_found"},
                        status=status.HTTP_401_UNAUTHORIZED
                    )

                # Generate a new access token
                access_payload = {
                    "user_type": user_type,
                    "user_id": user_id,
                    "username": username,
                    "email": email,
                    "token_type": "access",
                    "exp": datetime.datetime.utcnow() + settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'],
                    "iat": datetime.datetime.utcnow(),
                    "jti": uuid.uuid4().hex
                }

                access_token = jwt.encode(
                    access_payload,
                    settings.SIMPLE_JWT['SIGNING_KEY'],
                    algorithm=settings.SIMPLE_JWT['ALGORITHM']
                )

                # Check if we need to rotate the refresh token
                if settings.SIMPLE_JWT.get('ROTATE_REFRESH_TOKENS', False):
                    # Generate new refresh token
                    refresh_payload = {
                        "user_type": user_type,
                        "user_id": user_id,
                        "username": username,
                        "email": email,
                        "token_type": "refresh",
                        "exp": datetime.datetime.utcnow() + settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'],
                        "iat": datetime.datetime.utcnow(),
                        "jti": uuid.uuid4().hex
                    }

                    new_refresh_token = jwt.encode(
                        refresh_payload,
                        settings.SIMPLE_JWT['SIGNING_KEY'],
                        algorithm=settings.SIMPLE_JWT['ALGORITHM']
                    )

                    response_data = {
                        "access": access_token,
                        "refresh": new_refresh_token,
                        "user_id": user_id,
                        "user_type": user_type,
                        "username": username,
                        "email": email
                    }
                else:
                    response_data = {
                        "access": access_token,
                        "user_id": user_id,
                        "user_type": user_type,
                        "username": username,
                        "email": email
                    }

                logger.info("TokenRefreshView: Token refreshed successfully")
                return Response(response_data, status=status.HTTP_200_OK)

            except jwt.ExpiredSignatureError:
                logger.error("TokenRefreshView: Refresh token expired")
                return Response(
                    {"error": "Refresh token expired", "code": "token_expired"},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            except jwt.InvalidTokenError:
                logger.error("TokenRefreshView: Invalid refresh token")
                return Response(
                    {"error": "Invalid refresh token", "code": "token_invalid"},
                    status=status.HTTP_401_UNAUTHORIZED
                )

        except Exception as e:
            logger.error(f"TokenRefreshView: Error refreshing token - {str(e)}")

            return Response(
                {"error": "Failed to refresh token", "code": "refresh_failed", "detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


# Token Validation View
class ValidateTokenView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomJWTAuthentication]

    def get(self, request):
        try:
            # Add direct debug output
            print(f"\n\nVALIDATE TOKEN VIEW ACCESSED\n\n")
            print(f"User: {request.user} ({type(request.user).__name__})")
            print(f"User email: {getattr(request.user, 'email', 'NO EMAIL')}")
            print(f"User is_authenticated: {getattr(request.user, 'is_authenticated', False)}")
            print(f"Auth header: {request.headers.get('Authorization', 'NO AUTH HEADER')[:30]}...")
            user = request.user
            logger.info(f"ValidateTokenView: User authenticated as: {user.email}")
            logger.info(f"ValidateTokenView: User ID: {user.id}")
            logger.info(f"ValidateTokenView: User type: {type(user).__name__}")

            # Get the actual email from the JWT token payload
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                from rest_framework_simplejwt.tokens import AccessToken
                import jwt
                from django.conf import settings

                token = auth_header.split(' ')[1]
                try:
                    # First try to decode with JWT library to see raw payload
                    payload = jwt.decode(
                        token,
                        settings.SIMPLE_JWT['SIGNING_KEY'],
                        algorithms=[settings.SIMPLE_JWT['ALGORITHM']]
                    )
                    logger.info(f"ValidateTokenView: Raw token payload: {payload}")
                    logger.info(f"ValidateTokenView: Token email value: {payload.get('email')}")
                except Exception as e:
                    logger.error(f"ValidateTokenView: Error decoding raw token: {str(e)}")

            # Compare user email to the one in request.user
            if hasattr(user, 'email'):
                # Print exact character comparison to identify any invisible differences
                email = user.email.strip().lower()
                logger.info(f"ValidateTokenView: User email (raw): '{user.email}'")
                logger.info(f"ValidateTokenView: User email (normalized): '{email}'")

                # Create hex representation to spot invisible characters
                hex_email = ' '.join(hex(ord(c))[2:] for c in user.email)
                logger.info(f"ValidateTokenView: User email (hex): {hex_email}")

            # Return token validation success with user info
            return Response({
                "valid": True,
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "username": user.username,
                    "user_type": "artist" if isinstance(user, Artist) else "producer"
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"ValidateTokenView Error: {str(e)}")
            return Response(
                {"valid": False, "error": str(e)},
                status=status.HTTP_401_UNAUTHORIZED
            )


from django.core.mail import send_mail
from django.contrib.auth.hashers import make_password
from django.utils.crypto import get_random_string
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Artist, Producer

class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        if not email:
            return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)

        user = Artist.objects.filter(email=email).first() or Producer.objects.filter(email=email).first()
        if not user:
            return Response({"error": "User with this email does not exist"}, status=status.HTTP_404_NOT_FOUND)

        # Generate a 6-digit reset code
        reset_code = get_random_string(length=6, allowed_chars='1234567890')

        # Save reset code in database
        user.reset_code = reset_code
        user.save()

        # Send email with reset code
        send_mail(
            "Password Reset Code",
            f"Your password reset code is: {reset_code}",
            "no-reply@yourapp.com",
            [email],
            fail_silently=False,
        )

        return Response({"message": "Reset code sent successfully"}, status=status.HTTP_200_OK)


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        code = request.data.get("code")
        new_password = request.data.get("new_password")

        if not email or not code or not new_password:
            return Response({"error": "All fields are required"}, status=status.HTTP_400_BAD_REQUEST)

        user = Artist.objects.filter(email=email, reset_code=code).first() or Producer.objects.filter(email=email, reset_code=code).first()
        if not user:
            return Response({"error": "Invalid reset code"}, status=status.HTTP_400_BAD_REQUEST)

        # Reset the password and clear the reset code
        user.password = make_password(new_password)
        user.reset_code = None
        user.save()

        return Response({"message": "Password updated successfully"}, status=status.HTTP_200_OK)


from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from .models import Artist, Producer
from django.http import JsonResponse

class ExploreFeedView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        artists = Artist.objects.all()
        producers = Producer.objects.all()

        feed = []
        for artist in artists:
            feed.append({
                "id": artist.id,
                "username": artist.username,
                "image": artist.profile_picture.url if artist.profile_picture else None,
                "caption": artist.bio if artist.bio else "No bio available.",
                "likes": 120,  # Dummy likes
                "comments": 45,  # Dummy comments
            })

        for producer in producers:
            feed.append({
                "id": producer.id,
                "username": producer.username,
                "image": producer.profile_picture.url if producer.profile_picture else None,
                "caption": producer.bio if producer.bio else "No bio available.",
                "likes": 220,
                "comments": 78,
            })

        return JsonResponse(feed, safe=False)


class DiscoverView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [CustomJWTAuthentication]  # Allow authentication but don't require it

    def get(self, request):
        try:
            user_type = request.query_params.get('type', 'all')  # 'artist', 'producer', or 'all'
            search_query = request.query_params.get('search', '')
            genre = request.query_params.get('genre', '')

            artists_queryset = Artist.objects.all()
            producers_queryset = Producer.objects.all()

            # Exclude the current user if they are authenticated
            if request.user and request.user.is_authenticated:
                logger.info(f"DiscoverView: Excluding authenticated user {request.user.username} (ID: {request.user.id})")

                if isinstance(request.user, Artist):
                    # Current user is an artist, exclude them from artists queryset
                    artists_queryset = artists_queryset.exclude(id=request.user.id)
                    logger.info(f"DiscoverView: Excluded artist with ID {request.user.id} from results")

                elif isinstance(request.user, Producer):
                    # Current user is a producer, exclude them from producers queryset
                    producers_queryset = producers_queryset.exclude(id=request.user.id)
                    logger.info(f"DiscoverView: Excluded producer with ID {request.user.id} from results")

            # Apply search filter if provided
            if search_query:
                artists_queryset = artists_queryset.filter(
                    models.Q(username__icontains=search_query) |
                    models.Q(nom__icontains=search_query) |
                    models.Q(prenom__icontains=search_query) |
                    models.Q(bio__icontains=search_query) |
                    models.Q(talents__icontains=search_query)
                )
                producers_queryset = producers_queryset.filter(
                    models.Q(username__icontains=search_query) |
                    models.Q(nom__icontains=search_query) |
                    models.Q(prenom__icontains=search_query) |
                    models.Q(bio__icontains=search_query) |
                    models.Q(studio_name__icontains=search_query)
                )

            # Apply genre filter if provided
            if genre:
                artists_queryset = artists_queryset.filter(genres__icontains=genre)
                producers_queryset = producers_queryset.filter(genres__icontains=genre)

            # Filter by user type
            if user_type == 'artist':
                artists = ArtistSerializer(artists_queryset, many=True, context={'request': request}).data
                producers = []
            elif user_type == 'producer':
                artists = []
                producers = ProducerSerializer(producers_queryset, many=True, context={'request': request}).data
            else:  # 'all'
                artists = ArtistSerializer(artists_queryset, many=True, context={'request': request}).data
                producers = ProducerSerializer(producers_queryset, many=True, context={'request': request}).data

            return Response({
                'artists': artists,
                'producers': producers
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Discover Error: {str(e)}")
            return Response(
                {"error": "An error occurred while fetching discover data."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CollaborationRequestView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomJWTAuthentication]

    def post(self, request):
        try:
            # Debug request information
            logger.info(f"==== CREATING COLLABORATION REQUEST ====")
            logger.info(f"User sending request: {request.user.username} (ID: {request.user.id})")
            logger.info(f"User type: {'Artist' if isinstance(request.user, Artist) else 'Producer'}")
            logger.info(f"Request data: {request.data}")

            # Support both parameter formats for backward compatibility
            # Old format: receiver (ID only)
            # New format: receiver_id + receiver_type

            # Try to get receiver_id and receiver_type from request
            receiver_id = request.data.get('receiver_id')
            # If receiver_id is not present, try the old format
            if not receiver_id:
                receiver_id = request.data.get('receiver')
                logger.info(f"Using legacy parameter 'receiver': {receiver_id}")

            receiver_type = request.data.get('receiver_type', '').lower()  # 'artist' or 'producer'

            logger.info(f"Processed parameters - Receiver ID: {receiver_id}, Receiver type: {receiver_type}")

            if not receiver_id:
                logger.warning("No receiver_id/receiver provided in request")
                return Response(
                    {"error": "Receiver ID is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # If no receiver_type was provided, default to 'producer' for backward compatibility
            if not receiver_type:
                receiver_type = 'producer'  # Legacy behavior assumed producer
                logger.info(f"No receiver_type provided, defaulting to 'producer' for backward compatibility")

            if receiver_type not in ['artist', 'producer']:
                logger.warning(f"Invalid receiver_type: {receiver_type}")
                return Response(
                    {"error": "Valid receiver_type is required ('artist' or 'producer')"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Determine the sender type (current user)
            sender_is_artist = isinstance(request.user, Artist)

            # Find the receiver based on type
            receiver = None
            if receiver_type == 'artist':
                receiver = Artist.objects.filter(id=receiver_id).first()

                # Check if user is trying to send a request to themselves
                if sender_is_artist and request.user.id == int(receiver_id):
                    logger.warning(f"User attempted to send collaboration request to themselves: {request.user.username}")
                    return Response(
                        {"error": "You cannot send a collaboration request to yourself"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                if receiver:
                    logger.info(f"Found artist receiver: {receiver.username} (ID: {receiver.id})")
                else:
                    logger.warning(f"Could not find artist with ID: {receiver_id}")
            else:  # producer
                receiver = Producer.objects.filter(id=receiver_id).first()

                # Check if user is trying to send a request to themselves
                if not sender_is_artist and request.user.id == int(receiver_id):
                    logger.warning(f"User attempted to send collaboration request to themselves: {request.user.username}")
                    return Response(
                        {"error": "You cannot send a collaboration request to yourself"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                if receiver:
                    logger.info(f"Found producer receiver: {receiver.username} (ID: {receiver.id})")
                else:
                    logger.warning(f"Could not find producer with ID: {receiver_id}")

            if not receiver:
                # Try both types as a last resort if type was auto-assigned
                if receiver_type == 'producer' and not request.data.get('receiver_type'):
                    # For legacy calls without receiver_type, also check artist
                    fallback_receiver = Artist.objects.filter(id=receiver_id).first()
                    if fallback_receiver:
                        logger.info(f"Found artist receiver as fallback: {fallback_receiver.username} (ID: {fallback_receiver.id})")
                        receiver = fallback_receiver
                        receiver_type = 'artist'

            if not receiver:
                logger.error(f"Collaboration Request Error: Receiver ID {receiver_id} not found as {receiver_type}")
                return Response(
                    {"error": f"Receiver not found with ID {receiver_id}"},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Validate message content
            message = request.data.get('message', '')
            if not message or len(message.strip()) == 0:
                logger.warning("Empty message provided")
                return Response(
                    {"error": "Message is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            logger.info(f"Message: {message[:50]}{'...' if len(message) > 50 else ''}")

            # Create a new collaboration request
            collab_request = CollaborationRequest(
                message=message
            )

            # Set sender fields based on current user type
            if sender_is_artist:
                logger.info(f"Setting sender as artist: {request.user.username}")
                collab_request.sender_artist = request.user
                collab_request.sender_producer = None
            else:
                logger.info(f"Setting sender as producer: {request.user.username}")
                collab_request.sender_producer = request.user
                collab_request.sender_artist = None

            # Set receiver fields based on type
            if receiver_type == 'artist':
                logger.info(f"Setting receiver as artist: {receiver.username}")
                collab_request.receiver_artist = receiver
                collab_request.receiver_producer = None
            else:
                logger.info(f"Setting receiver as producer: {receiver.username}")
                collab_request.receiver_producer = receiver
                collab_request.receiver_artist = None

            # Save to database
            try:
                collab_request.save()
                logger.info(f"Successfully saved collaboration request with ID: {collab_request.id}")

                # Create a notification for the receiver
                notification = Notification()
                if receiver_type == 'artist':
                    notification.artist = receiver
                else:
                    notification.producer = receiver

                notification.notification_type = 'collaboration_request'
                notification.message = f"{request.user.username} sent you a collaboration request"
                notification.related_id = collab_request.id
                notification.save()

                logger.info(f"Created notification for {receiver.username} about new collaboration request")

            except Exception as save_error:
                logger.error(f"Error saving collaboration request: {str(save_error)}")
                return Response(
                    {"error": f"Error saving request: {str(save_error)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # Create response
            sender_type = 'artist' if sender_is_artist else 'producer'
            logger.info(f"Collaboration request created: {sender_type} {request.user.username} to {receiver_type} {receiver.username}")

            # Use serializer to return response data
            serializer = CollaborationRequestSerializer(collab_request)
            logger.info(f"==== END CREATING COLLABORATION REQUEST ====")
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Collaboration Request Error: {str(e)}")
            return Response(
                {"error": "An error occurred while creating the collaboration request."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def get(self, request):
        try:
            # Debug user information
            logger.info(f"==== COLLABORATION REQUESTS DEBUG ====")
            logger.info(f"User requesting collaboration requests: {request.user.username} (ID: {request.user.id})")
            user_is_artist = isinstance(request.user, Artist)
            logger.info(f"User type: {'Artist' if user_is_artist else 'Producer'}")

            # Find requests that involve this user (both sent and received)
            # For improved performance, we'll build the query specifically for the user type
            if user_is_artist:
                logger.info(f"Fetching collaboration requests for artist: {request.user.username}")
                # This user is an artist, so look at sender_artist and receiver_artist
                sent_requests = CollaborationRequest.objects.filter(sender_artist=request.user)
                received_requests = CollaborationRequest.objects.filter(receiver_artist=request.user)
            else:
                logger.info(f"Fetching collaboration requests for producer: {request.user.username}")
                # This user is a producer, so look at sender_producer and receiver_producer
                sent_requests = CollaborationRequest.objects.filter(sender_producer=request.user)
                received_requests = CollaborationRequest.objects.filter(receiver_producer=request.user)

            # Debug the queries
            logger.info(f"Sent requests query: {sent_requests.query}")
            logger.info(f"Sent requests count: {sent_requests.count()}")
            for req in sent_requests:
                receiver = req.receiver_artist or req.receiver_producer
                logger.info(f"  - Sent to: {receiver.username if receiver else 'Unknown'}, status: {req.status}")

            logger.info(f"Received requests query: {received_requests.query}")
            logger.info(f"Received requests count: {received_requests.count()}")
            for req in received_requests:
                sender = req.sender_artist or req.sender_producer
                logger.info(f"  - Received from: {sender.username if sender else 'Unknown'}, status: {req.status}")

            # Get all requests involving this user
            all_requests = sent_requests.union(received_requests).order_by('-created_at')
            logger.info(f"Total unique requests: {all_requests.count()}")

            # Format the response
            sent_data = CollaborationRequestSerializer(sent_requests, many=True).data
            received_data = CollaborationRequestSerializer(received_requests, many=True).data
            all_data = CollaborationRequestSerializer(all_requests, many=True).data

            logger.info(f"Response data counts - sent: {len(sent_data)}, received: {len(received_data)}, all: {len(all_data)}")
            logger.info(f"==== END COLLABORATION REQUESTS DEBUG ====")

            # Return the response with sent, received, and all requests
            return Response({
                "sent": sent_data,
                "received": received_data,
                "all": all_data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Get Collaboration Requests Error: {str(e)}")
            return Response(
                {"error": "An error occurred while fetching collaboration requests."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def delete(self, request, request_id=None):
        """
        Delete a specific collaboration request
        """
        try:
            if not request_id:
                return Response(
                    {"error": "Collaboration request ID is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            logger.info(f"Attempting to delete collaboration request with ID: {request_id}")

            # Find the collaboration request
            try:
                collab_request = CollaborationRequest.objects.get(id=request_id)
            except CollaborationRequest.DoesNotExist:
                logger.warning(f"Collaboration request not found with ID: {request_id}")
                return Response(
                    {"error": f"Collaboration request with ID {request_id} not found"},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Security check: Make sure the user is either the sender or receiver
            current_user = request.user
            user_is_sender = False
            user_is_receiver = False

            # Check if user is sender
            if isinstance(current_user, Artist) and collab_request.sender_artist == current_user:
                user_is_sender = True
            elif isinstance(current_user, Producer) and collab_request.sender_producer == current_user:
                user_is_sender = True

            # Check if user is receiver
            if isinstance(current_user, Artist) and collab_request.receiver_artist == current_user:
                user_is_receiver = True
            elif isinstance(current_user, Producer) and collab_request.receiver_producer == current_user:
                user_is_receiver = True

            if not (user_is_sender or user_is_receiver):
                logger.warning(f"User {current_user.username} attempted to delete a request they're not involved in: {request_id}")
                return Response(
                    {"error": "You don't have permission to delete this collaboration request"},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Delete the collaboration request
            collab_request.delete()
            logger.info(f"Successfully deleted collaboration request {request_id}")

            # Also delete any related notifications
            if user_is_sender or user_is_receiver:
                notifications = Notification.objects.filter(related_id=request_id)
                count = notifications.count()
                notifications.delete()
                logger.info(f"Deleted {count} notifications related to collaboration request {request_id}")

            return Response(
                {"success": True, "message": f"Collaboration request with ID {request_id} has been deleted"},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            logger.error(f"Error deleting collaboration request: {str(e)}")
            return Response(
                {"error": f"An error occurred while deleting the collaboration request: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CollaborationRequestActionView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomJWTAuthentication]

    def post(self, request, request_id):
        try:
            action = request.data.get('action', '').lower()
            if action not in ['accept', 'reject']:
                logger.warning(f"Invalid action attempted: {action}")
                return Response(
                    {"error": "Invalid action. Must be 'accept' or 'reject'"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get the collaboration request
            try:
                collab_request = CollaborationRequest.objects.get(id=request_id)
            except CollaborationRequest.DoesNotExist:
                logger.error(f"Collaboration request not found: {request_id}")
                return Response(
                    {"error": f"Collaboration request not found with ID {request_id}"},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Verify the current user is the intended receiver
            current_user = request.user
            is_artist = isinstance(current_user, Artist)

            # Check if the current user is the receiver of this request
            is_receiver = False
            if is_artist and collab_request.receiver_artist == current_user:
                is_receiver = True
            elif not is_artist and collab_request.receiver_producer == current_user:
                is_receiver = True

            # Ensure only the receiver can accept/reject requests
            if not is_receiver:
                logger.warning(f"User {current_user.username} attempted to action a request they didn't receive: {request_id}")
                return Response(
                    {"error": "You can only respond to collaboration requests sent to you"},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Update the request status based on the action
            collab_request.status = 'accepted' if action == 'accept' else 'rejected'
            collab_request.updated_at = timezone.now()
            collab_request.save()

            logger.info(f"Collaboration request {request_id} {action}ed by {current_user.username}")

            # If request is accepted, increment collaboration count for both users
            if action == 'accept':
                # Get sender and receiver
                sender = collab_request.sender_artist or collab_request.sender_producer
                receiver = collab_request.receiver_artist or collab_request.receiver_producer

                if sender and receiver:
                    # Increment collaboration counts
                    sender.collaboration_count += 1
                    receiver.collaboration_count += 1

                    # Save changes
                    sender.save(update_fields=['collaboration_count'])
                    receiver.save(update_fields=['collaboration_count'])

                    logger.info(f"Incremented collaboration counts for {sender.username} and {receiver.username}")

            # Create a notification for the sender
            sender = collab_request.sender_artist or collab_request.sender_producer
            if sender:
                # Determine which notification model to use based on sender type
                notification = Notification()
                if isinstance(sender, Artist):
                    notification.artist = sender
                else:
                    notification.producer = sender

                # Set notification details
                notification.notification_type = 'collaboration_update'
                notification.message = f"Your collaboration request to {current_user.username} has been {action}ed"
                notification.related_id = collab_request.id
                notification.save()

                logger.info(f"Created notification for {sender.username} about collaboration request {action}")

            # Return the updated collaboration request
            serializer = CollaborationRequestSerializer(collab_request)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"CollaborationRequestActionView Error: {str(e)}")
            return Response(
                {"error": "An error occurred while processing the collaboration request action"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# Add this after CollaborationRequestActionView
class TestCollaborationRequestsView(APIView):
    permission_classes = [AllowAny]  # Allow without authentication for testing

    def get(self, request):
        """Test endpoint to debug collaboration requests"""
        try:
            # Check all collaboration requests in the system
            all_requests = CollaborationRequest.objects.all().order_by('-created_at')

            results = {
                "total_count": all_requests.count(),
                "requests": []
            }

            for req in all_requests:
                sender = None
                sender_type = None
                if req.sender_artist:
                    sender = req.sender_artist
                    sender_type = "artist"
                elif req.sender_producer:
                    sender = req.sender_producer
                    sender_type = "producer"

                receiver = None
                receiver_type = None
                if req.receiver_artist:
                    receiver = req.receiver_artist
                    receiver_type = "artist"
                elif req.receiver_producer:
                    receiver = req.receiver_producer
                    receiver_type = "producer"

                results["requests"].append({
                    "id": req.id,
                    "created_at": req.created_at,
                    "status": req.status,
                    "message": req.message[:50] + ("..." if len(req.message) > 50 else ""),
                    "sender": {
                        "id": sender.id if sender else None,
                        "username": sender.username if sender else "Unknown",
                        "type": sender_type
                    },
                    "receiver": {
                        "id": receiver.id if receiver else None,
                        "username": receiver.username if receiver else "Unknown",
                        "type": receiver_type
                    }
                })

            return Response(results, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Test Collaboration Requests Error: {str(e)}")
            return Response({
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        """Test endpoint to create a collaboration request directly"""
        try:
            sender_type = request.data.get('sender_type')
            sender_id = request.data.get('sender_id')
            receiver_type = request.data.get('receiver_type')
            receiver_id = request.data.get('receiver_id')
            message = request.data.get('message', 'Test collaboration request')

            if not sender_type or not sender_id or not receiver_type or not receiver_id:
                return Response({
                    "error": "Missing required fields",
                    "required": ["sender_type", "sender_id", "receiver_type", "receiver_id"]
                }, status=status.HTTP_400_BAD_REQUEST)

            # Find sender
            sender = None
            if sender_type == 'artist':
                sender = Artist.objects.filter(id=sender_id).first()
            else:
                sender = Producer.objects.filter(id=sender_id).first()

            if not sender:
                return Response({"error": f"Sender not found with ID {sender_id}"}, status=status.HTTP_404_NOT_FOUND)

            # Find receiver
            receiver = None
            if receiver_type == 'artist':
                receiver = Artist.objects.filter(id=receiver_id).first()
            else:
                receiver = Producer.objects.filter(id=receiver_id).first()

            if not receiver:
                return Response({"error": f"Receiver not found with ID {receiver_id}"}, status=status.HTTP_404_NOT_FOUND)

            # Create request
            collab_request = CollaborationRequest(message=message)

            # Set sender
            if sender_type == 'artist':
                collab_request.sender_artist = sender
            else:
                collab_request.sender_producer = sender

            # Set receiver
            if receiver_type == 'artist':
                collab_request.receiver_artist = receiver
            else:
                collab_request.receiver_producer = receiver

            collab_request.save()

            return Response({
                "success": True,
                "message": f"Created collaboration request from {sender.username} to {receiver.username}",
                "request_id": collab_request.id
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Test Create Collaboration Request Error: {str(e)}")
            return Response({
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Notification pagination class
class NotificationPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

# Get and update notifications
class NotificationView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication, CustomJWTAuthentication]  # Add both authentication classes for compatibility
    pagination_class = NotificationPagination

    def get(self, request):
        try:
            # Log authentication info for debugging
            logger.info(f"NotificationView: Request received with auth: {request.auth}")
            logger.info(f"NotificationView: User: {request.user}")
            logger.info(f"NotificationView: User ID: {getattr(request.user, 'id', 'No ID')}")

            # Get the user type and id from the token
            user_id = request.user.id
            user_type = None

            # Determine user type
            if Producer.objects.filter(id=user_id).exists():
                user_type = "producer"
                logger.info(f"NotificationView: User is a producer with ID {user_id}")
            elif Artist.objects.filter(id=user_id).exists():
                user_type = "artist"
                logger.info(f"NotificationView: User is an artist with ID {user_id}")
            else:
                logger.error(f"NotificationView: Could not determine user type for ID {user_id}")
                return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

            # Query notifications based on user type
            if user_type == "producer":
                notifications = Notification.objects.filter(producer_id=user_id)
            else:  # artist
                notifications = Notification.objects.filter(artist_id=user_id)

            logger.info(f"NotificationView: Found {notifications.count()} notifications for {user_type} with ID {user_id}")

            # Log all notifications for debugging
            for notification in notifications:
                logger.info(f"NotificationView: Notification {notification.id}: {notification.notification_type} - {notification.message}")

            # Get notification type filter if provided
            notification_type = request.query_params.get('type')
            if notification_type:
                notifications = notifications.filter(notification_type=notification_type)
                logger.info(f"NotificationView: Filtered by type {notification_type}, now have {notifications.count()} notifications")

            # Get unread filter if provided
            unread_only = request.query_params.get('unread')
            if unread_only and unread_only.lower() == 'true':
                notifications = notifications.filter(read=False)
                logger.info(f"NotificationView: Filtered by unread, now have {notifications.count()} notifications")

            # Apply pagination
            paginator = self.pagination_class()
            paginated_notifications = paginator.paginate_queryset(notifications, request)

            # Serialize notifications
            serializer = NotificationSerializer(paginated_notifications, many=True, context={'request': request})

            # Return paginated response
            return paginator.get_paginated_response(serializer.data)

        except Exception as e:
            logger.error(f"NotificationView Error: {str(e)}")
            logger.error(traceback.format_exc())  # Log the full stack trace
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def put(self, request):
        """Mark all notifications as read"""
        try:
            user_id = request.user.id
            user_type = None

            # Determine user type
            if Producer.objects.filter(id=user_id).exists():
                user_type = "producer"
            elif Artist.objects.filter(id=user_id).exists():
                user_type = "artist"
            else:
                return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

            # Update all notifications to read based on user type
            if user_type == "producer":
                Notification.objects.filter(producer_id=user_id).update(read=True)
            else:  # artist
                Notification.objects.filter(artist_id=user_id).update(read=True)

            return Response({"message": "All notifications marked as read"}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error marking notifications as read: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Mark a single notification as read
class MarkNotificationReadView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication, CustomJWTAuthentication]

    def post(self, request, notification_id):
        try:
            # Log authentication info for debugging
            logger.info(f"MarkNotificationReadView: User ID: {getattr(request.user, 'id', 'No ID')}")

            user_id = request.user.id

            # Find the notification and ensure it belongs to this user
            notification = None
            try:
                # Check if user is a producer
                if Producer.objects.filter(id=user_id).exists():
                    notification = Notification.objects.get(id=notification_id, producer_id=user_id)
                    logger.info(f"MarkNotificationReadView: Found notification for producer {user_id}")
                # Check if user is an artist
                elif Artist.objects.filter(id=user_id).exists():
                    notification = Notification.objects.get(id=notification_id, artist_id=user_id)
                    logger.info(f"MarkNotificationReadView: Found notification for artist {user_id}")
            except Notification.DoesNotExist:
                logger.warning(f"MarkNotificationReadView: Notification {notification_id} not found for user {user_id}")
                return Response(
                    {"error": "Notification not found or you don't have permission to access it"},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Mark as read
            notification.read = True
            notification.save()
            logger.info(f"MarkNotificationReadView: Marked notification {notification_id} as read")

            return Response(
                {"success": True, "message": "Notification marked as read"},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            logger.error(f"MarkNotificationReadView Error: {str(e)}")
            logger.error(traceback.format_exc())
            return Response(
                {"error": f"Failed to mark notification as read: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# Delete a notification
class DeleteNotificationView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication, CustomJWTAuthentication]

    def delete(self, request, notification_id):
        try:
            # Log authentication info for debugging
            logger.info(f"DeleteNotificationView: User ID: {getattr(request.user, 'id', 'No ID')}")

            user_id = request.user.id

            # Find the notification and ensure it belongs to this user
            notification = None
            try:
                # Check if user is a producer
                if Producer.objects.filter(id=user_id).exists():
                    notification = Notification.objects.get(id=notification_id, producer_id=user_id)
                    logger.info(f"DeleteNotificationView: Found notification for producer {user_id}")
                # Check if user is an artist
                elif Artist.objects.filter(id=user_id).exists():
                    notification = Notification.objects.get(id=notification_id, artist_id=user_id)
                    logger.info(f"DeleteNotificationView: Found notification for artist {user_id}")
            except Notification.DoesNotExist:
                logger.warning(f"DeleteNotificationView: Notification {notification_id} not found for user {user_id}")
                return Response(
                    {"error": "Notification not found or you don't have permission to delete it"},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Delete the notification
            notification.delete()
            logger.info(f"DeleteNotificationView: Deleted notification {notification_id}")

            return Response(
                {"success": True, "message": "Notification deleted successfully"},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            logger.error(f"DeleteNotificationView Error: {str(e)}")
            logger.error(traceback.format_exc())
            return Response(
                {"error": f"Failed to delete notification: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# Google login view for OAuth process
class GoogleLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            # Get the id_token from the request
            id_token = request.data.get('id_token')
            if not id_token:
                return Response({'error': 'No token provided'}, status=status.HTTP_400_BAD_REQUEST)

            # Verify the token with Google
            from google.oauth2 import id_token as google_id_token
            from google.auth.transport import requests as google_requests

            # Get the Google client ID from the database
            try:
                google_app = SocialApp.objects.get(provider='google')
                client_id = google_app.client_id
            except SocialApp.DoesNotExist:
                return Response(
                    {'error': 'Google OAuth not configured properly'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            try:
                # Verify the token
                idinfo = google_id_token.verify_oauth2_token(
                    id_token, google_requests.Request(), client_id
                )

                # Get user info from the token
                email = idinfo['email']
                if not email:
                    return Response({'error': 'Email not provided by Google'}, status=status.HTTP_400_BAD_REQUEST)

                # Check if user exists
                artist_user = Artist.objects.filter(email=email).first()
                producer_user = Producer.objects.filter(email=email).first()

                # For simplicity, we'll prioritize Artist accounts over Producer accounts
                user = artist_user or producer_user

                if not user:
                    # User doesn't exist, create a new one
                    # For this example we'll create an Artist account
                    # Get user info from Google
                    first_name = idinfo.get('given_name', '')
                    last_name = idinfo.get('family_name', '')
                    picture = idinfo.get('picture', '')
                    username = email.split('@')[0]  # Create username from email

                    # Ensure username is unique
                    base_username = username
                    i = 1
                    while Artist.objects.filter(username=username).exists() or Producer.objects.filter(username=username).exists():
                        username = f"{base_username}{i}"
                        i += 1

                    # Create new user
                    import secrets
                    random_password = secrets.token_urlsafe(16)  # Generate a random password

                    user = Artist.objects.create(
                        username=username,
                        email=email,
                        nom=last_name,
                        prenom=first_name,
                        password=random_password  # This will be hashed in the save method
                    )

                    # If there's a profile picture, download and save it
                    if picture:
                        from django.core.files.base import ContentFile
                        import requests as req
                        response = req.get(picture)
                        if response.status_code == 200:
                            user.profile_picture.save(
                                f"{username}_profile.jpg",
                                ContentFile(response.content),
                                save=True
                            )

                # Generate tokens for user
                from rest_framework_simplejwt.tokens import RefreshToken
                refresh = RefreshToken.for_user(user)

                return Response({
                    'user': {
                        'id': user.id,
                        'username': user.username,
                        'email': user.email,
                        'user_type': 'artist' if isinstance(user, Artist) else 'producer',
                        'profile_picture': user.profile_picture.url if user.profile_picture else None,
                    },
                    'tokens': {
                        'refresh': str(refresh),
                        'access': str(refresh.access_token),
                    }
                }, status=status.HTTP_200_OK)

            except ValueError:
                # Invalid token
                return Response({'error': 'Invalid token'}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
