from django.contrib.auth.backends import BaseBackend
from .models import Artist, Producer
from django.contrib.auth.hashers import check_password
import logging

logger = logging.getLogger(__name__)

class CustomUserBackend(BaseBackend):
    """
    Custom authentication backend that checks both Artists and Producers.
    """

    def authenticate(self, request, email=None, password=None, **kwargs):
        logger.debug(f"CustomUserBackend.authenticate called with email: {email}")
        
        try:
            user = Artist.objects.get(email=email)
            logger.info(f"Found Artist with email {email}")
        except Artist.DoesNotExist:
            try:
                user = Producer.objects.get(email=email)
                logger.info(f"Found Producer with email {email}")
            except Producer.DoesNotExist:
                logger.warning(f"No user found with email {email}")
                return None  # No user found

        # 🔥 Check password
        if check_password(password, user.password):
            logger.info(f"Password matched for user {email}")
            return user
        
        logger.warning(f"Password did not match for user {email}")
        return None

    def get_user(self, user_id):
        """
        Used by Django to retrieve the user instance.
        """
        logger.debug(f"CustomUserBackend.get_user called with user_id: {user_id}")
        
        try:
            # Try to determine the model based on ID range
            if isinstance(user_id, int) or user_id.isdigit():
                user_id = int(user_id)
                
                # Check ID range to determine if it's a Producer or Artist
                if user_id >= 1000000:
                    user = Producer.objects.get(pk=user_id)
                    logger.info(f"Found Producer with ID {user_id}")
                    return user
            
            # Default to trying Artist first
            user = Artist.objects.get(pk=user_id)
            logger.info(f"Found Artist with ID {user_id}")
            return user
        except Artist.DoesNotExist:
            try:
                user = Producer.objects.get(pk=user_id)
                logger.info(f"Found Producer with ID {user_id}")
                return user
            except Producer.DoesNotExist:
                logger.warning(f"No user found with ID {user_id}")
                return None
