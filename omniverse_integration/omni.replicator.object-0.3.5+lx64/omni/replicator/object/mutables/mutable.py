from ..utility.interface import *
from ..utility.tex_attr_ops import tex_mut_attr_operation
from ..utility.safe_eval import safe_eval

class MutableAttribute:

    def __init__(self):
        self.curr_value = None

    def resolve(self):
        pass

    def update_to_logging_form(self):
        pass


class MutableAttributeSet(MutableAttribute):

    def __init__(self, values, index):
        self.values = values
        self.curr_macro_string_pair = None
        self.index = index

    def resolve(self):
        if self.index is not None:
            self.curr_value = self.values[self.index % len(self.values)]
        else:
            self.curr_value = random.choice(self.values)
        if isinstance(self.curr_value, MacroStringPair):
            self.curr_macro_string_pair = self.curr_value
            self.curr_value = self.curr_macro_string_pair.actual_string
        else:
            self.curr_macro_string_pair = None

    def update_to_logging_form(self):
        if self.curr_macro_string_pair:
            self.curr_value = self.curr_macro_string_pair.macro_string

    def get_full_set(self):
        return [value.actual_string if isinstance(value, MacroStringPair) else value for value in self.values]

class MutableAttributeRange(MutableAttribute):

    def __init__(self, start, end):
        self.start = start
        self.end = end

    def resolve(self):
        if isinstance(self.start, list) and isinstance(self.end, list):
            if len(self.start) != len(self.end):
                error(f'mismatching start/end dimension in range')
            self.curr_value = rand_range_list(self.start, self.end)
        else:
            self.curr_value = rand_range(self.start, self.end)


class MutableAttributeCameraFrustum(MutableAttribute):
    def __init__(self, camera_parameters, distance_min, distance_max, screen_space_range):
        standard_camera_parameters = camera_ov_to_standard(camera_parameters)
        self.pinhole_ratio = standard_camera_parameters['pinhole_ratio']
        self.aspect_ratio = standard_camera_parameters['screen_width'] / standard_camera_parameters['screen_height']
        self.distance_min = distance_min
        self.distance_max = distance_max
        self.screen_space_range = screen_space_range

    def resolve(self):
        distance = random_reciprocal(self.distance_min, self.distance_max)
        x_rand = self.screen_space_range * rand_range(-1, 1)
        y_rand = self.screen_space_range * rand_range(-1, 1)
        x_ndc, y_ndc = x_rand * distance, y_rand * distance
        res_x, res_y = x_ndc / self.pinhole_ratio * self.aspect_ratio, y_ndc / self.pinhole_ratio
        self.curr_value = [res_x, res_y, -distance]

class MutableAttributeFolder(MutableAttribute):

    def __init__(self, folder, suffix, index):
        if not isinstance(folder, (MacroStringPair, str)):
            error(f"invalid folder type: {type(folder)}")
        if isinstance(folder, str):
            folder = MacroStringPair(folder, folder)
        self.macro_string_pair = folder
        self.values = get_relative_paths_of_suffix(self.macro_string_pair.actual_string, suffix)
        if not self.values:
            error(f"folder {self.macro_string_pair.actual_string} is empty")
        self.curr_relative_path = None
        self.index = index

    def resolve(self):
        if self.index is not None:
            self.curr_relative_path = self.values[self.index % len(self.values)]
        else:
            self.curr_relative_path = random.choice(self.values)
        self.curr_value = os.path.join(self.macro_string_pair.actual_string, self.curr_relative_path)

    def update_to_logging_form(self):
        self.curr_value = os.path.join(self.macro_string_pair.macro_string, self.curr_relative_path)

    def get_full_set(self):
        return [os.path.join(self.macro_string_pair.actual_string, value) for value in self.values]


class MutableAttributeTexture(MutableAttribute):
    def __init__(self, operation):
        self.operation = operation

    def resolve(self):
        if self.operation in tex_mut_attr_operation:
            self.curr_value = f'operation:{self.operation}' # delegate operation to geometry randomization stage because the prim is not yet ready here
        else:
            error(f"unknown operation {self.operation}")

class MutableAttributeHarmonized(MutableAttribute):
    def __init__(self, harmonizer, mutable_name, pitch):
        self.harmonizer = harmonizer
        self.mutable_name = mutable_name
        self.pitch = pitch

    def resolve(self):
        if self.pitch is not None:
            self.harmonizer.absorb(self.mutable_name, self.pitch)

    def retrieve(self):
        self.curr_value = self.harmonizer.reflect(self.mutable_name)

