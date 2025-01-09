from .mutable import *
from .bottle import *
from .solder_point import SolderPoint
from ..utility.tex_attr_ops import tex_mut_attr_operation

from PIL import Image
import shutil, cv2

def turn_off_physics(prim):
    physics_on = prim.GetAttribute("physics:rigidBodyEnabled")
    if physics_on:
        physics_on.Set(False)
    for child in prim.GetChildren():
        turn_off_physics(child)

def process_image(src_path, usd_path, operation):
    abs_path = os.path.abspath(os.path.join(os.path.dirname(usd_path), str(src_path).strip("@")))
    ext = os.path.splitext(abs_path)[1]
    input_path = f'{get_tmp_dir()}/randomized_input{ext}'
    output_path = f'{get_tmp_dir()}/randomized_output{ext}'
    shutil.copy(abs_path, input_path) # TODO: from nucleus
    input = cv2.imread(input_path)
    if operation in tex_mut_attr_operation:
        output = tex_mut_attr_operation[operation](input)
        cv2.imwrite(output_path, output)
    else:
        # we already did a check previously, should not reach here
        error(f"unknown operation: {operation}")
    return output_path

def create_variant_mesh(scene_path, usd_paths):
    xform_prim = create_xform_prim(scene_path)
    variant_set = xform_prim.GetVariantSets().AddVariantSet("Meshes")
    for usd_path in usd_paths:
        name = get_base_name(usd_path)
        variant_set.AddVariant(name)
        variant_set.SetVariantSelection(name)
        with variant_set.GetVariantEditContext():
            xform_prim.GetReferences().AddReference(usd_path)
            xform_prim.SetInstanceable(False)
    return xform_prim, variant_set


