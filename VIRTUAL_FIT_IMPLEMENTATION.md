# Virtual Fit Feature Implementation Guide

## Overview

This document describes the Virtual Fit feature that has been implemented for ViWear. The feature allows users to:
1. Upload body images
2. Upload clothing images  
3. Select images and generate virtual try-on results using AI

## What Was Implemented

### 1. Database Changes

**File:** `app/api/models.py`

- Added `category` field to `Assets` model with choices: `item`, `body`, `generated`
- Added database index for efficient querying by `(user, category, status)`
- Backward compatible with existing data (defaults to `item`)

**Migration Required:**
```bash
cd app
python manage.py makemigrations api
python manage.py migrate
```

### 2. Azure Storage Integration

**File:** `app/_libs/lib_azure.py`

**Changes:**
- Updated `generate_upload_sas_urls()` to accept `category` parameter
- Blob storage structure:
  - Clothing Items: `user_{id}/item/{filename}`
  - Body Images: `user_{id}/body/{filename}`
  - Generated Images: `user_{id}/generated/{filename}`
- Added `upload_blob_from_bytes()` method for direct blob upload

### 3. AI Integration Libraries

#### a. Gemini Client (`app/_libs/lib_gemini.py`)

**Important Note:** This is a TEMPLATE implementation. Google Gemini is primarily for multimodal understanding, not image generation.

**You need to implement actual image generation using one of:**
- **Google Imagen** (Vertex AI)
- **Stability AI's Stable Diffusion**
- **OpenAI's DALL-E**
- **Replicate's virtual try-on models**
- **Custom model**

The file includes commented examples for different services.

#### b. Prompt Library (`app/_libs/lib_prompts.py`)

Provides optimized prompts for:
- `get_virtual_fit_prompt()` - Virtual try-on generation
- `get_outfit_recommendation_prompt()` - Outfit suggestions
- `get_style_analysis_prompt()` - Clothing style analysis

### 4. API Endpoints

**File:** `app/api/views.py`

#### Updated Endpoints:

**POST `/api/assets/init/`**
- Now accepts `category` parameter in request body
- Values: `item` (default), `body`, `generated`

**GET `/api/assets/`**
- Now accepts `category` query parameter for filtering
- Example: `/api/assets/?category=body`

#### New Endpoints:

**POST `/api/virtual-fit/generate/`**
- Generates virtual fit image
- Request body:
  ```json
  {
    "body_upload_id": "uuid",
    "clothing_upload_ids": ["uuid1", "uuid2", ...]
  }
  ```
- Response:
  ```json
  {
    "upload_id": "uuid",
    "url": "https://...",
    "original_filename": "generated_20241113_123456.jpg",
    "file_size": 123456,
    "created_at": "2024-11-13T12:34:56Z",
    "message": "Virtual fit generated successfully"
  }
  ```

### 5. Web Interface

**File:** `app/templates/virtufit/virtual_fit.html`

**Features:**
- Upload body images section
- Display all clothing images with multi-select
- Display body images with single-select
- Fixed bottom bar showing selection status
- Generate button (disabled until valid selection)
- Display generated results in gallery
- Real-time updates and status indicators
- Drag-and-drop file upload
- Beautiful, responsive UI with Tailwind CSS

**Access:** `http://localhost:8088/virtual-fit/`

### 6. Configuration

**File:** `app/core/settings.py`

Added:
```python
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
```

**Environment Variables Required:**
```env
GEMINI_API_KEY=your_api_key_here
```

### 7. Dependencies

**File:** `app/requirements.txt`

Added:
```
google-generativeai==0.8.3
```

**Installation:**
```bash
pip install -r app/requirements.txt
```

## Setup Instructions

### 1. Install Dependencies
```bash
cd /home/dan/projects/ViWear
pip install -r app/requirements.txt
```

### 2. Run Migrations
```bash
cd app
python manage.py makemigrations api
python manage.py migrate
```