def resolve_value_with_macro(value_with_macro, mappings, parenthesis_start='\$\[', parenthesis_end='\]', evaluate=True):
    def find_in_mappings(item):
        for mapping in mappings:
            for k, v in mapping.items():
                if item == k:
                    return v

    def resolve_value_with_macro_inner(value):
        def resolve_value_with_macro_inner_inner(string):
            for r in re.findall(f'{parenthesis_start}.*?{parenthesis_end}', string):
                item = r.strip(f"{parenthesis_start}{parenthesis_end}")
                if not evaluate:
                    val = find_in_mappings(item)
                    if val is not None:
                        item = val
                string = string.replace(r, str(item))
            return string

        if isinstance(value, str):
            with CHECK(f"evaluate {value} as an expression"):
                value = resolve_value_with_macro_inner_inner(value)
                if evaluate:
                    value = safe_eval(value, mappings)
            return value

        elif isinstance(value, (float, int, bool)):
            return value
        else:
            error(f"not supported macro value type: {value} - {type(value)}")

    if isinstance(value_with_macro, str) and value_with_macro.startswith('$(') and value_with_macro.endswith(')'):
        ref_key = value_with_macro[2:-1]
        mapped_value = find_in_mappings(ref_key)
        if mapped_value is not None:
            return mapped_value
        else:
            error(f"{ref_key} is not in macro mappings")
        return mappings[ref_key]
    if isinstance(value_with_macro, list):
        if len(value_with_macro) > 0 and isinstance(value_with_macro[0], list):
            return [[resolve_value_with_macro_inner(sub_value) for sub_value in row] for row in value_with_macro]
        else:
            return [resolve_value_with_macro_inner(sub_value) for sub_value in value_with_macro]
    else:
        return resolve_value_with_macro_inner(value_with_macro)


# def demacro_inner(value, expected_type, mappings):
#     value = resolve_value_with_macro(value, mappings)
#     with CHECK(f"evaluate attribute with expected type {expected_type}"):
#         value = expected_type(value)
#     return value

def get_mutable_attribute_inner(mutable_attr_name, attr_value, macro_mappings):
    demacro = lambda key: resolve_value_with_macro(ensured_retrieve(key, attr_value), macro_mappings)
    distribution_type = ensured_retrieve('distribution_type', attr_value)

    if distribution_type == 'range':
        return MutableAttributeRange(demacro('start'), demacro('end'))

    elif distribution_type == 'set':
        index = demacro('index') if 'index' in attr_value else None
        return MutableAttributeSet(ensured_retrieve('values', attr_value), index) # TODO: unify ${} macros

    elif distribution_type == 'folder':
        index = demacro('index') if 'index' in attr_value else None
        return MutableAttributeFolder(ensured_retrieve('value', attr_value), ensured_retrieve('suffix', attr_value, str), index)

    elif distribution_type == 'camera_frustum':
        return MutableAttributeCameraFrustum(demacro('camera_parameters'), demacro('distance_min'), \
            demacro('distance_max'), demacro('screen_space_range'))

    elif distribution_type == 'texture':
        return MutableAttributeTexture(ensured_retrieve('operation', attr_value, str))

    else:
        error(f'unrecognized distribution type "{distribution_type}" in "{mutable_attr_name}"')
        return None

def get_op_name(op):
    return list(op.keys())[0]

def get_op_value(op):
    return list(op.values())[0]

class Harmonizer:

    def __init__(self, name, config_item, scene):
        self.name = name
        self.scene = scene
        self.mappings = [config_item, scene.config]
        self.curr_value = None
        self.input = {}
        self.output = {}

    def absorb(self, mutable_name, pitch):
        self.input[mutable_name] = pitch

    def reflect(self, mutable_name):
        return self.output[mutable_name]

    def resonate(self):
        pass

    def post_resonate(self):
        pass



class HarmonizerMutableAttribute(Harmonizer):
    def __init__(self, name, config_item, scene):
        super().__init__(name, config_item, scene)

        self.mutable_attribute = get_mutable_attribute_inner(f'{name}(harmonizer): mutable_attribute', ensured_retrieve('mutable_attribute', config_item, dict), self.mappings)

    def resonate(self):
        self.mutable_attribute.resolve()

    def reflect(self, mutable_name):
        return self.mutable_attribute.curr_value


