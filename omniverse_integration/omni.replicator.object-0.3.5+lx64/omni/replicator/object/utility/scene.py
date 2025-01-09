import omni, carb, time, asyncio, trimesh
from .misc import error, LOG
from pxr import UsdGeom, UsdPhysics, PhysxSchema, Gf, Sdf, UsdShade
from omni.physx.scripts.physicsUtils import add_physics_material_to_prim

def apply_settings(settings):
    for key, value in settings.items():
        carb.settings.get_settings().set(key, value)

## scene

async def wait_frames(cnt=1):
    for i in range(cnt):
        await omni.kit.app.get_app_interface().next_update_async()

async def wait_seconds(cnt=1):
    start = time.time()
    while time.time() - start < cnt:
        await wait_frames()

async def new_stage_async():
    await omni.usd.get_context().new_stage_async()

def get_next_free_path(path):
    return omni.usd.get_stage_next_free_path(get_stage(), path, True)

def get_stage():
    return omni.usd.get_context().get_stage()

def get_prim(scene_path):
    return get_stage().GetPrimAtPath(scene_path)

def create_xform_prim(scene_path):
    return UsdGeom.Xform.Define(get_stage(), scene_path).GetPrim()

def create_or_get(scene_path, operation):
    prim = get_prim(scene_path)
    if not prim:
        operation()
        prim = get_prim(scene_path)
    return prim

def create_or_get_dome_light(scene_path='/World/DomeLight', intensity=1000):
    return create_or_get(scene_path, lambda: omni.kit.commands.execute("CreatePrim", prim_path=scene_path, prim_type='DomeLight', attributes={'inputs:intensity': intensity, 'inputs:texture:format': 'latlong'}))

def create_or_get_distant_light(scene_path='/World/DistantLight', intensity=3000):
    return create_or_get(scene_path, lambda: omni.kit.commands.execute("CreatePrim", prim_path=scene_path, prim_type='DistantLight', attributes={'inputs:angle': 1.0, 'inputs:intensity': intensity}))

def create_or_get_sphere_light(scene_path='/World/SphereLight', intensity=30000, radius=50):
    return create_or_get(scene_path, lambda: omni.kit.commands.execute("CreatePrim", prim_path=scene_path, prim_type='SphereLight', attributes={'inputs:radius': radius, 'inputs:intensity': intensity}))

def create_custom_mesh(scene_path, face_vertex_indices=None, face_vertex_counts=None, points=None, sts=None):
    mesh = UsdGeom.Mesh.Define(get_stage(), scene_path)
    mesh.CreateSubdivisionSchemeAttr("none")
    if face_vertex_indices is not None:
        mesh.GetFaceVertexIndicesAttr().Set(face_vertex_indices)
    if face_vertex_counts is not None:
        mesh.GetFaceVertexCountsAttr().Set(face_vertex_counts)
    if points is not None:
        mesh.GetPointsAttr().Set(points)
    if sts is not None:
        sts_primvar = UsdGeom.PrimvarsAPI(mesh).CreatePrimvar("st", Sdf.ValueTypeNames.TexCoord2fArray)
        sts_primvar.SetInterpolation("faceVarying")
        sts_primvar.Set(sts)
    return mesh

def create_or_get_mesh_prim(type, scene_path):
    if not type in ['cone', 'cube', 'cylinder', 'disk', 'torus', 'plane', 'sphere', 'torus']:
        error(f'unkown geometry type: {type}')
    return create_or_get(scene_path, lambda: omni.kit.commands.execute("CreateMeshPrimWithDefaultXform", prim_type=type.capitalize(), prim_path=scene_path))

def ensure_shader(material_path, material_name):
    shader = UsdShade.Shader(get_stage().GetPrimAtPath(f'{material_path}/Shader'))
    def ensure_attribute(name, type):
        if not shader.GetInput(name):
            shader.CreateInput(name, type)
    attrs = {
        "diffuse_texture": Sdf.ValueTypeNames.Asset,
        "reflection_roughness_constant": Sdf.ValueTypeNames.Float,
        "diffuse_tint": Sdf.ValueTypeNames.Float3,
    }
    if material_name == 'OmniGlass':
        attrs["glass_color"] = Sdf.ValueTypeNames.Float3
    for _name, _type in attrs.items():
        ensure_attribute(_name, _type)
    shader.GetInput("reflection_roughness_constant").Set(1)
    return shader

