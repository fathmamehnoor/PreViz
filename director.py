import bpy
import math

def apply_camera_settings(json_data):
    """
    Applies camera settings from JSON data to the active camera.
    """
    # Get or create camera
    camera = bpy.context.scene.camera
    if not camera:
        bpy.ops.object.camera_add(location=(0, -10, 2))
        camera = bpy.context.active_object
        bpy.context.scene.camera = camera
    
    # Map FOV to lens (focal length in mm)
    fov_str = json_data.get("field_of_view", "normal").lower()
    lens_map = {
        "wide": 24.0,
        "wide shot": 24.0,
        "standard": 50.0,
        "normal": 50.0,
        "telephoto": 85.0,
        "close up": 85.0
    }
    camera.data.lens = lens_map.get(fov_str, 50.0)
    
    # Map Camera Angle to Rotation
    # Blender uses radians for rotation
    # Default: Eye level (90 degrees on X to look forward if camera is Z-up, 
    # but standard Blender camera is -Z forward, Y up. 
    # Usually standard camera setup: Location (0, -10, 0), Rotation (90, 0, 0) looks along +Y?
    # Let's assume standard Blender camera orientation:
    # To look at (0,0,0) from (0, -10, 2):
    # Rotation (90-ish, 0, 0)
    
    angle_str = json_data.get("camera_angle", "eye level").lower()
    
    # We'll set rotation based on a standard setup looking at the origin
    if "low" in angle_str:
        camera.location.z = 0.5
        camera.rotation_euler = (math.radians(80), 0, 0)
    elif "high" in angle_str or "overhead" in angle_str:
        camera.location.z = 5.0
        camera.rotation_euler = (math.radians(45), 0, 0)
    else:
        # Eye level
        camera.location.z = 1.7 # approx human height
        camera.rotation_euler = (math.radians(90), 0, 0)

def apply_lighting_settings(json_data):
    """
    Applies lighting settings from JSON data to a Sun lamp.
    """
    # Find or create Sun lamp
    sun_light = None
    for obj in bpy.context.scene.objects:
        if obj.type == 'LIGHT' and obj.data.type == 'SUN':
            sun_light = obj
            break
            
    if not sun_light:
        bpy.ops.object.light_add(type='SUN', location=(0, 0, 10))
        sun_light = bpy.context.active_object
    
    # Map Lighting Direction and Quality
    lighting = json_data.get("lighting", {})
    
    # Normalize to dictionary if it's a string (e.g. "Natural")
    if isinstance(lighting, str):
        lighting = {"direction": lighting, "quality": "soft"}
        
    direction_str = lighting.get("direction", "natural").lower()
    quality_str = lighting.get("quality", "soft").lower()

    # Reset rotation
    sun_light.rotation_euler = (0, 0, 0)
    
    # Default "Natural" / "Overhead" -> slightly angled
    # Simple mapping logic
    if "left" in direction_str:
        sun_light.rotation_euler = (math.radians(45), math.radians(0), math.radians(90))
    elif "right" in direction_str:
        sun_light.rotation_euler = (math.radians(45), math.radians(0), math.radians(-90))
    elif "back" in direction_str or "silhouette" in direction_str:
        # Backlight, pointing towards camera
        sun_light.rotation_euler = (math.radians(-45), 0, 0)
    else:
        # Front/Top/Natural
        sun_light.rotation_euler = (math.radians(45), math.radians(10), 0)

    # Map Lighting Quality (Shadow Softness)
    # Sun light 'angle' property controls softness (angular diameter in radians)
    # 0 = hard shadows, higher = softer
    
    if "hard" in quality_str or "harsh" in quality_str:
        sun_light.data.angle = 0.0
    elif "soft" in quality_str or "diffuse" in quality_str:
        sun_light.data.angle = 0.5 # approx 28 degrees
    else:
        sun_light.data.angle = 0.1 # Default slightly soft

def setup_world_background(image_path):
    """
    Sets up the world background with the generated image.
    Uses a Window coordinate system for flat projection of backplates.
    """
    world = bpy.context.scene.world
    if not world:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world
    
    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    
    # Clear existing nodes
    nodes.clear()
    
    # 1. Texture Coordinate node
    node_coord = nodes.new(type='ShaderNodeTexCoord')
    node_coord.location = (-800, 0)
    
    # 2. Mapping node
    node_mapping = nodes.new(type='ShaderNodeMapping')
    node_mapping.location = (-600, 0)
    
    # 3. Image Texture node
    node_tex = nodes.new(type='ShaderNodeTexImage')
    node_tex.location = (-300, 0)
    node_tex.projection = 'FLAT'
    node_tex.interpolation = 'Linear' 
    
    # Load image
    try:
        img = bpy.data.images.load(image_path)
        node_tex.image = img
        # Set Color Space to Linear (for 16-bit EXR)
        if hasattr(img, 'colorspace_settings'):
            img.colorspace_settings.name = 'scene_linear'
    except Exception as e:
        print(f"Error loading background image: {e}")
        return

    # 4. Background node
    node_bg = nodes.new(type='ShaderNodeBackground')
    node_bg.location = (0, 0)
    # Default strength 1.0, but driven by image below
    
    # 5. World Output node
    node_out = nodes.new(type='ShaderNodeOutputWorld')
    node_out.location = (300, 0)
    
    # Link nodes
    # Texture Coordinate (Window) -> Mapping (Vector)
    links.new(node_coord.outputs["Window"], node_mapping.inputs["Vector"])
    
    # Mapping (Vector) -> Image Texture (Vector)
    links.new(node_mapping.outputs["Vector"], node_tex.inputs["Vector"])
    
    # Image Texture (Color) -> Background (Color)
    links.new(node_tex.outputs["Color"], node_bg.inputs["Color"])
    
    # Image Texture (Color) -> Background (Strength)
    # Connecting Color directly to Strength (Float input) converts RGB to Luminance automatically in Blender
    links.new(node_tex.outputs["Color"], node_bg.inputs["Strength"])
    
    # Background -> World Output
    links.new(node_bg.outputs["Background"], node_out.inputs["Surface"])


