from .symbol import *
import time
#from ..utility.metadata import save_2dlabels_coco
from .misc import LOG

config_folder = f"{os.path.dirname(__file__)}/../configs"

def get_config_path_or_folder(path):
    if os.path.isfile(path):
        return path
    absolute_path = f"{config_folder}/{path}.yaml"
    if os.path.isfile(absolute_path):
        return absolute_path
    if os.path.isdir(path):
        configs = []
        for file in os.listdir(path):
            if file.endswith('.yaml'):
                absolute_path = f'{path}/{file}'
                if os.path.isfile(absolute_path):
                    configs.append(absolute_path)
        return configs
    error(f"invalid description file/folder path: {path}")

def get_config_path(path):
    if os.path.isfile(path):
        return path
    absolute_path = f"{config_folder}/{path}.yaml"
    if os.path.isfile(absolute_path):
        return absolute_path
    error(f"invalid description file path: {path}")

def read_description(yaml_path):
    _dict = read_yaml(yaml_path)
    description = ensured_retrieve("omni.replicator.object", _dict, dict)
    version = ensured_retrieve("version", description)
    if version != VERSION:
        error(f"incompatible version number: {version}, expecting {VERSION}")
    return description

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

def read_yaml_recursive(yaml_path):
    config = read_description(get_config_path(yaml_path))
    while 'parent_config' in config:
        parent_path = get_config_path(config.pop('parent_config'))
        parent_config = read_description(parent_path)
        parent_config.update(config)
        config = parent_config
    return flatten(config)

async def simulate(yaml_path, scene):
    with PROFILE("simulate inner"): # demo_kaleidoscope
        config = read_yaml_recursive(yaml_path)
        description = Description(config, scene)

        output_path = ensured_retrieve('output_path', description.context, str)
        ensure_folder_recursive(f'{output_path}/descriptions')

        description.initialize(-1)
        metadata = resolve_scene(description, True)
        await scene.initialize(metadata)
        LOG("------ init ------")
        scene.num_frames = ensured_retrieve('num_frames', description.context, int)
        for index in range(scene.num_frames):
            with PROFILE(f"frame {index}"):
                start = time.time()
                description.initialize(index)
                metadata = resolve_scene(description)
                await scene.step(metadata, index, description.seed)
                LOG(f"------ frame {index} ------ ", time.time() - start, "s")
        scene.clean_up(metadata)

        # below comment: minimum example of description output
        # metadata_with_header = {
        #     "omni.replicator.object":{
        #         "version": VERSION,
        #     }
        # }
        # metadata_with_header["omni.replicator.object"].update(metadata)
        # output_name = description.seed
        # _output_name = tentative_retrieve('output_name', metadata, str)
        # if _output_name is not None:
        #     output_name = _output_name
        # write_yaml(metadata_with_header, f'{output_path}/descriptions/{output_name}.yaml')
        # print(f'{output_path}/descriptions/{output_name}.yaml')