class Geometry(Mutable):
    def __init__(self, name, config_item, scene):
        super().__init__("geometry", name, config_item, scene)

        shape = ensured_retrieve("subtype", config_item, str)
        if shape in ["cone", "cube", "cylinder", "disk", "torus", "plane", "sphere", "torus"]:
            self.prim = create_or_get_mesh_prim(shape, f"/World/Shapes/{shape}_{name}")
            # TODO
            if 'material_path' in self.config_item_template:
                self.materials_parent = f"/World/Shapes/{shape}_{name}_material_"
                self.materials = {}
            elif 'texture_path' in self.config_item_template or 'color' in self.config_item_template:
                self.shape_shader = create_and_bind_material_shader(
                    f"/World/Shapes/{shape}_{name}_material", "OmniPBR", self.prim
                )

        elif shape == "mesh":
            usd_path = ensured_retrieve("usd_path", self.config_item_template) # TODO
            if isinstance(usd_path, (MutableAttributeFolder, MutableAttributeSet)):
                usd_candidates = usd_path.get_full_set()
            elif isinstance(usd_path, MutableAttributeHarmonized):
                usd_candidates = self.config_item_template["usd_path"].harmonizer.mutable_attribute.get_full_set()
            else:
                usd_candidates = [resolve_string(usd_path)]
            self.prim, self.mesh_variant_set = create_variant_mesh(f"/World/Meshes/mesh_{name}", usd_candidates)

            # TODO standardize texture substitution
            """if 'texture_path' in self.config_item_template:
                mesh = get_prim(f'{self.prim.GetPath().pathString}/KV001_Tide_PUO_32ct')
                mesh_2 = get_prim(f'{self.prim.GetPath().pathString}')
                self.shape_shader = create_and_bind_material_shader(
                    f"/World/Shapes/{shape}_{name}_material", "OmniPBR", mesh
                )
                #print(self.config_item_template['texture_path'])"""

        elif shape == "bottle":
            scene_path = f"/World/Bottles/bottle_{name}"
            self.prim = create_xform_prim(scene_path)
            self.bottle = Bottle()
            self.control_points = [
                (0, -70, 0),
                (0, -70, 0),
                (0, -70, 18),
                (0, -60, 20),
                (0, -30, 20),
                (0, 20, 10),
                (0, 45, 8),
                (0, 75, 6),
                (0, 90, 6),
                (0, 90, 0),
                (0, 90, 0),
            ]
            self.bottle_body = create_custom_mesh(f"{scene_path}/Body")
            self.bottle_label = create_custom_mesh(f"{scene_path}/Label", sts=[])
            self.bottle_body_shader = create_and_bind_material_shader(
                f"{scene_path}/BodyMaterial", "OmniGlass", self.bottle_body
            )
            self.bottle_label_shader = create_and_bind_material_shader(
                f"{scene_path}/LabelMaterial", "OmniPBR", self.bottle_label
            )
        elif shape == "solder_point":
            scene_path = f"/World/SolderPoints/solder_point_{name}"
            self.solder_point = SolderPoint(scene_path)
            self.prim = self.solder_point.prim
        else:
            error(f"unrecognized shape {shape}")
        self.initialize_prim()

    def randomize(self):
        if self.metadata["subtype"] == "mesh":
            base_name = get_base_name(self.metadata["usd_path"])
            self.mesh_variant_set.SetVariantSelection(base_name) # after SetVariantSelection, [translate, rotateXYZ, scale] values will be spawned but not added to the xformOp list if they did not exist
            if 'tracked' in self.metadata and self.metadata['tracked']:
                enable_semantics(self.prim, f'{self.name}~~~{base_name}')
            # TODO: texture substitution
            """if 'texture_path' in self.metadata:
                texture_path = self.metadata['texture_path']
                #print('ha', texture_path)
                self.shape_shader.GetInput("diffuse_texture").Set(texture_path)"""

            # texture augmentation must happen here, before texture update, after mesh update

            shader_attributes = tentative_retrieve("shader_attributes", self.metadata, dict)
            if shader_attributes is not None:
                self.mesh_shader = UsdShade.Shader(find_first_of_type(self.prim, 'Shader'))
                for name, value in shader_attributes.items():
                    input = self.mesh_shader.GetInput(name)
                    if not input:
                        error(f'shader attribute {name} does not exist')
                    if isinstance(value, list):
                        value = tuple(value)
                    if isinstance(value, str) and value.startswith('operation:'):
                        value = process_image(input.Get(), self.metadata["usd_path"], value.split(':')[1])
                    input.Set(value)

        elif self.metadata["subtype"] == "bottle":
            def get_effector(name):
                return ensured_retrieve(name, self.metadata, (int, float))
            self.control_points[5] = (
                0,
                lerp(0, 35, get_effector("vertical_effector")),
                lerp(8, 20, get_effector("horizontal_effector")),
            )
            self.control_points[4] = (
                0,
                lerp(-30, self.control_points[5][1] - 20, get_effector("base_effector")),
                20,
            )
            self.control_points[6] = (
                0,
                lerp(self.control_points[5][1] + 10, 65, get_effector("neck_effector")),
                8,
            )

            self.bottle.update(self.control_points, 5)  # TODO
            # body
            self.bottle_body.GetPointsAttr().Set((self.bottle.body_mesh_points))
            self.bottle_body.GetFaceVertexIndicesAttr().Set(self.bottle.body_face_vertex_indices)
            self.bottle_body.GetFaceVertexCountsAttr().Set(self.bottle.body_face_vertex_counts)
            # label
            self.bottle_label.GetPointsAttr().Set((self.bottle.label_mesh_points))
            self.bottle_label.GetFaceVertexIndicesAttr().Set(self.bottle.get_label_face_vertex_indices())
            self.bottle_label.GetFaceVertexCountsAttr().Set(self.bottle.get_label_face_vertex_counts())
            UsdGeom.PrimvarsAPI(self.bottle_label).GetPrimvar("st").Set(self.bottle.get_label_sts())
            # label texture
            if "texture_path" in self.metadata:
                texture_path = self.metadata["texture_path"]
                self.bottle_label_shader.GetInput("diffuse_texture").Set(texture_path)

                # de-stretch
                Rp = self.bottle.label_size_ratio
                image_width, image_height = Image.open(texture_path).size
                Ri = image_width / image_height

                if Ri > Rp:
                    set_shader_tiling(self.bottle_label_shader, Rp / Ri, 1)
                else:
                    set_shader_tiling(self.bottle_label_shader, 1, Ri / Rp)
            if 'color' in self.metadata:
                color = self.metadata['color']
                self.bottle_body_shader.GetInput('glass_color').Set(Gf.Vec3f(color))
        elif self.metadata["subtype"] == "solder_point":
            self.solder_point.randomize()
        if self.metadata["subtype"] in ["cone", "cube", "cylinder", "disk", "torus", "plane", "sphere", "torus"]:
            if 'material_path' in self.metadata:
                material_path = self.metadata['material_path']
                self.switch_material(material_path)
            elif 'texture_path' in self.metadata:
                texture_path = self.metadata['texture_path']
                self.shape_shader.GetInput("diffuse_texture").Set(texture_path)

                # de-stretch TODO abstract with above
                Rp = 960 / 544 # TODO ...really need to access this somewhere
                image_width, image_height = Image.open(texture_path).size
                Ri = image_width / image_height

                if Ri > Rp:
                    set_shader_tiling(self.shape_shader, Rp / Ri, 1)
                else:
                    set_shader_tiling(self.shape_shader, 1, Ri / Rp)
            elif 'color' in self.metadata:
                color = self.metadata['color']
                self.shape_shader.GetInput("diffuse_tint").Set(Gf.Vec3f(color))

    def switch_material(self, mtl_url):
        basename = mtl_url[mtl_url.rfind('/')+1:-4]
        scene_path = self.materials_parent + basename
        if not basename in self.materials:
            omni.kit.commands.execute("CreateMdlMaterialPrim", mtl_url=mtl_url, mtl_name=basename, mtl_path=scene_path)
            self.materials[basename] = scene_path
        omni.kit.commands.execute("BindMaterial", material_path=scene_path, prim_path=[self.prim.GetPath()])

    def process_basic_shape_color(self):
        if self.metadata["subtype"] in ["cone", "cube", "cylinder", "disk", "torus", "plane", "sphere", "torus"]:
            if 'color' in self.metadata:
                color = self.metadata['color']
                self.shape_shader.GetInput("diffuse_tint").Set(Gf.Vec3f(color))
        elif self.metadata["subtype"] == "bottle":
            if 'color' in self.metadata:
                color = self.metadata['color']
                self.bottle_body_shader.GetInput('glass_color').Set(Gf.Vec3f(color))



