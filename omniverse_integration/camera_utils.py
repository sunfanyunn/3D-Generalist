import mathutils
import random
import math


def is_valid_pose(camera_location, target_location, walls):
    # Check if the camera's view towards the target intersects any walls
    direction = (target_location - camera_location).normalized()

    for wall in walls:
        # Define the wall as a plane
        wall_normal = mathutils.geometry.normal(wall[0], wall[1], wall[2])
        point_on_plane = wall[0]
        
        # Ray-plane intersection
        ray_direction = direction
        ray_origin = camera_location
        
        denom = wall_normal.dot(ray_direction)
        if abs(denom) > 1e-6:  # Not parallel
            t = (point_on_plane - ray_origin).dot(wall_normal) / denom
            if t >= 0 and t < (target_location - camera_location).length:  # NOTE: wall is blocking sight 
                intersection_point = ray_origin + ray_direction * t
                if is_point_in_polygon(intersection_point, wall):
                    return False
    return True

def is_point_in_polygon(point, polygon):
    # A simple point-in-polygon test for convex polygons
    for i in range(len(polygon)):
        edge = polygon[(i + 1) % len(polygon)] - polygon[i]
        vp = point - polygon[i]
        if mathutils.Vector.cross(edge, vp).dot(mathutils.geometry.normal(*polygon)) < 0:
            return False
    return True


def sample_camera_pose(radius, target_location):
    # Sample a random point on the upper hemisphere
    theta = random.uniform(0, 2 * math.pi)
    phi = random.uniform(0, math.pi / 2)

    x = radius * math.sin(phi) * math.cos(theta)
    y = radius * math.sin(phi) * math.sin(theta)
    z = radius * math.cos(phi)

    camera_location = mathutils.Vector((x, y, z)) + target_location
    return camera_location

def xyz_from_mat3(_r):
    r = _r.transposed()
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
    return mathutils.Vector((math.degrees(psi), math.degrees(theta), math.degrees(phi)))

mat_z_to_y = mathutils.Matrix()
mat_z_to_y[0][0:3] = 0, 0, 1
mat_z_to_y[1][0:3] = 1, 0, 0
mat_z_to_y[2][0:3] = 0, 1, 0
    
def get_valid_camera_poses(N, radius, target_location, walls):
    valid_poses = []
    while len(valid_poses) < N:
        camera_location = sample_camera_pose(radius, target_location)


        if is_valid_pose(camera_location, target_location, walls):
            up = mathutils.Vector((0, 1, 0)) # Y
            back = (camera_location @ mat_z_to_y.to_3x3() - target_location @ mat_z_to_y.to_3x3()).normalized() # Z
            right = mathutils.Vector.cross(up, back).normalized() # X
            mat = mathutils.Matrix()
            mat[2][0:3] = back
            mat[0][0:3] = right
            mat[1][0:3] = mathutils.Vector.cross(back, right)

            euler = xyz_from_mat3(mat.to_3x3())
            valid_poses.append((camera_location @ mat_z_to_y.to_3x3(), euler))
    
    return valid_poses