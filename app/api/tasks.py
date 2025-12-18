"""
Background tasks using Huey for async processing
"""
import uuid
import redis
import time
import requests
from io import BytesIO
from datetime import datetime
from django.conf import settings
from huey.contrib.djhuey import db_task
from loguru import logger
from django.utils import timezone
from .models import Assets, GenerationTask
from _libs.lib_azure import AzureBlobClient
from _libs.lib_openai import detect_clothing_part
from _libs import lib_aigeneration
from _libs.lib_prompts import get_gemini_virtual_fit_prompt



def _get_redis_client():
    """Get Redis client for progress tracking"""
    try:
        return redis.from_url(settings.REDIS_URL, decode_responses=True)
    except Exception as e:
        logger.warning(f"Redis not available for progress tracking: {e}")
        return None


def _update_progress(task_id, progress):
    """Update generation progress in Redis"""
    redis_client = _get_redis_client()
    if redis_client:
        try:
            redis_client.setex(f"vftask:{task_id}:progress", 600, progress)
        except Exception as e:
            logger.warning(f"Failed to update progress in Redis: {e}")


@db_task()
def detect_clothing_part_task(asset_id):
    """
    Async task to detect clothing part using OpenAI Vision
    
    Args:
        asset_id: UUID string of the asset to process
    """
    try:
        logger.info(f"[Upload Task] Starting clothing part detection for asset {asset_id}")
        
        # Get asset
        try:
            asset = Assets.objects.get(asset_id=asset_id)
        except Assets.DoesNotExist:
            logger.error(f"[Upload Task] Asset not found: {asset_id}")
            return False
        
        # Only process clothing items (category='item')
        if asset.category != 'item':
            logger.debug(f"[Upload Task] Skipping part detection for non-item category: {asset.category}")
            return False
        
        # Skip if already detected
        if asset.part:
            logger.debug(f"[Upload Task] Part already detected for {asset_id}: {asset.part}")
            return True
        
        # Skip if not available yet
        if asset.status != 'available':
            logger.warning(f"[Upload Task] Asset {asset_id} not available yet, status: {asset.status}")
            return False
        
        # Generate SAS URL to download the image from Azure Storage
        logger.debug(f"[Upload Task] Generating SAS URL for asset {asset_id}")
        azure_client = AzureBlobClient()
        sas_url = azure_client.generate_read_sas_url(
            settings.AZURE_CONTAINER_NAME,
            asset.azure_blob_name
        )
        
        if not sas_url:
            logger.error(f"[Upload Task] Failed to generate SAS URL for {asset_id}")
            return False
        
        # Detect clothing part using OpenAI Vision API
        logger.debug(f"[Upload Task] Calling OpenAI Vision API for asset {asset_id}")
        detected_part = detect_clothing_part(sas_url)
        
        if detected_part:
            asset.part = detected_part
            asset.save(update_fields=['part'])
            logger.info(f"[Upload Task] Successfully detected part '{detected_part}' for asset {asset_id} (user: {asset.user.id})")
            return True
        else:
            logger.warning(f"[Upload Task] Failed to detect part for asset {asset_id}")
            return False
            
    except Exception as e:
        logger.error(f"[Upload Task] Error in clothing part detection for asset {asset_id}: {e}", exc_info=True)
        return False