class Geometry_DEV(Mutable_DEV):
    def __init__(self, name):
        super().__init__(name)

    def switch_material(self, mtl_url):
        basename = mtl_url[mtl_url.rfind('/')+1:-4]
        scene_path = self.materials_parent + basename
        if not basename in self.materials:
            omni.kit.commands.execute("CreateMdlMaterialPrim", mtl_url=mtl_url, mtl_name=basename, mtl_path=scene_path)
            self.materials[basename] = scene_path
        omni.kit.commands.execute("BindMaterial", material_path=scene_path, prim_path=[self.prim.GetPath()])


class GBasic(Geometry_DEV):
    def __init__(self, name, metadata, scene):
        super().__init__(name)
        shape = metadata["subtype"]
        self.prim = create_or_get_mesh_prim(shape, f"/World/Shapes/{shape}_{name}")
        # TODO
        if 'material_path' in metadata:
            self.materials_parent = f"/World/Shapes/{shape}_{name}_material_"
            self.materials = {}
        elif 'texture_path' in metadata or 'color' in metadata:
            self.shape_shader = create_and_bind_material_shader(
                f"/World/Shapes/{shape}_{name}_material", "OmniPBR", self.prim
            )
        self.initialize_prim(metadata, scene)

    def step(self, metadata):
        super().step(metadata)
        if 'material_path' in metadata:
            material_path = metadata['material_path']
            self.switch_material(material_path)
        elif 'texture_path' in metadata:
            texture_path = metadata['texture_path']
            self.shape_shader.GetInput("diffuse_texture").Set(texture_path)

            # de-stretch TODO abstract with above
            Rp = 960 / 544 # TODO ...really need to access this somewhere
            image_width, image_height = Image.open(texture_path).size
            Ri = image_width / image_height

            if Ri > Rp:
                set_shader_tiling(self.shape_shader, Rp / Ri, 1)
            else:
                set_shader_tiling(self.shape_shader, 1, Ri / Rp)
        elif 'color' in metadata:
            color = metadata['color']
            self.shape_shader.GetInput("diffuse_tint").Set(Gf.Vec3f(color))

