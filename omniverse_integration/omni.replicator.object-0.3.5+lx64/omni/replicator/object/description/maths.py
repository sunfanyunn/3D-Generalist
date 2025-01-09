import random, math
import numpy as np

# randomize

def rand_range(a, b):
    return a + (b - a) * random.random()

def rand_range_list(a, b):
    assert len(a) == len(b) # keeping it here, there is another check that throws error when calling
    return [rand_range(a[i], b[i]) for i in range(len(a))]

def random_reciprocal(a, b):
    return a * b / (a + (b - a) * random.random())

# rotation

def get_trig(deg):
    return math.cos(math.radians(deg)), math.sin(math.radians(deg))

def rot_x_np(deg):
    c, s = get_trig(deg)
    return np.array([[1, 0, 0], [0, c, s], [0, -s, c]])

def rot_y_np(deg):
    c, s = get_trig(deg)
    return np.array([[c, 0, -s], [0, 1, 0], [s, 0, c]])

def rot_z_np(deg):
    c, s = get_trig(deg)
    return np.array([[c, s, 0], [-s, c, 0], [0, 0, 1]])

# seed

import hashlib
def attribute_seed(name, global_seed, user_seed=None):
    seed = int(hashlib.md5(name.encode('utf-8')).hexdigest(), 16)
    if user_seed is None:
        seed += global_seed
    else:
        seed += user_seed
    random.seed(seed)