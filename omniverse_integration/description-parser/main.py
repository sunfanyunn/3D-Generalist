from description import *
import os, asyncio

class Scene:

    def __init__(self):
        self.num_frames = 0

    async def initialize(self, metadata):
        self.output_path = ensured_retrieve('output_path', metadata, str)
        ensure_folder(f'{self.output_path}/descriptions')
        print('initialize scene')

    async def step(self, metadata, index, seed):
        self.seed = seed

        output_name = tentative_retrieve("output_name", metadata, str, f'{self.seed}')
        metadata_with_header = {
            "omni.replicator.object":{
                "version": VERSION,
            }
        }

        metadata_with_header["omni.replicator.object"].update(metadata)
        metadata_with_header["omni.replicator.object"]['output_path'] += '__NEXT' # convenience for restoration
        write_yaml(metadata_with_header, f'{self.output_path}/descriptions/{output_name}.yaml')

        print(f'step scene, index: {index}, seed: {seed}')

    def clean_up(self, metadata):
        print('clean up scene')

async def on_simulate(description_path):
    print(description_path)
    with PROFILE("oro simulate"):
        function_name = 'on_simulate'
        logging.info(f"{EXTENSION_NAME} [{function_name}]: entry")
        return_code = 0
        
        description_paths = get_config_path_or_folder(description_path) # a folder, or a path, or a name in config folder
        if isinstance(description_paths, str):
            description_paths = [description_paths]
        with CHECK("simulate"):
            CLEAR()
            for path in description_paths:
                with CHECK(f"simulate {path}"):
                    global_message(f"simulate {path}")
                    scene = Scene()
                    await parse.simulate(path, scene)
            

asyncio.run(on_simulate('./configs/demo_bin_pack.yaml'))