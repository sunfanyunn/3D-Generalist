from .camera import *
from .light import *
from .geometry import *

def flatten(config):
    flattened_config = {}
    for key, value in config.items():
        if isinstance(value, dict) and 'count' in value:
            count = ensured_retrieve('count', value, int)
            if count < 0:
                error('count should be non-negative int')
            for i in range(count):
                flattened_config[f'{key}_{i}'] = copy.deepcopy(value)
                flattened_config[f'{key}_{i}']['index'] = i
        else:
            flattened_config[key] = value
    return flattened_config

def resolve_as_macro(value):
    if isinstance(value, list):
        return [resolve_as_macro(v) for v in value]
    elif isinstance(value, MacroStringPair):
        return value.macro_string
    else:
        return value

def resolve_output_name(output_name, frame, seed, camera_name):
    for r in re.findall(r'\$\[.*?\]', output_name):
        item = r.strip("$\[\]")
        if item == 'frame':
            output_name = output_name.replace(r, str(frame))
        elif item == 'seed':
            output_name = output_name.replace(r, str(seed))
        elif item == 'camera_name':
            output_name = output_name.replace(r, str(camera_name))
    return output_name


class Scene:

    def __init__(self, config):
        self.mutables = {}
        self.harmonizers = {}
        config = flatten(config)
        self.config = config
        self.output_path = None
        self.metadata = {}
        self.create_folders()
        self.physics_global = {
            "friction": tentative_retrieve("friction", config, (int, float), 1),
            "linear_damping": tentative_retrieve("linear_damping", config, (int, float), 0),
            "angular_damping": tentative_retrieve("angular_damping", config, (int, float), 0)
        }
        for key, value in config.items():
            if isinstance(value, dict):
                if 'harmonizer_type' in value:
                    harmonizer_type = value['harmonizer_type']
                    with CHECK(f'initialize {key}({harmonizer_type})'):
                        if harmonizer_type == 'mutable_attribute':
                            self.harmonizers[key] = HarmonizerMutableAttribute(key, value, self)
                        elif harmonizer_type == 'permutate':
                            self.harmonizers[key] = HarmonizerPermutate(key, value, self)
                        elif harmonizer_type == 'bin_pack':
                            self.harmonizers[key] = HarmonizerBinPack(key, value, self)
                        else:
                            error(f'unrecognized harmonizer type: {harmonizer_type}')
        for key, value in config.items():
            if isinstance(value, dict):
                if 'type' in value:
                    mutable_type = value['type']
                    with CHECK(f'initialize {key}({mutable_type})'):
                        if mutable_type == 'light':
                            self.mutables[key] = Light(key, value, self)
                        elif mutable_type == 'geometry':
                            self.mutables[key] = Geometry(key, value, self)
                        elif mutable_type == 'camera':
                            self.mutables[key] = Camera(key, value, self)
                        else:
                            error(f'unrecognized mutable type: {mutable_type}')

    def create_folders(self):
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
        output_switches = tentative_retrieve('output_switches', self.config, dict)

        if output_switches is not None:
            for key in output_switches:
                if not key in self.output_switches:
                    error(f'unrecognized output switch: {key}')
                self.output_switches[key] = ensured_retrieve(key, output_switches, bool)
        self.output_path = ensured_retrieve('output_path', self.config, str)

        # if 2d label, 3d label, segmentation, or depth is turned on then we save the images even if images is turned off
        if self.output_switches['labels'] or self.output_switches['3d_labels'] or self.output_switches['segmentation'] or self.output_switches['depth'] or self.output_switches['normal']:
            if not self.output_switches['images']:

                logging.info('[METROPERF]: When label, 3d_labels, segmentation, or depth is turned on, switching off so that images are saved.')
                self.output_switches['images'] = True


        with CHECK("create folders"):
            ensure_folder_recursive(self.output_path)
            for key, value in self.output_switches.items():
                if value:
                    ensure_folder(f'{self.output_path}/{key}')

    async def randomize(self, index):
        with CHECK("scene randomize"):
            self.seed = ensured_retrieve('seed', self.config, int) + index
            self.index = index
            random.seed(self.seed)
            metadata = {}
            for key, value in self.config.items():
                if key in self.mutables:
                    self.mutables[key].free_randomize()
            # this is becoming a sandwich, need to optimize later when things get more complicated
            for harmonizer in self.harmonizers.values():
                with CHECK(f"harmonizer {harmonizer.name} resonate"):
                    harmonizer.resonate()
            for key, value in self.config.items():
                if key in self.mutables:
                    await self.mutables[key].harmonized_randomize()
            for harmonizer in self.harmonizers.values():
                with CHECK(f"harmonizer {harmonizer.name} post resonate"):
                    harmonizer.post_resonate()
            for key, value in self.config.items():
                if key in self.mutables:
                    metadata[key] = self.mutables[key].post_harmonized_randomize()
                elif key == 'num_frames':
                    metadata[key] = 1
                elif key == 'seed':
                    metadata[key] = self.seed
                else:
                    metadata[key] = resolve_as_macro(value)
            self.metadata = metadata

    # randomize() must be called before this, so that self.metadata has resolved values of the mutables
    def capture(self, index, coco_2dlabels=None, progress_bar=None):
        with CHECK("capture"):

            bboxes_3d = None
            at_least_one_visible_tracked_mutable = False
            occlusion_threshold = tentative_retrieve('occlusion_threshold', self.metadata, float, 1)
            for mutable in self.mutables.values():
                if isinstance(mutable, Camera):
                    with CHECK(f"camera {mutable.name}"):
                        output_name = resolve_value_with_macro(tentative_retrieve("output_name", self.metadata, str, f"$[seed]_$[camera]"), [{'seed': self.seed, 'frame': self.index, 'camera': mutable.name}], evaluate=False)

                        image, bboxes_2d, segmentation, instance_id_segmentation, depth, normal = mutable.capture()

                        if len(bboxes_2d) == 0 and tentative_retrieve('skip_frames_with_no_visible_tracked_mutables', self.metadata, bool, False):
                            continue
                        at_least_one_visible_tracked_mutable = True

                        self.metadata[mutable.name]['bounding_boxes_2d'] = bboxes_2d
                        visible_labeled_set = set()
                        if self.output_switches['labels']:
                            visible_labeled_set = save_bbox_2d_to_kitti(bboxes_2d, f'{self.output_path}/labels/{output_name}.txt', occlusion_threshold)
                            filtered_bboxes_2d = {name: bboxes_2d[name] for name in visible_labeled_set}
                            if coco_2dlabels is not None:
                                coco_2dlabels[output_name] = filtered_bboxes_2d

                        # TODO
                        if self.output_switches['3d_labels']:
                            if not bboxes_3d: # one for all
                                bboxes_3d = mutable.capture_global_space()
                                for name, box in bboxes_3d.items():
                                    self.metadata[resolve_mutable_name(name, False)]['bounding_box_3d'] = box

                        #visible_mutables = [name for name in bboxes_2d.keys()]
                        #bboxes_3d_filtered = {key: bboxes_3d[key] for key in visible_mutables}
                        if self.output_switches['3d_labels']:
                            save_to_3d_labels(self.metadata[mutable.name], bboxes_3d, f'{self.output_path}/3d_labels/{output_name}.json', visible_labeled_set)

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
                        message = f"[METROPERF]: image saved at {output_path}, [{index + 1}/{self.config['num_frames']}]"
                        logging.info(message)
                        print(message)
                        if progress_bar is not None:
                            progress_bar.model.set_value((index + 1)/self.config['num_frames'])

            if tentative_retrieve('skip_frames_with_no_visible_tracked_mutables', self.metadata, bool, False):
                if not at_least_one_visible_tracked_mutable:
                    return

            if self.output_switches['usd']:
                omni.usd.get_context().save_as_stage(f'{self.output_path}/usd/{output_name}.usd')

            ## need to check carefully here
            output_name = resolve_value_with_macro(tentative_retrieve("output_name", self.metadata, str, f"$[seed]"), [{'seed': self.seed, 'frame': self.index, 'camera': 'global'}], evaluate=False)
            metadata_with_header = {
                "omni.replicator.object":{
                    "version": VERSION,
                }
            }
            metadata_with_header["omni.replicator.object"].update(self.metadata)
            if self.output_switches['descriptions']:
                write_yaml(metadata_with_header, f'{self.output_path}/descriptions/{output_name}.yaml')