import logging, carb
from .utility.interface import *
from .mutables.scene import *
from .utility.metadata import *

from .description import parse
from .description.parse import *
from .mutables.scene_dev import *

def resolve_placeholders_inner(description_item, global_description):
    for key, value in description_item.items():
        if type(value) == dict:
            resolve_placeholders_inner(description_item[key], global_description)
        elif type(value) == list:
            for i, item in enumerate(value):
                if type(item) == str and '${' in item:
                    value[i] = MacroStringPair(item, replace_macro(item, global_description))
        elif type(value) in [float, int, bool]:
            pass
        elif type(value) == str:
            value = value.strip()
            if value.startswith('$(') and value.endswith(')'):
                ref_key = value[2:-1]
                description_item[key] = ensured_retrieve(ref_key, global_description)
            elif '${' in value: # we don't want MacroStringPair everywhere
                description_item[key] = MacroStringPair(value, replace_macro(value, global_description)) # (macro string, actual string)
            else:
                description_item[key] = value
        else:
            error("unknown type in config") # should not reach here though
    return description_item

def resolve_placeholders(global_description):
    return resolve_placeholders_inner(global_description, global_description)

def parse_yaml_config(yaml_path, data_in=None, data_out=None, images_root=None, assets_root=None):
    config = read_yaml_recursive(yaml_path)

    if data_in is not None:
        config['data_in'] = data_in
    if data_out is not None:
        config['output_path'] = data_out
    if images_root is not None:
        config['images_root'] = images_root
    if assets_root is not None:
        config['assets_root'] = assets_root

    resolved_config = resolve_placeholders(config)
    disentangle(resolved_config)
    return resolved_config

def get_config_path(path):
    if os.path.isfile(path):
        return path
    absolute_path = f"{os.path.dirname(__file__)}/configs/{path}.yaml"
    if os.path.isfile(absolute_path):
        return absolute_path
    error(f"invalid description file path: {path}")

async def on_simulate(extension, config_path, progress_bar=None, windowless=False, data_in=None, data_out=None, images_root=None, assets_root=None, binary_obj_det=None):
    CLEAR()
    function_name = 'on_simulate'
    logging.info(f"{EXTENSION_NAME} [{function_name}]: entry")

    await omni.replicator.object.new_stage_async()
    await omni.replicator.object.wait_frames()

    return_code = 0
    try:
        with CHECK("simulate", log=True):
            with CHECK(f'read config'):

                config_path = get_config_path(config_path)
                config = parse_yaml_config(config_path, data_in, data_out, images_root, assets_root)

            with CHECK(f'init usdrt stage'):
                while not get_stage():
                    await wait_frames()
                settings = {
                    "/app/renderer/resolution/width": ensured_retrieve('screen_width', config, int),
                    "/app/renderer/resolution/height": ensured_retrieve('screen_height', config, int),
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
                if tentative_retrieve('path_tracing', config, bool, False):
                    settings = {
                        "/rtx/rendermode": "PathTracing",
                    }
                    apply_settings(settings)
                scene = UsdPhysics.Scene.Define(get_stage(), "/World/physicsScene")
                scene.CreateGravityDirectionAttr().Set(Gf.Vec3f(0, -1, 0))
                gravity = tentative_retrieve('gravity', config, (int, float), 0)
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

            with CHECK(f'initialize scene'):
                scene = Scene(config)
                await rep.orchestrator.step_async() # for init


            coco_2dlabels={}
            for index in range(ensured_retrieve('num_frames', config, int)):
                with CHECK(f'process frame {index}'):
                    await wait_frames() # for the isaac-kit mismatching
                    timeline_play()
                    await scene.randomize(index) # update to async
                    await wait_frames(10)
                    inter_frame_time = tentative_retrieve('inter_frame_time', config, (int, float), 0)
                    if inter_frame_time < 0:
                        error('inter_frame_time should be non-negative int')

                    await wait_seconds(inter_frame_time)

                    await rep.orchestrator.step_async() # wait for the update for camera to take place
                    scene.capture(index, coco_2dlabels, progress_bar)

                    timeline_stop()
                    LOG(f'============== frame {index} ==============')
            save_2dlabels_coco(coco_2dlabels, config['output_path'], config['screen_height'], config['screen_width'], binary_obj_det)

    except Exception as e:
        logging.error(f'simulation terminated, error at: {e}')
        return_code = 1

    if windowless:
        logging.info(f"{EXTENSION_NAME} [{function_name}]: shutting down extension.")
        carb.settings.get_settings().set("/app/fastShutdown", True)
        await omni.usd.get_context().close_stage_async()
        omni.kit.app.get_app().post_quit(return_code=return_code)


async def on_simulate_dev(extension, description_path, progress_bar=None, windowless=False, data_in=None, data_out=None, images_root=None, assets_root=None, binary_obj_det=None):
    function_name = 'on_simulate'
    logging.info(f"{EXTENSION_NAME} [{function_name}]: entry")
    return_code = 0
    try:
        description_paths = get_config_path_or_folder(description_path) # a folder, or a path, or a name in config folder
        if isinstance(description_paths, str):
            description_paths = [description_paths]
        with CHECK("simulate"):
            CLEAR()
            for path in description_paths:
                with CHECK(f"simulate {path}"):
                    global_message(f"simulate {path}")
                    scene = Scene_DEV(binary_obj_det, progress_bar)
                    await parse.simulate(path, scene)

    except Exception as e:
        logging.error(f'simulation terminated, error at: {e}')
        # raise e  # for global debug
        return_code = 1

    if windowless:
        logging.info(f"{EXTENSION_NAME} [{function_name}]: shutting down extension.")
        carb.settings.get_settings().set("/app/fastShutdown", True)
        await omni.usd.get_context().close_stage_async()
        omni.kit.app.get_app().post_quit(return_code=return_code)