class HarmonizerPermutate(Harmonizer):
    def __init__(self, name, config_item, scene):
        super().__init__(name, config_item, scene)

    def resonate(self):
        values = list(self.input.values())
        random.shuffle(values)
        for i, key in enumerate(self.input):
            self.output[key] = values[i]

    def reflect(self, mutable_name):
        return self.output[mutable_name]

from py3dbp import Packer, Bin, Item

def get_dimension(min, max):
    return [max[0] - min[0], max[1] - min[1], max[2] - min[2]]

def serialize_packer(packer):
    serialized_packer = {}
    bin = packer.bins[0]
    for item in bin.items:
        serialized_packer[item.name] = {
            'fitted': True,
            'position': [float(item.position[0]), float(item.position[1]), float(item.position[2])],
            'rotation_type': int(item.rotation_type),
        }
    for item in bin.unfitted_items:
        serialized_packer[item.name] = {
            'fitted': False
        }
    return serialized_packer

def calc_box_xform(name, aabb, packer, bin_size):
    if not packer[name]['fitted']:
        return [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [10000, 0, 0, 1]]
    else:
        dimension = get_dimension(aabb[0], aabb[1])

        translate_local = [-(aabb[0][0] + aabb[1][0]) / 2, -(aabb[0][1] + aabb[1][1]) / 2, -(aabb[0][2] + aabb[1][2]) / 2]
        translate_local_xform = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [translate_local[0], translate_local[1], translate_local[2], 1]])

        if packer[name]['rotation_type'] == 0:
            rotate_xform_3d = np.identity(3)
            dimension_offset = [dimension[0], dimension[1], dimension[2]]
        elif packer[name]['rotation_type'] == 1:
            rotate_xform_3d = rot_z_np(90)
            dimension_offset = [dimension[1], dimension[0], dimension[2]]
        elif packer[name]['rotation_type'] == 2:
            rotate_xform_3d = rot_z_np(90) @ rot_x_np(90)
            dimension_offset = [dimension[1], dimension[2], dimension[0]] # z uses what's originally x as offset
        elif packer[name]['rotation_type'] == 3:
            rotate_xform_3d = rot_y_np(90)
            dimension_offset = [dimension[2], dimension[1], dimension[0]]
        elif packer[name]['rotation_type'] == 4:
            rotate_xform_3d = rot_z_np(90) @ rot_y_np(90)
            dimension_offset = [dimension[2], dimension[0], dimension[1]]
        elif packer[name]['rotation_type'] == 5:
            rotate_xform_3d = rot_x_np(90)
            dimension_offset = [dimension[0], dimension[2], dimension[1]]
        rotate_xform = np.identity(4)
        rotate_xform[:3,:3] = rotate_xform_3d

        position = np.array(packer[name]['position']) + np.array(dimension_offset) / 2 - np.array(bin_size) / 2
        position_xform = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [position[0], position[1], position[2], 1]])

        return (translate_local_xform @ rotate_xform @ position_xform).tolist()

class HarmonizerBinPack(Harmonizer):
    def __init__(self, name, config_item, scene):
        super().__init__(name, config_item, scene)
        bin_size = ensured_retrieve('bin_size', config_item)
        self.bin_size_mutable_attribute = None
        if isinstance(bin_size, dict):
            self.bin_size_mutable_attribute = get_mutable_attribute_inner(f'{name}(harmonizer): bin_size', bin_size, self.mappings)
        elif isinstance(bin_size, list) and len(bin_size) == 3:
            self.bin_size = bin_size
        else:
            error(f"invalid type for {name}(harmonizer): bin_size")

    def post_resonate(self):
        if self.bin_size_mutable_attribute is not None:
            self.bin_size_mutable_attribute.resolve()
            self.bin_size = self.bin_size_mutable_attribute.curr_value

        packer = Packer()
        packer.add_bin(Bin(self.name, self.bin_size[0], self.bin_size[1], self.bin_size[2], 1))
        for name, aabb in self.input.items():
            x, y, z = get_dimension(aabb[0], aabb[1])
            packer.add_item(Item(name, x, y, z, 0))
        packer.pack()
        packer = serialize_packer(packer)
        for name, aabb in self.input.items():
            self.output[name] = calc_box_xform(name, aabb, packer, self.bin_size)

    def reflect(self, mutable_name):
        return self.output[mutable_name]