class GMesh(Geometry_DEV):
    def __init__(self, name, metadata, scene):
        super().__init__(name)
        usd_candidates = ensured_retrieve("usd_path", metadata)
        if isinstance(usd_candidates, str):
            usd_candidates = [usd_candidates]
        elif not isinstance(usd_candidates, list):
            error(f"incorrect type for usd_path {type(usd_candidates)} at {name}")
        self.prim, self.mesh_variant_set = create_variant_mesh(f"/World/Meshes/mesh_{name}", usd_candidates)

        # TODO standardize texture substitution
        """if 'texture_path' in self.config_item_template:
            mesh = get_prim(f'{self.prim.GetPath().pathString}/KV001_Tide_PUO_32ct')
            mesh_2 = get_prim(f'{self.prim.GetPath().pathString}')
            self.shape_shader = create_and_bind_material_shader(
                f"/World/Shapes/{shape}_{name}_material", "OmniPBR", mesh
            )
            #print(self.config_item_template['texture_path'])"""

        self.initialize_prim(metadata, scene)
        self.has_updated_usd = False

    def step(self, metadata):
        super().step(metadata)
        if not self.has_updated_usd:
            self.update_usd(metadata['usd_path'])

        shader_attributes = tentative_retrieve("shader_attributes", metadata, dict)
        if shader_attributes is not None:
            self.mesh_shader = UsdShade.Shader(find_first_of_type(self.prim, 'Shader'))
            for name, value in shader_attributes.items():
                input = self.mesh_shader.GetInput(name)
                if not input:
                    error(f'shader attribute {name} does not exist')
                if isinstance(value, list):
                    value = tuple(value)
                if isinstance(value, str):
                    value = value.strip()
                    if value.startswith('<') and value.endswith('>'):
                        value = process_image(input.Get(), metadata["usd_path"], value.strip('<>'))
                input.Set(value)

        base_name = get_base_name(metadata['usd_path'])
        if tentative_retrieve('tracked', metadata, bool, False):
            enable_semantics(self.prim, f'{self.name}~~~{base_name}')
        self.has_updated_usd = False

    def update_usd(self, usd_path, get_prim_aabb=False):
        self.has_updated_usd = True
        base_name = get_base_name(usd_path)
        self.mesh_variant_set.SetVariantSelection(base_name) # after SetVariantSelection, [translate, rotateXYZ, scale] values will be spawned but not added to the xformOp list if they did not exist
        if get_prim_aabb:
            return get_prim_aabb_trimesh(self.prim)

class GBottle(Geometry_DEV):
    def __init__(self, name, metadata, scene):
        super().__init__(name)

        scene_path = f"/World/Bottles/bottle_{name}"
        self.prim = create_xform_prim(scene_path)
        self.bottle = Bottle()
        self.control_points = [
            (0, -70, 0),
            (0, -70, 0),
            (0, -70, 18),
            (0, -60, 20),
            (0, -30, 20),
            (0, 20, 10),
            (0, 45, 8),
            (0, 75, 6),
            (0, 90, 6),
            (0, 90, 0),
            (0, 90, 0),
        ]
        self.bottle_body = create_custom_mesh(f"{scene_path}/Body")
        self.bottle_label = create_custom_mesh(f"{scene_path}/Label", sts=[])
        self.bottle_body_shader = create_and_bind_material_shader(
            f"{scene_path}/BodyMaterial", "OmniGlass", self.bottle_body
        )
        self.bottle_label_shader = create_and_bind_material_shader(
            f"{scene_path}/LabelMaterial", "OmniPBR", self.bottle_label
        )

        self.initialize_prim(metadata, scene)

    def step(self, metadata):
        super().step(metadata)

        def get_effector(name):
            return ensured_retrieve(name, metadata, (int, float))
        self.control_points[5] = (
            0,
            lerp(0, 35, get_effector("vertical_effector")),
            lerp(8, 20, get_effector("horizontal_effector")),
        )
        self.control_points[4] = (
            0,
            lerp(-30, self.control_points[5][1] - 20, get_effector("base_effector")),
            20,
        )
        self.control_points[6] = (
            0,
            lerp(self.control_points[5][1] + 10, 65, get_effector("neck_effector")),
            8,
        )

        self.bottle.update(self.control_points, 5)  # TODO
        # body
        self.bottle_body.GetPointsAttr().Set((self.bottle.body_mesh_points))
        self.bottle_body.GetFaceVertexIndicesAttr().Set(self.bottle.body_face_vertex_indices)
        self.bottle_body.GetFaceVertexCountsAttr().Set(self.bottle.body_face_vertex_counts)
        # label
        self.bottle_label.GetPointsAttr().Set((self.bottle.label_mesh_points))
        self.bottle_label.GetFaceVertexIndicesAttr().Set(self.bottle.get_label_face_vertex_indices())
        self.bottle_label.GetFaceVertexCountsAttr().Set(self.bottle.get_label_face_vertex_counts())
        UsdGeom.PrimvarsAPI(self.bottle_label).GetPrimvar("st").Set(self.bottle.get_label_sts())
        # label texture
        if "texture_path" in metadata:
            texture_path = metadata["texture_path"]
            self.bottle_label_shader.GetInput("diffuse_texture").Set(texture_path)

            # de-stretch
            Rp = self.bottle.label_size_ratio
            image_width, image_height = Image.open(texture_path).size
            Ri = image_width / image_height

            if Ri > Rp:
                set_shader_tiling(self.bottle_label_shader, Rp / Ri, 1)
            else:
                set_shader_tiling(self.bottle_label_shader, 1, Ri / Rp)
        if 'color' in metadata:
            color = metadata['color']
            self.bottle_body_shader.GetInput('glass_color').Set(Gf.Vec3f(color))
