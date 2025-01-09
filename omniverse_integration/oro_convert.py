import yaml
import numpy as np
import os
import json
import bpy
import random
import math
import mathutils
from mathutils import Vector

import sys
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(CURRENT_DIR)
from camera_utils import get_valid_camera_poses

# sys.path.append(os.path.join(CURRENT_DIR, '..', 'asset_indexing'))
# from asset_to_usd import need_to_bake
#
# Set Blender's preferences to include the script directory for add-ons
#bpy.context.preferences.filepaths.script_directory = "/home/owner/scripts"
## Save the preferences so the change persists
#bpy.ops.wm.save_userpref()


def load_blend_scene(blend_path):
    # Clear existing scene
    bpy.ops.wm.read_factory_settings(use_empty=True)
    # Load the .blend file
    bpy.ops.wm.open_mainfile(filepath=blend_path)
    # Return the loaded scene
    return bpy.context.scene

def read_json(path):
    with open(path) as infile:
        json_data = json.load(infile)
        return json_data
    
def write_yaml(data, yaml_path):
    with open(yaml_path, 'w') as yaml_file:
        yaml.dump(data, yaml_file)


if __name__ == "__main__":
    import sys
    INPUT_DIR = sys.argv[1]
    OUTPUT_DIR = sys.argv[2]

    print(INPUT_DIR, OUTPUT_DIR)
    data = read_json(os.path.join(INPUT_DIR, 'scene.json'))
    input_blend_path = os.path.join(INPUT_DIR, 'scene_topdown.blend')
    yaml_path = os.path.join(INPUT_DIR, 'oro_scene.yaml')

    # output_id = INPUT_DIR.split('airblender_foundation/scripts/ORO')[-1]
    output = {
        # 'output_path': os.path.join(OUTPUT_DIR, output_id)
        'output_path': OUTPUT_DIR
    }
    # import pdb;pdb.set_trace()

    has_light = False
    obstacles = []
    for name, object in data['objects'].items():
        if object["category"] == "walls" or object["category"] == "floors" or object["category"] == "ceilings":
            obstacles.append([mathutils.Vector(point) for point in object["metadata"]["polygon"]])
        if object["category"] == "objects":
            if "is_ceiling_light" in object["metadata"].keys():
                for placement in object["placements"]:
                    # if object["metadata"]["is_ceiling_light"]:
                    sphere_light = {
                        'type': 'light',
                        'intensity': 10000,
                        'subtype': 'sphere',
                        'color': [
                            object["metadata"]["light_color"][0]*2,
                            object["metadata"]["light_color"][1]*2,
                            object["metadata"]["light_color"][2]*2
                        ],
                        'transform_operators': [
                            {'rotateXYZ': [0, -90, -90]},
                            {'translate': [placement["position"][0], placement["position"][1], placement["position"][2]]},
                            {'scale': [0.01, 0.01, 0.01]}
                        ]
                    }
                    output['sphere_light'] = sphere_light
                    has_light = True

    if not has_light:
        output['sphere_light'] = {
            'type': 'light',
            'intensity': 5000,
            'subtype': 'sphere',
            'color': [1, 1, 1],
            'transform_operators': [
                {'rotateXYZ': [0, -90, -90]},
                {'translate': [0, 0, 0]},
                {'scale': [0.01, 0.01, 0.01]}
            ]
        }

    # Load the Blender scene
    # blend_scene = load_blend_scene(input_blend_path)
    # Ensure everything is shown and visible for rendering
    # remove the HDRI in the scene
    # bpy.data.worlds['World'].node_tree.nodes['Background'].inputs[0].default_value = (0.0, 0.0, 0.0, 1.0)
    for obj in bpy.data.objects:
        if obj.name == "ceilings":
            obj.hide_viewport = True
            obj.hide_render = True
        else:
            obj.hide_viewport = False
            obj.hide_render = False
    # Set all collections to be visible
    for collection in bpy.data.collections:
        collection.hide_viewport = False
        collection.hide_render = False
    # Ensure all objects are selectable
    for obj in bpy.data.objects:
        obj.hide_select = False
    # iterate through the objects in the scene and put them in a list
    #print("objects in the scene:")
    #for obj in bpy.data.objects:
    #    if obj.type == 'MESH':
    #        print(obj.name, need_to_bake(obj))
    # export the whole scene as a .usdc file
    recorded_objects = []
    output_usdc_path = os.path.join(INPUT_DIR, 'scene.usd')
    #print("exporting scene to usdc")
    #bpy.ops.omni_sceneopt.export(
    #    generate_duplicate=True,
    #    generate_type='CONVEX_HULL',
    #    merge=False, verbose=True, selected=False, export_textures=True, validate=True,
    #    weld=False, weld_distance=0.0001, unwrap=False, unwrap_margin=0,
    #    decimate=False, decimate_ratio=50, decimate_use_symmetry=False, decimate_symmetry_axis='X',
    #    decimate_min_face_count=500, decimate_remove_shape_keys=False, chop=False, generate=False, filepath=output_usdc_path
    #)
    bpy.ops.wm.usd_export(
        filepath=output_usdc_path,
        selected_objects_only=False,
        visible_objects_only=False,
        export_materials=True,
        export_textures=True
    )
    ### material baking
    recorded_objects.append({
        'instance_name': "scene", 
        'position': [0, 0, 0], 
        'rotation': [0, 0, 0],
        'path': output_usdc_path
    })

    # Define parameters
    N = 10  # Number of valid camera poses
    radius = 2.5 # Radius of the hemisphere
    target_location = mathutils.Vector((0, 0, 1))  # Center of the sphere
    # Get valid camera poses
    valid_poses = get_valid_camera_poses(N, radius, target_location, obstacles)
    #
    output['default_camera'] = {
        'camera_parameters': '$[/camera_parameters]',
        'transform_operators': [
            {'rotateXYZ_global': [0, 0, 0]},
            {
                "translate": {
                    "distribution_type": "set",
                    "values": [
                    ],
                    "index": "$[seed]"
                }
            },
            {
                "rotateXYZ": {
                    "distribution_type": "set",
                    "values": [
                    ],
                    "index": "$[seed]"
                }
            },
        ],
        'type': 'camera'
    }
    for i in range(N):
        output["default_camera"]["transform_operators"][1]["translate"]["values"].append(
                [
                    valid_poses[i][0].x,
                    valid_poses[i][0].y,
                    valid_poses[i][0].z
                ]
        )
        output["default_camera"]["transform_operators"][2]["rotateXYZ"]["values"].append(
            [
                float(valid_poses[i][1].x),
                float(valid_poses[i][1].y),
                float(valid_poses[i][1].z)
            ]
        )
        
    for object in recorded_objects:
        #if 'sofa' in object['instance_name']:
        #    import pdb;pdb.set_trace()
        output[object['instance_name']] = {
            'tracked': True,
            'type': 'geometry',
            #'subtype': 'torus',
            'subtype': 'mesh',
            'usd_path': object['path'],
            'transform_operators': [
                {'rotateXYZ_global': [0, -90, -90]},
                {'translate': [0, 0, 0]},
                {'rotateXYZ': [0, 0, 0]},
                {'scale': ['$[/size]', '$[/size]', '$[/size]']}
            ]
        }
    output.update({
        'num_frames': N,
        'seed': 0,
        'screen_height': 2160,
        'screen_width': 3840,
        'camera_parameters': {
            'screen_width': '$[/screen_width]',
            'screen_height': '$[/screen_height]',
            'focal_length': 14.228393962367306,
            'horizontal_aperture': 20.955,
            'near_clip': 0.1,
            'far_clip': 100000
        },
        #'dome_light': {
        #    'intensity': {
        #        'distribution_type': 'range',
        #        'start': 500,
        #        'end': 3000
        #    },
        #    'subtype': 'dome',
        #    'transform_operators': [
        #        {'rotateX': 270}
        #    ],
        #    'type': 'light'
        #},
    })
    output_outer = {
        'omni.replicator.object': {
            'version': '0.3.5',
            'num_frames': 1,
            'size': 1
        }
    }
    output_outer['omni.replicator.object'].update(output)
    print("exporting yaml")
    write_yaml(output_outer, yaml_path)
    exit(0)