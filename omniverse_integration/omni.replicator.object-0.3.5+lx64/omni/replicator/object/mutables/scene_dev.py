from ..utility.interface import *
from .camera import *
from .light import *
from .geometry import *

class Scene_DEV:

    def __init__(self, binary_obj_det=None, progress_bar=None):
        self.coco_2dlabels = {}
        self.binary_obj_det = binary_obj_det
        self.progress_bar = progress_bar
        self.num_frames = 1

    async def initialize(self, metadata):
        await self.initialize_scene(metadata)
        self.create_folders(metadata)
        self.create_mutables(metadata)

    async def initialize_scene(self, metadata):
        with CHECK(f'init usdrt stage'):
            await new_stage_async()
            await wait_frames()
            while not get_stage():
                await wait_frames()
            settings = {
                "/app/renderer/resolution/width": ensured_retrieve('screen_width', metadata, int),
                "/app/renderer/resolution/height": ensured_retrieve('screen_height', metadata, int),
                "/persistent/app/stage/upAxis": "Y",
                "/persistent/simulation/defaultMetersPerUnit": 0.01,
                "/omni/replicator/captureOnPlay": False,
                "/persistent/app/primCreation/DefaultXformOpType": "Scale, Rotate, Translate",
                "/app/viewport/grid/enabled": False,
                "/app/viewport/show/camera": False,
                "/app/viewport/show/light": False,
                "/persistent/app/viewport/displayOptions": 0, # remove light icon
            }
            apply_settings(settings)
            await wait_frames()
            await wait_seconds(2)
            await new_stage_async()
            if tentative_retrieve('path_tracing', metadata, bool, False):
                settings = {
                    "/rtx/rendermode": "PathTracing",
                }
                apply_settings(settings)
            scene = UsdPhysics.Scene.Define(get_stage(), "/World/physicsScene")
            scene.CreateGravityDirectionAttr().Set(Gf.Vec3f(0, -1, 0))
            gravity = tentative_retrieve('gravity', metadata, (int, float), 0)
            scene.CreateGravityMagnitudeAttr().Set(gravity)

            physxSceneAPI = PhysxSchema.PhysxSceneAPI.Apply(scene.GetPrim())
            physxSceneAPI.CreateGpuCollisionStackSizeAttr().Set(1e9)
            await wait_frames()

            settings = {
                "/app/viewport/show/camera": False,
                "/app/viewport/show/light": False,
                "/persistent/app/viewport/displayOptions": 0, # remove light icon
            }
            apply_settings(settings)

            await rep.orchestrator.step_async() # for init

    async def step(self, metadata, index, seed):
        with CHECK(f'process frame {index}'):
            await wait_frames() # for the isaac-kit mismatching
            timeline_play()
            self.seed = seed

            # record global transforms used to be here
            for key, mutable in self.mutables.items():
                mutable.step(metadata[key])

            await wait_frames(10)
            inter_frame_time = tentative_retrieve('inter_frame_time', metadata, (int, float), 0)
            if inter_frame_time < 0:
                error('inter_frame_time should be non-negative int')
            await wait_seconds(inter_frame_time) # physics resolution

            # record after resolution, before step_async
            for key, mutable in self.mutables.items():
                if mutable.prim is not None:
                    steady_transform = to_array(get_total_xform(mutable.prim))
                    metadata[key]['global_transform'] = copy.deepcopy(steady_transform) # TODO: provide options
                    metadata[key]['transform_operators'] = [{'transform': copy.deepcopy(steady_transform)}] # get before capturing
                if 'physics' in metadata[key]:
                    metadata[key].pop('physics')

            for key in metadata:
                if isinstance(metadata[key], dict) and 'count' in metadata[key]:
                    ref_count = metadata[key].pop('count')
                    metadata[key]['ref_count'] = ref_count # to avoid multiple spawning during scene restoration

            metadata['num_frames'] = 1
            metadata['inter_frame_time'] = 0.01

            await rep.orchestrator.step_async() # wait for the update for camera to take place

            self.capture(metadata, index)
            timeline_stop()

    def create_folders(self, metadata):
        self.output_switches = {
            'images': True,
            'labels': True,
            'descriptions': True,
            '3d_labels': True,
            'segmentation': True,
            'depth': True,
            'normal': True,
            'instance_id_segmentation': True,
            'usd': False,
        }
        output_switches = tentative_retrieve('output_switches', metadata, dict)

        if output_switches is not None:
            for key in output_switches:
                if not key in self.output_switches:
                    error(f'unrecognized output switch: {key}')
                self.output_switches[key] = ensured_retrieve(key, output_switches, bool)
        self.output_path = ensured_retrieve('output_path', metadata, str)

        dependent_switches = ['labels', '3d_labels', 'segmentation', 'instance_id_segmentation', 'depth', 'normal']
        if any([self.output_switches[_] for _ in dependent_switches]):
            if not self.output_switches['images']:
                logging.info('[METROPERF]: When label, 3d_labels, segmentation, instance_id_segmentation, depth or normal is turned on, switching on images so that images are saved.')
                self.output_switches['images'] = True

        with CHECK("create folders"):
            ensure_folder_recursive(self.output_path)
            for key, value in self.output_switches.items():
                if value:
                    ensure_folder(f'{self.output_path}/{key}')

    def create_mutables(self, metadata):
        self.physics_global = {
            "friction": tentative_retrieve("friction", metadata, (int, float), 1),
            "linear_damping": tentative_retrieve("linear_damping", metadata, (int, float), 0),
            "angular_damping": tentative_retrieve("angular_damping", metadata, (int, float), 0)
        }

        self.mutables = {}
        for key, value in metadata.items():
            if isinstance(value, dict):
                if 'type' in value:
                    mutable_type = value['type']
                    with CHECK(f'initialize {key}({mutable_type})'):
                        if mutable_type == 'light':
                            self.mutables[key] = Light_DEV(key, value, self)
                        elif mutable_type == 'geometry':
                            shape = ensured_retrieve("subtype", value, str)
                            if shape in ["cone", "cube", "cylinder", "disk", "torus", "plane", "sphere", "torus"]:
                                self.mutables[key] = GBasic(key, value, self)
                            elif shape == "mesh":
                                self.mutables[key] = GMesh(key, value, self)
                            elif shape == "bottle":
                                self.mutables[key] = GBottle(key, value, self)
                        elif mutable_type == 'camera':
                            self.mutables[key] = Camera_DEV(key, value, self)
                        else:
                           error(f'unrecognized mutable type: {mutable_type}')

    def capture(self, metadata, index):
        with CHECK("capture"):
            bboxes_3d = None
            at_least_one_visible_tracked_mutable = False
            occlusion_threshold = tentative_retrieve('occlusion_threshold', metadata, float, 1)
            for mutable in self.mutables.values():
                if isinstance(mutable, Camera_DEV):
                    with CHECK(f"camera {mutable.name}"):
                        output_name = tentative_retrieve("output_name", metadata, str, f'{self.seed}_{mutable.name}')

                        image, bboxes_2d, segmentation, instance_id_segmentation, depth, normal = mutable.capture(self.output_switches)

                        if len(bboxes_2d) == 0 and tentative_retrieve('skip_frames_with_no_visible_tracked_mutables', metadata, bool, False):
                            continue
                        at_least_one_visible_tracked_mutable = True

                        metadata[mutable.name]['bounding_boxes_2d'] = bboxes_2d
                        visible_labeled_set = set()
                        if self.output_switches['labels']:
                            visible_labeled_set = save_bbox_2d_to_kitti(bboxes_2d, f'{self.output_path}/labels/{output_name}.txt', occlusion_threshold)
                            filtered_bboxes_2d = {name: bboxes_2d[name] for name in visible_labeled_set}
                            if self.coco_2dlabels is not None:
                                self.coco_2dlabels[output_name] = filtered_bboxes_2d

                        # TODO
                        if self.output_switches['3d_labels']:
                            if not bboxes_3d: # one for all
                                bboxes_3d = mutable.capture_global_space()
                                for name, box in bboxes_3d.items():
                                    metadata[resolve_mutable_name(name, False)]['bounding_box_3d'] = box

                        #visible_mutables = [name for name in bboxes_2d.keys()]
                        #bboxes_3d_filtered = {key: bboxes_3d[key] for key in visible_mutables}
                        if self.output_switches['3d_labels']:
                            save_to_3d_labels(metadata[mutable.name], bboxes_3d, f'{self.output_path}/3d_labels/{output_name}.json', visible_labeled_set)

                        if self.output_switches['segmentation']:
                            segmentation[0].save(f'{self.output_path}/segmentation/{output_name}.png')
                            write_yaml(segmentation[1], f'{self.output_path}/segmentation/{output_name}.yaml')

                        if self.output_switches['instance_id_segmentation']:
                            instance_id_segmentation[0].save(f'{self.output_path}/instance_id_segmentation/{output_name}.png')
                            write_yaml(instance_id_segmentation[1], f'{self.output_path}/instance_id_segmentation/{output_name}.yaml')

                        if self.output_switches['depth']:
                            with open(f'{self.output_path}/depth/{output_name}.npy', 'wb') as f:
                                np.save(f, depth)

                        if self.output_switches['normal']:
                            with open(f'{self.output_path}/normal/{output_name}.npy', 'wb') as f:
                                np.save(f, normal)

                        if self.output_switches['images']:
                            output_path = f'{self.output_path}/images/{output_name}.jpg'
                        image.save(output_path)
                        message = f"[METROPERF]: image saved at {output_path}, [{index + 1}/{self.num_frames}]"
                        logging.info(message)
                        print(message)
                        if self.progress_bar is not None:
                            self.progress_bar.model.set_value((index + 1)/self.num_frames)

            if tentative_retrieve('skip_frames_with_no_visible_tracked_mutables', metadata, bool, False):
                if not at_least_one_visible_tracked_mutable:
                    return

            ## need to check carefully here
            output_name = tentative_retrieve("output_name", metadata, str, f'{self.seed}')
            metadata_with_header = {
                "omni.replicator.object":{
                    "version": VERSION,
                }
            }

            metadata_with_header["omni.replicator.object"].update(metadata)
            if self.output_switches['descriptions']:
                metadata_with_header["omni.replicator.object"]['output_path'] += '__NEXT' # convenience for restoration
                write_yaml(metadata_with_header, f'{self.output_path}/descriptions/{output_name}.yaml')

            if self.output_switches['usd']:
                omni.usd.get_context().save_as_stage(f'{self.output_path}/usd/{output_name}.usd')

    def clean_up(self, metadata):
        save_2dlabels_coco(self.coco_2dlabels, metadata['output_path'], metadata['screen_height'], metadata['screen_width'], self.binary_obj_det)
