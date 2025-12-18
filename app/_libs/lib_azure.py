from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions, CorsRule, ContentSettings
from azure.core.exceptions import ResourceNotFoundError, ResourceExistsError
from datetime import datetime, timedelta
import redis
from loguru import logger
from django.conf import settings
from django.utils import timezone



class AzureBlobClient:
    def __init__(self):
        """Initialize Azure Blob client with connection string"""
        connection_string = settings.AZURE_CONNECTION_STRING
        if not connection_string:
            logger.error("AZURE_CONNECTION_STRING not configured")
            raise ValueError("AZURE_CONNECTION_STRING not configured")
        
        # Initialize Azure Blob Storage client
        try:
            self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
            self.container_name = settings.AZURE_CONTAINER_NAME
            # logger.debug(f"Azure Blob client initialized with container: {self.container_name}")
        except Exception as e:
            logger.error(f"Failed to initialize Azure Blob client: {e}", exc_info=True)
            raise ConnectionError(f"Unable to connect to Azure Blob Storage: {str(e)}")
        
        # Initialize Redis client for SAS URL caching
        try:
            self.redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        except Exception as e:
            logger.warning(f"Redis not available, SAS caching disabled: {e}")
            self.redis_client = None

    def generate_upload_sas_urls(self, container_name, files_list, category='item'):
        """
        Generate SAS URLs for direct upload to Azure Blob Storage
        
        Args:
            container_name: Azure container name
            files_list: List of file info dicts with 'user_id' and 'name'
            category: Category of files ('item', 'body', 'generated')
        """
        try:
            logger.info(f"Generating SAS URLs for category: {category}")
            
            # Ensure container exists
            container_client = self.blob_service_client.get_container_client(container_name)
            try:
                container_client.get_container_properties()
                # logger.debug(f"Container {container_name} exists")
            except ResourceNotFoundError:
                # Create container if it doesn't exist
                logger.info(f"Creating container: {container_name}")
                container_client.create_container()
                logger.info(f"Created container: {container_name}")

            sas_urls = []
            for file_info in files_list:
                # Generate blob name using user_id, category, and original filename
                user_id = file_info.get('user_id')
                original_filename = file_info['name']
                logger.debug(f"Processing file: user_id={user_id}, filename={original_filename}, category={category}")
                blob_name = f"user_{user_id}/{category}/{original_filename}"
                
                # logger.debug(f"Generating SAS token for blob: {blob_name}")
                
                # Generate SAS token for upload
                sas_token = generate_blob_sas(
                    account_name=self.blob_service_client.account_name,
                    container_name=container_name,
                    blob_name=blob_name,
                    account_key=self.blob_service_client.credential.account_key,
                    permission=BlobSasPermissions(write=True),
                    expiry=timezone.now() + timedelta(hours=1)  # 1 hour expiry
                )
                
                # Construct full URL
                blob_url = f"https://{self.blob_service_client.account_name}.blob.core.windows.net/{container_name}/{blob_name}?{sas_token}"
                
                sas_urls.append({
                    'url': blob_url,
                    'blob_name': blob_name
                })
                
                logger.info(f"Generated SAS URL for {blob_name}")
            
            logger.info(f"Generated {len(sas_urls)} SAS URLs")
            return sas_urls
            
        except Exception as e:
            logger.error(f"Error generating SAS URLs: {e}", exc_info=True)
            return None

    def generate_read_sas_url(self, container_name, blob_name):
        """Generate a read SAS URL (not cached - for single use)"""
        try:
            # Generate SAS token for read access
            sas_token = generate_blob_sas(
                account_name=self.blob_service_client.account_name,
                container_name=container_name,
                blob_name=blob_name,
                account_key=self.blob_service_client.credential.account_key,
                permission=BlobSasPermissions(read=True),
                expiry=timezone.now() + timedelta(hours=2)  # 2 hours for processing
            )
            
            # Construct full URL
            blob_url = f"https://{self.blob_service_client.account_name}.blob.core.windows.net/{container_name}/{blob_name}?{sas_token}"
            return blob_url
            
        except Exception as e:
            logger.error(f"Error generating read SAS URL: {e}", exc_info=True)
            return None

    def get_blob_url(self, container_name, blob_name):
        """Get the full URL for a blob"""
        return f"https://{self.blob_service_client.account_name}.blob.core.windows.net/{container_name}/{blob_name}"

    def get_container_client(self, container_name):
        """Get container client for operations"""
        return self.blob_service_client.get_container_client(container_name)

    def configure_cors(self):
        """Configure CORS for direct browser uploads"""
        try:
            # Create CORS rule using the proper Azure SDK class
            cors_rule = CorsRule(
                allowed_origins=['*'],  # Allow all origins for now
                allowed_methods=['GET', 'POST', 'PUT'],
                allowed_headers=['*'],
                exposed_headers=['*'],
                max_age_in_seconds=86400
            )
            # Set CORS rules on the service
            self.blob_service_client.set_service_properties(cors=[cors_rule])
            logger.info("CORS configured for Azure Blob Service")
        except Exception as e:
            logger.error(f"Failed to configure CORS: {e}")
            # Continue without CORS - it might already be configured

    def check_upload_complete(self, blob_name, expected_size):
        """Check if blob upload is complete"""
        try:
            container_client = self.get_container_client(self.container_name)
            blob_client = container_client.get_blob_client(blob_name)
            properties = blob_client.get_blob_properties()
            
            # These properties only exist when upload is complete
            is_complete = (
                properties.size == expected_size and
                properties.last_modified is not None and
                properties.etag is not None
            )
            
            if is_complete:
                logger.info(f"Upload complete for blob: {blob_name}, size: {properties.size}")
            else:
                logger.debug(f"Upload in progress for blob: {blob_name}, current size: {properties.size}, expected: {expected_size}")
            
            return is_complete
            
        except Exception as e:
            # Handle specific Azure errors
            if "404" in str(e) or "not found" in str(e).lower():
                logger.debug(f"Blob not found yet: {blob_name}")
                return False
            elif "connection" in str(e).lower() or "timeout" in str(e).lower():
                logger.warning(f"Connection error checking blob {blob_name}: {e}")
                return False
            else:
                logger.debug(f"Error checking blob {blob_name}: {e}")
                return False

    def get_cached_sas_urls(self, assets):
        """Get SAS URLs for assets with Redis caching"""
        try:
            if not self.redis_client or not assets:
                # Fallback: generate without cache
                return self._generate_all_sas_urls(assets)
            
            # Step 1: Try to get all from cache (batch MGET)
            cache_keys = [f"asset_sas:{asset.user_id}:{asset.asset_id}" for asset in assets]
            cached_urls = self.redis_client.mget(cache_keys)
            
            # Step 2: Identify misses and generate
            result = {}
            to_generate = []
            
            for i, asset in enumerate(assets):
                if cached_urls[i]:
                    result[str(asset.asset_id)] = cached_urls[i]
                else:
                    to_generate.append(asset)
            
            # Step 3: Generate missing SAS URLs
            if to_generate:
                logger.info(f"Generating {len(to_generate)} missing SAS URLs (cache misses)")
                new_urls = self._generate_and_cache_sas_urls(to_generate)
                result.update(new_urls)
            else:
                logger.debug(f"Loaded all {len(assets)} SAS URLs from cache")
            
            return result
            
        except Exception as e:
            logger.error(f"Error with cached SAS URLs: {e}")
            # Fallback to generating without cache
            return self._generate_all_sas_urls(assets)
    
    def _generate_all_sas_urls(self, assets):
        """Generate SAS URLs without caching (fallback)"""
        result = {}
        for asset in assets:
            url = self.generate_read_sas_url(self.container_name, asset.azure_blob_name)
            if url:
                result[str(asset.asset_id)] = url
        return result
    
    def _generate_and_cache_sas_urls(self, assets):
        """Generate SAS URLs and cache them in Redis"""
        result = {}
        cache_data = {}
        ttl = 2 * 60 * 60  # 2 hours in seconds
        
        for asset in assets:
            url = self.generate_read_sas_url(self.container_name, asset.azure_blob_name)
            if url:
                asset_id_str = str(asset.asset_id)
                result[asset_id_str] = url
                cache_data[f"asset_sas:{asset.user_id}:{asset.asset_id}"] = url
        
        # Batch set with expiry
        if cache_data and self.redis_client:
            try:
                pipe = self.redis_client.pipeline()
                for key, value in cache_data.items():
                    pipe.setex(key, ttl, value)
                pipe.execute()
                logger.debug(f"Cached {len(cache_data)} SAS URLs with 2hr TTL")
            except Exception as e:
                logger.warning(f"Failed to cache SAS URLs: {e}")
        
        return result
    
    def clear_asset_cache(self, user_id, upload_id):
        """Clear cached SAS URL for a specific asset"""
        if self.redis_client:
            try:
                self.redis_client.delete(f"asset_sas:{user_id}:{upload_id}")
            except Exception as e:
                logger.warning(f"Failed to clear asset cache: {e}")

    def upload_blob_from_bytes(self, blob_name, data, content_type='image/jpeg'):
        """
        Upload blob data directly from bytes
        
        Args:
            blob_name: Full blob name including path (e.g., 'user_1/generated/image.jpg')
            data: Binary data to upload
            content_type: MIME type of the content
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            container_client = self.get_container_client(self.container_name)
            blob_client = container_client.get_blob_client(blob_name)
            
            content_settings = ContentSettings(content_type=content_type)
            
            blob_client.upload_blob(
                data,
                overwrite=True,
                content_settings=content_settings
            )
            
            logger.info(f"Successfully uploaded blob: {blob_name} ({len(data)} bytes)")
            return True
            
        except Exception as e:
            logger.error(f"Error uploading blob {blob_name}: {e}", exc_info=True)
            return False
    
    def delete_blob(self, blob_name):
        """Delete a specific blob"""
        try:
            container_client = self.get_container_client(self.container_name)
            container_client.delete_blob(blob_name)
            logger.info(f"Deleted blob: {blob_name}")
            return True
        except Exception as e:
            logger.error(f"Error deleting blob {blob_name}: {e}")
            return False

    def delete_user_data(self, user_id):
        """Delete all blobs for a user from the container"""
        try:
            container_client = self.blob_service_client.get_container_client(self.container_name)
            user_folder = f"user_{user_id}"
            
            # List all blobs in user folder
            blobs = container_client.list_blobs(name_starts_with=user_folder)
            
            # Delete each blob
            for blob in blobs:
                container_client.delete_blob(blob.name)
                logger.info(f"Deleted blob: {blob.name}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting user data: {e}")
            return False