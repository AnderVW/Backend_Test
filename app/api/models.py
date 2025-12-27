from django.db import models
from django.contrib.auth.models import User
import uuid

STATUS_CHOICES = [
    ('available', 'Available'),  # Uploaded/generated successfully
    ('failed', 'Failed'),        # Upload/generation failed
]



class ClothingItem(models.Model):
    """Clothing items uploaded by users"""
    
    TYPE_CHOICES = [
        ('upper', 'Upper'),
        ('lower', 'Lower'),
        ('full_set', 'Full Set'),
        ('unclassified', 'Unclassified'),
    ]
    
    id = models.AutoField(primary_key=True)
    
    # UUID for API/external use
    asset_id = models.UUIDField(unique=True, default=uuid.uuid4, db_index=True)
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    
    azure_blob_name = models.CharField(max_length=500)
    file_size = models.BigIntegerField()
    
    # Clothing-specific fields
    type = models.CharField(max_length=50, choices=TYPE_CHOICES, default='unclassified', db_index=True)
    category = models.CharField(max_length=100, blank=True, db_index=True)  # e.g. tops, dress, ShortJacket,LongJacket
    color = models.CharField(max_length=100, blank=True, db_index=True)
    subcategory = models.CharField(max_length=100, blank=True, db_index=True)  # e.g., 'jeans', 't-shirt', 'dress'
    comments = models.TextField(blank=True)
    
    display_name = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available', db_index=True)
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        ordering = ['-id']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['user', 'type', 'status']),
            models.Index(fields=['user', 'category', 'status']),
            models.Index(fields=['user', 'color', 'status']),
        ]
        verbose_name = 'Clothing Item'
        verbose_name_plural = 'Clothing Items'
    
    def __str__(self):
        return f"{self.display_name} ({self.category} - {self.status})"




class BaseImage(models.Model):
    """Base images uploaded by users"""
    
    id = models.AutoField(primary_key=True)
    
    # UUID for API/external use
    asset_id = models.UUIDField(unique=True, default=uuid.uuid4, db_index=True)
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    
    azure_blob_name = models.CharField(max_length=500)
    file_size = models.BigIntegerField()
    
    display_name = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available', db_index=True)
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        ordering = ['-id']
        indexes = [
            models.Index(fields=['user', 'status']),
        ]
        verbose_name = 'Base Image'
        verbose_name_plural = 'Base Images'
    
    def __str__(self):
        return f"{self.display_name} (Base - {self.status})"


class GeneratedImage(models.Model):
    """AI-generated virtual fit images"""
    
    id = models.AutoField(primary_key=True)
    
    # UUID for API/external use
    asset_id = models.UUIDField(unique=True, default=uuid.uuid4, db_index=True)
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    
    azure_blob_name = models.CharField(max_length=500)
    file_size = models.BigIntegerField()
    
    display_name = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available', db_index=True)
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        ordering = ['-id']
        indexes = [
            models.Index(fields=['user', 'status']),
        ]
        verbose_name = 'Generated Image'
        verbose_name_plural = 'Generated Images'
    
    def __str__(self):
        return f"{self.display_name} (Generated - {self.status})"


# class Assets(models.Model):
#     """File metadata with final status (detailed process tracking in Tasks)"""
    
#     CATEGORY_CHOICES = [
#         ('item', 'Clothing Items'),
#         ('body', 'Body Images'),
#         ('generated', 'Generated Images'),
#     ]
    
#     PART_CHOICES = [
#         ('upper', 'Upper'),
#         ('lower', 'Lower'),
#         ('full_set', 'Full Set'),
#     ]

#     STATUS_CHOICES = [
#         ('available', 'Available'),  # Uploaded/generated successfully
#         ('failed', 'Failed'),        # Upload/generation failed
#     ]
    
#     id = models.AutoField(primary_key=True)
    
#     # UUID for API/external use
#     asset_id = models.UUIDField(unique=True, default=uuid.uuid4, db_index=True)
    
#     user = models.ForeignKey(User, on_delete=models.CASCADE)
    
#     azure_blob_name = models.CharField(max_length=500)
#     file_size = models.BigIntegerField()
    
#     category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
#     part = models.CharField(max_length=50, choices=PART_CHOICES, blank=True, null=True)
#     display_name = models.CharField(max_length=255)
#     status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available', db_index=True)
    
#     created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
#     class Meta:
#         ordering = ['-id']
#         indexes = [
#             models.Index(fields=['user', 'category', 'status']),
#         ]
    
#     def __str__(self):
#         return f"{self.display_name} ({self.category} - {self.status})"

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
    
    # Asset references - only one should be set per task
    clothing_item = models.OneToOneField(ClothingItem, on_delete=models.CASCADE, null=True, blank=True, related_name='upload_task')
    base_image = models.OneToOneField(BaseImage, on_delete=models.CASCADE, null=True, blank=True, related_name='upload_task')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    error_message = models.TextField(blank=True)
    
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
    base_image = models.ForeignKey(BaseImage, on_delete=models.SET_NULL, null=True, related_name='used_in_generations')
    clothing_upload_ids = models.JSONField(default=list)  # ['uuid1', 'uuid2'] - UUIDs of ClothingItem.asset_id
    
    # Generator config (no choices - validate in views)
    generator_type = models.CharField(max_length=50, db_index=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    provider_task_id = models.CharField(max_length=200, blank=True)
    error_message = models.TextField(blank=True)
    
    result_image = models.ForeignKey(GeneratedImage, on_delete=models.SET_NULL, null=True, blank=True, related_name='generated_by_task')
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-id']
        indexes = [
            models.Index(fields=['user', 'status']),
        ]