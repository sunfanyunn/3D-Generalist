from .mutable import *

class Light(Mutable):

    def __init__(self, name, config_item, scene):
        super().__init__('light', name, config_item, scene)

        with CHECK(f'mutable {name}(light) creation'):
            subtype = ensured_retrieve('subtype', config_item, str)
            if subtype == 'dome':
                self.prim = create_or_get_dome_light(f"/World/Lights/dome_light_{name}")
            elif subtype == 'distant':
                self.prim = create_or_get_distant_light(f"/World/Lights/distant_light_{name}")
            else:
                error(f"unrecognized light type {subtype}")
            self.initialize_prim()

    def randomize(self):
        if 'intensity' in self.metadata:
            intensity = self.ensure_typed_attribute('intensity', (float, int))
            self.prim.GetAttribute('inputs:intensity').Set(intensity)
        if 'texture_path' in self.metadata:
            texture_path = self.ensure_typed_attribute('texture_path', str)
            self.prim.GetAttribute('inputs:texture:file').Set(texture_path)
        if 'color' in self.metadata:
            color = self.metadata['color']#self.ensure_typed_attribute('color', 'vector', 3)
            self.prim.GetAttribute('inputs:color').Set(Gf.Vec3f(color))

    def ensure_typed_attribute(self, _name, _type, dimension=None):
        value = self.metadata[_name]
        #if _type == 'scalar':

        if not isinstance(value, _type):
            error(f'{_name} - expected {_type} but got {type(self.metadata[_name])}')
        return value

class Light_DEV(Mutable_DEV):

    def __init__(self, name, metadata, scene):
        super().__init__(name)

        with CHECK(f'mutable {name}(light) creation'):
            subtype = ensured_retrieve('subtype', metadata, str)
            if subtype == 'dome':
                self.prim = create_or_get_dome_light(f"/World/Lights/dome_light_{name}")
            elif subtype == 'distant':
                self.prim = create_or_get_distant_light(f"/World/Lights/distant_light_{name}")
            elif subtype == 'sphere':
                self.prim = create_or_get_sphere_light(f"/World/Lights/sphere_light_{name}")
            else:
                error(f"unrecognized light type {subtype}")
            self.initialize_prim(metadata, scene)

    def step(self, metadata):
        super().step(metadata)
        intensity = tentative_retrieve('intensity', metadata, (float, int), 1000)
        self.prim.GetAttribute('inputs:intensity').Set(intensity)

        texture_path = tentative_retrieve('texture_path', metadata, str, None)
        if texture_path is not None:
            self.prim.GetAttribute('inputs:texture:file').Set(texture_path)
            LOG(texture_path, metadata)

        color = tentative_retrieve('color', metadata, list, None)
        if color is not None:
            self.prim.GetAttribute('inputs:color').Set(Gf.Vec3f(color))
