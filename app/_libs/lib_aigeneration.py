"""
AI image generation factory and custom model implementations
"""
import base64
import requests
from loguru import logger
from . import lib_gemini
from . import lib_prompts

def generate_virtual_fit_sync(body_image_url, clothing_image_urls, generator_type="gemini", part=None):
    """
    Generate virtual fit image using specified AI generator
    
    Args:
        body_image_url: URL to the body image (with SAS token)
        clothing_image_urls: List of URLs to clothing images (with SAS tokens)
        generator_type: Type of generator ("gemini", "vwflux", or "vwcatvton")
            Note: FitRoom is handled separately in tasks.py with async progress tracking
        part: Clothing part ('upper', 'lower', 'full_set')
        
    Returns:
        bytes: Generated image data, or None if failed
    """
    if generator_type == "gemini":
        prompt_text = lib_prompts.get_gemini_virtual_fit_prompt(num_clothing_items=len(clothing_image_urls))
        return lib_gemini.generate_virtual_fit(body_image_url, clothing_image_urls, prompt_text)
    elif generator_type == "vwflux":
        return _generate_vwflux_model(body_image_url, clothing_image_urls[0] if clothing_image_urls else None, part)
    elif generator_type == "vwcatvton":
        return _generate_vwcatvton_model(body_image_url, clothing_image_urls[0] if clothing_image_urls else None, part)
    else:
        logger.error(f"Unknown generator type: {generator_type}")
        return None


def _generate_vwflux_model(body_image_url, clothing_image_url, part='full_set'):
    """
    Generate virtual fit using VWFlux (ViWear Flux) proprietary model API
    
    Args:
        body_image_url: URL to the body image (with SAS token)
        clothing_image_url: URL to the clothing image (with SAS token)
        part: Clothing part ('upper', 'lower', 'full_set') or None
        
    Returns:
        bytes: Generated image data, or None if failed
    """
    try:
        logger.info("Starting VWFlux model generation")
        
        # Static token
        token = 'L9!p@j5*xZ&R7$Qc'
        
        # API endpoint
        api_url = "https://sunwenjun1997--viwear-flux-run.modal.run"
        
        # Download images and convert to base64
        body_image_data = _download_image(body_image_url)
        if not body_image_data:
            logger.error("Failed to download body image")
            return None
        
        clothing_image_data = _download_image(clothing_image_url)
        if not clothing_image_data:
            logger.error("Failed to download clothing image")
            return None
        
        # Convert to base64
        body_base64 = base64.b64encode(body_image_data).decode('utf-8')
        garment_base64 = base64.b64encode(clothing_image_data).decode('utf-8')
        
        # Prepare request payload
        payload = {
            "image": body_base64,
            "garment": garment_base64,
            "part": part,
            "token": token
        }
        
        logger.info(f"Calling VWFlux API with part: {part}")
        
        # Make API request
        response = requests.post(api_url, json=payload, timeout=120)
        response.raise_for_status()
        
        result_json = response.json()
        
        # Extract image from response
        if "image_base64" not in result_json:
            logger.error("VWFlux API response missing 'image_base64' field")
            return None
        
        # Decode base64 image
        generated_image_data = base64.b64decode(result_json["image_base64"])
        
        logger.info(f"VWFlux model generation successful: {len(generated_image_data)} bytes")
        
        return generated_image_data
        
    except requests.exceptions.RequestException as e:
        logger.error(f"VWFlux API request failed: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Error in VWFlux model generation: {type(e).__name__}: {str(e)}", exc_info=True)
        return None


def _generate_vwcatvton_model(body_image_url, clothing_image_url, part='full_set'):
    """
    Generate virtual fit using VWCatVTON (ViWear CatVTON) proprietary model API
    
    Args:
        body_image_url: URL to the body image (with SAS token)
        clothing_image_url: URL to the clothing image (with SAS token)
        part: Clothing part ('upper', 'lower', 'full_set') or None
        
    Returns:
        bytes: Generated image data, or None if failed
    """
    try:
        logger.info("Starting VWCatVTON model generation")
        
        # Static token
        token = 'L9!p@j5*xZ&R7$Qc'
        
        # API endpoint
        api_url = "https://sunwenjun1997--viwear-catvton-run.modal.run"
        
        # Download images and convert to base64
        body_image_data = _download_image(body_image_url)
        if not body_image_data:
            logger.error("Failed to download body image")
            return None
        
        clothing_image_data = _download_image(clothing_image_url)
        if not clothing_image_data:
            logger.error("Failed to download clothing image")
            return None
        
        # Convert to base64
        body_base64 = base64.b64encode(body_image_data).decode('utf-8')
        garment_base64 = base64.b64encode(clothing_image_data).decode('utf-8')
        
        # Prepare request payload
        payload = {
            "image": body_base64,
            "garment": garment_base64,
            "part": part,
            "token": token
        }
        
        logger.info(f"Calling VWCatVTON API with part: {part}")
        
        # Make API request
        response = requests.post(api_url, json=payload, timeout=120)
        response.raise_for_status()
        
        result_json = response.json()
        
        # Extract image from response
        if "image_base64" not in result_json:
            logger.error("VWCatVTON API response missing 'image_base64' field")
            return None
        
        # Decode base64 image
        generated_image_data = base64.b64decode(result_json["image_base64"])
        
        logger.info(f"VWCatVTON model generation successful: {len(generated_image_data)} bytes")
        
        return generated_image_data
        
    except requests.exceptions.RequestException as e:
        logger.error(f"VWCatVTON API request failed: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Error in VWCatVTON model generation: {type(e).__name__}: {str(e)}", exc_info=True)
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
