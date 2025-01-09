import omni.replicator.core as rep
from .mutable import *
from PIL import Image

def get_replicator_annotators(name, camera_parameters, output_switches):
    camera = rep.create.camera(name=f'Camera_{name}', position=(0, 0, 0), rotation=(0, 0, 0),
        horizontal_aperture=camera_parameters['horizontal_aperture'], focal_length=camera_parameters['focal_length'],
        clipping_range=(camera_parameters['near_clip'], camera_parameters['far_clip']))
    rp = rep.create.render_product(camera, (camera_parameters['screen_width'], camera_parameters['screen_height']))

    # to-do: solve dependency between switches
    replicator_param = {}

    if output_switches["images"]:
        rgb = rep.AnnotatorRegistry.get_annotator("rgb")
        rgb.attach(rp)
        replicator_param["rgb"] = rgb

    if output_switches["labels"]:
        bbox_2d_tight = rep.AnnotatorRegistry.get_annotator("bounding_box_2d_tight_fast", init_params={"semanticTypes": [SEMANTIC_CLASS_STRING]})
        bbox_2d_tight.attach(rp)
        replicator_param["bbox_2d"] = bbox_2d_tight

    if output_switches["3d_labels"]:
        bbox_3d = rep.AnnotatorRegistry.get_annotator("bounding_box_3d_fast", init_params={"semanticTypes": [SEMANTIC_CLASS_STRING]})
        bbox_3d.attach(rp)
        replicator_param["bbox_3d"] = bbox_3d

    if output_switches["segmentation"]:
        segmentation = rep.AnnotatorRegistry.get_annotator("semantic_segmentation", init_params={"colorize": True})
        segmentation.attach(rp)
        replicator_param["segmentation"] = segmentation

    if output_switches["instance_id_segmentation"]:
        instance_id_segmentation = rep.AnnotatorRegistry.get_annotator("instance_id_segmentation", init_params={"colorize": True})
        instance_id_segmentation.attach(rp)
        replicator_param["instance_id_segmentation"] = instance_id_segmentation

    if output_switches["depth"]:
        depth = rep.AnnotatorRegistry.get_annotator("distance_to_image_plane") # was distance_to_camera
        depth.attach(rp)
        replicator_param["depth"] = depth

    if output_switches["normal"]:
        normal = rep.AnnotatorRegistry.get_annotator("SmoothNormal")
        normal.attach(rp)
        replicator_param["normal"] = normal

    return replicator_param

def update_camera_with_proxy(camera_name, camera_proxy):
    camera_prim = get_prim(f'/Replicator/Camera_{camera_name}_Xform')
    _xform = get_total_xform(camera_proxy)
    _xlate, _xyz = get_xlate_and_xyz_from_xform(_xform)
    get_xform_op(camera_prim, "translate").Set(_xlate)
    get_xform_op(camera_prim, "rotateXYZ").Set(_xyz)

def serialize_bbox_3d(bbox_3d_data):
    res = {}
    id_to_labels = bbox_3d_data['info']['idToLabels']
    for data in bbox_3d_data['data']:
        res[id_to_labels[data['semanticId']][SEMANTIC_CLASS_STRING]] = {
            'x_min': float(data['x_min']),
            'y_min': float(data['y_min']),
            'z_min': float(data['z_min']),
            'x_max': float(data['x_max']),
            'y_max': float(data['y_max']),
            'z_max': float(data['z_max']),
            'transform': [[float(item) for item in row] for row in data['transform']]
        }
    return res

def serialize_bbox_2d(bbox_2d_data):
    id_to_labels = bbox_2d_data['info']['idToLabels']
    res = {}
    for data in bbox_2d_data['data']:
        res[id_to_labels[data['semanticId']][SEMANTIC_CLASS_STRING]] = {
            'x_min': int(data['x_min']),
            'y_min': int(data['y_min']),
            'x_max': int(data['x_max']),
            'y_max': int(data['y_max']),
            'occlusion': float(data['occlusionRatio'])
        }
    return res

