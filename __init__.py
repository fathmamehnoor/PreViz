bl_info = {
    "name": "PreViz",
    "author": "Fathma Mehnoor",
    "version": (1, 0),
    "blender": (2, 80, 0),
    "location": "View3D > Sidebar > PreViz",
    "description": "Run Python scripts from the 3D Viewport",
    "warning": "",
    "doc_url": "",
    "category": "Development",
}

import bpy
import json
import math
import os
from datetime import datetime
import importlib
from . import scene_parser
from . import director
from . import cinematographer

# Force reload of submodules during development
importlib.reload(scene_parser)
importlib.reload(director)
importlib.reload(cinematographer)

# Global storage for the last generated scene data (for refinement)
_last_scene_data = {}




class SCENE_OT_paste_script(bpy.types.Operator):
    """Paste text from clipboard into the script block"""
    bl_idname = "scene.paste_script"
    bl_label = "Paste Clipboard"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        clipboard = context.window_manager.clipboard
        if not clipboard:
            self.report({'WARNING'}, "Clipboard is empty")
            return {'CANCELLED'}

        # Get or create text block
        text_block = context.scene.custom_script_text
        if not text_block:
            text_block = bpy.data.texts.new(name="PreViz_Script.py")
            context.scene.custom_script_text = text_block
        
        text_block.clear()
        text_block.write(clipboard)
        
        self.report({'INFO'}, "Script pasted from clipboard")
        return {'FINISHED'}


class SCENE_OT_generate_scene(bpy.types.Operator):
    """Execute the custom script"""
    bl_idname = "scene.generate_scene"
    bl_label = "Generate Scene"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        print("Button Clicked")
        
        # Get script input
        text_block = context.scene.custom_script_text
        if not text_block:
            self.report({'WARNING'}, "No Script Selected!")
            return {'CANCELLED'}
            
        script_content = text_block.as_string()
        if not script_content.strip():
            self.report({'WARNING'}, "Script is empty!")
            return {'CANCELLED'}

        # 1. Parse Script (Brain)
        self.report({'INFO'}, "Parsing Script...")
        scene_data = scene_parser.get_scene_parameters(script_content)
        print(f"Parsed Data: {scene_data}")
        
        # Store for refinement
        global _last_scene_data
        _last_scene_data = scene_data.copy()

        # 2. Apply Settings (Director)
        self.report({'INFO'}, "Applying Camera Settings...")
        director.apply_camera_settings(scene_data)
        
        self.report({'INFO'}, "Applying Lighting Settings...")
        director.apply_lighting_settings(scene_data)
        
        # 3. Generate Background Image (Cinematographer)
        self.report({'INFO'}, "Requesting Background Image...")
        
        # Set loading status
        context.scene.previz_status = "⏳ Generating background..."
        
        def image_ready_callback(path):
            if path:
                print(f"Background Image Ready: {path}")
                
                def update_scene():
                    # Update status - loading image
                    bpy.context.scene.previz_status = "⏳ Loading image..."
                    
                    # Set up world background
                    director.setup_world_background(path)
                    
                    # Create shadow catcher plane for grounding objects
                    director.create_shadow_catcher_plane()
                    
                    # Force Viewport to Rendered Mode
                    for area in bpy.context.screen.areas:
                        if area.type == 'VIEW_3D':
                            for space in area.spaces:
                                if space.type == 'VIEW_3D':
                                    space.shading.type = 'RENDERED'
                    
                    # Update status - done
                    bpy.context.scene.previz_status = "✅ Ready"
                    return None # Unregister timer

                # Schedule update on main thread
                bpy.app.timers.register(update_scene)
                
            else:
                print("Background Image Generation Failed")
                bpy.context.scene.previz_status = "❌ Generation failed"

        cinematographer.generate_background_image(scene_data, image_ready_callback)
        
        self.report({'INFO'}, "Background generation started...")
        return {'FINISHED'}


