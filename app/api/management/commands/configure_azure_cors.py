"""
Django management command to configure CORS for Azure Blob Storage
"""
from django.core.management.base import BaseCommand
from _libs.lib_azure import AzureBlobClient
from loguru import logger


class Command(BaseCommand):
    help = 'Configure CORS rules for Azure Blob Storage to allow direct browser uploads'

    def handle(self, *args, **options):
        self.stdout.write('Configuring CORS for Azure Blob Storage...')
        
        try:
            azure_client = AzureBlobClient()
            azure_client.configure_cors()
            
            self.stdout.write(self.style.SUCCESS('✓ CORS configured successfully!'))
            self.stdout.write('You can now upload files directly from the browser to Azure.')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Failed to configure CORS: {e}'))
            logger.error(f"Failed to configure Azure CORS: {e}", exc_info=True)

