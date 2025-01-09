from pxr import Semantics
from .maths import *
from .misc import *
import numpy as np

def enable_semantics(prim, semantic_label):
    if not prim.HasAPI(Semantics.SemanticsAPI):
        sem = Semantics.SemanticsAPI.Apply(prim, "Semantics")
        sem.CreateSemanticTypeAttr()
        sem.CreateSemanticDataAttr()
    else:
        sem = Semantics.SemanticsAPI.Get(prim, "Semantics")
    sem.GetSemanticTypeAttr().Set(SEMANTIC_CLASS_STRING)
    sem.GetSemanticDataAttr().Set(semantic_label)

from scipy.spatial.transform import Rotation

def save_bbox_2d_to_kitti(bboxes_2d, path, occlusion_threshold):
    lbl_txt = ''
    visible_labeled_set = set()
    for name, data in bboxes_2d.items():
        # used to be resolve_mutable_name(name, True) which is the class name, or name if there is no class name
        if data['occlusion'] <= occlusion_threshold:
            lbl_txt += f"{name} 0 {data['occlusion']} 0 {data['x_min']} {data['y_min']} {data['x_max']} {data['y_max']} 0 0 0 0 0 0 0\n"
            visible_labeled_set.add(name)
    with open(path, 'w') as f:
        f.write(lbl_txt)
    return visible_labeled_set

def camera_ov_to_standard(camera_parameters):
    standard_camera_parameters = {}
    for key, value in camera_parameters.items():
        if not key in ["focal_length", "horizontal_aperture"]:
            standard_camera_parameters[key] = value
    standard_camera_parameters["pinhole_ratio"] = 2 * camera_parameters["focal_length"] / camera_parameters["horizontal_aperture"] * camera_parameters["screen_width"] / camera_parameters["screen_height"]
    return standard_camera_parameters

def get_projection_matrix(camera_intrinsics):
    n, f = camera_intrinsics["near_clip"], camera_intrinsics["far_clip"]
    P = (n+f)/(n-f)
    Q = 2*n*f/(n-f)
    screen_width, screen_height = camera_intrinsics["screen_width"], camera_intrinsics["screen_height"]
    pinhole_ratio = camera_intrinsics["pinhole_ratio"]
    return np.transpose(np.array([[pinhole_ratio / screen_width * screen_height, 0, 0, 0], [0, pinhole_ratio, 0, 0], [0, 0, P, Q], [0, 0, -1, 0]]))

def model_to_2d(pt, obj_xform, camera_xform, camera_intrinsics):
    model_space = np.array([pt[0], pt[1], pt[2], 1])
    world_space = model_space @ obj_xform
    camera_space = world_space @ np.linalg.inv(camera_xform)

    proj_mat = get_projection_matrix(camera_intrinsics)
    ndc_space = camera_space @ proj_mat
    ndc_space /= ndc_space[3]

    screen_width, screen_height = camera_intrinsics["screen_width"], camera_intrinsics["screen_height"]
    x = (1 + ndc_space[0]) / 2 * screen_width
    y = (1 - ndc_space[1]) / 2 * screen_height
    return {'2d': (int(x), int(y)), '3d': (camera_space[:3] @ rot_z(90))}

def get_intrinsics(camera_intrinsics):
    screen_width, screen_height = camera_intrinsics["screen_width"], camera_intrinsics["screen_height"]
    pinhole_ratio = camera_intrinsics["pinhole_ratio"]
    aspect_ratio = screen_width / screen_height
    fx = screen_width * pinhole_ratio / aspect_ratio / 2
    fy = screen_height * pinhole_ratio / 2
    cx = screen_width / 2
    cy = screen_height / 2
    return fx, fy, cx, cy

