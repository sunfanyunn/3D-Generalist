import warp as wp
import math
from pxr import Vt, Gf

@wp.func
def get_control_point_wp(control_points: wp.array(dtype=wp.vec3), i: int, j: int, dim_x: int):
    # ring
    if i >= dim_x:
        i = i % dim_x + 1
    return control_points[j * dim_x + i]


@wp.func
def get_catmull_rom_param_wp(u: float, i: int):
    if i == 0:
        return (-u + 2.0 * u * u - u * u * u) / 2.0
    elif i == 1:
        return (2.0 - 5.0 * u * u + 3.0 * u * u * u) / 2.0
    elif i == 2:
        return (u + 4.0 * u * u - 3.0 * u * u * u) / 2.0
    elif i == 3:
        return (-u * u + u * u * u) / 2.0
    else:
        return 0.0


@wp.kernel
def get_mesh_points_wp(
    mesh_points: wp.array(dtype=wp.vec3),
    sub_control_points: wp.array(dtype=wp.vec3),
    subdivision: int,
    dim_x: int,
    dim_y: int,
    num_sector: int,
):
    j, i = wp.tid()

    frame_i = i // subdivision
    u = float(i % subdivision) / float(subdivision)
    frame_j = j // subdivision
    v = float(j % subdivision) / float(subdivision)

    vertex_row_size = (dim_x - 1) * subdivision + 1
    vertex_col_size = (dim_y - 3) * subdivision + 1

    # if > 0, it's for the label; otherwise it's for the body.
    if num_sector > 0:
        vertex_row_size = num_sector * subdivision + 1
        vertex_col_size = subdivision + 1

    if i == vertex_row_size - 1:
        u = 1.0
        frame_i -= 1
    if j == vertex_col_size - 1:
        v = 1.0
        frame_j -= 1

    sum = wp.vec3(0.0, 0.0, 0.0)
    patch_dim_x = dim_x
    if num_sector > 0:
        patch_dim_x = num_sector + 3
    for _j in range(4):
        row = wp.vec3(0.0, 0.0, 0.0)
        for _i in range(4):
            row += get_control_point_wp(
                sub_control_points, frame_i + _i, frame_j + _j, patch_dim_x
            ) * get_catmull_rom_param_wp(u, _i)
        sum += row * get_catmull_rom_param_wp(v, _j)
    mesh_points[j * vertex_row_size + i] = sum


class Bottle:
    def __init__(self):
        # sub control point init params
        self.dim_x, self.dim_y = 7, 11

        # mesh update params
        self.subdivision = 100
        self.body_vertex_row_size = (self.dim_x - 1) * self.subdivision + 1
        self.body_vertex_col_size = (self.dim_y - 3) * self.subdivision + 1
        ## label_vertex_row_size will be determined per update
        self.label_vertex_col_size = self.subdivision + 1

        # usd data
        self.body_face_vertex_indices = self.get_face_vertex_indices(self.body_vertex_row_size, self.body_vertex_col_size)
        self.body_face_vertex_counts = self.get_face_vertex_counts(self.body_vertex_row_size, self.body_vertex_col_size)
        self.body_vertex_sts = self.get_st(self.body_vertex_row_size, self.body_vertex_col_size)

    def get_sub_control_points(self):
        self.sub_control_points = []
        for j in range(self.dim_y):
            _x = self.control_points[j]
            radius = math.sqrt(_x[0] * _x[0] + _x[2] * _x[2])
            for i in range(self.dim_x):
                x = i % self.dim_x
                angle = x * 2 * math.pi / (self.dim_x - 1)
                self.sub_control_points.append((radius * math.sin(angle), _x[1], radius * math.cos(angle)))

    def get_label_sub_control_points(self, num_sector):
        self.label_sub_control_points = []
        for j in range(2, 6):
            for i in range(num_sector + 3):
                self.label_sub_control_points.append(self.sub_control_points[j * self.dim_x + i])

    def get_label_size_ratio(self, num_sector):
        control_point_bottom = self.control_points[3]
        control_point_top = self.control_points[4]
        def get_radius(xlate):
            return math.sqrt(xlate[0] * xlate[0] + xlate[2] * xlate[2])
        radius = get_radius(control_point_bottom)
        width = num_sector / (self.dim_x - 1) * 2 * math.pi * radius
        height = (Gf.Vec3f(control_point_top) - Gf.Vec3f(control_point_bottom)).GetLength()
        return width / height

    @classmethod
    def get_face_vertex_indices(cls, row_size, col_size):
        indices = []
        for i in range(col_size * row_size):
            x, y = i % row_size, i // row_size
            if x != row_size - 1 and y != col_size - 1:
                indices += [i, i + 1, i + 1 + row_size, i + row_size]
        return indices

    @classmethod
    def get_face_vertex_counts(cls, row_size, col_size):
        return [4 for i in range((row_size - 1) * (col_size - 1))]

    @classmethod
    def get_st(cls, row_size, col_size):
        st = []
        for j in range(col_size - 1):
            for i in range(row_size - 1):
                st += [
                    (i / (row_size - 1), j / (col_size - 1)),
                    ((i + 1) / (row_size - 1), j / (col_size - 1)),
                    ((i + 1) / (row_size - 1), (j + 1) / (col_size - 1)),
                    (i / (row_size - 1), (j + 1) / (col_size - 1)),
                ]
        return st

    def get_mesh_points(self, sub_control_points, vertex_row_size, vertex_col_size, num_sector):
        mesh_points_wp = wp.empty(shape=vertex_row_size * vertex_col_size, dtype=wp.vec3, device="cuda")
        subs_control_points_wp = wp.from_numpy(sub_control_points, dtype=wp.vec3, device="cuda")
        wp.launch(
            kernel=get_mesh_points_wp,
            dim=(vertex_col_size, vertex_row_size),
            inputs=[mesh_points_wp, subs_control_points_wp, self.subdivision, self.dim_x, self.dim_y, num_sector],
            device="cuda",
        )
        return Vt.Vec3fArray.FromNumpy(mesh_points_wp.numpy())

    def update(self, control_points, num_sector):
        self.control_points = control_points

        self.get_sub_control_points()
        self.get_label_sub_control_points(num_sector)

        # body
        self.body_mesh_points = self.get_mesh_points(
            self.sub_control_points, self.body_vertex_row_size, self.body_vertex_col_size, 0
        )

        # label
        self.label_vertex_row_size = num_sector * self.subdivision + 1
        self.label_mesh_points = self.get_mesh_points(
            self.label_sub_control_points, self.label_vertex_row_size, self.label_vertex_col_size, num_sector
        )
        ## jiggle
        self.label_mesh_points = [(point[0] * 1.01, point[1], point[2] * 1.01) for point in self.label_mesh_points]

        self.label_size_ratio = self.get_label_size_ratio(num_sector)

    def get_label_face_vertex_indices(self):
        return self.get_face_vertex_indices(self.label_vertex_row_size, self.label_vertex_col_size)

    def get_label_face_vertex_counts(self):
        return self.get_face_vertex_counts(self.label_vertex_row_size, self.label_vertex_col_size)

    def get_label_sts(self):
        return self.get_st(self.label_vertex_row_size, self.label_vertex_col_size)
