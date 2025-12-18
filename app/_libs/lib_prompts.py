"""
Prompt templates for AI image generation

Category definitions:
- 'item': Clothing items/garments
- 'body': Body/person images
- 'generated': AI-generated virtual fit images
"""


def get_gemini_virtual_fit_prompt(num_clothing_items=1):
    """
    Get the prompt for Gemini virtual fit generation
    
    Args:
        num_clothing_items: Number of clothing items being tried on
        
    Returns:
        str: The formatted prompt optimized for Gemini
    """
    if num_clothing_items == 1:
        prompt = """Create a professional e-commerce fashion photo. Take the clothing from the first image and let the woman from the second image wear it. Generate a realistic, full-body shot of the woman wearing the clothing, with the lighting and shadows adjusted to match the environment."""
    else:
        prompt = f"""Create a professional e-commerce fashion photo. Take all {num_clothing_items} clothing items from the first images and let the woman from the final image wear them together. Generate a realistic, full-body shot with adjusted lighting and shadows."""
    # prompt = "Generate a full-body e-commerce fashion photo of a new, unique female model. This model should have the same approximate body type and proportions as the person in the first provided image. She should be wearing the two clothing items from the other two provided images. Ensure realistic lighting, shadows, and a professional studio background."

    return prompt


def get_virtual_fit_prompt(num_clothing_items=1):
    """
    Get the prompt for virtual fit generation
    
    Args:
        num_clothing_items: Number of clothing items being tried on
        
    Returns:
        str: The formatted prompt
    """
    if num_clothing_items == 1:
        prompt = """You are an expert fashion designer and image editor. I'm providing you with two images:
1. A photo of a person (body image)
2. A clothing item

Please create a realistic, high-quality image showing how this person would look wearing this clothing item. 

Important guidelines:
- Maintain the person's body proportions, skin tone, and facial features
- Ensure the clothing fits naturally on the body with proper draping and folds
- Keep the lighting consistent with the original body image
- Make sure the clothing aligns properly with the body structure
- The result should look professional and realistic, as if the person is actually wearing the clothing
- Preserve the style and details of the clothing item

Generate a photorealistic image of the person wearing the clothing."""
    else:
        prompt = f"""You are an expert fashion designer and image editor. I'm providing you with:
1. A photo of a person (body image)
2. {num_clothing_items} different clothing items

Please create a realistic, high-quality image showing how this person would look wearing ALL of these clothing items together as a complete outfit.

Important guidelines:
- Maintain the person's body proportions, skin tone, and facial features
- Ensure all clothing pieces fit naturally on the body with proper draping and folds
- Coordinate the clothing items to create a cohesive outfit
- Keep the lighting consistent with the original body image
- Make sure all clothing aligns properly with the body structure
- The result should look professional and realistic, as if the person is actually wearing the complete outfit
- Preserve the style and details of each clothing item
- Layer the clothing appropriately (e.g., shirt under jacket)

Generate a photorealistic image of the person wearing all the clothing items as a complete outfit."""
    
    return prompt


def get_outfit_recommendation_prompt(body_type, occasion, style_preference):
    """
    Get prompt for outfit recommendations
    
    Args:
        body_type: Description of body type
        occasion: Type of occasion (casual, formal, etc.)
        style_preference: User's style preference
        
    Returns:
        str: The formatted prompt
    """
    prompt = f"""Based on the following information:
- Body type: {body_type}
- Occasion: {occasion}
- Style preference: {style_preference}

Please suggest clothing combinations that would look great. Include:
1. Specific clothing items (tops, bottoms, shoes, accessories)
2. Color combinations that work well
3. Style tips for this body type and occasion

Be specific and practical in your recommendations."""
    
    return prompt


def get_style_analysis_prompt(image_description):
    """
    Get prompt for style analysis of clothing images
    
    Args:
        image_description: Description of the image or context
        
    Returns:
        str: The formatted prompt
    """
    prompt = f"""Analyze this clothing item and provide:
1. Style category (casual, formal, sporty, etc.)
2. Suitable occasions to wear it
3. Colors that would pair well with it
4. Complementary clothing items
5. Season/weather suitability

Context: {image_description}

Provide a concise but comprehensive analysis."""
    
    return prompt

