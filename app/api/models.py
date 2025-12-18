from django.db import models
from django.contrib.auth.models import User
import uuid


class Assets(models.Model):
    """File metadata with final status (detailed process tracking in Tasks)"""
    
    CATEGORY_CHOICES = [
        ('item', 'Clothing Items'),
        ('body', 'Body Images'),
        ('generated', 'Generated Images'),
    ]
    
    PART_CHOICES = [
        ('upper', 'Upper'),
        ('lower', 'Lower'),
        ('full_set', 'Full Set'),
    ]

    STATUS_CHOICES = [
        ('available', 'Available'),  # Uploaded/generated successfully
        ('failed', 'Failed'),        # Upload/generation failed
    ]
    
    id = models.AutoField(primary_key=True)
    
    # UUID for API/external use
    asset_id = models.UUIDField(unique=True, default=uuid.uuid4, db_index=True)
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    
    azure_blob_name = models.CharField(max_length=500)
    file_size = models.BigIntegerField()
    
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    part = models.CharField(max_length=50, choices=PART_CHOICES, blank=True, null=True)
    display_name = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available', db_index=True)
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        ordering = ['-id']
        indexes = [
            models.Index(fields=['user', 'category', 'status']),
        ]
    
    def __str__(self):
        return f"{self.display_name} ({self.category} - {self.status})"


class UploadTask(models.Model):
    """Upload process tracking"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),      # Queued in Huey
        ('uploading', 'Uploading'),   # Client uploading to Azure
        ('uploaded', 'Uploaded'),     # Upload complete
        ('failed', 'Failed'),         # Upload failed
    ]

    id = models.AutoField(primary_key=True)
    
    # UUID for API/external use
    task_id = models.UUIDField(unique=True, default=uuid.uuid4, db_index=True)
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    asset = models.OneToOneField(Assets, on_delete=models.CASCADE, related_name='upload_task')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    error_message = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-id']


class GenerationTask(models.Model):
    """Image generation process tracking"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    id = models.AutoField(primary_key=True)
    
    # UUID for API/external use
    task_id = models.UUIDField(unique=True, default=uuid.uuid4, db_index=True)
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # Source images
    body_asset = models.ForeignKey(Assets, on_delete=models.SET_NULL, null=True, related_name='used_as_body_in_generations')
    clothing_upload_ids = models.JSONField(default=list)  # ['uuid1', 'uuid2']
    
    # Generator config (no choices - validate in views)
    generator_type = models.CharField(max_length=50, db_index=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    provider_task_id = models.CharField(max_length=200, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    
    result_asset = models.ForeignKey(Assets, on_delete=models.SET_NULL, null=True, blank=True, related_name='generated_by_task')
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-id']
        indexes = [
            models.Index(fields=['user', 'status']),
        ]