@db_task()
def process_generation_task(task_id):
    """
    Process virtual fit generation task in background
    
    Args:
        task_id: UUID string of the GenerationTask to process
    """
    try:
        logger.info(f"[Generation Task] Starting task {task_id}")
        
        # Get generation task
        try:
            task = GenerationTask.objects.get(task_id=task_id)
        except GenerationTask.DoesNotExist:
            logger.error(f"[Generation Task] Task not found: {task_id}")
            return False
        
        logger.info(f"[Generation Task] Task {task_id} - User: {task.user.id}, Generator: {task.generator_type}, Status: pending → processing")
        
        # Update status to processing
        task.status = 'processing'
        task.save(update_fields=['status'])
        _update_progress(str(task_id), 5)
        
        # Validate body asset
        if not task.body_asset:
            error_msg = "Body asset not found"
            logger.error(f"[Generation Task] Task {task_id} - {error_msg}")
            task.status = 'failed'
            task.error_message = error_msg
            task.completed_at = timezone.now()
            task.save()
            return False
        
        # Get clothing assets
        clothing_assets = Assets.objects.filter(
            asset_id__in=task.clothing_upload_ids,
            user=task.user,
            category='item',
            status='available'
        )
        
        if clothing_assets.count() != len(task.clothing_upload_ids):
            error_msg = "One or more clothing assets not found or not available"
            logger.error(f"[Generation Task] Task {task_id} - {error_msg}")
            task.status = 'failed'
            task.error_message = error_msg
            task.completed_at = timezone.now()
            task.save()
            return False
        
        logger.debug(f"[Generation Task] Task {task_id} - Validated {len(clothing_assets)} clothing asset(s)")
        
        # Get SAS URLs
        azure_client = AzureBlobClient()
        all_assets = [task.body_asset] + list(clothing_assets)
        sas_urls = azure_client.get_cached_sas_urls(all_assets)
        
        body_image_url = sas_urls.get(str(task.body_asset.asset_id))
        clothing_image_urls = [sas_urls.get(str(asset.asset_id)) for asset in clothing_assets]
        
        if not body_image_url or not all(clothing_image_urls):
            error_msg = "Failed to generate image URLs"
            logger.error(f"[Generation Task] Task {task_id} - {error_msg}")
            task.status = 'failed'
            task.error_message = error_msg
            task.completed_at = timezone.now()
            task.save()
            return False
        
        logger.debug(f"[Generation Task] Task {task_id} - Generated SAS URLs for images")
        
        # Get part from first clothing asset
        clothing_asset = clothing_assets.first()
        part = clothing_asset.part if clothing_asset else None
                
        # Update progress
        _update_progress(str(task_id), 10)
        
        # Generate image based on generator type
        logger.info(f"[Generation Task] Task {task_id} - Starting generation with {task.generator_type}")
        
        try:
            if task.generator_type == 'fitroom':
                # FitRoom handles progress internally via Redis
                generated_image_data = _generate_fitroom_with_progress(
                    task_id, body_image_url, clothing_image_urls[0], part
                )
            else:
                # Other generators: simulate progress
                _update_progress(str(task_id), 40)
                generated_image_data = lib_aigeneration.generate_virtual_fit_sync(
                    body_image_url,
                    clothing_image_urls,
                    generator_type=task.generator_type,
                    part=part
                )
                _update_progress(str(task_id), 90)
                
        except ValueError as val_error:
            error_msg = str(val_error)
            logger.warning(f"[Generation Task] Task {task_id} - Generation refused: {error_msg}")
            task.status = 'failed'
            task.error_message = error_msg
            task.completed_at = timezone.now()
            task.save()
            logger.info(f"[Generation Task] Task {task_id} - Status: processing → failed")
            return False
        except Exception as gen_error:
            error_msg = f"Generation failed: {str(gen_error)}"
            logger.error(f"[Generation Task] Task {task_id} - {error_msg}", exc_info=True)
            task.status = 'failed'
            task.error_message = error_msg
            task.completed_at = timezone.now()
            task.save()
            logger.info(f"[Generation Task] Task {task_id} - Status: processing → failed")
            return False
        
        if not generated_image_data:
            error_msg = f"Failed to generate image using {task.generator_type}"
            logger.error(f"[Generation Task] Task {task_id} - {error_msg}")
            task.status = 'failed'
            task.error_message = error_msg
            task.completed_at = timezone.now()
            task.save()
            logger.info(f"[Generation Task] Task {task_id} - Status: processing → failed")
            return False
        
        logger.info(f"[Generation Task] Task {task_id} - Image generated successfully, uploading to Azure")
        
        # Upload generated image to Azure
        generated_asset_id = uuid.uuid4()
        blob_name = f"{generated_asset_id}.jpg"
        azure_blob_name = f"user_{task.user.id}/generated/{blob_name}"
        
        upload_success = azure_client.upload_blob_from_bytes(
            azure_blob_name,
            generated_image_data,
            'image/jpeg'
        )
        
        if not upload_success:
            error_msg = "Failed to save generated image to Azure"
            logger.error(f"[Generation Task] Task {task_id} - {error_msg}")
            task.status = 'failed'
            task.error_message = error_msg
            task.completed_at = timezone.now()
            task.save()
            logger.info(f"[Generation Task] Task {task_id} - Status: processing → failed")
            return False
        
        logger.debug(f"[Generation Task] Task {task_id} - Uploaded to Azure: {azure_blob_name}")
        
        # Create Assets record
        display_name = f"generated_{task.generator_type}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.jpg"
        generated_asset = Assets.objects.create(
            user=task.user,
            asset_id=generated_asset_id,
            azure_blob_name=azure_blob_name,
            file_size=len(generated_image_data),
            category='generated',
            display_name=display_name,
            status='available'
        )
        
        # Link result to task - reload to get latest provider_task_id
        task.refresh_from_db()
        task.result_asset = generated_asset
        task.status = 'completed'
        task.completed_at = timezone.now()
        task.save(update_fields=['result_asset', 'status', 'completed_at'])
        
        # Final progress
        _update_progress(str(task_id), 100)
        
        logger.info(f"[Generation Task] Task {task_id} - Status: processing → completed (User: {task.user.id}, Generator: {task.generator_type}, Asset: {generated_asset_id})")
        return True
        
    except Exception as e:
        logger.error(f"[Generation Task] Unexpected error in task {task_id}: {e}", exc_info=True)
        try:
            task = GenerationTask.objects.get(task_id=task_id)
            task.status = 'failed'
            task.error_message = f"Unexpected error: {str(e)}"
            task.completed_at = timezone.now()
            task.save()
            logger.info(f"[Generation Task] Task {task_id} - Status: processing → failed (unexpected error)")
        except Exception:
            pass
        return False


