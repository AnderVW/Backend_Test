"""
API views for mobile app authentication and asset management
"""
import jwt
import uuid
import redis
from datetime import datetime, timedelta
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from allauth.socialaccount.models import SocialAccount
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from loguru import logger

from .models import ClothingItem, BaseImage, GeneratedImage, GenerationTask, UploadTask
from _libs.lib_azure import AzureBlobClient
from .tasks import detect_clothing_item_params_task, process_generation_task

User = get_user_model()


def generate_jwt_token(user):
    """Generate JWT token for user"""
    payload = {
        'user_id': user.id,
        'email': user.email,
        'exp': datetime.utcnow() + timedelta(days=30),  # Token expires in 30 days
        'iat': datetime.utcnow(),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
    # Ensure token is a string (PyJWT 2.x returns string, but being explicit)
    return str(token) if isinstance(token, bytes) else token


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    """Email/password login endpoint"""
    email = request.data.get('email')
    password = request.data.get('password')
    
    if not email or not password:
        return Response(
            {'error': 'Email and password are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Authenticate using email as username (since we store email in username field)
    user = authenticate(request, username=email, password=password)
    
    if user is None:
        return Response(
            {'error': 'Invalid email or password'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    token = generate_jwt_token(user)
    
    return Response({
        'token': token,
        'user': {
            'id': user.id,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
        }
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def signup(request):
    """Email/password signup endpoint"""
    email = request.data.get('email')
    password = request.data.get('password')
    first_name = request.data.get('first_name', '')
    last_name = request.data.get('last_name', '')
    
    if not email or not password:
        return Response(
            {'error': 'Email and password are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if User.objects.filter(email=email).exists():
        return Response(
            {'error': 'User with this email already exists'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if len(password) < 8:
        return Response(
            {'error': 'Password must be at least 8 characters long'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    user = User.objects.create_user(
        username=email,  # Use email as username for email-based auth
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
    )
    
    token = generate_jwt_token(user)
    
    return Response({
        'token': token,
        'user': {
            'id': user.id,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
        }
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
def google_auth(request):
    """Google OAuth token verification endpoint"""
    google_token = request.data.get('token')
    
    if not google_token:
        return Response(
            {'error': 'Google token is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Verify the Google token
        idinfo = id_token.verify_oauth2_token(
            google_token,
            google_requests.Request(),
            settings.SOCIALACCOUNT_PROVIDERS['google']['APP']['client_id']
        )
        
        if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
            raise ValueError('Wrong issuer')
        
        email = idinfo['email']
        first_name = idinfo.get('given_name', '')
        last_name = idinfo.get('family_name', '')
        google_id = idinfo['sub']
        
        # Get or create user
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            user = User.objects.create_user(
                username=email,  # Use email as username for email-based auth
                email=email,
                first_name=first_name,
                last_name=last_name,
                password=None,  # No password for social accounts
            )
        
        # Link Google account if not already linked
        social_account, created = SocialAccount.objects.get_or_create(
            user=user,
            provider='google',
            defaults={'uid': google_id}
        )
        if not created:
            social_account.uid = google_id
            social_account.save()
        
        token = generate_jwt_token(user)
        
        return Response({
            'token': token,
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
            }
        })
        
    except ValueError as e:
        return Response(
            {'error': f'Invalid Google token: {str(e)}'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    except Exception as e:
        return Response(
            {'error': f'Authentication failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_info(request):
    """Get current user information"""
    user = request.user
    return Response({
        'id': user.id,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    """Logout endpoint (client should discard token)"""
    return Response({'message': 'Logged out successfully'})


# ==================== Asset Upload Management ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def init_clothing_upload(request):
    """Initialize clothing items upload - create DB records and generate SAS URLs"""
    try:
        files = request.data.get('files', [])
        
        if not files:
            return Response(
                {'error': 'No files provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(files) > 20:
            return Response(
                {'error': 'Maximum 20 files per upload'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate file data
        for file_data in files:
            if not file_data.get('name') or not file_data.get('size'):
                return Response(
                    {'error': 'Each file must have name and size'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Create Azure client
        azure_client = AzureBlobClient()
        
        # Prepare files list for Azure with unique blob names
        upload_records = []
        azure_files = []
        
        for file_data in files:
            asset_id = uuid.uuid4()
            display_name = file_data['name']
            file_size = file_data['size']
            
            # Generate unique blob name to avoid conflicts
            file_extension = display_name.rsplit('.', 1)[-1] if '.' in display_name else 'jpg'
            blob_name = f"{asset_id}.{file_extension}"
            azure_blob_name = f"user_{request.user.id}/item/{blob_name}"
            
            # Create ClothingItem
            asset = ClothingItem.objects.create(
                user=request.user,
                asset_id=asset_id,
                display_name=display_name,
                file_size=file_size,
                status='available',
                azure_blob_name=azure_blob_name
            )
            
            # Create UploadTask for tracking
            UploadTask.objects.create(
                user=request.user,
                clothing_item=asset,
                status='uploading'
            )
            
            upload_records.append({
                'asset_id': str(asset_id),
                'display_name': display_name,
                'file_size': file_size
            })
            
            azure_files.append({
                'user_id': request.user.id,
                'name': blob_name
            })
        
        # Generate SAS URLs for direct upload
        sas_urls = azure_client.generate_upload_sas_urls(
            settings.AZURE_CONTAINER_NAME,
            azure_files,
            'item'
        )
        
        if not sas_urls:
            return Response(
                {'error': 'Failed to generate upload URLs'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Combine records with SAS URLs
        response_data = []
        for i, record in enumerate(upload_records):
            response_data.append({
                'asset_id': record['asset_id'],
                'display_name': record['display_name'],
                'upload_url': sas_urls[i]['url'],
                'blob_name': sas_urls[i]['blob_name'],
                'expires_in': 3600  # 1 hour
            })
        
        logger.info(f"Initialized clothing upload for user {request.user.id}: {len(response_data)} files")
        
        return Response({'uploads': response_data}, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"Error initializing clothing upload: {e}", exc_info=True)
        return Response(
            {'error': 'Failed to initialize upload'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_clothing_status(request, asset_id):
    """Check clothing item upload status"""
    try:
        try:
            item = ClothingItem.objects.get(asset_id=asset_id, user=request.user)
        except ClothingItem.DoesNotExist:
            return Response(
                {'error': 'Clothing item not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get upload task if exists
        upload_task = getattr(item, 'upload_task', None)
        
        # If already uploaded, return status
        if upload_task and upload_task.status == 'uploaded':
            return Response({
                'asset_id': str(item.asset_id),
                'status': 'uploaded',
                'completed_at': upload_task.completed_at,
                'type': item.type,
                'category': item.category,
                'color': item.color,
                'subcategory': item.subcategory,
                'comments': item.comments
            })
        
        # If still uploading, check Azure
        if not upload_task or upload_task.status == 'uploading':
            azure_client = AzureBlobClient()
            is_complete = azure_client.check_upload_complete(
                item.azure_blob_name,
                item.file_size
            )
            
            if is_complete:
                if upload_task:
                    upload_task.status = 'uploaded'
                    upload_task.completed_at = timezone.now()
                    upload_task.save()
                else:
                    upload_task = UploadTask.objects.create(
                        user=request.user,
                        clothing_item=item,
                        status='uploaded',
                        completed_at=timezone.now()
                    )
                
                logger.info(f"[Clothing Upload] [asset {asset_id}] Upload completed, queuing type detection (user: {request.user.id})")
                detect_clothing_item_params_task(str(item.asset_id))
        
        return Response({
            'asset_id': str(item.asset_id),
            'status': upload_task.status if upload_task else 'uploading',
            'completed_at': upload_task.completed_at if upload_task else None,
            'type': item.type,
            'category': item.category,
            'color': item.color,
            'subcategory': item.subcategory,
            'comments': item.comments
        })
        
    except Exception as e:
        logger.error(f"Error checking clothing status: {e}", exc_info=True)
        return Response(
            {'error': 'Failed to check upload status'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_clothing(request):
    """List all clothing items for the current user"""
    try:
        items = ClothingItem.objects.filter(user=request.user, status='available')
        azure_client = AzureBlobClient()
        items_data = []
        
        for item in items:
            upload_task = getattr(item, 'upload_task', None)
            url = azure_client.generate_read_sas_url(
                settings.AZURE_CONTAINER_NAME,
                item.azure_blob_name
            )
            items_data.append({
                'asset_id': str(item.asset_id),
                'display_name': item.display_name,
                'file_size': item.file_size,
                'status': 'uploaded' if upload_task and upload_task.status == 'uploaded' else item.status,
                'type': item.type,
                'category': item.category,
                'subcategory': item.subcategory,
                'color': item.color,
                'comments': item.comments,
                'url': url,
                'created_at': item.created_at,
                'completed_at': upload_task.completed_at if upload_task else None
            })
        
        return Response({'items': items_data})
        
    except Exception as e:
        logger.error(f"Error listing clothing items: {e}", exc_info=True)
        return Response(
            {'error': 'Failed to list clothing items'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_clothing_type(request, asset_id):
    """Update clothing item type"""
    try:
        try:
            item = ClothingItem.objects.get(asset_id=asset_id, user=request.user)
        except ClothingItem.DoesNotExist:
            return Response(
                {'error': 'Clothing item not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        new_type = request.data.get('type')
        
        if not new_type:
            return Response(
                {'error': 'Type is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate type choice
        valid_types = ['upper', 'lower', 'full_set']
        if new_type not in valid_types:
            return Response(
                {'error': f'Invalid type. Must be one of: {", ".join(valid_types)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        item.type = new_type
        item.save(update_fields=['type'])
        
        logger.info(f"Updated clothing item {asset_id} type to {new_type} for user {request.user.id}")
        
        return Response({
            'message': 'Clothing item type updated successfully',
            'type': item.type
        })
        
    except Exception as e:
        logger.error(f"Error updating clothing item type: {e}", exc_info=True)
        return Response(
            {'error': 'Failed to update clothing item type'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_clothing_category(request, asset_id):
    """Update clothing item category"""
    try:
        try:
            item = ClothingItem.objects.get(asset_id=asset_id, user=request.user)
        except ClothingItem.DoesNotExist:
            return Response(
                {'error': 'Clothing item not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        new_category = request.data.get('category')
        
        if new_category is None:
            return Response(
                {'error': 'Category is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Django will handle max_length validation automatically
        item.category = new_category
        item.save(update_fields=['category'])
        
        logger.info(f"Updated clothing item {asset_id} category to {new_category} for user {request.user.id}")
        
        return Response({
            'message': 'Clothing item category updated successfully',
            'category': item.category
        })
        
    except Exception as e:
        logger.error(f"Error updating clothing item category: {e}", exc_info=True)
        return Response(
            {'error': 'Failed to update clothing item category'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_clothing_color(request, asset_id):
    """Update clothing item color"""
    try:
        try:
            item = ClothingItem.objects.get(asset_id=asset_id, user=request.user)
        except ClothingItem.DoesNotExist:
            return Response(
                {'error': 'Clothing item not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        new_color = request.data.get('color')
        
        if new_color is None:
            return Response(
                {'error': 'Color is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Django will handle max_length validation automatically
        item.color = new_color
        item.save(update_fields=['color'])
        
        logger.info(f"Updated clothing item {asset_id} color to {new_color} for user {request.user.id}")
        
        return Response({
            'message': 'Clothing item color updated successfully',
            'color': item.color
        })
        
    except Exception as e:
        logger.error(f"Error updating clothing item color: {e}", exc_info=True)
        return Response(
            {'error': 'Failed to update clothing item color'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_clothing_subcategory(request, asset_id):
    """Update clothing item subcategory"""
    try:
        try:
            item = ClothingItem.objects.get(asset_id=asset_id, user=request.user)
        except ClothingItem.DoesNotExist:
            return Response(
                {'error': 'Clothing item not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        new_subcategory = request.data.get('subcategory')
        
        if new_subcategory is None:
            return Response(
                {'error': 'Subcategory is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Django will handle max_length validation automatically
        item.subcategory = new_subcategory
        item.save(update_fields=['subcategory'])
        
        logger.info(f"Updated clothing item {asset_id} subcategory to {new_subcategory} for user {request.user.id}")
        
        return Response({
            'message': 'Clothing item subcategory updated successfully',
            'subcategory': item.subcategory
        })
        
    except Exception as e:
        logger.error(f"Error updating clothing item subcategory: {e}", exc_info=True)
        return Response(
            {'error': 'Failed to update clothing item subcategory'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_clothing_comments(request, asset_id):
    """Update clothing item comments"""
    try:
        try:
            item = ClothingItem.objects.get(asset_id=asset_id, user=request.user)
        except ClothingItem.DoesNotExist:
            return Response(
                {'error': 'Clothing item not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        new_comments = request.data.get('comments')
        
        if new_comments is None:
            return Response(
                {'error': 'Comments are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Django will handle max_length validation automatically
        item.comments = new_comments
        item.save(update_fields=['comments'])
        
        logger.info(f"Updated clothing item {asset_id} comments to {new_comments} for user {request.user.id}")
        
        return Response({
            'message': 'Clothing item comments updated successfully',
            'comments': item.comments
        })
        
    except Exception as e:
        logger.error(f"Error updating clothing item comments: {e}", exc_info=True)
        return Response(
            {'error': 'Failed to update clothing item comments'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_clothing(request, asset_id):
    """Delete a clothing item"""
    try:
        try:
            item = ClothingItem.objects.get(asset_id=asset_id, user=request.user)
        except ClothingItem.DoesNotExist:
            return Response(
                {'error': 'Clothing item not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Delete from Azure
        azure_client = AzureBlobClient()
        azure_client.delete_blob(item.azure_blob_name)
        
        # Delete from DB (UploadTask will be deleted via CASCADE)
        item.delete()
        
        logger.info(f"Deleted clothing item {asset_id} for user {request.user.id}")
        
        return Response({'message': 'Clothing item deleted successfully'})
        
    except Exception as e:
        logger.error(f"Error deleting clothing item: {e}", exc_info=True)
        return Response(
            {'error': 'Failed to delete clothing item'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# ==================== Base Images Management ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def init_base_upload(request):
    """Initialize base images upload - create DB records and generate SAS URLs"""
    try:
        files = request.data.get('files', [])
        
        if not files:
            return Response(
                {'error': 'No files provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(files) > 5:
            return Response(
                {'error': 'Maximum 5 files per upload'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate file data
        for file_data in files:
            if not file_data.get('name') or not file_data.get('size'):
                return Response(
                    {'error': 'Each file must have name and size'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Create Azure client
        azure_client = AzureBlobClient()
        
        # Prepare files list for Azure with unique blob names
        upload_records = []
        azure_files = []
        
        for file_data in files:
            asset_id = uuid.uuid4()
            display_name = file_data['name']
            file_size = file_data['size']
            
            # Generate unique blob name to avoid conflicts
            file_extension = display_name.rsplit('.', 1)[-1] if '.' in display_name else 'jpg'
            blob_name = f"{asset_id}.{file_extension}"
            azure_blob_name = f"user_{request.user.id}/body/{blob_name}"
            
            # Create BaseImage
            asset = BaseImage.objects.create(
                user=request.user,
                asset_id=asset_id,
                display_name=display_name,
                file_size=file_size,
                status='available',
                azure_blob_name=azure_blob_name
            )
            
            # Create UploadTask for tracking
            UploadTask.objects.create(
                user=request.user,
                base_image=asset,
                status='uploading'
            )
            
            upload_records.append({
                'asset_id': str(asset_id),
                'display_name': display_name,
                'file_size': file_size
            })
            
            azure_files.append({
                'user_id': request.user.id,
                'name': blob_name
            })
        
        # Generate SAS URLs for direct upload
        sas_urls = azure_client.generate_upload_sas_urls(
            settings.AZURE_CONTAINER_NAME,
            azure_files,
            'body'
        )
        
        if not sas_urls:
            return Response(
                {'error': 'Failed to generate upload URLs'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Combine records with SAS URLs
        response_data = []
        for i, record in enumerate(upload_records):
            response_data.append({
                'asset_id': record['asset_id'],
                'display_name': record['display_name'],
                'upload_url': sas_urls[i]['url'],
                'blob_name': sas_urls[i]['blob_name'],
                'expires_in': 3600  # 1 hour
            })
        
        logger.info(f"Initialized base image upload for user {request.user.id}: {len(response_data)} files")
        
        return Response({'uploads': response_data}, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"Error initializing base upload: {e}", exc_info=True)
        return Response(
            {'error': 'Failed to initialize upload'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_base_status(request, asset_id):
    """Check base image upload status"""
    try:
        try:
            base_img = BaseImage.objects.get(asset_id=asset_id, user=request.user)
        except BaseImage.DoesNotExist:
            return Response(
                {'error': 'Base image not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get upload task if exists
        upload_task = getattr(base_img, 'upload_task', None)
        
        # If already uploaded, return status
        if upload_task and upload_task.status == 'uploaded':
            return Response({
                'asset_id': str(base_img.asset_id),
                'status': 'uploaded',
                'completed_at': upload_task.completed_at
            })
        
        # If still uploading, check Azure
        if not upload_task or upload_task.status == 'uploading':
            azure_client = AzureBlobClient()
            is_complete = azure_client.check_upload_complete(
                base_img.azure_blob_name,
                base_img.file_size
            )
            
            if is_complete:
                if upload_task:
                    upload_task.status = 'uploaded'
                    upload_task.completed_at = timezone.now()
                    upload_task.save()
                else:
                    upload_task = UploadTask.objects.create(
                        user=request.user,
                        base_image=base_img,
                        status='uploaded',
                        completed_at=timezone.now()
                    )
                
                logger.info(f"[Base Image Upload] [asset {asset_id}] Upload completed (user: {request.user.id})")
        
        return Response({
            'asset_id': str(base_img.asset_id),
            'status': upload_task.status if upload_task else 'uploading',
            'completed_at': upload_task.completed_at if upload_task else None
        })
        
    except Exception as e:
        logger.error(f"Error checking base image status: {e}", exc_info=True)
        return Response(
            {'error': 'Failed to check upload status'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_base(request):
    """List all base images for the current user"""
    try:
        base_images = BaseImage.objects.filter(user=request.user, status='available')
        azure_client = AzureBlobClient()
        images_data = []
        
        for base_img in base_images:
            upload_task = getattr(base_img, 'upload_task', None)
            url = azure_client.generate_read_sas_url(
                settings.AZURE_CONTAINER_NAME,
                base_img.azure_blob_name
            )
            images_data.append({
                'asset_id': str(base_img.asset_id),
                'display_name': base_img.display_name,
                'file_size': base_img.file_size,
                'status': 'uploaded' if upload_task and upload_task.status == 'uploaded' else base_img.status,
                'url': url,
                'created_at': base_img.created_at,
                'completed_at': upload_task.completed_at if upload_task else None
            })
        
        return Response({'images': images_data})
        
    except Exception as e:
        logger.error(f"Error listing base images: {e}", exc_info=True)
        return Response(
            {'error': 'Failed to list base images'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_base(request, asset_id):
    """Delete a base image"""
    try:
        try:
            base_img = BaseImage.objects.get(asset_id=asset_id, user=request.user)
        except BaseImage.DoesNotExist:
            return Response(
                {'error': 'Base image not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Delete from Azure
        azure_client = AzureBlobClient()
        azure_client.delete_blob(base_img.azure_blob_name)
        
        # Delete from DB (UploadTask will be deleted via CASCADE)
        base_img.delete()
        
        logger.info(f"Deleted base image {asset_id} for user {request.user.id}")
        
        return Response({'message': 'Base image deleted successfully'})
        
    except Exception as e:
        logger.error(f"Error deleting base image: {e}", exc_info=True)
        return Response(
            {'error': 'Failed to delete base image'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



# @api_view(['POST'])
# @permission_classes([IsAuthenticated])
# def generate_virtual_fit(request):
#     """Queue virtual fit generation task (async)"""
#     try:
#         body_asset_id = request.data.get('body_asset_id')
#         is_body = request.data.get('is_body')
#         clothing_asset_ids = request.data.get('clothing_asset_ids', [])
#         generator_type = request.data.get('generator_type')
        
#         if not body_asset_id:
#             return Response(
#                 {'error': 'Body image Id is required'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )
        
#         if not clothing_asset_ids or len(clothing_asset_ids) == 0:
#             return Response(
#                 {'error': 'At least one clothing item is required'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )
        
#         if len(clothing_asset_ids) > 2:
#             return Response(
#                 {'error': 'Maximum 2 clothing items allowed'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )
        
#         # Validate generator type
#         valid_generators = ['gemini', 'vwflux', 'vwcatvton', 'fitroom']
#         if generator_type not in valid_generators:
#             return Response(
#                 {'error': f'Invalid generator_type. Must be one of: {", ".join(valid_generators)}'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )
        
#         logger.debug(f"[Generation] [user {request.user.id}] Request received - Body: {body_asset_id}, Clothing: item: {clothing_asset_ids}, Generator: {generator_type}")
        
       
#         # Get body asset
#         try:
#             if is_body:
                
#                 body_asset = Assets.objects.get(
#                     asset_id=body_asset_id,
#                     user=request.user,
#                     category='body',
#                     status='available'
#                 )
#             else: 
#                 body_asset = Assets.objects.get(
#                     asset_id = body_asset_id,
#                     user=request.user,
#                     category="generated",
#                     status='available'
#                 )
#         except Assets.DoesNotExist:
#             return Response(
#                 {'error': 'Body image not found or not available'},
#                 status=status.HTTP_404_NOT_FOUND
#             )
        
#         # Get clothing assets
#         clothing_assets = Assets.objects.filter(
#             asset_id__in=clothing_asset_ids,
#             user=request.user,
#             category='item',
#             status='available'
#         )
        
#         if clothing_assets.count() != len(clothing_asset_ids):
#             return Response(
#                 {'error': 'One or more clothing items not found or not available'},
#                 status=status.HTTP_404_NOT_FOUND
#             )
        
#         # Create GenerationTask
#         clothing_ids = [str(asset.asset_id) for asset in clothing_assets]
#         generation_task = GenerationTask.objects.create(
#             user=request.user,
#             body_asset=body_asset,
#             clothing_upload_ids=clothing_ids,
#             generator_type=generator_type,
#             status='pending'
#         )
        
#         # Queue Huey task
#         process_generation_task(str(generation_task.task_id))
        
#         logger.info(f"[Generation task] {generation_task.task_id} Queued - User: {request.user.id}, Generator: {generator_type}")
        
#         return Response({
#             'task_id': str(generation_task.task_id),
#             'status': 'pending',
#             'message': 'Generation task queued successfully'
#         }, status=status.HTTP_201_CREATED)
        
#     except Exception as e:
#         logger.error(f"[Generation] [user {request.user.id}] Error queuing task: {e}", exc_info=True)
#         return Response(
#             {'error': f'Failed to queue generation task: {str(e)}'},
#             status=status.HTTP_500_INTERNAL_SERVER_ERROR
#         )


# ==================== Generated Images Management ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_generated(request):
    """List all generated images for the current user"""
    try:
        gen_images = GeneratedImage.objects.filter(user=request.user, status='available')
        azure_client = AzureBlobClient()
        images_data = []
        
        for gen_img in gen_images:
            url = azure_client.generate_read_sas_url(
                settings.AZURE_CONTAINER_NAME,
                gen_img.azure_blob_name
            )
            images_data.append({
                'asset_id': str(gen_img.asset_id),
                'display_name': gen_img.display_name,
                'file_size': gen_img.file_size,
                'status': gen_img.status,
                'url': url,
                'created_at': gen_img.created_at
            })
        
        return Response({'images': images_data})
        
    except Exception as e:
        logger.error(f"Error listing generated images: {e}", exc_info=True)
        return Response(
            {'error': 'Failed to list generated images'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_generated(request, asset_id):
    """Delete a generated image"""
    try:
        try:
            gen_img = GeneratedImage.objects.get(asset_id=asset_id, user=request.user)
        except GeneratedImage.DoesNotExist:
            return Response(
                {'error': 'Generated image not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Delete from Azure
        azure_client = AzureBlobClient()
        azure_client.delete_blob(gen_img.azure_blob_name)
        
        # Delete from DB
        gen_img.delete()
        
        logger.info(f"Deleted generated image {asset_id} for user {request.user.id}")
        
        return Response({'message': 'Generated image deleted successfully'})
        
    except Exception as e:
        logger.error(f"Error deleting generated image: {e}", exc_info=True)
        return Response(
            {'error': 'Failed to delete generated image'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_virtual_fit(request):
    """Queue virtual fit generation task (async)"""
    try:
        body_asset_id = request.data.get('body_asset_id')
        clothing_asset_ids = request.data.get('clothing_asset_ids', [])
        generator_type = request.data.get('generator_type')
        
        if not body_asset_id:
            return Response(
                {'error': 'Body image asset_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not clothing_asset_ids or len(clothing_asset_ids) == 0:
            return Response(
                {'error': 'At least one clothing item is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(clothing_asset_ids) > 2:
            return Response(
                {'error': 'Maximum 2 clothing items allowed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate generator type
        valid_generators = ['gemini', 'vwflux', 'vwcatvton', 'fitroom']
        if generator_type not in valid_generators:
            return Response(
                {'error': f'Invalid generator_type. Must be one of: {", ".join(valid_generators)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        logger.debug(f"[Generation] [user {request.user.id}] Request received - Body: {body_asset_id}, Clothing: {clothing_asset_ids}, Generator: {generator_type}")
        
        # Get base image
        try:
            base_image = BaseImage.objects.get(
                asset_id=body_asset_id,
                user=request.user,
                status='available'
            )
        except BaseImage.DoesNotExist:
            return Response(
                {'error': 'Base image not found or not available'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get clothing items
        clothing_items = ClothingItem.objects.filter(
            asset_id__in=clothing_asset_ids,
            user=request.user,
            status='available'
        )
        
        if clothing_items.count() != len(clothing_asset_ids):
            return Response(
                {'error': 'One or more clothing items not found or not available'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Create GenerationTask
        clothing_ids = [str(item.asset_id) for item in clothing_items]
        generation_task = GenerationTask.objects.create(
            user=request.user,
            base_image=base_image,
            clothing_upload_ids=clothing_ids,
            generator_type=generator_type,
            status='pending'
        )
        
        # Queue Huey task
        process_generation_task(str(generation_task.task_id))
        
        logger.info(f"[Generation task] {generation_task.task_id} Queued - User: {request.user.id}, Generator: {generator_type}")
        
        return Response({
            'task_id': str(generation_task.task_id),
            'status': 'pending',
            'message': 'Generation task queued successfully'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"[Generation] [user {request.user.id}] Error queuing task: {e}", exc_info=True)
        return Response(
            {'error': f'Failed to queue generation task: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def generation_task_status(request, task_id):
    """Get generation task status and progress"""
    try:
        # Get task
        try:
            task = GenerationTask.objects.get(task_id=task_id, user=request.user)
        except GenerationTask.DoesNotExist:
            return Response(
                {'error': 'Generation task not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get live progress from Redis if processing
        progress = 5
        if task.status == 'processing':
            try:
                redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
                redis_progress = redis_client.get(f"vftask:{task_id}:progress")
                if redis_progress:
                    progress = int(redis_progress)
            except Exception:
                pass
        
        # Build response
        response_data = {
            'task_id': str(task.task_id),
            'status': task.status,
            'progress': progress,
            'generator_type': task.generator_type,
            'created_at': task.created_at,
        }
        
        # Add result if completed
        if task.status == 'completed' and task.result_image:
            azure_client = AzureBlobClient()
            result_url = azure_client.generate_read_sas_url(
                settings.AZURE_CONTAINER_NAME,
                task.result_image.azure_blob_name
            )
            response_data['result'] = {
                'asset_id': str(task.result_image.asset_id),
                'url': result_url,
                'display_name': task.result_image.display_name,
                'file_size': task.result_image.file_size,
                'created_at': task.result_image.created_at,
            }
            progress = 100
        
        # Add error if failed
        if task.status == 'failed':
            response_data['error_message'] = task.error_message
        
        # Add completed timestamp
        if task.completed_at:
            response_data['completed_at'] = task.completed_at
        
        return Response(response_data)
        
    except Exception as e:
        logger.error(f"Error getting generation task status: {e}", exc_info=True)
        return Response(
            {'error': 'Failed to get task status'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )