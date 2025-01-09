import bpy


def export_optimized_scene(scene_path):
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.object.editmode_toggle()
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.dissolve_degenerate()
    bpy.ops.object.editmode_toggle()
    bpy.ops.omni_sceneopt.optimize(generate_duplicate=True, generate_type='CONVEX_HULL', merge=False, verbose=True, selected=False, export_textures=True, validate=True, weld=False, weld_distance=0.0001, unwrap=False, unwrap_margin=0, decimate=False, decimate_ratio=50, decimate_use_symmetry=False, decimate_symmetry_axis='X', decimate_min_face_count=500, decimate_remove_shape_keys=False, chop=False, generate=False)