def serialize_segmentation(segmentation_data):
    id_to_labels = segmentation_data['info']['idToLabels']
    color_to_object = {}
    for k, v in id_to_labels.items():
        color_to_object[k] = list(v.values())[0] #v[SEMANTIC_CLASS_STRING]
    return Image.fromarray(segmentation_data['data'], "RGBA").convert("RGB"), color_to_object

def serialize_instance_id_segmentation(segmentation_data):
    return Image.fromarray(segmentation_data['data'], "RGBA").convert("RGB"), segmentation_data['info']['idToLabels']

class Camera(Mutable):

    def __init__(self, name, config_item, scene):
        super().__init__('camera', name, config_item, scene)
        camera_parameters = ensured_retrieve_dict('camera_parameters', config_item, {
            'screen_width': int,
            'screen_height': int,
            'horizontal_aperture': (int, float),
            'focal_length': (int, float),
            'near_clip': (int, float),
            'far_clip': (int, float)
        })

        self.replicator_annotators = get_replicator_annotators(name, camera_parameters, scene.output_switches)
        self.prim = create_xform_prim(f'/World/CameraProxies/camera_proxy_{name}')
        self.initialize_prim()

    def post_randomize(self):
        update_camera_with_proxy(self.name, self.prim)

    def capture(self):
        rgb = Image.fromarray(self.replicator_annotators["rgb"].get_data(), "RGBA").convert("RGB")
        bbox_2d = serialize_bbox_2d(self.replicator_annotators["bbox_2d"].get_data())
        segmentation = serialize_segmentation(self.replicator_annotators["segmentation"].get_data())
        instance_id_segmentation = serialize_instance_id_segmentation(self.replicator_annotators["instance_id_segmentation"].get_data())
        depth = np.nan_to_num(self.replicator_annotators["depth"].get_data(), posinf=0)
        normal = np.nan_to_num(self.replicator_annotators["normal"].get_data(), posinf=0)
        return rgb, bbox_2d, segmentation, instance_id_segmentation, depth, normal

    def capture_global_space(self):
        bbox_3d = serialize_bbox_3d(self.replicator_annotators["bbox_3d"].get_data())
        return bbox_3d

class Camera_DEV(Mutable_DEV):
    def __init__(self, name, metadata, scene):
        super().__init__(name)
        camera_parameters = ensured_retrieve_dict('camera_parameters', metadata, {
            'screen_width': int,
            'screen_height': int,
            'horizontal_aperture': (int, float),
            'focal_length': (int, float),
            'near_clip': (int, float),
            'far_clip': (int, float)
        })
        self.replicator_annotators = get_replicator_annotators(name, camera_parameters, scene.output_switches)
        self.prim = create_xform_prim(f'/World/CameraProxies/camera_proxy_{name}')
        self.initialize_prim(metadata, scene)

    def step(self, metadata):
        super().step(metadata)
        update_camera_with_proxy(self.name, self.prim)

    def capture(self, output_switches):
        rgb = Image.fromarray(self.replicator_annotators["rgb"].get_data(), "RGBA").convert("RGB") if output_switches["images"] else None
        bbox_2d = serialize_bbox_2d(self.replicator_annotators["bbox_2d"].get_data()) if output_switches["labels"] else None
        segmentation = serialize_segmentation(self.replicator_annotators["segmentation"].get_data()) if output_switches["segmentation"] else None
        instance_id_segmentation = serialize_instance_id_segmentation(self.replicator_annotators["instance_id_segmentation"].get_data()) if output_switches["instance_id_segmentation"] else None
        depth = np.nan_to_num(self.replicator_annotators["depth"].get_data(), posinf=0) if output_switches["depth"] else None
        normal = np.nan_to_num(self.replicator_annotators["normal"].get_data(), posinf=0) if output_switches["normal"] else None
        return rgb, bbox_2d, segmentation, instance_id_segmentation, depth, normal

    def capture_global_space(self):
        bbox_3d = serialize_bbox_3d(self.replicator_annotators["bbox_3d"].get_data())
        return bbox_3d