def create_shadow_catcher_plane(size=100, location=(0, 0, 0)):
    """
    Creates a large plane at the floor level (Z=0) with shadow catcher enabled.
    
    This prevents 3D objects from looking like they're floating when composited
    on top of AI-generated backgrounds in Cycles rendering.
    
    Args:
        size (float): The size of the plane. Default is 100 units.
        location (tuple): The (x, y, z) location of the plane. Default is origin.
    
    Returns:
        bpy.types.Object: The created shadow catcher plane object.
    """
    # Create a large plane at the specified location
    bpy.ops.mesh.primitive_plane_add(size=size, location=location)
    plane = bpy.context.active_object
    plane.name = "ShadowCatcherPlane"
    
    # Enable shadow catcher - this makes the plane invisible but catches shadows
    # Only works with Cycles renderer
    plane.is_shadow_catcher = True
    
    # Ensure Cycles is the active render engine for shadow catcher to work
    if bpy.context.scene.render.engine != 'CYCLES':
        print("Note: Shadow catcher requires Cycles render engine. Switching to Cycles.")
        bpy.context.scene.render.engine = 'CYCLES'
    
    return plane


def import_image_as_card(image_path, distance=5.0, scale=2.0):
    """
    Imports a transparent PNG as a 3D card (Image as Plane) positioned in front of the camera.
    
    Args:
        image_path (str): Path to the transparent PNG image.
        distance (float): Distance in meters from the camera (default 5m).
        scale (float): Scale of the card in Blender units (default 2.0).
    
    Returns:
        bpy.types.Object: The created image card object.
    """
    import os
    
    # Load the image
    try:
        img = bpy.data.images.load(image_path)
        img.colorspace_settings.name = 'sRGB'  # Standard color space for PNG
    except Exception as e:
        print(f"Error loading foreground image: {e}")
        return None
    
    # Get camera for positioning
    camera = bpy.context.scene.camera
    if not camera:
        print("No active camera found for positioning foreground element")
        # Create at origin if no camera
        location = (0, distance, 0)
        rotation = (math.radians(90), 0, 0)
    else:
        # Position the card in front of the camera
        # Camera forward direction is -Z in local space
        import mathutils
        
        cam_matrix = camera.matrix_world
        cam_location = cam_matrix.translation
        
        # Get camera's forward direction (negative Z-axis)
        forward = cam_matrix.to_3x3() @ mathutils.Vector((0, 0, -1))
        forward.normalize()
        
        # Calculate card position (distance meters in front of camera)
        location = cam_location + forward * distance
        
        # Card should be parallel to the camera (Billboard behavior)
        # Simply copying the camera's rotation ensures the plane is parallel to the view plane
        # Camera looks down -Z, Plane face is +Z.
        # With same rotation, Plane +Z points opposite to Camera view (facing the camera).
        rotation = camera.rotation_euler

    
    # Calculate aspect ratio from image
    aspect = img.size[0] / img.size[1] if img.size[1] > 0 else 1.0
    
    # Create plane with correct aspect ratio
    bpy.ops.mesh.primitive_plane_add(
        size=scale,
        location=location,
        rotation=rotation
    )
    card = bpy.context.active_object
    card.name = f"FG_{os.path.basename(image_path).split('.')[0]}"
    
    # Scale to match image aspect ratio
    card.scale.x = aspect
    
    # Create material with transparency support
    mat = bpy.data.materials.new(name=f"Mat_{card.name}")
    mat.use_nodes = True
    mat.blend_method = 'BLEND'  # Enable transparency blending
    try:
        mat.shadow_method = 'CLIP'  # Shadows respect alpha (Eevee Legacy)
    except AttributeError:
        # Blender 4.2+ / Eevee Next does not use shadow_method on material
        # Shadows are raytraced or handled differently
        pass
    
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    
    # Clear default nodes
    nodes.clear()
    
    # Create shader nodes for transparent image
    node_tex = nodes.new(type='ShaderNodeTexImage')
    node_tex.image = img
    node_tex.location = (-400, 200)
    
    node_bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    node_bsdf.location = (0, 200)
    
    node_output = nodes.new(type='ShaderNodeOutputMaterial')
    node_output.location = (300, 200)
    
    # Link: Image Color -> BSDF Base Color
    links.new(node_tex.outputs['Color'], node_bsdf.inputs['Base Color'])
    
    # Link: Image Alpha -> BSDF Alpha
    links.new(node_tex.outputs['Alpha'], node_bsdf.inputs['Alpha'])
    
    # Link: BSDF -> Output
    links.new(node_bsdf.outputs['BSDF'], node_output.inputs['Surface'])
    
    # Set emission to 0 and roughness high for flat look
    node_bsdf.inputs['Roughness'].default_value = 1.0
    node_bsdf.inputs['Specular IOR Level'].default_value = 0.0
    
    # Assign material to card
    card.data.materials.append(mat)
    
    print(f"Foreground card created: {card.name} at distance {distance}m from camera")
    return card

