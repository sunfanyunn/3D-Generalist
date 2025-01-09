import random, math
import numpy as np
from pxr import Gf

def lerp(a, b, t):
    return a + (b - a) * t

# randomize

def rand_range(a, b):
    return a + (b - a) * random.random()

def rand_range_list(a, b):
    assert len(a) == len(b) # keeping it here, there is another check that throws error when calling
    return [rand_range(a[i], b[i]) for i in range(len(a))]

def random_reciprocal(a, b):
    return a * b / (a + (b - a) * random.random())

def rand_quatd():
    return Gf.Quatd(rand_range(-1, 1), Gf.Vec3d(rand_range(-1, 1), rand_range(-1, 1), rand_range(-1, 1))).GetNormalized()

def rand_quatf():
    return Gf.Quatf(rand_range(-1, 1), Gf.Vec3f(rand_range(-1, 1), rand_range(-1, 1), rand_range(-1, 1))).GetNormalized()

# rotation

def get_trig(deg):
    return math.cos(math.radians(deg)), math.sin(math.radians(deg))

def rot_x(deg):
    c, s = get_trig(deg)
    return Gf.Matrix3d(1, 0, 0, 0, c, s, 0, -s, c)

def rot_y(deg):
    c, s = get_trig(deg)
    return Gf.Matrix3d(c, 0, -s, 0, 1, 0, s, 0, c)

def rot_z(deg):
    c, s = get_trig(deg)
    return Gf.Matrix3d(c, s, 0, -s, c, 0, 0, 0, 1)

def rot_x_np(deg):
    c, s = get_trig(deg)
    return np.array([[1, 0, 0], [0, c, s], [0, -s, c]])

def rot_y_np(deg):
    c, s = get_trig(deg)
    return np.array([[c, 0, -s], [0, 1, 0], [s, 0, c]])

def rot_z_np(deg):
    c, s = get_trig(deg)
    return np.array([[c, s, 0], [-s, c, 0], [0, 0, 1]])

def quat_to_mat3(q):
    w = q.GetReal()
    x = q.GetImaginary()[0]
    y = q.GetImaginary()[1]
    z = q.GetImaginary()[2]

    sqw = w * w
    sqx = x * x
    sqy = y * y
    sqz = z * z

    invs = 1 / (sqx + sqy + sqz + sqw)
    m00 = ( sqx - sqy - sqz + sqw) * invs
    m11 = (-sqx + sqy - sqz + sqw) * invs
    m22 = (-sqx - sqy + sqz + sqw) * invs

    tmp1 = x * y
    tmp2 = z * w
    m10 = 2.0 * (tmp1 + tmp2) * invs
    m01 = 2.0 * (tmp1 - tmp2) * invs

    tmp1 = x * z
    tmp2 = y * w
    m20 = 2.0 * (tmp1 - tmp2) * invs
    m02 = 2.0 * (tmp1 + tmp2) * invs
    tmp1 = y * z
    tmp2 = x * w
    m21 = 2.0 * (tmp1 + tmp2) * invs
    m12 = 2.0 * (tmp1 - tmp2) * invs
    m = Gf.Matrix3d(m00, m01, m02, m10, m11, m12, m20, m21, m22)
    return m.GetTranspose()

def xyz_from_mat3(_r):
    r = _r.GetTranspose()
    if r[2][0] != -1 and r[2][0] != 1:
        theta = -math.asin(r[2][0])
        psi = math.atan2(r[2][1], r[2][2])
        phi = math.atan2(r[1][0], r[0][0])
    else:
        phi = 0
        if r[2][0] == -1:
            theta = math.pi / 2
            psi = phi + math.atan2(r[0][1], r[0][2])
        else:
            theta = -math.pi / 2
            psi = -phi + math.atan2(-r[0][1], -r[0][2])
    return Gf.Vec3d(math.degrees(psi), math.degrees(theta), math.degrees(phi))

def yxz_from_mat3(r):
    if r[1][2] != -1 and r[1][2] != 1:
        x = math.asin(r[1][2])
        y = math.atan2(-r[0][2], r[2][2])
        z = math.atan2(-r[1][0], r[1][1])
    else:
        z = 0
        if r[1][2] == -1:
            x = -math.pi / 2
            y = math.atan2(-r[0][1], r[2][1])
            z = 0 #
        else:
            x = math.pi / 2
            y = 0 #
            z = math.atan2(r[0][1], -r[2][1])
    return Gf.Vec3d(math.degrees(x), math.degrees(y), math.degrees(z))

def get_xlate_and_xyz_from_xform(xform):
    xlate = xform.ExtractTranslation()
    rotation = xform.ExtractRotation()
    mat3 = quat_to_mat3(rotation.GetQuat())
    xyz = xyz_from_mat3(mat3)
    return xlate, xyz

def get_xlate_and_yxz_from_xform(xform):
    xlate = xform.ExtractTranslation()
    rotation = xform.ExtractRotation()
    mat3 = quat_to_mat3(rotation.GetQuat())
    yxz = yxz_from_mat3(mat3)
    return xlate, yxz