class Mutable:

    def __init__(self, type, name, config_item, scene):
        self.type = type
        self.name = name
        self.prim = None
        self.scene = scene
        self.config_item = config_item
        self.metadata = {}
        self.get_config_item_template()

    def get_mutable_attribute(self, attr_name, attr_value):
        mutable_attr_name = f'{self.name}({self.type}): {attr_name}'
        distribution_type = ensured_retrieve('distribution_type', attr_value, str)

        # mutable local and special values before scene global values
        mappings = [self.config_item, self.scene.config]

        if distribution_type == 'harmonized':
            harmonizer_name = ensured_retrieve('harmonizer_name', attr_value, str)
            harmonizer = ensured_retrieve(harmonizer_name, self.scene.harmonizers, Harmonizer)
            pitch = None
            if 'pitch' in attr_value:
                if attr_value['pitch'] in ['local_aabb']: # special value
                    pitch = attr_value['pitch']
                else:
                    pitch = resolve_value_with_macro(attr_value['pitch'], mappings) # TODO: check type
            return MutableAttributeHarmonized(harmonizer, self.name, pitch)

        return get_mutable_attribute_inner(mutable_attr_name, attr_value, mappings)

    def get_transform_operator_mutable_attributes(self):
        mutable_attr_name = f'{self.name}({self.type}): transform_operators'
        attr_value = self.config_item["transform_operators"]
        if not isinstance(attr_value, list):
            error(f"expecting a list of transform operators, attribute {mutable_attr_name} is not a list")
        for i, op in enumerate(attr_value):
            if not isinstance(op, dict) and len(op) == 1:
                error(f"expecting transform operator to be a (operator name): (operator value) pair, but got {op}")
            name = get_op_name(op)
            value = get_op_value(op)
            # TODO more detailed type checks
            if isinstance(value, dict):
                if 'distribution_type' in value:
                    attr_value[i][name] = self.get_mutable_attribute(f"transform_operators: {name}", value)
                else:
                    error(f"attribute {mutable_attr_name}: {value} is a dictionary, but has no distribution_type")
            elif isinstance(value, str) and name == 'orient' and value == 'random_quaternion':
                q = rand_quatf()
                v = q.GetImaginary()
                attr_value[i][name] = [q.GetReal(), v[0], v[1], v[2]]
            else:
                attr_value[i][name] = value
        return attr_value

    def get_material_mutable_attributes(self):
        materials = {}
        for name, value in ensured_retrieve("shader_attributes", self.config_item, dict).items():
            if isinstance(value, dict):
                ensured_retrieve('distribution_type', value, str)
                materials[name] = self.get_mutable_attribute(f"shader_attributes: {name}", value)
            else:
                materials[name] = value
        return materials

    def get_config_item_template(self):
        self.config_item_template = {}
        for attr_name, attr_value in self.config_item.items():
            if isinstance(attr_value, dict) and 'distribution_type' in attr_value:
                self.config_item_template[attr_name] = self.get_mutable_attribute(attr_name, attr_value)
            elif attr_name == 'transform_operators':
                self.config_item_template[attr_name] = self.get_transform_operator_mutable_attributes()
            elif attr_name == 'shader_attributes':
                self.config_item_template[attr_name] = self.get_material_mutable_attributes()
            else:
                self.config_item_template[attr_name] = attr_value

    def initialize_prim(self):
        if not self.prim:
            error(f"prim does not exist for mutable {self.name}")
        if 'tracked' in self.config_item_template and self.config_item_template['tracked']:
            enable_semantics(self.prim, self.name)
        if 'physics' in self.config_item_template:
            friction = self.scene.physics_global["friction"]
            linear_damping = self.scene.physics_global["linear_damping"]
            angular_damping = self.scene.physics_global["angular_damping"]
            is_concave = tentative_retrieve('concave', self.config_item_template, bool, False)
            if self.config_item_template['physics'] == 'collision':
                set_physics_properties(self.prim, False, friction)
            elif self.config_item_template['physics'] == 'rigidbody':
                set_physics_properties(self.prim, True, friction, linear_damping, angular_damping, is_concave)
            else:
                error('unrecognized physics setting')
        self.set_up_transform_operators_for_prim()

    def set_up_transform_operators_for_prim(self):
        if not self.prim:
            error(f"prim does not exist for mutable {self.name}")
        if 'transform_operators' in self.config_item_template:
            set_xform_ops(self.prim, [(get_op_name(op).replace('_', ':'), None) for op in self.config_item_template['transform_operators']])
        else:
            set_xform_ops(self.prim, [])

    def update_prim_transform(self, transform_operators): # move to xform/py
        self.set_up_transform_operators_for_prim()
        for op in transform_operators:
            value = get_op_value(op)
            if isinstance(value, list):
                if len(value) == 0:
                    error(f"empty list for transform operator {get_op_name(op)}")
                elif isinstance(value[0], list):
                    value = Gf.Matrix4d(value)
                elif len(value) == 4:
                    value = Gf.Quatf(*value)
                else:
                    value = tuple(value)
            get_xform_op(self.prim, get_op_name(op).replace('_', ':')).Set(value)

    def resolve_config_item_template(self, for_logging=False):
        self.metadata = {}
        for attr_name, attr_value in self.config_item_template.items():
            if attr_name in ['transform_operators', 'color']:
                continue # transform operators resolve after all other attributes are resolved
            if isinstance(attr_value, MutableAttribute):
                if for_logging:
                    attr_value.update_to_logging_form()
                # no need to resolve here, done outside; just grab the resolved value
                self.metadata[attr_name] = attr_value.curr_value
            elif isinstance(attr_value, MacroStringPair):
                if for_logging:
                    self.metadata[attr_name] = attr_value.macro_string
                else:
                    self.metadata[attr_name] = attr_value.actual_string
            else:
                self.metadata[attr_name] = attr_value

    def post_resolve_config_item_template(self, for_logging=False):
        if not for_logging:
            self.resolve_transform_operator_mutable_attributes()
            self.resolve_color()
        # grab value directly
        if 'transform_operators' in self.config_item_template:
            self.metadata['transform_operators'] = self.resolved_transform_operators
        if 'color' in self.config_item_template:
            self.metadata['color'] = self.resolved_color

    def resolve_value(self, value):
        if isinstance(value, MutableAttribute):
            if isinstance(value, MutableAttributeHarmonized):
                value.retrieve()
            else:
                value.resolve()
            _value = value.curr_value
        else:
            mappings = [{'seed': self.scene.seed, 'frame': self.scene.index}, self.metadata, self.scene.config]
            _value = resolve_value_with_macro(value, mappings)
        return _value

    def resolve_transform_operator_mutable_attributes(self):
        self.resolved_transform_operators = []
        if not 'transform_operators' in self.config_item_template:
            return
        transform_operators = self.config_item_template['transform_operators']
        if not isinstance(transform_operators, list):
            error(f"transform_operators is not a list for mutable {self.name}")
        for op in transform_operators:
            if not isinstance(op, dict) and len(op) == 1:
                error(f"expecting transform operator to be a (operator name): (operator value) pair, but got {op}")
            value = self.resolve_value(get_op_value(op))
            self.resolved_transform_operators.append({get_op_name(op): value})

    async def preprocess_transform_operator_mutable_attributes(self):
        # DUPLICATED BELOW
        if not 'transform_operators' in self.config_item_template:
            return
        transform_operators = self.config_item_template['transform_operators']
        if not isinstance(transform_operators, list):
            error(f"transform_operators is not a list for mutable {self.name}")
        for op in transform_operators:
            if not isinstance(op, dict) and len(op) == 1:
                error(f"expecting transform operator to be a (operator name): (operator value) pair, but got {op}")
            # DUPLICATED ABOVE, NEED TO MERGE

            operator = get_op_value(op)
            if isinstance(operator, MutableAttributeHarmonized):
                restore_token = False
                if operator.pitch == 'local_aabb':
                    operator.pitch = get_prim_aabb_trimesh(self.prim) # await get_prim_aabb(self.prim)
                    scale = tentative_retrieve('scale', transform_operators[-1], list)
                    if scale:
                        operator.pitch = list(np.array(operator.pitch) * np.array(scale))
                    restore_token = True
                operator.resolve()
                if restore_token:
                    operator.pitch = 'local_aabb'

    def resolve_color(self):
        # color is a potentially harmonized randomizeable value
        self.resolved_color = None
        if not 'color' in self.config_item_template:
            return
        value = self.config_item_template['color']
        value = self.resolve_value(value)
        self.resolved_color = value

    def resolve_shader_attributes(self):
        shader_attributes = tentative_retrieve("shader_attributes", self.config_item_template, dict)
        if shader_attributes is not None:
            output_shader_attributes = {}
            for name, value in shader_attributes.items():
                output_shader_attributes[name] = self.resolve_value(value)
            self.metadata['shader_attributes'] = output_shader_attributes

    def free_randomize(self):
        with CHECK(f'mutable {self.name}({self.type}) free randomize'):
            for attr_name, attr_value in self.config_item_template.items():
                if attr_name == 'color':
                    continue
                if isinstance(attr_value, MutableAttribute):
                    attr_value.resolve()

    def randomize(self):
        pass

    def post_randomize(self):
        pass

    async def harmonized_randomize(self):
        with CHECK(f'mutable {self.name}({self.type}) harmonized randomize'):
            for attr_value in self.config_item_template.values():
                if isinstance(attr_value, MutableAttributeHarmonized):
                    attr_value.retrieve()
            self.resolve_config_item_template() # except xformops and color
            self.resolve_shader_attributes()

            # mutable specific randomize - real update in fabric, must be after material randomize
            self.randomize()

            await self.preprocess_transform_operator_mutable_attributes()

    def post_harmonized_randomize(self):
        with CHECK(f'mutable {self.name}({self.type}) post harmonized randomize'):
            self.post_resolve_config_item_template()

            if self.prim:
                if 'transform_operators' in self.metadata:
                    self.update_prim_transform(self.metadata['transform_operators'])
                if 'physics' in self.metadata and self.metadata['physics'] == 'rigidbody':
                    reset_velocity(self.prim) # otherwise, faster and faster
                self.process_basic_shape_color()

            # e.g. for camera
            self.post_randomize()

            # upload to logging form
            self.resolve_config_item_template(for_logging=True)
            self.post_resolve_config_item_template(for_logging=True)
            if self.prim:
                self.metadata['global_transform'] = to_array(get_total_xform(self.prim))
            return self.metadata

    def process_basic_shape_color(self):
        pass