class SCENE_OT_refine_scene(bpy.types.Operator):
    """Refine the current scene based on director's feedback"""
    bl_idname = "scene.refine_scene"
    bl_label = "Refine Scene"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        global _last_scene_data
        
        # Check if we have a previous scene to refine
        if not _last_scene_data:
            self.report({'WARNING'}, "No previous scene to refine. Generate a scene first!")
            return {'CANCELLED'}
        
        # Get refinement request
        refinement_text = context.scene.previz_refine_text
        if not refinement_text.strip():
            self.report({'WARNING'}, "Please enter a refinement instruction")
            return {'CANCELLED'}
        
        self.report({'INFO'}, f"Refining scene: {refinement_text}")
        
        # 1. Refine the scene parameters
        refined_data = scene_parser.refine_scene_parameters(_last_scene_data, refinement_text)
        print(f"Refined Data: {refined_data}")
        print(f"Changes from: {_last_scene_data}")
        
        # Update the stored scene data
        _last_scene_data = refined_data.copy()
        
        # 2. Apply refined settings (Director)
        self.report({'INFO'}, "Applying Refined Camera Settings...")
        director.apply_camera_settings(refined_data)
        
        self.report({'INFO'}, "Applying Refined Lighting Settings...")
        director.apply_lighting_settings(refined_data)
        
        # 3. Regenerate background with refined data (Cinematographer)
        self.report({'INFO'}, "Regenerating Background with Refinements...")
        
        def image_ready_callback(path):
            if path:
                print(f"Refined Background Image Ready: {path}")
                
                def update_scene():
                    # Set up world background
                    director.setup_world_background(path)
                    
                    # Force Viewport to Rendered Mode
                    for area in bpy.context.screen.areas:
                        if area.type == 'VIEW_3D':
                            for space in area.spaces:
                                if space.type == 'VIEW_3D':
                                    space.shading.type = 'RENDERED'
                    return None # Unregister timer

                # Schedule update on main thread
                bpy.app.timers.register(update_scene)
                
            else:
                print("Refined Background Image Generation Failed")

        cinematographer.generate_background_image(refined_data, image_ready_callback)
        
        # Clear the refinement text after use
        context.scene.previz_refine_text = ""
        
        self.report({'INFO'}, "Scene Refinement Applied")
        return {'FINISHED'}


class SCENE_OT_export_to_set(bpy.types.Operator):
    """Export camera and lighting data to a JSON file for on-set reference"""
    bl_idname = "scene.export_to_set"
    bl_label = "Export to Set"
    bl_options = {'REGISTER'}
    
    # File browser properties
    filepath: bpy.props.StringProperty(
        name="File Path",
        description="Path to save the export file",
        subtype='FILE_PATH',
        default="previz_export.json"
    )
    
    def invoke(self, context, event):
        """Open file browser when operator is invoked"""
        # Set default filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filepath = f"previz_set_data_{timestamp}.json"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    
    def execute(self, context):
        """Export camera and sun data to JSON file"""
        export_data = {
            "version": "1.0",
            "exported_at": datetime.now().isoformat(),
            "scene_name": context.scene.name,
            "camera": self._get_camera_data(context),
            "sun": self._get_sun_data(context)
        }
        
        # Ensure .json extension
        filepath = self.filepath
        if not filepath.lower().endswith('.json'):
            filepath += '.json'
        
        try:
            with open(filepath, 'w') as f:
                json.dump(export_data, f, indent=2)
            
            self.report({'INFO'}, f"Exported to: {filepath}")
            return {'FINISHED'}
        
        except Exception as e:
            self.report({'ERROR'}, f"Export failed: {str(e)}")
            return {'CANCELLED'}
    
    def _get_camera_data(self, context):
        """Extract camera position, rotation, and lens data"""
        camera = context.scene.camera
        if not camera:
            return {"error": "No active camera found"}
        
        # Convert rotation from radians to degrees for readability
        rotation_deg = (
            math.degrees(camera.rotation_euler.x),
            math.degrees(camera.rotation_euler.y),
            math.degrees(camera.rotation_euler.z)
        )
        
        return {
            "name": camera.name,
            "coordinates": {
                "x": round(camera.location.x, 4),
                "y": round(camera.location.y, 4),
                "z": round(camera.location.z, 4),
                "units": "meters"
            },
            "rotation": {
                "x": round(rotation_deg[0], 2),
                "y": round(rotation_deg[1], 2),
                "z": round(rotation_deg[2], 2),
                "units": "degrees"
            },
            "lens": {
                "focal_length_mm": round(camera.data.lens, 2),
                "sensor_width_mm": round(camera.data.sensor_width, 2),
                "sensor_fit": camera.data.sensor_fit
            }
        }
    
    def _get_sun_data(self, context):
        """Extract sun light position and rotation data"""
        sun_light = None
        for obj in context.scene.objects:
            if obj.type == 'LIGHT' and obj.data.type == 'SUN':
                sun_light = obj
                break
        
        if not sun_light:
            return {"error": "No sun light found"}
        
        # Convert rotation from radians to degrees
        rotation_deg = (
            math.degrees(sun_light.rotation_euler.x),
            math.degrees(sun_light.rotation_euler.y),
            math.degrees(sun_light.rotation_euler.z)
        )
        
        # Calculate sun direction vector (useful for set lighting)
        # Sun points in -Z direction in local space, rotated by euler angles
        direction_x = -math.sin(sun_light.rotation_euler.z) * math.cos(sun_light.rotation_euler.x)
        direction_y = math.cos(sun_light.rotation_euler.z) * math.cos(sun_light.rotation_euler.x)
        direction_z = -math.sin(sun_light.rotation_euler.x)
        
        return {
            "name": sun_light.name,
            "angle": {
                "elevation": round(90 - rotation_deg[0], 2),  # Convert to elevation angle
                "azimuth": round(rotation_deg[2], 2),
                "units": "degrees",
                "note": "Elevation: 0=horizon, 90=overhead. Azimuth: 0=front, 90=right"
            },
            "rotation_euler": {
                "x": round(rotation_deg[0], 2),
                "y": round(rotation_deg[1], 2),
                "z": round(rotation_deg[2], 2),
                "units": "degrees"
            },
            "direction_vector": {
                "x": round(direction_x, 4),
                "y": round(direction_y, 4),
                "z": round(direction_z, 4),
                "note": "Normalized vector pointing from sun towards scene"
            },
            "angular_diameter": round(math.degrees(sun_light.data.angle), 2),
            "strength": round(sun_light.data.energy, 2)
        }


