import threading
import requests
import os
import tempfile
import logging
import shutil
from .scene_parser import BRIA_API_KEY

# Configure logging
logger = logging.getLogger(__name__)

BRIA_IMAGE_ENDPOINT = "https://engine.prod.bria-api.com/v2/image/generate"
BRIA_RMBG_ENDPOINT = "https://engine.prod.bria-api.com/v2/image/edit/remove_background"

def generate_background_image(scene_data, callback=None):
    """
    Generates a background image using the FIBO API in a separate thread.
    
    Args:
        scene_data (dict): The scene parameters from Phase 2.
        callback (function): A function to call with the downloaded image path (or None on failure).
    """
    def _run_async():
        image_path = _make_api_call(scene_data)
        if callback:
            callback(image_path)

    thread = threading.Thread(target=_run_async)
    thread.daemon = True # Daemon thread so it doesn't block Blender exit
    thread.start()

def _make_api_call(scene_data):
    """
    Makes the blocking API call to generate the image.
    """
    headers = {
        "api_token": BRIA_API_KEY,
        "Content-Type": "application/json"
    }
    
    # Prepare payload
    # Based on API docs, 'structured_prompt' is for recreation with a seed.
    # For new images, we must use 'prompt'.
    # We will construct a rich text prompt from our structured data.
    
    parts = []
    
    # 1. Base Description
    if "short_description" in scene_data:
        parts.append(scene_data["short_description"])
    elif "prompt" in scene_data:
        parts.append(scene_data["prompt"])
        
    # 2. Lighting
    if "lighting" in scene_data:
        l = scene_data["lighting"]
        if isinstance(l, dict):
            lighting_desc = f"Lighting: {l.get('direction', '')} {l.get('conditions', '')} {l.get('shadows', '')}"
            parts.append(lighting_desc)
        elif isinstance(l, str):
            parts.append(f"Lighting: {l}")
            
    # 3. Background
    if "background_setting" in scene_data:
        parts.append(f"Background: {scene_data['background_setting']}")
    elif "background" in scene_data:
        parts.append(f"Background: {scene_data['background']}")

    # 4. Key Objects (Optional, but adds detail)
    if "objects" in scene_data and isinstance(scene_data["objects"], list):
        obj_descs = []
        for obj in scene_data["objects"][:3]: # Limit to top 3 to avoid prompt getting too long
            if isinstance(obj, dict) and "description" in obj:
                obj_descs.append(obj["description"])
        if obj_descs:
            parts.append("Objects: " + ", ".join(obj_descs))

    # Combine into single prompt
    final_prompt = " ".join(parts)
    
    # Fallback if empty
    if not final_prompt.strip():
        final_prompt = "A cinematic scene"

    payload = {
        "prompt": final_prompt,
        "format": "exr" 
    }

    
    try:
        logger.info(f"Sending image generation request to {BRIA_IMAGE_ENDPOINT}")
        response = requests.post(BRIA_IMAGE_ENDPOINT, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        
        data = response.json()
        
        # Check if async response (status_url)
        if "status_url" in data:
            status_url = data["status_url"]
            logger.info(f"Async request started. Polling status at: {status_url}")
            
            import time
            max_retries = 60 # Wait up to 60 seconds
            for _ in range(max_retries):
                time.sleep(1)
                try:
                    status_response = requests.get(status_url, headers=headers, timeout=10)
                    status_response.raise_for_status()
                    status_data = status_response.json()
                    
                    if status_data.get("status") == "COMPLETED":
                        # Success! Get the result
                        if "result" in status_data and "image_url" in status_data["result"]:
                             image_url = status_data["result"]["image_url"]
                        elif "result" in status_data and "urls" in status_data["result"]:
                             image_url = status_data["result"]["urls"][0]
                        elif "image_url" in status_data:
                             image_url = status_data["image_url"]
                        else:
                             # Fallback: try to find any URL in result
                             logger.warning(f"Completed but could not find URL in: {status_data}")
                             return None
                        break
                    elif status_data.get("status") == "FAILED":
                        logger.error(f"Image generation failed: {status_data.get('error')}")
                        return None
                    # If PENDING or PROCESSING, continue loop
                except Exception as e:
                    logger.warning(f"Error polling status: {e}")
            else:
                logger.error("Image generation timed out.")
                return None
        else:
            # Synchronous response (legacy or different endpoint behavior)
            image_url = None
            if "result" in data and isinstance(data["result"], list) and len(data["result"]) > 0:
                 image_url = data["result"][0] 
            elif "result" in data and isinstance(data["result"], dict):
                 image_url = data["result"].get("url") or data["result"].get("image_url")
            elif "image_url" in data:
                 image_url = data["image_url"]
            elif "urls" in data:
                 image_url = data["urls"][0]

        if not image_url:
            logger.warning(f"Could not parse Image URL from response: {data}")
            return None

        logger.info(f"Image generated at: {image_url}")
        
        # Download the image
        return _download_image(image_url)

    except requests.exceptions.RequestException as e:
        logger.error(f"Image generation API request failed: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during image generation: {e}")
        return None

def _download_image(url):
    """
    Downloads the image from the URL to a temporary file.
    """
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        # Create a temporary file
        ext = ".exr" 
        
        # Create a named temporary file that persists
        fd, path = tempfile.mkstemp(suffix=ext, prefix="previz_bg_")
        
        with os.fdopen(fd, 'wb') as tmp:
            shutil.copyfileobj(response.raw, tmp)
            
        logger.info(f"Image downloaded to: {path}")
        return path
        
    except Exception as e:
        logger.error(f"Failed to download image: {e}")
        return None


def generate_foreground_element(description, callback=None):
    """
    Generates a foreground element with transparent background.
    
    Workflow:
    1. Generate image with white background using Text-to-Image
    2. Remove background using RMBG 2.0 API
    3. Return transparent PNG path
    
    Args:
        description (str): Description of the element (e.g., "burning car")
        callback (function): Called with (image_path, None) on success or (None, error) on failure
    """
    def _run_async():
        try:
            result_path = _generate_foreground_sync(description)
            if callback:
                callback(result_path, None)
        except Exception as e:
            logger.error(f"Foreground generation failed: {e}")
            if callback:
                callback(None, str(e))

    thread = threading.Thread(target=_run_async)
    thread.daemon = True
    thread.start()


def _generate_foreground_sync(description):
    """
    Synchronous foreground element generation.
    """
    headers = {
        "api_token": BRIA_API_KEY,
        "Content-Type": "application/json"
    }
    
    # Step 1: Generate image with white background
    prompt = f"{description}, isolated on pure white background, product photography style, high quality"
    
    payload = {
        "prompt": prompt,
        "format": "png"  # PNG for better quality before background removal
    }
    
    logger.info(f"Generating foreground element: {description}")
    
    try:
        # Generate the base image
        response = requests.post(BRIA_IMAGE_ENDPOINT, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        
        # Handle async response (same pattern as background generation)
        image_url = _poll_for_image_result(data, headers)
        
        if not image_url:
            raise Exception("Failed to generate base image")
        
        logger.info(f"Base image generated, removing background...")
        
        # Step 2: Remove background using RMBG API
        transparent_url = _remove_background(image_url, headers)
        
        if not transparent_url:
            raise Exception("Failed to remove background")
        
        logger.info(f"Background removed successfully")
        
        # Step 3: Download the transparent PNG
        return _download_image_as_png(transparent_url)
        
    except Exception as e:
        logger.error(f"Foreground element generation failed: {e}")
        raise


def _poll_for_image_result(data, headers):
    """
    Polls for async image generation result.
    Returns the image URL or None on failure.
    """
    import time
    
    if "status_url" in data:
        status_url = data["status_url"]
        logger.info(f"Polling status at: {status_url}")
        
        max_retries = 60
        for _ in range(max_retries):
            time.sleep(1)
            try:
                status_response = requests.get(status_url, headers=headers, timeout=10)
                status_response.raise_for_status()
                status_data = status_response.json()
                
                if status_data.get("status") == "COMPLETED":
                    # Extract URL from various possible response formats
                    if "result" in status_data:
                        result = status_data["result"]
                        if isinstance(result, dict):
                            return result.get("image_url") or (result.get("urls", [None])[0] if result.get("urls") else None)
                        elif isinstance(result, list) and len(result) > 0:
                            return result[0]
                    return status_data.get("image_url")
                    
                elif status_data.get("status") == "FAILED":
                    logger.error(f"Generation failed: {status_data.get('error')}")
                    return None
                    
            except Exception as e:
                logger.warning(f"Polling error: {e}")
                
        logger.error("Image generation timed out")
        return None
    else:
        # Synchronous response
        if "result" in data:
            result = data["result"]
            if isinstance(result, dict):
                return result.get("url") or result.get("image_url")
            elif isinstance(result, list) and len(result) > 0:
                return result[0]
        return data.get("image_url") or (data.get("urls", [None])[0] if data.get("urls") else None)


def _remove_background(image_url, headers):
    """
    Removes background from an image using Bria's RMBG 2.0 API.
    Returns URL of transparent image.
    """
    import time
    
    # Bria's image edit API uses 'image' parameter for the image URL
    payload = {
        "image": image_url
    }
    
    logger.info(f"Calling RMBG API with image: {image_url[:50]}...")
    
    try:
        response = requests.post(BRIA_RMBG_ENDPOINT, headers=headers, json=payload, timeout=60)
        
        # Log response for debugging
        if not response.ok:
            logger.error(f"RMBG API error {response.status_code}: {response.text[:500]}")
        
        response.raise_for_status()
        data = response.json()
        
        # Handle async response
        if "status_url" in data:
            status_url = data["status_url"]
            
            max_retries = 30
            for _ in range(max_retries):
                time.sleep(1)
                try:
                    status_response = requests.get(status_url, headers=headers, timeout=10)
                    status_response.raise_for_status()
                    status_data = status_response.json()
                    
                    if status_data.get("status") == "COMPLETED":
                        result = status_data.get("result", {})
                        if isinstance(result, dict):
                            return result.get("image_url") or result.get("result_url")
                        return status_data.get("image_url") or status_data.get("result_url")
                        
                    elif status_data.get("status") == "FAILED":
                        logger.error(f"RMBG failed: {status_data.get('error')}")
                        return None
                        
                except Exception as e:
                    logger.warning(f"RMBG polling error: {e}")
                    
            logger.error("RMBG timed out")
            return None
        else:
            # Synchronous response
            result = data.get("result", {})
            if isinstance(result, dict):
                return result.get("image_url") or result.get("result_url")
            return data.get("image_url") or data.get("result_url")
            
    except Exception as e:
        logger.error(f"RMBG API request failed: {e}")
        return None


def _download_image_as_png(url):
    """
    Downloads image and saves as PNG to preserve transparency.
    """
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        fd, path = tempfile.mkstemp(suffix=".png", prefix="previz_foreground_")
        
        with os.fdopen(fd, 'wb') as tmp:
            shutil.copyfileobj(response.raw, tmp)
            
        logger.info(f"Foreground element downloaded to: {path}")
        return path
        
    except Exception as e:
        logger.error(f"Failed to download foreground image: {e}")
        return None
