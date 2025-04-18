from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import UntypedToken
from django.conf import settings
import logging
from rest_framework.authentication import BaseAuthentication
from .models import Artist, Producer
from rest_framework import exceptions
import jwt
from jwt.exceptions import InvalidTokenError, DecodeError
import traceback

logger = logging.getLogger(__name__)

class CustomJWTAuthentication(JWTAuthentication):
    """
    Custom JWT Authentication that properly handles both Artist and Producer user types
    and populates the user's email field from the token payload.
    """
    
    def authenticate(self, request):
        """
        Override the authenticate method to directly handle JWT validation
        """
        try:
            header = self.get_header(request)
            if header is None:
                logger.error("CustomJWT: Authentication failed - No Auth header found")
                return None

            raw_token = self.get_raw_token(header)
            if raw_token is None:
                logger.error("CustomJWT: Authentication failed - No token found in header")
                return None
                
            # Log the raw token (first 10 chars for security)
            token_preview = raw_token.decode()[:10] + "..." if hasattr(raw_token, "decode") else str(raw_token)[:10] + "..."
            logger.info(f"CustomJWT: Processing token (preview): {token_preview}")
            
            # Validate token manually to have more control
            try:
                # Try to decode the token with verification first
                decoded_token = jwt.decode(
                    raw_token,
                    settings.SIMPLE_JWT['SIGNING_KEY'],
                    algorithms=[settings.SIMPLE_JWT['ALGORITHM']]
                )
                logger.info(f"CustomJWT: Token validated successfully, payload: {decoded_token}")
            except (InvalidTokenError, DecodeError) as e:
                logger.error(f"CustomJWT: Token validation failed: {str(e)}")
                return None
                
            # Get the user from the validated token
            try:
                user = self.get_user(decoded_token)
                if user is None:
                    logger.error("CustomJWT: User lookup failed")
                    return None
                    
                logger.info(f"CustomJWT: Authentication successful for user {user.username} (ID: {user.id})")
                return (user, decoded_token)
            except Exception as e:
                logger.error(f"CustomJWT: Error during user lookup: {str(e)}")
                return None
        
        except Exception as e:
            # Log the full exception with traceback for debugging
            logger.error(f"CustomJWT: Unexpected error during authentication: {str(e)}")
            logger.error(traceback.format_exc())
            return None
    
    def get_user(self, validated_token):
        """
        Override the get_user method to properly handle different user types
        and set the email field from token claims
        """
        try:
            # Extract user information from token
            user_id = validated_token.get('user_id')
            user_type = validated_token.get('user_type', '')
            email = validated_token.get('email', '')
            username = validated_token.get('username', '')
            
            logger.info(f"CustomJWT: Token contains user_id={user_id}, user_type={user_type}, email={email}, username={username}")
            
            # Check for required token claims
            if not user_id:
                logger.error("CustomJWT: Token missing user_id claim")
                raise exceptions.AuthenticationFailed({
                    'detail': 'Invalid token - missing user_id',
                    'code': 'invalid_token'
                })
                
            if not user_type:
                # Default to checking both user types if not specified
                logger.warning("CustomJWT: Token missing user_type claim, will check both types")
            
            # Find the user based on user_type and user_id
            user = None
            
            # Try Artist first if user_type is not specified or is 'artist'
            if not user_type or user_type.lower() == 'artist':
                try:
                    user = Artist.objects.get(id=user_id)
                    logger.info(f"CustomJWT: Found Artist with id={user_id}, username={user.username}")
                    # Set the user_type if it wasn't in the token
                    user_type = 'artist'
                except Artist.DoesNotExist:
                    logger.warning(f"CustomJWT: Artist with id={user_id} not found")
            
            # Try Producer if user is still not found or user_type is 'producer'
            if (not user) and (not user_type or user_type.lower() == 'producer'):
                try:
                    user = Producer.objects.get(id=user_id)
                    logger.info(f"CustomJWT: Found Producer with id={user_id}, username={user.username}")
                    # Set the user_type if it wasn't in the token
                    user_type = 'producer'
                except Producer.DoesNotExist:
                    logger.warning(f"CustomJWT: Producer with id={user_id} not found")
            
            if not user:
                logger.error(f"CustomJWT: User not found for user_id={user_id}, user_type={user_type}")
                raise exceptions.AuthenticationFailed({
                    'detail': 'User not found',
                    'code': 'user_not_found'
                })
            
            # Ensure the user has an email attribute
            if hasattr(user, 'email') and (not user.email or user.email.strip() == ""):
                user.email = email
                logger.info(f"CustomJWT: Updated user email to: '{email}'")
            
            # Ensure username is set correctly if provided in token
            if username and hasattr(user, 'username') and user.username != username:
                logger.warning(f"CustomJWT: Username mismatch - Token: '{username}', DB: '{user.username}'")
                # Don't override database username, but log the discrepancy
            
            # Add user_type attribute to the user object for convenience
            user.user_type = user_type
            
            # Make sure the user object has is_authenticated attribute
            if not hasattr(user, 'is_authenticated'):
                logger.info(f"CustomJWT: Adding is_authenticated to user of type {type(user)}")
                user.is_authenticated = True
            
            logger.info(f"CustomJWT: Final user: ID={user.id}, username='{getattr(user, 'username', 'N/A')}', email='{getattr(user, 'email', 'N/A')}', type={user_type}, authenticated={getattr(user, 'is_authenticated', False)}")
            return user
            
        except Exception as e:
            logger.error(f"CustomJWT Error in get_user: {str(e)}")
            logger.error(traceback.format_exc())
            raise
