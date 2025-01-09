import bpy
import bmesh
from mathutils import Vector

def get_vertex_coordinates(obj):
    """Get coordinates of all vertices in world space"""
    mesh = obj.data
    return [obj.matrix_world @ v.co for v in mesh.vertices]

def objects_share_vertices(obj1, obj2, threshold=0.0001):
    """Check if two objects share any vertex positions"""
    verts1 = get_vertex_coordinates(obj1)
    verts2 = get_vertex_coordinates(obj2)
    
    # Compare each vertex from obj1 with each vertex from obj2
    for v1 in verts1:
        for v2 in verts2:
            # If vertices are close enough (within threshold)
            if (v1 - v2).length <= threshold:
                return True
    return False

# Step 1: Ensure we are in Object Mode and prepare for separation
if bpy.context.object.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')

# Select the active object
target_object = bpy.context.active_object

# Deselect everything and select only the target object
bpy.ops.object.select_all(action='DESELECT')
target_object.select_set(True)
bpy.context.view_layer.objects.active = target_object

# Enter Edit Mode to separate by loose parts
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.separate(type='LOOSE')
bpy.ops.object.mode_set(mode='OBJECT')

# Step 2: Combine separated parts that share vertices
# Store object names instead of references
object_names = [obj.name for obj in bpy.context.selected_objects]
processed_names = set()

# Process each object by name
for i, name in enumerate(object_names):
    # Skip if object has been processed or no longer exists
    if name not in bpy.data.objects or name in processed_names:
        continue
    
    current_obj = bpy.data.objects[name]
    objects_to_merge = [current_obj]
    merge_names = {name}
    
    # Find objects that share vertices
    for other_name in object_names[i+1:]:
        if other_name in bpy.data.objects and other_name not in processed_names:
            other_obj = bpy.data.objects[other_name]
            if objects_share_vertices(current_obj, other_obj):
                objects_to_merge.append(other_obj)
                merge_names.add(other_name)
    
    # Combine objects if we found any to merge
    if len(objects_to_merge) > 1:
        # Deselect all objects
        bpy.ops.object.select_all(action='DESELECT')
        
        # Select objects to merge
        for obj in objects_to_merge:
            if obj.name in bpy.data.objects:  # Double check existence
                obj.select_set(True)
        
        # Set active object
        bpy.context.view_layer.objects.active = objects_to_merge[0]
        
        # Join objects
        bpy.ops.object.join()
        
        # Add all merged object names to processed set
        processed_names.update(merge_names)

# Optional: Rename remaining objects
for idx, obj in enumerate(bpy.context.selected_objects):
    if obj.name in bpy.data.objects:  # Verify object still exists
        obj.name = f"Combined_Surface_{idx + 1}"