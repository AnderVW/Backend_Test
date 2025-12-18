# Gemini AI Integration Guide

## Overview
Successfully integrated Google Gemini 2.5 Flash Image generation with support for future custom models. The system allows users to generate virtual try-on images by selecting a body image and clothing items.

## Architecture

### 1. AI Generation Library (`app/_libs/lib_aigeneration.py`)

**Base Class:**
- `BaseAIGenerator`: Abstract base class for all generators

**Implemented Generators:**
- `GeminiGenerator`: Google Gemini 2.5 Flash Image generator
- `CustomModelGenerator`: Placeholder for future custom model (ready to implement)

**Factory Function:**
- `get_generator(generator_type)`: Returns appropriate generator instance

**Key Features:**
- Downloads images from Azure (no local storage)
- Converts to bytes for API calls
- Streams response from Gemini
- Returns generated image bytes

### 2. Prompts (`app/_libs/lib_prompts.py`)

**New Function:**
- `get_gemini_virtual_fit_prompt(num_clothing_items)`: Optimized prompt for Gemini
- Uses your tested prompt: "replace the person cloth with the added images..."

**Existing Function:**
- `get_virtual_fit_prompt()`: Generic prompt for other generators

### 3. API Endpoint (`app/api/views.py`)

**Updated Endpoint:** `/api/virtual-fit/generate/`

**Request Body:**
```json
{
  "body_upload_id": "uuid",
  "clothing_upload_ids": ["uuid1", "uuid2"],
  "generator_type": "gemini"  // or "custom"
}
```

**Response:**
```json
{
  "upload_id": "uuid",
  "url": "azure_sas_url",
  "original_filename": "generated_gemini_20241114_120000.jpg",
  "file_size": 123456,
  "created_at": "2024-11-14T12:00:00Z",
  "generator_type": "gemini",
  "message": "Virtual fit generated successfully"
}
```

**Flow:**
1. Validates input (body + clothing images)
2. Retrieves assets from database
3. Gets SAS URLs from Azure (with caching)
4. Downloads images temporarily (not stored on server)
5. Calls appropriate generator
6. Uploads result to Azure under `user_{id}/generated/`
7. Creates database record with status='uploaded'
8. Returns SAS URL for frontend display

### 4. Frontend (`app/templates/virtufit/virtual_fit.html`)

**Two Generation Buttons:**
- **Generate with Gemini** (Purple/Pink gradient): Calls Gemini API
- **Generate with Custom Model** (Blue/Teal gradient): Placeholder for custom model

**Features:**
- Separate buttons for each generator
- Visual feedback during generation (modal with spinner)
- Automatic reload of generated images
- Error handling with user-friendly notifications

## Setup Instructions

### 1. Environment Variables

Add to your `.env` file:
```bash
GEMINI_API_KEY=your_gemini_api_key_here
```

Get your API key from: https://aistudio.google.com/app/apikey

### 2. Dependencies

Already in `requirements.txt`:
```
google-genai==1.50.1
```

Install if needed:
```bash
pip install google-genai
```

### 3. Database

No migrations needed - uses existing `Assets` model with `category='generated'`

## Testing the Integration

### Manual Testing:

1. **Navigate to Virtual Fit page:** `/virtual-fit/`

2. **Upload a body image:**
   - Click "Upload Body Image"
   - Select a full-body photo
   - Wait for upload completion

3. **Select images:**
   - Click on ONE body image (purple border when selected)
   - Click on 1-3 clothing items (blue border when selected)

4. **Generate:**
   - Bottom bar appears with two buttons
   - Click "Generate with Gemini"
   - Wait 30-60 seconds (modal shows progress)
   - Result appears in "Generated Results" section

5. **Verify:**
   - Generated image displays correctly
   - Image is saved to Azure under `user_{id}/generated/`
   - Database record exists with status='uploaded'
   - Can download/view generated image

### API Testing with cURL:

```bash
# Get CSRF token and session cookie first by logging in

# Generate with Gemini
curl -X POST http://localhost:8000/api/virtual-fit/generate/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "X-CSRFToken: YOUR_CSRF_TOKEN" \
  -d '{
    "body_upload_id": "your-body-upload-id",
    "clothing_upload_ids": ["clothing-id-1", "clothing-id-2"],
    "generator_type": "gemini"
  }'
```

## Mobile App Integration

The API is ready for mobile app consumption:

### Authentication:
- Use JWT tokens (already implemented)
- Send token in `Authorization: Bearer {token}` header

### Endpoints:
```
POST /api/virtual-fit/generate/
```

**Headers:**
```
Authorization: Bearer {jwt_token}
Content-Type: application/json
```

**Body:**
```json
{
  "body_upload_id": "uuid",
  "clothing_upload_ids": ["uuid1", "uuid2"],
  "generator_type": "gemini"
}
```

**Polling for Results:**
Mobile apps can poll `/api/assets/?category=generated` to check for new images.

## Adding Custom Model (Future)

When you're ready to implement your custom model:

### 1. Update `CustomModelGenerator` in `lib_aigeneration.py`:

```python
class CustomModelGenerator(BaseAIGenerator):
    def __init__(self):
        super().__init__()
        # Initialize your model/API client
        self.api_url = os.environ.get("CUSTOM_MODEL_API_URL")
        self.api_key = os.environ.get("CUSTOM_MODEL_API_KEY")
        logger.info("Custom model generator initialized")
    
    def generate_virtual_fit(self, body_image_url, clothing_image_urls, prompt_text):
        # Download images
        body_image_data = self._download_image(body_image_url)
        clothing_images_data = [self._download_image(url) for url in clothing_image_urls]
        
        # Convert to base64 if needed
        body_b64 = base64.b64encode(body_image_data).decode('utf-8')
        clothing_b64 = [base64.b64encode(img).decode('utf-8') for img in clothing_images_data]
        
        # Call your API
        response = requests.post(
            self.api_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "prompt": prompt_text,
                "body_image": body_b64,
                "clothing_images": clothing_b64
            }
        )
        
        # Return image bytes
        return response.content
```

### 2. Add environment variables:
```bash
CUSTOM_MODEL_API_URL=https://your-api.com/generate
CUSTOM_MODEL_API_KEY=your_api_key
```

### 3. Test:
Click "Generate with Custom Model" button on frontend.

## Technical Details

### Image Handling:
- Images are downloaded from Azure using SAS URLs
- Held in memory temporarily (not saved to disk)
- Sent to Gemini as bytes
- Generated images are uploaded directly to Azure
- Server never stores images permanently

### Performance:
- Generation takes 30-60 seconds (Gemini processing time)
- SAS URLs are cached in Redis (2 hours TTL)
- Asynchronous uploads to Azure

### Security:
- All endpoints require authentication
- SAS URLs expire after 2 hours
- CSRF protection enabled
- Images scoped to user folders

### Error Handling:
- API validates all inputs
- Graceful fallbacks if Redis unavailable
- Detailed logging for debugging
- User-friendly error messages

## Troubleshooting

### Issue: "GEMINI_API_KEY not configured"
**Solution:** Add API key to `.env` file and restart server

### Issue: "Failed to download body image"
**Solution:** Check Azure connectivity and SAS URL generation

### Issue: "No image data received from Gemini"
**Solution:** 
- Check API key is valid
- Check Gemini API quota/limits
- Review prompt format
- Check image formats (should be JPEG)

### Issue: "Custom model not implemented yet"
**Solution:** Expected - implement `CustomModelGenerator` class when ready

## Next Steps

1. ✅ Test Gemini generation with real images
2. ⏳ Monitor performance and error rates
3. ⏳ Implement custom model when ready
4. ⏳ Add analytics/tracking for generation requests
5. ⏳ Consider adding generation history/favorites

## API Documentation

Full API documentation available at: (Add your API docs URL)

For support, contact: (Add your support contact)