def save_to_3d_labels(camera_info, bboxes_3d, path, visible_labeled_set):
    camera_xform = np.array(camera_info["global_transform"])
    camera_parameters = camera_info["camera_parameters"]
    camera_intrinsics = camera_ov_to_standard(camera_parameters)

    proj_mat_output = np.transpose(get_projection_matrix(camera_intrinsics))
    proj_mat_output[0][0], proj_mat_output[1][1] = proj_mat_output[1][1], proj_mat_output[0][0]
    fx, fy, cx, cy = get_intrinsics(camera_intrinsics)

    objects_metadata = []
    for name, bbox_3d in bboxes_3d.items():
        if name in visible_labeled_set:
            model_pts = [
                ((bbox_3d["x_min"] + bbox_3d["x_max"]) / 2, (bbox_3d["y_min"] + bbox_3d["y_max"]) / 2, (bbox_3d["z_min"] + bbox_3d["z_max"]) / 2),
                (bbox_3d["x_min"], bbox_3d["y_min"], bbox_3d["z_min"]),
                (bbox_3d["x_min"], bbox_3d["y_min"], bbox_3d["z_max"]),
                (bbox_3d["x_min"], bbox_3d["y_max"], bbox_3d["z_min"]),
                (bbox_3d["x_min"], bbox_3d["y_max"], bbox_3d["z_max"]),
                (bbox_3d["x_max"], bbox_3d["y_min"], bbox_3d["z_min"]),
                (bbox_3d["x_max"], bbox_3d["y_min"], bbox_3d["z_max"]),
                (bbox_3d["x_max"], bbox_3d["y_max"], bbox_3d["z_min"]),
                (bbox_3d["x_max"], bbox_3d["y_max"], bbox_3d["z_max"]),
            ]
            screen_camera_pts = [model_to_2d(pt, np.array(bbox_3d["transform"]), camera_xform, camera_intrinsics) for pt in model_pts]
            scale = [float(bbox_3d["x_max"] - bbox_3d["x_min"]), float(bbox_3d["y_max"] - bbox_3d["y_min"]), float(bbox_3d["z_max"] - bbox_3d["z_min"])]
            object_metadata = {
                "name": name, # used to be resolve_mutable_name(name, True) as above
                "keypoints_3d": [list(pt['3d']) for pt in screen_camera_pts],
                'quaternion_xyzw': list(Rotation.from_matrix(np.transpose(np.array(bbox_3d["transform"])[:3, :3] @ np.linalg.inv(camera_xform[:3, :3]) @ rot_z(90))).as_quat()),
                'location': list(screen_camera_pts[0]['3d']),
                'projected_cuboid': [list(pt['2d']) for pt in screen_camera_pts],
                "scale": scale
            }
            objects_metadata.append(object_metadata)

    metadata = {
        "camera_data": {
            "camera_projection_matrix": to_array(proj_mat_output),
            "intrinsics": {
                "cx": cx,
                "cy": cy,
                "fx": fx,
                "fy": fy
            },
        },
        "objects": objects_metadata
    }

    write_json(metadata, path)
    
    
def save_2dlabels_coco( coco_labels, output_path, height, width, binary_obj_det=None):
    
    from datetime import datetime
    images = []
    annotations = []
    categories_dict = {}
    images_count = 1
    annotations_count = 1
    categories_count = 1
    
    for k, v in coco_labels.items():
        
        annotation_for_this_image = 0    
        for cn, details in v.items():
            if "~~~" in cn:
                sp = cn.split("~~~")
                if len(sp) == 2:
                    class_name = sp[1]
                else:
                    class_name = cn
            else:
                class_name = cn
                
            if class_name in categories_dict:
                cid = categories_dict[class_name]
            else:
                categories_dict[class_name] = categories_count
                cid = categories_count
                categories_count+=1
             
            bbox_x = details['x_min']
            bbox_y = details['y_min']
            if bbox_x < 0:
                bbox_x = 0
            if bbox_x > width:
                bbox_x = width - 1
            if bbox_y < 0:
                bbox_y = 0
            if bbox_y > height:
                bbox_y = height - 1
            bbox_w = details['x_max'] - bbox_x
            bbox_h = details['y_max'] - bbox_y
            if bbox_w > 0 and bbox_w < width and bbox_h > 0 and bbox_h < height:
                if binary_obj_det is not None and binary_obj_det:
                    annotations.append({'id':annotations_count, 'category_id':1, 'image_id':images_count, 'iscrowd':0, 'area':(bbox_w * bbox_h), 'bbox':[bbox_x, bbox_y, bbox_w, bbox_h]})
                else:
                    annotations.append({'id':annotations_count, 'category_id':cid, 'image_id':images_count, 'iscrowd':0, 'area':(bbox_w * bbox_h), 'bbox':[bbox_x, bbox_y, bbox_w, bbox_h]})
                annotations_count+=1
                annotation_for_this_image+=1
                
        if annotation_for_this_image > 0:
            images.append({'id':images_count, 'date_captured':str(datetime.utcnow()), 'width':width, 'height':height, 'file_name':f'{k}.jpg'})
            images_count+=1
        
        categories=[]
        if binary_obj_det is not None and binary_obj_det:
            categories.append({'id':1, 'name':'retail_object'})
        else:
            for k, v in categories_dict.items():
                categories.append({'id':v, 'name':k})
            
        data = {'categories':categories, 'annotations':annotations, 'images':images}
        
        write_json(data, os.path.join(output_path, 'annotations.json'), no_sort=True)
    