import warp as wp
import math, random
from pxr import Vt, Gf
from ..utility.scene import create_custom_mesh, create_and_bind_material_shader, create_xform_prim

###
@wp.func
def lerp(a: float, b: float, t: float):
    return a + (b - a) * t

@wp.func
def fbm_1d(
    kernel_seed: int,
    x_i: float,
):
    state = wp.rand_init(kernel_seed)
    frequency = 5.0 #.3
    amplitude = 1.0
    output_i = 0.0
    for _ in range(16):
        p = frequency * x_i
        output_i += amplitude * wp.pnoise(state, 1.0 / 2.0 / 3.14159 * p / 5.0, 1)
        #output_i += amplitude * wp.pnoise(state, p, 1)
        frequency *= 2.0
        amplitude *= 0.5
    return output_i

@wp.kernel
def get_mesh_points_wp_pad(
    mesh_points: wp.array(dtype=wp.vec3),
    num_theta_sector: int,
    num_phi_sector: int,
    R: float,
    r: float,
    seed: int
):
    j, i = wp.tid()
    pi = 3.14159
    phi = 2.0 * pi / float(num_phi_sector - 1) * float(i)
    theta = 2.0 * pi / float(num_theta_sector - 1) * float(j)
    ff = fbm_1d(seed, theta) * 4.0 #1.5
    _r = r * (1.0 + ff)
    x = R + _r * warp.cos(phi)
    mesh_points[j * num_phi_sector + i] = wp.vec3(x * warp.cos(theta), r * warp.sin(phi), -x * warp.sin(theta))

class Pad:

    def __init__(self, path, seed, R, r):
        self.R = R
        self.r = r
        self.num_phi_sector = 100
        self.num_theta_sector = 1000
        self.seed = seed

        self.mesh = create_custom_mesh(path)
        self.shader = create_and_bind_material_shader(
                f"{self.mesh.GetPath().pathString}/Material", "OmniGlass", self.mesh
            )

    def get_mesh_points(self):
        mesh_points_wp = wp.empty(shape=self.num_phi_sector * self.num_theta_sector, dtype=wp.vec3, device="cuda")
        wp.launch(
            kernel=get_mesh_points_wp_pad,
            dim=(self.num_theta_sector, self.num_phi_sector),
            inputs=[mesh_points_wp, self.num_theta_sector, self.num_phi_sector, self.R, self.r, self.seed],
            device="cuda",
        )
        return Vt.Vec3fArray.FromNumpy(mesh_points_wp.numpy())

    def get_face_vertex_indices(self):
        row_size, col_size = self.num_phi_sector, self.num_theta_sector
        indices = []
        for i in range(col_size * row_size):
            x, y = i % row_size, i // row_size
            if x != row_size - 1 and y != col_size - 1:
                indices += [i, i + 1, i + 1 + row_size, i + row_size]
        return indices

    def get_face_vertex_counts(self):
        row_size, col_size = self.num_phi_sector, self.num_theta_sector
        return [4 for i in range((row_size - 1) * (col_size - 1))]

    def generate_mesh(self):
        self.mesh.GetPointsAttr().Set(self.get_mesh_points())
        self.mesh.GetFaceVertexIndicesAttr().Set(self.get_face_vertex_indices())
        self.mesh.GetFaceVertexCountsAttr().Set(self.get_face_vertex_counts())
        self.shader.GetInput('glass_color').Set(Gf.Vec3f(random.random(), random.random(), random.random()))

class SolderPoint:
    def __init__(self, scene_path):
        self.scene_path = scene_path
        self.prim = create_xform_prim(scene_path)
        pad1 = Pad(f"{scene_path}/pad1", random.randint(0, 1000), 90, 30)
        pad2 = Pad(f"{scene_path}/pad2", random.randint(0, 1000), 75, 30)
        pad3 = Pad(f"{scene_path}/pad3", random.randint(0, 1000), 50, 10)
        pad4 = Pad(f"{scene_path}/pad4", random.randint(0, 1000), 20, 30)
        self.pads = [pad1, pad2, pad3, pad4]

    def randomize(self):
        pad1 = Pad(f"{self.scene_path}/pad1", random.randint(0, 1000), 90, 30)
        pad2 = Pad(f"{self.scene_path}/pad2", random.randint(0, 1000), 75, 30)
        pad3 = Pad(f"{self.scene_path}/pad3", random.randint(0, 1000), 50, 10)
        pad4 = Pad(f"{self.scene_path}/pad4", random.randint(0, 1000), 20, 30)
        self.pads = [pad1, pad2, pad3, pad4]
        for pad in self.pads:
            pad.generate_mesh()