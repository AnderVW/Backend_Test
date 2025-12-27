"""
OpenAI GPT-4 Vision integration for clothing part detection
"""
import json
from loguru import logger
from django.conf import settings
from openai import OpenAI


def detect_clothing_item_params_ai(image_url):
    """
    Detect clothing item parameters using OpenAI Structured Output (Vision).

    Returns:
        dict: {
            "type": "upper" | "lower" | "full_set" | "unclassified",
            "category": str | "unclassified",
            "color": str | "unclassified",
            "subcategory": str | "unclassified"
        }
    """
    try:
        api_key = getattr(settings, "OPENAI_API_KEY", None)
        if not api_key:
            logger.error("OPENAI_API_KEY not configured")
            return {"type": "unclassified", "category": "unclassified"}

        client = OpenAI(api_key=api_key)

        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Analyze the clothing image.\n"
                                "Identify:\n"
                                "1) part of the body (type): one of [upper, lower, full_set]. Treat dresses and coats as full_set!\n"
                                "2) category: one of [Tops, Bottom, Dress, ShortJacket, LongJacket, Miscellaneous]\n"
                                "3) subcategory: a specific clothing type, one of "
                                "[Shirt, T-Shirt, Sweater, Hoodie, Blazer, Jacket, Sport, Trench, Coat, "
                                "Jeans, Trouser, Skirt, Shorts, Dress, Trousers, Other]"
                                "4) color: one of "
                                "[Black, White, Grey, Beige, Brown, Burgundy, Navy Blue, Blue, Turquoise, Green, "
                                "Olive, Orange, Yellow, Red, Pink, Lavender, Purple, Gold, Silver, Other]\n"
                                "If unsure for any field, use 'unclassified'."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": image_url},
                        },
                    ],
                }
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "clothing_detection",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": ["upper", "lower", "full_set", "unclassified"],
                            },
                            "category": {
                                "type": "string",
                                "enum": [
                                    "Tops",
                                    "Bottom",
                                    "Dress",
                                    "ShortJacket",
                                    "LongJacket",
                                    "Miscellaneous",
                                    "unclassified",
                                ],
                            },
                            "subcategory": {
                                "type": "string",
                                "enum": [
                                    "Shirt",
                                    "T-Shirt",
                                    "Sweater",
                                    "Hoodie",
                                    "Blazer",
                                    "Jacket",
                                    "Sport",
                                    "Trench",
                                    "Coat",
                                    "Jeans",
                                    "Trouser",
                                    "Skirt",
                                    "Short",
                                    "Dress",
                                    "Other",
                                    "unclassified",
                                ],
                            },
                            "color": {
                                "type": "string",
                                "enum": [
                                    "Black",
                                    "White",
                                    "Grey",
                                    "Beige",
                                    "Brown",
                                    "Burgundy",
                                    "Navy Blue",
                                    "Blue",
                                    "Turquoise",
                                    "Green",
                                    "Olive",
                                    "Orange",
                                    "Yellow",
                                    "Red",
                                    "Pink",
                                    "Lavender",
                                    "Purple",
                                    "Gold",
                                    "Silver",
                                    "Other",
                                    "unclassified",
                                ],
                            },
                        },
                        "required": ["type", "category", "subcategory", "color"],
                        "additionalProperties": False,
                    },
                },
            },

            max_tokens=100,
        )

        # Parse JSON string from content
        content = response.choices[0].message.content
        parsed = json.loads(content)
        
        # Extract actual values from properties (response structure: {"type":"object","properties":{"type":"lower","category":"Jean"}})
        result = parsed.get("properties", parsed)

        # Normalize and validate all parameters
        # Use .strip() for all fields and handle empty strings/None values
        type = (result.get("type") or "").strip() or "unclassified"
        category = (result.get("category") or "").strip() or "unclassified"
        subcategory = (result.get("subcategory") or "").strip() or "unclassified"
        color = (result.get("color") or "").strip() or "unclassified"

        # Validate type enum for only critical param 'type'
        if type not in ["upper", "lower", "full_set", "unclassified"]:
            type = "unclassified"

        return {
            "type": type,
            "category": category,
            "subcategory": subcategory,
            "color": color,
        }

    except Exception as e:
        logger.error(f"Error detecting clothing data: {e}", exc_info=True)
        return {"type": "unclassified", "category": "unclassified", "subcategory": "unclassified", "color": "unclassified"}