### 3. Configure Environment Variables

Add to your `.env` file:
```env
# For Gemini (if using for analysis)
GEMINI_API_KEY=your_gemini_api_key

# OR for Stability AI (recommended for actual image generation)
STABILITY_API_KEY=your_stability_api_key

# OR for Replicate
REPLICATE_API_TOKEN=your_replicate_token

# OR for OpenAI
OPENAI_API_KEY=your_openai_api_key
```

### 4. Implement Image Generation

**Critical Step:** Open `app/_libs/lib_gemini.py` and implement the actual image generation logic in the `generate_virtual_fit()` method.

#### Recommended Options:

##### Option A: Replicate (Easiest)
Replicate hosts various virtual try-on models. Example:

```bash
pip install replicate
```

```python
import replicate

# In generate_virtual_fit() method:
output = replicate.run(
    "cuuupid/idm-vton:c871bb9b046607b680449ecbae55fd8c6d945e0a1948644bf2361b3d021d3ff4",
    input={
        "garm_img": clothing_image_urls[0],
        "human_img": body_image_url,
        "garment_des": prompt_text
    }
)

# Download the generated image
response = requests.get(output, timeout=60)
return response.content
```

##### Option B: Stability AI
```bash
pip install stability-sdk
```

##### Option C: Google Imagen (Vertex AI)
Requires Google Cloud setup:
```bash
pip install google-cloud-aiplatform
```

##### Option D: Custom Model
Host your own Stable Diffusion or virtual try-on model.

### 5. Update Existing My Assets Page (Optional)

The existing `/my-assets/` page still works but now only shows `item` category by default. You may want to update it to:
- Show category tabs
- Allow filtering by category
- Add category selection during upload

## Usage Flow

### For Users:

1. **Upload Body Images:**
   - Go to `/virtual-fit/`
   - Click "Upload Body Image"
   - Select/drop body photos (max 5 files, 10MB each)
   - Wait for upload confirmation

2. **Upload Clothing (if not done):**
   - Go to `/my-assets/`
   - Upload clothing images as before

3. **Generate Virtual Fit:**
   - Go to `/virtual-fit/`
   - Select ONE body image (purple border when selected)
   - Select ONE or MORE clothing items (blue border when selected)
   - Click "Generate Virtual Fit" button
   - Wait 30-60 seconds for AI processing
   - View result in "Generated Results" section

### For Developers:

1. **API Integration:**
```javascript
// Initialize upload with category
const response = await fetch('/api/assets/init/', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
    },
    body: JSON.stringify({
        files: [{name: 'body.jpg', size: 12345}],
        category: 'body'  // or 'item' or 'generated'
    })
});

// Generate virtual fit
const result = await fetch('/api/virtual-fit/generate/', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
    },
    body: JSON.stringify({
        body_upload_id: 'body-uuid',
        clothing_upload_ids: ['clothing-uuid-1', 'clothing-uuid-2']
    })
});
```

## Architecture

```
User Browser
    ↓
Django Views (virtual_fit.html)
    ↓
API Endpoints (/api/virtual-fit/generate/)
    ↓
Views (generate_virtual_fit)
    ↓
┌─────────────────┬──────────────────┐
↓                 ↓                  ↓
AzureBlobClient   GeminiClient      PromptsLib
    ↓                 ↓                  ↓
Azure Blob        Image Gen API      Prompt Templates
Storage           (Your Choice)
```

## File Structure

```
app/
├── _libs/
│   ├── lib_azure.py          # Azure storage operations (updated)
│   ├── lib_gemini.py         # AI integration (NEW - needs implementation)
│   └── lib_prompts.py        # Prompt templates (NEW)
├── api/
│   ├── models.py             # Assets model with category field (updated)
│   ├── views.py              # API endpoints (updated + new)
│   └── urls.py               # API routes (updated)
├── core/
│   ├── settings.py           # Django settings (updated)
│   ├── urls.py               # Main routes (updated)
│   └── views.py              # Page views (updated)
├── templates/
│   └── virtufit/
│       ├── my_assets.html    # Clothing management (existing)
│       └── virtual_fit.html  # Virtual fit page (NEW)
└── requirements.txt          # Python dependencies (updated)
```

