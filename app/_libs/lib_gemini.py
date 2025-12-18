"""
Google Gemini API integration for virtual try-on image generation
"""
from django.conf import settings
from loguru import logger
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO
import requests
import time


def _prepare_image_for_gemini(img_data, image_name="image"):
    """
    Prepare image for Gemini: convert to RGB, resize if needed
    
    Args:
        img_data: Raw image bytes
        image_name: Name for logging purposes
        
    Returns:
        PIL.Image: Processed PIL Image ready for Gemini
    """
    img = Image.open(BytesIO(img_data))
    logger.debug(f"{image_name}: format={img.format}, mode={img.mode}, size={img.size}")
    
    # Handle transparency for PNG (composite onto white background)
    if img.mode in ('RGBA', 'LA', 'P'):
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
        img = background
        logger.debug(f"{image_name} converted from {img.mode} to RGB with white background")
    elif img.mode != 'RGB':
        img = img.convert('RGB')
        logger.debug(f"{image_name} converted to RGB")
    
    # Resize if height > 1024px
    if img.size[1] > 1024:
        ratio = 1024 / img.size[1]
        new_size = (int(img.size[0] * ratio), 1024)
        img = img.resize(new_size, Image.Resampling.LANCZOS)
        logger.debug(f"{image_name} resized to {new_size}")
    
    return img


def generate_virtual_fit(body_image_url, clothing_image_urls, prompt_text):
    """
    Generate virtual fit image using Gemini 2.5 Flash Image
    
    Args:
        body_image_url: URL to the body image (with SAS token)
        clothing_image_urls: List of URLs to clothing images (with SAS tokens)
        prompt_text: The prompt text for generation
        
    Returns:
        bytes: Generated image data, or None if failed
    """
    try:
        logger.info(f"Starting Gemini generation with {len(clothing_image_urls)} clothing items")
        
        # Initialize Gemini client
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        
        # Download and prepare images
        body_image_data = _download_image(body_image_url)
        if not body_image_data:
            logger.error("Failed to download body image")
            return None
        
        clothing_images_data = []
        for url in clothing_image_urls:
            img_data = _download_image(url)
            if not img_data:
                logger.error(f"Failed to download clothing image: {url[:50]}")
                return None
            clothing_images_data.append(img_data)
        
        logger.info(f"Downloaded all images successfully")
        
        # Prepare PIL Images (convert to RGB, resize)
        clothing_images = []
        for i, img_data in enumerate(clothing_images_data):
            pil_img = _prepare_image_for_gemini(img_data, f"Clothing {i+1}")
            clothing_images.append(pil_img)
        
        body_image = _prepare_image_for_gemini(body_image_data, "Body")
        
        # Build contents: clothing images + body + text (as per official docs)
        contents = clothing_images + [body_image, prompt_text]
        
        # Configure generation
        generate_content_config = types.GenerateContentConfig(
            response_modalities=["IMAGE"],
        )
        
        logger.info("Calling Gemini API...")
        logger.debug(f"Contents: {len(clothing_images)} clothing + 1 body + 1 text = {len(contents)} total")
        
        # Call Gemini API (no retry)
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash-image",
                contents=contents,
                config=generate_content_config,
            )
            logger.info(f"Gemini API response received")
            
        except Exception as api_error:
            logger.error(f"Gemini API call failed: {type(api_error).__name__}: {str(api_error)}")
            return None
        
        # Check for IMAGE_OTHER rejection
        if (hasattr(response, 'candidates') and response.candidates and 
            hasattr(response.candidates[0], 'finish_reason') and
            str(response.candidates[0].finish_reason) == 'FinishReason.IMAGE_OTHER'):
            
            logger.error("===== GEMINI REJECTED IMAGE (IMAGE_OTHER) =====")
            
            # Log full response details
            try:
                response_dict = response.to_json_dict()
                logger.error(f"Full response JSON: {response_dict}")
            except Exception as e:
                logger.error(f"Could not serialize response: {e}")

            raise ValueError("Gemini refused to generate the image.")
        
        # Extract image from response
        try:
            
            if not hasattr(response, 'parts'):
                logger.error(f"Response has no 'parts' attribute")
                # Try to get parts from candidates
                if hasattr(response, 'candidates') and response.candidates:
                    candidate = response.candidates[0]
                    if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                        parts = candidate.content.parts
                        logger.info(f"Found parts in candidates[0].content.parts: {len(parts)}")
                    else:
                        logger.error("No parts found in candidates either")
                        return None
                else:
                    return None
            else:
                parts = response.parts
            
            if not parts:
                logger.error("Parts list is empty")
                return None
            
            logger.info(f"Found {len(parts)} parts to process")
            
            image_parts = []
            for i, part in enumerate(parts):
                logger.debug(f"Part {i}: has inline_data={hasattr(part, 'inline_data')}, has text={hasattr(part, 'text')}")
                if hasattr(part, 'inline_data') and part.inline_data:
                    logger.debug(f"Part {i} has inline_data with data={part.inline_data.data is not None}")
                    if part.inline_data.data:
                        image_parts.append(part.inline_data.data)
                elif hasattr(part, 'text') and part.text:
                    logger.debug(f"Part {i} text: {part.text[:200]}")
            
            if not image_parts:
                logger.error("No image data in Gemini response parts")
                return None
            
            generated_image_data = image_parts[0]
            logger.info(f"Generation successful: {len(generated_image_data)} bytes")
            
            return generated_image_data
            
        except Exception as extract_error:
            logger.error(f"Failed to extract image from response: {type(extract_error).__name__}: {str(extract_error)}", exc_info=True)
            return None
        
    except ValueError:
        # Re-raise ValueError (Gemini rejection) to be caught by API view
        raise
    except Exception as e:
        logger.error(f"Unexpected error in Gemini generation: {type(e).__name__}: {str(e)}", exc_info=True)
        return None


def _download_image(url):
    """
    Download image from URL
    
    Args:
        url: Image URL (Azure SAS URL)
        
    Returns:
        bytes: Image data or None if failed
    """
    try:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        return response.content
    except Exception as e:
        logger.error(f"Failed to download image: {str(e)}")
        return None
