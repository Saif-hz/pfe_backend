from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from .models import Project
from .serializers import ProjectSerializer
from .permissions import IsProducer
from users.models import Producer
from django.contrib.auth.models import User
import logging
from django.db import transaction

logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def debug_user(request):
    """Debug endpoint to identify authentication issues"""
    data = {
        'user_id': request.user.id,
        'username': request.user.username if hasattr(request.user, 'username') else None,
        'auth_header': request.META.get('HTTP_AUTHORIZATION', '').startswith('Bearer '),
        'producer_exists': Producer.objects.filter(id=request.user.id).exists(),
        'all_producer_ids': list(Producer.objects.values_list('id', flat=True)[:10])  # First 10 producer IDs
    }
    return Response(data)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def debug_project_permission(request):
    """Debug endpoint to check if a user can create projects"""
    producer_check = IsProducer()
    can_create = producer_check.has_permission(request, None)
    
    producer_exists = Producer.objects.filter(id=request.user.id).exists()
    
    data = {
        'user_id': request.user.id,
        'username': request.user.username if hasattr(request.user, 'username') else None,
        'can_create_projects': can_create,
        'producer_exists': producer_exists,
        'user_type': getattr(request.user, 'user_type', 'unknown'),
        'all_producer_ids': list(Producer.objects.values_list('id', flat=True)[:20])  # First 20 producer IDs
    }
    return Response(data)

@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def check_producer_1000000(request):
    """Debug endpoint to specifically check producer ID 1000000"""
    producer_exists = Producer.objects.filter(id=1000000).exists()
    
    producer_details = None
    if producer_exists:
        producer = Producer.objects.get(id=1000000)
        producer_details = {
            'id': producer.id,
            'username': producer.username,
            'email': producer.email
        }
    
    data = {
        'producer_exists': producer_exists,
        'producer_details': producer_details,
        'all_producer_ids': list(Producer.objects.values_list('id', flat=True)[:30])  # First 30 producer IDs
    }
    return Response(data)

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def fix_producer_1000000(request):
    """Endpoint to fix producer ID 1000000 if needed"""
    try:
        # Check if a producer with ID 1000000 already exists
        producer_exists = Producer.objects.filter(id=1000000).exists()
        
        if producer_exists:
            return Response({
                'status': 'producer_exists',
                'message': 'Producer with ID 1000000 already exists'
            })
        
        # Try to find a user with this ID first (in case there's a general User model)
        user = None
        try:
            # This assumes you have a User model imported - adjust if needed
            user = User.objects.filter(id=1000000).first()
        except:
            user = None
        
        # Create or update the producer
        with transaction.atomic():
            if not user:
                # Create a new producer with ID 1000000
                producer = Producer(
                    id=1000000,
                    username="hamza",
                    email="bouchnek@gmail.com",
                    # Set other required fields here
                )
                # Set password if needed
                producer.set_password("1234")  # Set a default password
                producer.save()
                logger.info(f"Created new producer with ID 1000000")
            else:
                # Create a producer entry with same data as user
                producer = Producer(
                    id=1000000,
                    username=getattr(user, 'username', 'hamza'),
                    email=getattr(user, 'email', 'bouchnek@gmail.com'),
                    # Copy other fields as needed
                )
                producer.set_password("1234")  # Set a default password
                producer.save()
                logger.info(f"Created producer from existing user with ID 1000000")
        
        return Response({
            'status': 'success',
            'message': 'Producer with ID 1000000 has been created or fixed',
            'producer_details': {
                'id': producer.id,
                'username': producer.username,
                'email': producer.email
            }
        })
    except Exception as e:
        logger.error(f"Error fixing producer: {str(e)}")
        return Response({
            'status': 'error',
            'message': f'Error fixing producer: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ProjectViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing projects.
    """
    queryset = Project.objects.all().order_by('-created_at')
    serializer_class = ProjectSerializer

    def get_permissions(self):
        """
        Only producers can create, update or delete projects.
        Any authenticated user can view projects.
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsProducer]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        """
        Set the created_by_producer field to the current producer
        """
        try:
            # Get the current user
            user = self.request.user
            logger.info(f"Project create attempt by user ID: {user.id}")
            
            # Check if user has a user_type attribute from JWT token
            user_type = getattr(user, 'user_type', None)
            
            # If user_type is set to producer from JWT, use the user directly
            if user_type and user_type.lower() == 'producer':
                # Try to get the producer object
                try:
                    producer = Producer.objects.get(id=user.id)
                    logger.info(f"Found producer by JWT user_type: {producer.username}")
                    serializer.save(created_by_producer=producer)
                    return
                except Producer.DoesNotExist:
                    # This is unlikely to happen if permissions are working properly
                    logger.warning(f"User has producer type in JWT but not in database, ID: {user.id}")
            
            # Otherwise check if user exists in Producer model
            producer = Producer.objects.get(id=user.id)
            logger.info(f"Found producer in database: {producer.username}")
            serializer.save(created_by_producer=producer)
            
        except Producer.DoesNotExist:
            # This shouldn't happen since permissions should prevent non-producers
            # from reaching this point, but just in case
            logger.error(f"Producer not found for user ID: {self.request.user.id}")
            raise Response(
                {"detail": "You must be a producer to create projects.", "code": "producer_required"},
                status=status.HTTP_403_FORBIDDEN
            )
    
    def create(self, request, *args, **kwargs):
        """
        Override create to add better error handling
        """
        try:
            logger.info(f"Project creation started by user ID: {self.request.user.id}")
            serializer = self.get_serializer(data=request.data)
            
            if not serializer.is_valid():
                logger.error(f"Project validation errors: {serializer.errors}")
                return Response(
                    {"detail": serializer.errors, "code": "validation_error"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            logger.info(f"Project created successfully with ID: {serializer.data.get('id')}")
            return Response(
                serializer.data, 
                status=status.HTTP_201_CREATED, 
                headers=headers
            )
        except Exception as e:
            logger.error(f"Error creating project: {str(e)}")
            if isinstance(e, Response):
                return e
            return Response(
                {"detail": "Error creating project", "code": "project_creation_error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            ) 