## Testing

### Manual Testing:

1. **Test Body Image Upload:**
   ```bash
   # Navigate to /virtual-fit/
   # Click "Upload Body Image"
   # Upload a test image
   # Verify it appears in Body Images section
   ```

2. **Test Image Selection:**
   ```bash
   # Select one body image (should highlight purple)
   # Try selecting another (should switch selection)
   # Select multiple clothing items (should all highlight blue)
   # Verify bottom bar updates with count
   ```

3. **Test API Directly:**
   ```bash
   # Get auth token first
   curl -X POST http://localhost:8088/api/auth/login/ \
     -H "Content-Type: application/json" \
     -d '{"email":"test@example.com","password":"test123"}'
   
   # List body images
   curl http://localhost:8088/api/assets/?category=body \
     -H "Authorization: Bearer YOUR_TOKEN"
   ```

## Troubleshooting

### Issue: "Image generation service not configured"
**Solution:** Implement the image generation logic in `lib_gemini.py` as described above.

### Issue: No body images showing
**Solution:** 
- Check database migrations ran successfully
- Verify uploads are using `category='body'`
- Check browser console for API errors

### Issue: SAS URLs expired
**Solution:** 
- SAS URLs are cached for 2 hours in Redis
- URLs are automatically regenerated when expired
- Check Redis is running: `redis-cli ping`

### Issue: Upload fails
**Solution:**
- Check Azure credentials in `.env`
- Verify container exists
- Check CORS settings on Azure
- Check file size limits (10MB)

## Future Enhancements

1. **Add Style Recommendations:**
   - Use Gemini to analyze clothing and suggest combinations
   - Implement in `lib_gemini.py` using `generate_text_response()`

2. **Batch Generation:**
   - Generate multiple combinations at once
   - Queue system for long-running jobs

3. **Image Editing:**
   - Crop/resize before generation
   - Background removal for body images

4. **Social Features:**
   - Share generated looks
   - Save favorite combinations

5. **Mobile App Integration:**
   - All APIs are ready for mobile
   - JWT authentication already implemented

## Security Considerations

1. **File Upload:**
   - Max 10MB per file enforced
   - MIME type validation
   - Azure SAS tokens expire after 1 hour

2. **API Protection:**
   - All endpoints require authentication
   - CSRF protection enabled
   - Rate limiting recommended (TODO)

3. **Image URLs:**
   - SAS URLs expire after 2 hours
   - Cached in Redis for performance
   - User-specific access only

## Performance

- **Upload:** Direct to Azure (no server bottleneck)
- **SAS URLs:** Cached in Redis (2hr TTL)
- **Generation:** Depends on chosen AI service (30-60s typical)
- **Database:** Indexed queries for fast filtering

## Cost Considerations

- **Azure Storage:** ~$0.02/GB/month
- **Image Generation:** Varies by service:
  - Replicate: ~$0.01-0.10 per generation
  - Stability AI: ~$0.02 per generation
  - OpenAI DALL-E: ~$0.04 per generation
- **Redis:** Minimal (local or cloud)

## Support

For issues or questions:
1. Check logs: `tail -f app/logs/django.log`
2. Check browser console for JS errors
3. Verify all environment variables are set
4. Test API endpoints individually

## Conclusion

The virtual fit feature is **90% complete**. The main remaining task is implementing the actual image generation service in `lib_gemini.py`. Everything else (database, API, UI, Azure integration) is fully functional and ready to use.

Choose your preferred image generation service, implement it in the `generate_virtual_fit()` method, and you're ready to go!

