# ViWear Category Reference

## Category Names

The system now uses **three distinct categories** for organizing assets:

| Category Name | Description | Azure Blob Path |
|--------------|-------------|-----------------|
| `item` | Clothing items/garments | `user_{id}/item/{filename}` |
| `body` | Body/person images | `user_{id}/body/{filename}` |
| `generated` | AI-generated virtual fit images | `user_{id}/generated/{filename}` |

## Default Category

- **Default for uploads:** `item`
- **Default for My Assets page:** `item` (shows clothing)

## Usage Across the System

### 1. Database Model (`app/api/models.py`)
```python
CATEGORY_CHOICES = [
    ('item', 'Clothing Items'),
    ('body', 'Body Images'),
    ('generated', 'Generated Images'),
]

category = models.CharField(
    max_length=50, 
    choices=CATEGORY_CHOICES, 
    default='item'
)
```

### 2. Azure Storage (`app/_libs/lib_azure.py`)
```python
def generate_upload_sas_urls(self, container_name, files_list, category='item'):
    """
    category: Category of files ('item', 'body', 'generated')
    """
    # Blob name format: user_{id}/{category}/{filename}
    blob_name = f"user_{user_id}/{category}/{original_filename}"
```

### 3. API Endpoints (`app/api/views.py`)

#### Upload Initialization
```python
# POST /api/assets/init/
{
    "files": [...],
    "category": "item"  // or "body" or "generated"
}

valid_categories = ['item', 'body', 'generated']
```

#### List Assets
```python
# GET /api/assets/?category=item
# GET /api/assets/?category=body
# GET /api/assets/?category=generated
```

#### Virtual Fit Generation
```python
# POST /api/virtual-fit/generate/
{
    "body_upload_id": "uuid",      # Must be category='body'
    "clothing_upload_ids": [...]   # Must be category='item'
}
# Returns: category='generated'
```

### 4. Frontend (`app/templates/virtufit/`)

#### My Assets Page (my_assets.html)
- Shows only `category='item'` assets
- Implicit filter (no category parameter = default 'item')

#### Virtual Fit Page (virtual_fit.html)
```javascript
// Load body images
fetch('/api/assets/?category=body')

// Load clothing items
fetch('/api/assets/?category=item')

// Load generated results
fetch('/api/assets/?category=generated')

// Upload body image
fetch('/api/assets/init/', {
    body: JSON.stringify({
        files: [...],
        category: 'body'
    })
})
```

### 5. Prompts Library (`app/_libs/lib_prompts.py`)
```python
"""
Category definitions:
- 'item': Clothing items/garments
- 'body': Body/person images
- 'generated': AI-generated virtual fit images
"""
```

## Migration from Old System

If you had existing data with different category names:

### Before:
- Category was not used or defaulted to 'images'
- Azure paths were: `user_{id}/images/{filename}`

### After:
- Category is `item` for clothing
- Azure paths are: `user_{id}/item/{filename}`

### Migration Strategy:

**Option 1: Database Default**
- New uploads automatically use `category='item'`
- Old records without category field will get default `item` after migration

**Option 2: Data Migration (if needed)**
```python
# If you need to migrate old 'images' category to 'item'
from api.models import Assets

# Update category field
Assets.objects.filter(category='images').update(category='item')

# Note: Azure blob paths don't need to change unless you want consistency
# The system will work with existing /images/ paths as long as 
# azure_blob_name field is correct
```

## Best Practices

1. **Always specify category explicitly** when uploading:
   ```javascript
   // Good
   { files: [...], category: 'body' }
   
   // Avoid relying on defaults
   { files: [...] }  // Will default to 'item'
   ```

2. **Filter by category** when querying:
   ```python
   # Good - explicit
   Assets.objects.filter(user=user, category='item', status='uploaded')
   
   # Works but less clear
   Assets.objects.filter(user=user, status='uploaded')  # Returns all categories
   ```

3. **Validate category** in custom code:
   ```python
   VALID_CATEGORIES = ['item', 'body', 'generated']
   if category not in VALID_CATEGORIES:
       raise ValueError(f"Invalid category: {category}")
   ```

## Category Flow Diagram

```
Upload Flow:
User → Frontend → /api/assets/init/ → Backend → Azure Blob Storage
                   (category='item')             user_{id}/item/

Virtual Fit Flow:
User selects:
  - 1 body image (category='body')
  - N item images (category='item')
      ↓
  /api/virtual-fit/generate/
      ↓
  AI Processing
      ↓
  Generated image saved (category='generated')
      ↓
  Stored in: user_{id}/generated/
```

## Redis Cache Keys

SAS URLs are cached with category information:
```
Key format: asset_sas:{user_id}:{upload_id}
TTL: 2 hours

Note: Cache key doesn't include category, but it's tied to upload_id
which has a category in the database.
```

## Summary

- **Use `item`** for clothing/garments (not 'images' or 'asset')
- **Use `body`** for body/person photos
- **Use `generated`** for AI-generated results
- **Azure paths match categories:** `user_{id}/{category}/{filename}`
- **Default is `item`** for backward compatibility