def _generate_fitroom_with_progress(task_id, body_image_url, clothing_image_url, part):
    """
    Generate using FitRoom API with progress tracking in Redis
    
    Args:
        task_id: GenerationTask UUID for progress tracking
        body_image_url: URL to body image
        clothing_image_url: URL to clothing image
        part: Clothing part ('upper', 'lower', 'full_set')
        
    Returns:
        bytes: Generated image data or None if failed
    """
  
    api_key = settings.FITROOM_API_KEY
    if not api_key:
        logger.error("FITROOM_API_KEY not configured")
        return None
    
    create_task_url = "https://platform.fitroom.app/api/tryon/v2/tasks"
    
    # Map part to FitRoom cloth_type
    cloth_type_map = {
        'upper': 'upper',
        'lower': 'lower',
        'full_set': 'full_set'
    }
    cloth_type = cloth_type_map.get(part, 'upper')
    
    # Download images
    body_image_data = lib_aigeneration._download_image(body_image_url)
    if not body_image_data:
        return None
    
    clothing_image_data = lib_aigeneration._download_image(clothing_image_url)
    if not clothing_image_data:
        return None
    
    # Create FitRoom task
    logger.debug(f"[Generation Task] Task {task_id} - Creating FitRoom API task (cloth_type: {cloth_type})")
    files = {
        'model_image': ('model.jpg', BytesIO(body_image_data), 'image/jpeg'),
        'cloth_image': ('cloth.jpg', BytesIO(clothing_image_data), 'image/jpeg')
    }
    data = {'cloth_type': cloth_type, 'hd_mode': 'false'}
    headers = {'X-API-KEY': api_key}
    
    response = requests.post(create_task_url, files=files, data=data, headers=headers, timeout=60)
    response.raise_for_status()
    
    response_data = response.json()
    logger.debug(f"[Generation Task] Task {task_id} - FitRoom API response: {response_data}")
    
    # FitRoom API returns {"task_id": "123456", "status": "CREATED"}
    fitroom_task_id = response_data.get('task_id')
    
    if not fitroom_task_id:
        logger.error(f"[Generation Task] Task {task_id} - FitRoom API response missing 'task_id' field. Response: {response_data}")
        return None
    
    logger.info(f"[Generation Task] Task {task_id} - FitRoom task created: {fitroom_task_id}")
    
    # Store provider task ID immediately after getting it
    try:
        generation_task = GenerationTask.objects.get(task_id=task_id)
        generation_task.provider_task_id = str(fitroom_task_id)
        generation_task.save(update_fields=['provider_task_id'])
        logger.debug(f"[Generation Task] Task {task_id} - Saved provider_task_id: {fitroom_task_id}")
    except Exception as save_error:
        logger.error(f"[Generation Task] Task {task_id} - Failed to save provider_task_id: {save_error}", exc_info=True)
        # Continue anyway - we still have the ID for polling
    
    # Poll FitRoom status with progress updates
    status_url = f"https://platform.fitroom.app/api/tryon/v2/tasks/{fitroom_task_id}"
    max_attempts = 60
    poll_interval = 3
    
    for attempt in range(max_attempts):
        time.sleep(poll_interval)
        
        status_response = requests.get(status_url, headers=headers, timeout=30)
        status_response.raise_for_status()
        
        status_data = status_response.json()
        fitroom_status = status_data.get('status')
        progress = status_data.get('progress', 10)
        
        # Update progress in Redis
        _update_progress(str(task_id), progress)
        
        if fitroom_status == 'COMPLETED':
            logger.info(f"[Generation Task] Task {task_id} - FitRoom task {fitroom_task_id} completed (100%), downloading result")
            download_url = status_data.get('download_signed_url')
            if not download_url:
                logger.error(f"[Generation Task] Task {task_id} - FitRoom task completed but missing 'download_signed_url'")
                return None
            
            result_response = requests.get(download_url, timeout=60)
            result_response.raise_for_status()
            
            logger.debug(f"[Generation Task] Task {task_id} - FitRoom result downloaded successfully")
            return result_response.content
            
        elif fitroom_status == 'FAILED':
            error_msg = status_data.get('error', 'Unknown error')
            logger.error(f"[Generation Task] Task {task_id} - FitRoom task {fitroom_task_id} failed: {error_msg}")
            return None
    
    logger.error(f"[Generation Task] Task {task_id} - FitRoom task {fitroom_task_id} timed out after {max_attempts * poll_interval}s")
    return None

