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

from .models import Assets, GenerationTask, UploadTask
from _libs.lib_azure import AzureBlobClient
from .tasks import detect_clothing_part_task, process_generation_task

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
def init_upload(request):
    """Initialize upload session - create DB records and generate SAS URLs"""
    try:
        files = request.data.get('files', [])
        category = request.data.get('category', 'item')  # item, body, or generated
        
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
        
        # Validate category
        valid_categories = ['item', 'body', 'generated']
        if category not in valid_categories:
            return Response(
                {'error': f'Invalid category. Must be one of: {", ".join(valid_categories)}'},
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
            
            # Create DB record with status='available' (will be verified after upload)
            asset = Assets.objects.create(
                user=request.user,
                asset_id=asset_id,
                display_name=display_name,
                file_size=file_size,
                status='available',
                category=category,
                azure_blob_name=f"user_{request.user.id}/{category}/{blob_name}"
            )
            
            # Create UploadTask for tracking upload process
            upload_task = UploadTask.objects.create(
                user=request.user,
                asset=asset,
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
            category
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
        
        logger.info(f"Initialized upload for user {request.user.id}: {len(response_data)} files, category: {category}")
        
        return Response({'uploads': response_data}, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"Error initializing upload: {e}", exc_info=True)
        return Response(
            {'error': 'Failed to initialize upload'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_upload_status(request, asset_id):
    """Check upload status for a specific file"""
    try:
        asset = Assets.objects.get(asset_id=asset_id, user=request.user)
        
        # Get upload task if exists
        upload_task = getattr(asset, 'upload_task', None)
        
        # If already uploaded, return status
        if upload_task and upload_task.status == 'uploaded':
            return Response({
                'asset_id': str(asset.asset_id),
                'status': 'uploaded',
                'completed_at': upload_task.completed_at,
                'part': asset.part
            })
        
        # If still uploading, check Azure
        if not upload_task or upload_task.status == 'uploading':
            azure_client = AzureBlobClient()
            is_complete = azure_client.check_upload_complete(
                asset.azure_blob_name,
                asset.file_size
            )
            
            if is_complete:
                if upload_task:
                    upload_task.status = 'uploaded'
                    upload_task.completed_at = timezone.now()
                    upload_task.save()
                else:
                    # Create upload task if missing
                    upload_task = UploadTask.objects.create(
                        user=request.user,
                        asset=asset,
                        status='uploaded',
                        completed_at=timezone.now()
                    )
                
                # Log based on category (minimal - task will log processing)
                if asset.category == 'item':
                    logger.info(f"[Clothing Upload] [asset {asset_id}] Upload completed, queuing part detection (user: {request.user.id})")
                    detect_clothing_part_task(str(asset.asset_id))
                elif asset.category == 'body':
                    logger.info(f"[Body Upload] [asset {asset_id}] Upload completed (user: {request.user.id})")
                else:
                    logger.info(f"[Upload] [asset {asset_id}] Upload completed (user: {request.user.id}, category: {asset.category})")
        
        return Response({
            'asset_id': str(asset.asset_id),
            'status': upload_task.status if upload_task else 'uploading',
            'completed_at': upload_task.completed_at if upload_task else None,
            'part': asset.part
        })
        
    except Assets.DoesNotExist:
        return Response(
            {'error': 'Upload not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error checking upload status: {e}", exc_info=True)
        return Response(
            {'error': 'Failed to check upload status'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_assets(request):
    """List all assets for the current user with read URLs"""
    try:
        category = request.GET.get('category', None)
        
        # Filter by category if provided (only show available assets)
        if category:
            assets = Assets.objects.filter(user=request.user, status='available', category=category)
        else:
            assets = Assets.objects.filter(user=request.user, status='available')
        
        if not assets.exists():
            return Response({'assets': []})
        
        # Get SAS URLs with Redis caching
        # Generate new SAS URL if not in cache
        azure_client = AzureBlobClient()
        sas_urls = azure_client.get_cached_sas_urls(assets)
        
        assets_data = []
        for asset in assets:
            # Get upload task for completed_at if exists
            upload_task = getattr(asset, 'upload_task', None)
            
            assets_data.append({
                'asset_id': str(asset.asset_id),
                'display_name': asset.display_name,
                'file_size': asset.file_size,
                'status': 'uploaded' if upload_task and upload_task.status == 'uploaded' else asset.status,
                'category': asset.category,
                'part': asset.part,
                'url': sas_urls.get(str(asset.asset_id)),
                'created_at': asset.created_at,
                'completed_at': upload_task.completed_at if upload_task else None
            })
        
        return Response({'assets': assets_data})
        
    except Exception as e:
        logger.error(f"Error listing assets: {e}", exc_info=True)
        return Response(
            {'error': 'Failed to list assets'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_asset(request, asset_id):
    """Delete an asset"""
    try:
        asset = Assets.objects.get(asset_id=asset_id, user=request.user)
        
        # Delete from Azure and clear cache
        azure_client = AzureBlobClient()
        azure_client.delete_blob(asset.azure_blob_name)
        azure_client.clear_asset_cache(request.user.id, asset_id)
        
        # Delete from DB (UploadTask will be deleted via CASCADE)
        asset.delete()
        
        logger.info(f"Deleted asset {asset_id} for user {request.user.id}")
        
        return Response({'message': 'Asset deleted successfully'})
        
    except Assets.DoesNotExist:
        return Response(
            {'error': 'Asset not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error deleting asset: {e}", exc_info=True)
        return Response(
            {'error': 'Failed to delete asset'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ==================== Virtual Fit ====================

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
        
        logger.debug(f"[Generation] [user {request.user.id}] Request received - Body: {body_asset_id}, Clothing: item: {clothing_asset_ids}, Generator: {generator_type}")
        
        # Get body asset
        try:
            body_asset = Assets.objects.get(
                asset_id=body_asset_id,
                user=request.user,
                category='body',
                status='available'
            )
        except Assets.DoesNotExist:
            return Response(
                {'error': 'Body image not found or not available'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get clothing assets
        clothing_assets = Assets.objects.filter(
            asset_id__in=clothing_asset_ids,
            user=request.user,
            category='item',
            status='available'
        )
        
        if clothing_assets.count() != len(clothing_asset_ids):
            return Response(
                {'error': 'One or more clothing items not found or not available'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Create GenerationTask
        clothing_ids = [str(asset.asset_id) for asset in clothing_assets]
        generation_task = GenerationTask.objects.create(
            user=request.user,
            body_asset=body_asset,
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
        if task.status == 'completed' and task.result_asset:
            azure_client = AzureBlobClient()
            result_url = azure_client.generate_read_sas_url(
                settings.AZURE_CONTAINER_NAME,
                task.result_asset.azure_blob_name
            )
            response_data['result'] = {
                'asset_id': str(task.result_asset.asset_id),
                'url': result_url,
                'display_name': task.result_asset.display_name,
                'file_size': task.result_asset.file_size,
                'created_at': task.result_asset.created_at,
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
