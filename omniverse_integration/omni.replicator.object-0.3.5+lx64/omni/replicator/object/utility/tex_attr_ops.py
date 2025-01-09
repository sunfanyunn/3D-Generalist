import cv2
import random
import numpy as np

"""
functions starting with tex_op__{name} represents a texture operation,
which will be automatically collected and linked to operation:{name} specified in
the texture mutable attribute
"""

def tex_op__color_map(image):
    map = random.choice([cv2.COLORMAP_JET, cv2.COLORMAP_OCEAN, cv2.COLORMAP_SUMMER, cv2.COLORMAP_PINK])
    return cv2.applyColorMap(image, map)

def tex_op__transform(image):
    h, w = image.shape[:2]
    angle = np.random.uniform(-180, 180)
    scale = np.random.uniform(1, 4)
    R = cv2.getRotationMatrix2D((w / 2, h / 2), angle, scale)
    return cv2.warpAffine(image, R, (w, h))

def tex_op__add_noise(image):
    output = np.zeros(image.shape,np.uint8)
    for i in range(image.shape[0]):
        for j in range(image.shape[1]):
            rdn = random.random()
            if rdn <= 0.2:
                output[i][j] = 0
            elif rdn > 0.2 and rdn <= 0.4:
                output[i][j] = 255
            else:
                output[i][j] = image[i][j]
    return output

def tex_op__apply_blur(image):
    k_size = random.randrange(50, 100)
    if k_size % 2 == 0:
        k_size += 1
    return cv2.GaussianBlur(image, (k_size, k_size), 0)

def tex_op__color_shift(image):
    B, G, R = cv2.split(image)
    B = cv2.add(B, random.randint(-50, 50))
    G = cv2.add(G, random.randint(-50, 50))
    R = cv2.add(R, random.randint(-50, 50))
    return cv2.merge([B, G, R])

def tex_op__invert_color(image):
    return 255 - image

def tex_op__sobel_edges(image):
    gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    sobel_x = cv2.Sobel(gray_image, cv2.CV_64F, 1, 0, ksize=5)
    sobel_y = cv2.Sobel(gray_image, cv2.CV_64F, 0, 1, ksize=5)
    return cv2.bitwise_or(cv2.convertScaleAbs(sobel_x), cv2.convertScaleAbs(sobel_y))

def tex_op__random_mutation(image):
    keys = list(tex_mut_attr_operation.keys())
    key = random.choice(keys)
    while key == 'random_mutation':
        key = random.choice(keys)
    return tex_mut_attr_operation[key](image)

def create_dir():
    ret = {}
    for name, obj in globals().items():
        if callable(obj) and name.startswith("tex_op__"):
            ret[name[len("tex_op__"):]] = obj
    return ret

tex_mut_attr_operation = create_dir()
