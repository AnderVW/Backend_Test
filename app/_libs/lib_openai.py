"""
OpenAI GPT-4 Vision integration for clothing part detection
"""
from loguru import logger
from django.conf import settings
from openai import OpenAI


def detect_clothing_part(image_url):
    """
    Detect clothing part using OpenAI GPT-4 Vision API
    
    Args:
        image_url: URL to the clothing image (with SAS token)
        
    Returns:
        str: 'upper', 'lower', or 'full_set', or None if failed
    """
    try:
        api_key = getattr(settings, 'OPENAI_API_KEY', None)
        if not api_key:
            logger.error("OPENAI_API_KEY not configured")
            return None
        
        # Initialize OpenAI client
        client = OpenAI(api_key=api_key)
        
        # logger.info("Calling OpenAI GPT-4 Vision API for clothing part detection")
        
        # Call OpenAI Vision API
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Analyze this clothing image and determine which part of the body it belongs to. Respond with ONLY one word: 'upper' for upper body clothing (t-shirts, shirts, jackets, tops), 'lower' for lower body clothing (pants, jeans, skirts, shorts), or 'full_set' for full-body clothing (dresses, jumpsuits)."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url
                            }
                        }
                    ]
                }
            ],
            max_tokens=10
        )
        
        detected_part = response.choices[0].message.content.strip().lower()
        
        # Validate response
        valid_parts = ['upper', 'lower', 'full_set']
        if detected_part not in valid_parts:
            logger.warning(f"OpenAI returned unexpected part: {detected_part}, defaulting to None")
            return None
        
        # logger.info(f"Detected clothing part: {detected_part}")
        return detected_part
        
    except Exception as e:
        logger.error(f"Error detecting clothing part: {e}", exc_info=True)
        return None

