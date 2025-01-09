import omni.ext
import omni.ui as ui

import carb.settings

import logging, asyncio, os
from .simulate import *
import warp as wp

class OmniReplicatorObjectExtension(omni.ext.IExt):
    def on_startup(self, ext_id):
        # for debug purpose mod triggers hot reload
        wp.init()
        function_name = 'on_startup'
        logging.getLogger().setLevel(logging.INFO)

        logging.info(f"{EXTENSION_NAME} [{function_name}]: omni replicator object startup")

        settings = carb.settings.get_settings()
        if settings.get("/isTest"):
            return

        if settings.get('/deep/debug') is not None:
            if settings.get('/deep/debug') > 0:
                settings.set("/crashreporter/enabled", True)
                settings.set("/crashreporter/url", "https://services.nvidia.com/submit")
                settings.set("/crashreporter/product", "Omniverse-oro-debug")
                settings.set("/crashreporter/version", "dev")
                settings.set("/privacy/performance", True)
                #settings.set("/crashreporter/data/debuggingCrash", "1")
                settings.set("/crashreporter/devOnlyOverridePrivacyAndForceUpload", True)
                settings.set("/crashreporter/alwaysUpload", True)
            if settings.get('/deep/debug') > 1:
                settings.set("/persistent/physics/omniPvdOvdRecordingDirectory", "/tmp/")
                settings.set("/physics/omniPvdOutputEnabled", True)


        settings.set("/omni/replicator/asyncRendering", False)
        settings.set("/app/settings/flatCacheStageFrameHistoryCount", 3)
        windowless = settings.get("/windowless")

        # this is for osmo workflows
        data_in = settings.get("/data/in")
        data_out = settings.get("/data/out")
        images_root = settings.get("/images/root")
        assets_root = settings.get("/assets/root")
        binary_obj_detection = settings.get('/binary')
        if windowless is not None and windowless:
            logging.info(f"{EXTENSION_NAME} [{function_name}]: windowless mode on")
            config_path_from_argument = settings.get("/config/file")
            if config_path_from_argument is None:
                config_path = f"{os.path.dirname(__file__)}/configs/minimum.yaml"
                asyncio.ensure_future(on_simulate_dev(self, config_path, None, True, data_in, data_out, images_root, assets_root, binary_obj_detection))
            else:
                logging.info(f"{EXTENSION_NAME} [{function_name}]: config file is {config_path_from_argument}.")
                asyncio.ensure_future(on_simulate_dev(self, config_path_from_argument, None, True, data_in, data_out, images_root, assets_root, binary_obj_detection))
        else:
            logging.info(f"{EXTENSION_NAME} [{function_name}]: windowless mode off")
            self._window = ui.Window("omni.replicator.object", width=300, height=200)
            with self._window.frame:
                with ui.VStack():
                    ui.Label("Description File")

                    #model = ui.SimpleStringModel("minimum")
                    model = ui.SimpleStringModel()
                    field = ui.StringField(model, multiline=True)

                    progress_bar = ui.ProgressBar()
                    #ui.Button("Simulate Old", clicked_fn=lambda: asyncio.ensure_future(on_simulate(self, field.model.get_value_as_string(), progress_bar, False, data_in, data_out, images_root, assets_root, binary_obj_detection)))
                    ui.Button("Simulate", clicked_fn=lambda: asyncio.ensure_future(on_simulate_dev(self, field.model.get_value_as_string(), progress_bar, False, data_in, data_out, images_root, assets_root, binary_obj_detection)))


    def on_shutdown(self):
        logging.info(f"{EXTENSION_NAME} [on_shutdown]: omni replicator object shutdown")