class Mutable_DEV:
    def __init__(self, name):
        self.name = name

    def initialize_prim(self, metadata, scene):
        if not self.prim:
            error(f"prim does not exist for mutable {self.name}")
        if tentative_retrieve('tracked', metadata, bool, False):
            enable_semantics(self.prim, self.name)
        if 'physics' in metadata:
            friction = scene.physics_global["friction"]
            linear_damping = scene.physics_global["linear_damping"]
            angular_damping = scene.physics_global["angular_damping"]
            is_concave = tentative_retrieve('concave', metadata, bool, False)
            if metadata['physics'] == 'collision':
                set_physics_properties(self.prim, False, friction)
            elif metadata['physics'] == 'rigidbody':
                set_physics_properties(self.prim, True, friction, linear_damping, angular_damping, is_concave)
            else:
                error(f'unrecognized physics mode {metadata["physics"]}')
        self.set_up_transform_operators_for_prim(metadata)

    def set_up_transform_operators_for_prim(self, metadata):
        if not self.prim:
            error(f"prim does not exist for mutable {self.name}")
        if 'transform_operators' in metadata:
            set_xform_ops(self.prim, [(get_op_name(op).replace('_', ':'), None) for op in metadata['transform_operators']])
        else:
            set_xform_ops(self.prim, [])

    def step(self, metadata):
        if self.prim is not None:
            if 'transform_operators' in metadata:
                self.update_prim_transform(metadata)
            if 'physics' in metadata and metadata["physics"] == 'rigidbody':
                reset_velocity(self.prim) # otherwise, faster and faster
            self.global_transform = to_array(get_total_xform(self.prim))
            # NOTE: not recorded in output metadata

    def update_prim_transform(self, metadata): # move to xform/py
        self.set_up_transform_operators_for_prim(metadata)
        transform_operators = metadata['transform_operators']
        for op in transform_operators:
            value = get_op_value(op)
            if isinstance(value, list):
                if len(value) == 0:
                    error(f"empty list for transform operator {get_op_name(op)}")
                elif isinstance(value[0], list):
                    value = Gf.Matrix4d(value)
                elif len(value) == 4:
                    value = Gf.Quatf(*value)
                else:
                    value = tuple(value)
            get_xform_op(self.prim, get_op_name(op).replace('_', ':')).Set(value)