def create_and_bind_material_shader(scene_path, _mtl_name, prim):
    omni.kit.commands.execute("CreateMdlMaterialPrim", mtl_url=f'{_mtl_name}.mdl', mtl_name=_mtl_name, mtl_path=scene_path)
    omni.kit.commands.execute("BindMaterial", material_path=scene_path, prim_path=[prim.GetPath()])
    return ensure_shader(scene_path, _mtl_name)

def set_shader_tiling(shader, scale_x, scale_y):
    if not shader.GetInput("texture_scale"):
        shader.CreateInput("texture_scale", Sdf.ValueTypeNames.Float2)
    shader.GetInput('texture_scale').Set(Gf.Vec2f(scale_x, scale_y))

def find_first_of_type(prim, type):
    if prim.GetTypeName() == type:
        return prim
    for child in prim.GetChildren():
        material = find_first_of_type(child, type)
        if material is not None:
            return material
    return None

## physics

def apply_collision_recursive(prim, approximation):
    if prim.GetTypeName() == 'Mesh':
        UsdPhysics.CollisionAPI.Apply(prim) # needs to apply on each single mesh for local bounding box query
        mesh_collision_api = UsdPhysics.MeshCollisionAPI.Apply(prim)
        mesh_collision_api.GetApproximationAttr().Set(approximation)
        #LOG(prim, prim.GetAttribute('physics:collisionEnabled').Get())
    for child in prim.GetChildren():
        apply_collision_recursive(child, approximation)

def set_physics_properties(prim, is_rigidbody=True, friction=0.15, linear_damping=0, angular_damping=0, is_concave=False):
    UsdPhysics.CollisionAPI.Apply(prim)

    if is_rigidbody:
        if is_concave:
            approximation = "convexDecomposition"
        else:
            approximation = "convexHull"
    else:
        approximation = "meshSimplification"

    apply_collision_recursive(prim, approximation)
    mesh_collision_api = UsdPhysics.MeshCollisionAPI.Apply(prim)
    mesh_collision_api.GetApproximationAttr().Set(approximation)

    if is_rigidbody:
        # basic physics properties
        physicsAPI = UsdPhysics.RigidBodyAPI.Apply(prim)
        #physicsAPI.CreateVelocityAttr().Set(Gf.Vec3f(0.0))
        #physicsAPI.CreateAngularVelocityAttr().Set(Gf.Vec3f(0.0))
        massApi = UsdPhysics.MassAPI.Apply(prim)
        #massApi.GetMassAttr().Set(10000)

        # physx properties
        physicsBodyAPI = PhysxSchema.PhysxRigidBodyAPI.Apply(prim)
        physicsBodyAPI.CreateLinearDampingAttr(linear_damping)
        physicsBodyAPI.CreateAngularDampingAttr(angular_damping) # TODO sep

        PhysxSchema.PhysxCollisionAPI.Apply(prim)

    # material
    material_prim = UsdShade.Material.Define(get_stage(), f"{prim.GetPath().pathString}_physicsMaterial").GetPrim()
    material = UsdPhysics.MaterialAPI.Apply(material_prim)
    material.CreateStaticFrictionAttr().Set(friction)
    material.CreateDynamicFrictionAttr().Set(friction)

    add_physics_material_to_prim(get_stage(), prim, material_prim.GetPath())

def reset_velocity(prim):
    physicsAPI = UsdPhysics.RigidBodyAPI.Apply(prim)
    physicsAPI.CreateVelocityAttr().Set(Gf.Vec3f(0.0))
    physicsAPI.CreateAngularVelocityAttr().Set(Gf.Vec3f(0.0))

from pxr import UsdUtils, PhysicsSchemaTools, UsdUtils
from omni.physx import get_physx_property_query_interface
from omni.physx.bindings._physx import PhysxPropertyQueryColliderResponse, PhysxPropertyQueryMode

