# Clothing Part Detection Implementation

## Overview

This feature automatically detects whether uploaded clothing items belong to the upper body, lower body, or are full_set/full-body garments (like dresses). The detection uses OpenAI GPT-4 Vision API and runs asynchronously via Huey task queue.

## Architecture

### Flow

1. **Upload Flow:**
   - User uploads clothing image via `/api/assets/init/`
   - Frontend receives SAS URL and uploads directly to Azure Storage
   - When upload completes (status changes to 'uploaded'), a Huey task is triggered
   - Task downloads image, calls OpenAI GPT-4 Vision, detects part
   - Database is updated with detected `part` field

2. **Generation Flow:**
   - User calls `/api/virtual-fit/generate/` with clothing items
   - System uses detected parts from database (or accepts override via `parts` parameter)
   - Parts information is included in the AI generation prompt

## Database Changes

### Assets Model

Added new field:
```python
part = models.CharField(
    max_length=20, 
    choices=PART_CHOICES, 
    blank=True, 
    null=True,
    help_text='Detected clothing part: upper, lower, or full_set'
)
```

**Choices:**
- `'upper'` - Upper body clothing (t-shirts, shirts, jackets, tops)
- `'lower'` - Lower body clothing (pants, jeans, skirts, shorts)
- `'full_set'` - Full-body clothing (dresses, jumpsuits)

**Migration Required:**
```bash
cd app
python manage.py makemigrations api
python manage.py migrate
```

## API Changes

### 1. List Assets Endpoint

**GET `/api/assets/`**

Response now includes `part` field:
```json
{
  "assets": [
    {
      "upload_id": "uuid",
      "original_filename": "shirt.jpg",
      "part": "upper",  // New field
      "category": "item",
      "status": "uploaded",
      ...
    }
  ]
}
```

### 2. Generate Virtual Fit Endpoint

**POST `/api/virtual-fit/generate/`**

New optional parameter:
```json
{
  "body_upload_id": "uuid",
  "clothing_upload_ids": ["uuid1", "uuid2"],
  "generator_type": "gemini",
  "parts": ["upper", "lower"]  // Optional: override detected parts
}
```

**Behavior:**
- If `parts` is provided: validates length matches `clothing_upload_ids` and uses provided values
- If `parts` is omitted: uses detected parts from database (may be `null` if not detected yet)
- Parts information is included in the AI generation prompt

## Configuration

### Environment Variables

Add to your `.env` file:
```bash
# OpenAI API Key for clothing part detection
OPENAI_API_KEY=your_openai_api_key_here

# Redis URL (already configured for Huey)
REDIS_URL=redis://localhost:6379/0
```

### Huey Worker

Run the Huey worker to process background tasks:
```bash
cd app
python manage.py run_huey
```

## Usage Examples

### 1. Upload and Auto-Detect

```python
# 1. Initialize upload
POST /api/assets/init/
{
  "files": [{"name": "shirt.jpg", "size": 123456}],
  "category": "item"
}

# 2. Frontend uploads to SAS URL

# 3. Check upload status (triggers part detection)
GET /api/assets/check/{upload_id}/

# 4. Part detection runs in background
# Database is updated automatically

# 5. List assets (includes detected part)
GET /api/assets/?category=item
# Response includes: "part": "upper"
```