class SCENE_OT_add_foreground(bpy.types.Operator):
    """Generate and add a foreground element with transparent background"""
    bl_idname = "scene.add_foreground"
    bl_label = "Add Foreground Element"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        description = context.scene.previz_foreground_text.strip()
        
        if not description:
            self.report({'WARNING'}, "Please enter a description (e.g., 'burning car')")
            return {'CANCELLED'}
        
        self.report({'INFO'}, f"Generating: {description}...")
        
        def on_complete(image_path, error):
            if error:
                print(f"Foreground generation failed: {error}")
                return
            
            if image_path:
                print(f"Foreground element ready: {image_path}")
                
                def import_card():
                    # Import as 3D card 5m in front of camera
                    card = director.import_image_as_card(image_path, distance=5.0, scale=2.0)
                    
                    if card:
                        # Force viewport to rendered mode
                        for area in bpy.context.screen.areas:
                            if area.type == 'VIEW_3D':
                                for space in area.spaces:
                                    if space.type == 'VIEW_3D':
                                        space.shading.type = 'RENDERED'
                    return None  # Unregister timer
                
                # Schedule on main thread
                bpy.app.timers.register(import_card)
            else:
                print("Foreground generation returned no image")
        
        # Start async generation
        cinematographer.generate_foreground_element(description, on_complete)
        
        # Clear input
        context.scene.previz_foreground_text = ""
        
        self.report({'INFO'}, "Generating foreground element... (check console for progress)")
        return {'FINISHED'}




