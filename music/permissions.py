from rest_framework import permissions
from users.models import Producer
import logging

logger = logging.getLogger(__name__)

class IsProducer(permissions.BasePermission):
    """
    Custom permission to only allow producers to create/update/delete projects
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            logger.error(f"IsProducer: User not authenticated")
            return False
        
        logger.info(f"IsProducer: Checking if user {request.user.id} is a producer")
        
        try:
            # Method 1: Check user_type from JWT token
            user_type = getattr(request.user, 'user_type', None)
            if user_type and user_type.lower() == 'producer':
                logger.info(f"IsProducer: User is a producer based on JWT user_type")
                return True
            
            # Method 2: Check if user exists in the Producer model
            exists = Producer.objects.filter(id=request.user.id).exists()
            logger.info(f"IsProducer: User exists in Producer model: {exists}")
            return exists
            
        except Exception as e:
            logger.error(f"IsProducer: Error checking producer role: {str(e)}")
            return False 