"""async def get_prim_aabb(prim):
    aabb_local = [None, None]
    finished = [False]
    def _finish():
        finished[0] = True
    def report_collider(collider_info : PhysxPropertyQueryColliderResponse, aabb_local):
        _min, _max = collider_info.aabb_local_min, collider_info.aabb_local_max
        aabb_local[0], aabb_local[1] = _min, _max
    get_physx_property_query_interface().query_prim(
        UsdUtils.StageCache.Get().Insert(get_stage()).ToLongInt(),
        PhysicsSchemaTools.sdfPathToInt(prim.GetPath()),
        query_mode=PhysxPropertyQueryMode.QUERY_RIGID_BODY_WITH_COLLIDERS,
        collider_fn=lambda collider_info: report_collider(collider_info, aabb_local),
        finished_fn=_finish()
    )
    while not finished[0]:
        await wait_frames()
    LOG(aabb_local)
    return aabb_local"""

def get_bounds_trimesh(points):
    bounds = trimesh.PointCloud(points).bounds
    return Gf.BBox3d(Gf.Range3d(Gf.Vec3d(bounds[0][0], bounds[0][1], bounds[0][2]), Gf.Vec3d(bounds[1][0], bounds[1][1], bounds[1][2])))

def get_prim_aabb_trimesh_inner(prim, aabb_local):
    if prim.GetTypeName() == 'Mesh':
        points = prim.GetAttribute('points').Get()
        bbox3d = get_bounds_trimesh(points)
        aabb_local[0] = Gf.BBox3d.Combine(aabb_local[0], bbox3d)
    for child in prim.GetChildren():
        get_prim_aabb_trimesh_inner(child, aabb_local)

def get_prim_aabb_trimesh(prim):
    aabb_local = [Gf.BBox3d()]
    get_prim_aabb_trimesh_inner(prim, aabb_local)
    return (aabb_local[0].GetBox().GetMin(), aabb_local[0].GetBox().GetMax())

# will remove later
async def get_prim_aabb(prim):
    aabb_local = [Gf.BBox3d()]
    #default = aabb_local[0]
    LOG(prim, '---start', aabb_local[0].GetRange())
    finished = [False]

    def _merge_bbox3d(bbox3d):
        aabb_local[0] = Gf.BBox3d.Combine(aabb_local[0], bbox3d)
        LOG(prim, '------subbox', bbox3d.GetRange())

    def _finish():
        finished[0] = True
        LOG(prim, '------finished')

    def report_collider(collider_info : PhysxPropertyQueryColliderResponse):
        _min, _max = collider_info.aabb_local_min, collider_info.aabb_local_max
        LOG(_min, _max)
        _merge_bbox3d(Gf.BBox3d(Gf.Range3d(Gf.Vec3d(_min[0], _min[1], _min[2]), Gf.Vec3d(_max[0], _max[1], _max[2]))))

    await wait_frames()
    get_physx_property_query_interface().query_prim(
        UsdUtils.StageCache.Get().Insert(get_stage()).ToLongInt(),
        PhysicsSchemaTools.sdfPathToInt(prim.GetPath()),
        query_mode=PhysxPropertyQueryMode.QUERY_RIGID_BODY_WITH_COLLIDERS,
        collider_fn=lambda collider_info: report_collider(collider_info),
        finished_fn=_finish
    )
    LOG(prim, 'final box', aabb_local[0], aabb_local[0].GetBox().GetMax() - aabb_local[0].GetBox().GetMin())
    """cnt = 0
    while not finished[0]:
        LOG(f'f{cnt}')
        cnt += 1
        await wait_frames()"""
    #while aabb_local[0] == default:
    #    LOG(f'awaiting bbox for {prim}')
    #    await wait_frames()
    while not finished[0]:
       await wait_frames()
    #await wait_frames(2)
    #LOG(f'---end')
    return (aabb_local[0].GetBox().GetMin(), aabb_local[0].GetBox().GetMax())

## timeline

def timeline_play():
    omni.timeline.get_timeline_interface().play()

def timeline_pause():
    omni.timeline.get_timeline_interface().pause()

def timeline_stop():
    omni.timeline.get_timeline_interface().stop()