class VIEW3D_PT_previz_panel(bpy.types.Panel):
    """Creates a Panel in the View3D UI"""
    bl_label = "PreViz Tools"
    bl_idname = "VIEW3D_PT_previz_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "PreViz"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # Text Input
        layout.label(text="Script Input:")
        row = layout.row(align=True)
        row.template_ID(scene, "custom_script_text", new="text.new", open="text.open")
        
        # Paste Button
        row = layout.row()
        row.operator("scene.paste_script", icon='PASTEDOWN')

        # Script Preview Box
        text_block = scene.custom_script_text
        if text_block:
            box = layout.box()
            box.label(text="Script Preview:", icon='TEXT')
            
            script_content = text_block.as_string()
            if script_content.strip():
                lines = script_content.split('\n')
                # Show first 5 lines, truncated to 40 chars
                for i, line in enumerate(lines[:5]):
                    display_line = line[:40] + "..." if len(line) > 40 else line
                    box.label(text=display_line if display_line.strip() else " ")
                
                if len(lines) > 5:
                    box.label(text=f"... ({len(lines) - 5} more lines)")
            else:
                box.label(text="(empty)")

        # Generate Button
        layout.operator("scene.generate_scene")
        
        layout.separator()
        
        # Refine Section
        box = layout.box()
        box.label(text="🎬 Director's Refinement:", icon='MODIFIER')
        
        # Refine text input
        row = box.row()
        row.prop(scene, "previz_refine_text", text="")
        
        # Refine button - only enabled if there's a previous scene
        row = box.row()
        refine_op = row.operator("scene.refine_scene", icon='FILE_REFRESH')
        
        # Show hint if no scene generated yet
        if not _last_scene_data:
            box.label(text="Generate a scene first", icon='INFO')
        else:
            box.label(text="e.g., 'make lights warmer'", icon='LIGHT')
        
        layout.separator()
        

        
        # Add Foreground Element Section
        box = layout.box()
        box.label(text="🎨 Add Foreground Element", icon='IMAGE_PLANE')
        
        # Description input
        row = box.row()
        row.prop(scene, "previz_foreground_text", text="")
        
        # Add button
        row = box.row()
        row.operator("scene.add_foreground", icon='ADD')
        
        # Hint
        box.label(text="e.g., 'burning car', 'fallen tree'", icon='LIGHT')
        
        layout.separator()
        

        
        # Export to Set Section 
        box = layout.box()
        box.label(text="📦 Export to Set", icon='EXPORT')
        box.operator("scene.export_to_set", icon='FILE_TICK')
        box.label(text="Saves camera & sun data to JSON", icon='INFO')
        
        layout.separator()

        # Status Label - shows dynamic loading status
        status_box = layout.box()
        status_box.label(text=f"Status: {scene.previz_status}", icon='INFO')

def register():

    
    # Register operators
    bpy.utils.register_class(SCENE_OT_generate_scene)
    bpy.utils.register_class(SCENE_OT_paste_script)
    bpy.utils.register_class(SCENE_OT_refine_scene)
    bpy.utils.register_class(SCENE_OT_export_to_set)
    bpy.utils.register_class(SCENE_OT_add_foreground)

    bpy.utils.register_class(VIEW3D_PT_previz_panel)
    
    # Register properties
    bpy.types.Scene.custom_script_text = bpy.props.PointerProperty(
        name="Script",
        type=bpy.types.Text,
        description="Text block containing the script"
    )
    
    bpy.types.Scene.previz_refine_text = bpy.props.StringProperty(
        name="Refine",
        description="Enter refinement instructions (e.g., 'make lights warmer', 'use low angle')",
        default=""
    )
    
    bpy.types.Scene.previz_foreground_text = bpy.props.StringProperty(
        name="Foreground",
        description="Describe the foreground element to add (e.g., 'burning car', 'fallen tree')",
        default=""
    )
    

    
    # Status property for loading feedback
    bpy.types.Scene.previz_status = bpy.props.StringProperty(
        name="Status",
        description="Current PreViz status",
        default="Ready"
    )

def unregister():
    # Unregister operators
    bpy.utils.unregister_class(SCENE_OT_generate_scene)
    bpy.utils.unregister_class(SCENE_OT_paste_script)
    bpy.utils.unregister_class(SCENE_OT_refine_scene)
    bpy.utils.unregister_class(SCENE_OT_export_to_set)
    bpy.utils.unregister_class(SCENE_OT_add_foreground)

    bpy.utils.unregister_class(VIEW3D_PT_previz_panel)
    

    
    # Unregister properties
    del bpy.types.Scene.custom_script_text
    del bpy.types.Scene.previz_refine_text
    del bpy.types.Scene.previz_foreground_text

    del bpy.types.Scene.previz_status

if __name__ == "__main__":
    register()
