import json
import requests
import logging
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

BRIA_API_KEY = os.getenv("BRIA_API_KEY")
BRIA_ENDPOINT = "https://engine.prod.bria-api.com/v2/structured_prompt/generate"

DEFAULT_PARAMETERS = {
    "camera_angle": "Eye Level",
    "lighting": "Natural",
    "composition": "Wide Shot",
    "field_of_view": "35mm"
}

def get_scene_parameters(text_prompt: str) -> dict:
    """
    Converts a raw screenplay text prompt into structured scene parameters using the Bria API.

    Args:
        text_prompt (str): The raw text description of the scene (e.g., "INT. WAREHOUSE - NIGHT").

    Returns:
        dict: A dictionary containing structured scene parameters (camera_angle, lighting, composition, field_of_view).
              Returns default parameters if the API call fails or returns invalid data.
    """
    headers = {
        "api_token": BRIA_API_KEY,
        "Content-Type": "application/json"
    }
    
    payload = {
        "prompt": text_prompt,
        "sync": True
    }

    try:
        logger.info(f"Sending request to Bria API for prompt: '{text_prompt}'")
        response = requests.post(BRIA_ENDPOINT, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        # The API returns a nested JSON string in 'result.structured_prompt'
        # Structure: { "result": { "structured_prompt": "{\"camera_angle\": ...}" } }
        if "result" not in data or "structured_prompt" not in data["result"]:
            logger.error(f"Unexpected API response format: {data}")
            return DEFAULT_PARAMETERS.copy()
            
        structured_prompt_str = data["result"]["structured_prompt"]
        
        try:
            structured_params = json.loads(structured_prompt_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse structured_prompt JSON string: {e}")
            return DEFAULT_PARAMETERS.copy()
            
        # Start with defaults
        final_params = DEFAULT_PARAMETERS.copy()
        # Update with actual values (this keeps all keys from structured_params)
        final_params.update(structured_params)
            
        return final_params

    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {e}")
        return DEFAULT_PARAMETERS.copy()
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return DEFAULT_PARAMETERS.copy()


def refine_scene_parameters(existing_params: dict, refinement_request: str) -> dict:
    """
    Refines existing scene parameters based on a natural language modification request.
    
    Instead of generating from scratch, this function takes the existing scene JSON
    and modifies only the specific fields mentioned in the refinement request.
    
    Args:
        existing_params (dict): The existing scene parameters from the previous generation.
        refinement_request (str): Natural language instruction like "make the lights warmer" 
                                  or "change to a low angle shot".
    
    Returns:
        dict: The refined scene parameters with only the relevant fields modified.
    """
    headers = {
        "api_token": BRIA_API_KEY,
        "Content-Type": "application/json"
    }
    
    # Create a combined prompt that includes the existing parameters and the refinement request
    # This tells the API to modify the existing scene rather than create new
    existing_json_str = json.dumps(existing_params, indent=2)
    
    combined_prompt = f"""Current scene settings:
{existing_json_str}

Director's refinement request: "{refinement_request}"

Please modify the scene settings based on the director's request, keeping all other settings unchanged."""

    payload = {
        "prompt": combined_prompt,
        "sync": True
    }

    try:
        logger.info(f"Sending refinement request to Bria API: '{refinement_request}'")
        response = requests.post(BRIA_ENDPOINT, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        if "result" not in data or "structured_prompt" not in data["result"]:
            logger.error(f"Unexpected API response format during refinement: {data}")
            # Fall back to manual refinement based on keywords
            return _fallback_refinement(existing_params, refinement_request)
            
        structured_prompt_str = data["result"]["structured_prompt"]
        
        try:
            refined_params = json.loads(structured_prompt_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse refined JSON: {e}")
            return _fallback_refinement(existing_params, refinement_request)
        
        # Merge: start with existing, update with refined values
        # This ensures we don't lose any fields that weren't in the response
        final_params = existing_params.copy()
        final_params.update(refined_params)
            
        return final_params

    except requests.exceptions.RequestException as e:
        logger.error(f"Refinement API request failed: {e}")
        return _fallback_refinement(existing_params, refinement_request)
    except Exception as e:
        logger.error(f"An unexpected error occurred during refinement: {e}")
        return _fallback_refinement(existing_params, refinement_request)


def _fallback_refinement(existing_params: dict, refinement_request: str) -> dict:
    """
    Fallback refinement using keyword matching when API fails.
    Handles common refinement requests locally.
    """
    refined = existing_params.copy()
    request_lower = refinement_request.lower()
    
    # Lighting temperature modifications
    if "warm" in request_lower:
        if isinstance(refined.get("lighting"), dict):
            refined["lighting"]["temperature"] = "warm"
            refined["lighting"]["quality"] = refined["lighting"].get("quality", "soft")
        else:
            refined["lighting"] = {"direction": refined.get("lighting", "natural"), "temperature": "warm"}
    elif "cool" in request_lower or "cold" in request_lower:
        if isinstance(refined.get("lighting"), dict):
            refined["lighting"]["temperature"] = "cool"
        else:
            refined["lighting"] = {"direction": refined.get("lighting", "natural"), "temperature": "cool"}
    
    # Lighting intensity
    if "bright" in request_lower or "brighter" in request_lower:
        if isinstance(refined.get("lighting"), dict):
            refined["lighting"]["intensity"] = "bright"
        else:
            refined["lighting"] = {"direction": refined.get("lighting", "natural"), "intensity": "bright"}
    elif "dim" in request_lower or "darker" in request_lower:
        if isinstance(refined.get("lighting"), dict):
            refined["lighting"]["intensity"] = "dim"
        else:
            refined["lighting"] = {"direction": refined.get("lighting", "natural"), "intensity": "dim"}
    
    # Camera angle modifications
    if "low angle" in request_lower or "lower angle" in request_lower:
        refined["camera_angle"] = "Low Angle"
    elif "high angle" in request_lower or "higher angle" in request_lower or "overhead" in request_lower:
        refined["camera_angle"] = "High Angle"
    elif "eye level" in request_lower:
        refined["camera_angle"] = "Eye Level"
    
    # Shot type / FOV modifications
    if "close" in request_lower or "closer" in request_lower:
        refined["field_of_view"] = "close up"
    elif "wide" in request_lower or "wider" in request_lower:
        refined["field_of_view"] = "wide"
    elif "medium" in request_lower:
        refined["field_of_view"] = "normal"
    
    # Soft/hard lighting
    if "soft" in request_lower or "softer" in request_lower:
        if isinstance(refined.get("lighting"), dict):
            refined["lighting"]["quality"] = "soft"
        else:
            refined["lighting"] = {"direction": refined.get("lighting", "natural"), "quality": "soft"}
    elif "hard" in request_lower or "harsh" in request_lower:
        if isinstance(refined.get("lighting"), dict):
            refined["lighting"]["quality"] = "hard"
        else:
            refined["lighting"] = {"direction": refined.get("lighting", "natural"), "quality": "hard"}
    
    logger.info(f"Applied fallback refinement for: '{refinement_request}'")
    return refined
