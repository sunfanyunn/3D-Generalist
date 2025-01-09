from pxr import UsdGeom, Gf, Usd
import logging
from .misc import error, LOG
from .maths import *

_precisions = {
    'orient': UsdGeom.XformOp.PrecisionFloat,
    'scale': UsdGeom.XformOp.PrecisionHalf
}

def resolve_precision(op_key):
    if op_key in _precisions:
        return _precisions[op_key]
    else:
        return UsdGeom.XformOp.PrecisionDouble

def resolve_gfvec3(v, precision):
    if precision == UsdGeom.XformOp.PrecisionDouble:
        return Gf.Vec3d(*v)
    elif precision == UsdGeom.XformOp.PrecisionFloat:
        return Gf.Vec3f(*v)
    elif precision == UsdGeom.XformOp.PrecisionHalf:
        return Gf.Vec3h(*v)
    else:
        error("unrecognized precision type")

def create_xform_op(prim, op_key, suffix, op_func):
    attr_name = 'xformOp:' + op_key
    if suffix:
        attr_name += ':' + suffix
    else:
        suffix = ''
    op = prim.GetAttribute(attr_name)
    if not op or not op.HasValue():
        precision = resolve_precision(op_key)
        if op and op_key in ['translate', 'rotateXYZ', 'rotateXZY', 'rotateYXZ', 'rotateYZX', 'rotateZXY', 'rotateZYX', 'scale']: # override if precision exists; precision can't change after creating the xformOp, default precisions are too volatile across different versions
            precision = UsdGeom.XformOp(op).GetPrecision()
        op = op_func(opSuffix=suffix, precision=precision)

        # initialize value to unblock the attribute
        if op_key in ['translate', 'rotateXYZ', 'rotateXZY', 'rotateYXZ', 'rotateYZX', 'rotateZXY', 'rotateZYX']:
            op.Set(resolve_gfvec3((0, 0, 0), precision))
        elif op_key == 'orient':
            op.Set(Gf.Quatf(1, 0, 0, 0))
        elif op_key == 'scale':
            op.Set(resolve_gfvec3((1, 1, 1), precision))
        elif op_key == 'transform':
            op.Set(Gf.Matrix4d(1))
        elif op_key in ['rotateX', 'rotateY', 'rotateZ']:
            op.Set(0)
        else:
            error(f'unknown operator: {op_key}')
    return op

def get_xform_op(prim, name):
    op = prim.GetAttribute('xformOp:' + name)
    if not op or not op.HasValue():
        error(f'non-existent or blocked operator: {name}')
    return op

def log_ops(prim):
    logging.warn(UsdGeom.Xform(prim).GetXformOpOrderAttr().Get())

def clear_ops(prim):
    # clearing will not delete the attributes, but you can call AddXOp on a cleared op. we block before clearing, and check whether it HasValue() before creating.
    # also if you play with the UI, the ops will HasValue() again, without being in the order. we have to block all attributes starting with xformOp.
    for attr in prim.GetAttributes():
        if "xformOp:" in attr.GetName():
            attr.Block()
    UsdGeom.Xform(prim).ClearXformOpOrder()

def ensure_scalar(s):
    if not isinstance(s, (int, float)):
        error(f'expected scalar, got {s}')

def ensure_vector(v, size=3):
    if not isinstance(v, (list, tuple)) or not len(v) == size:
        error(f'expected vector with dimension {size}, got {v}')
    for item in v:
        ensure_scalar(item)

def ensure_matrix(m, size=4):
    if not isinstance(m, (list, tuple)) or not len(m) == size:
        error(f'expected matrix with row count {size}, got {m}')
    for row in m:
        ensure_vector(row, size)

def set_xform_ops(prim, ops):
    clear_ops(prim)
    used_keys = []
    for op in ops:
        # op: (op_func, value)
        name = op[0]
        suffix = None
        if name in used_keys:
            error(f"duplicate op: {op}")
        used_keys.append(name)
        if name.count(':') > 1:
            error(f"at most 1 colon in op: {op}")
        elif name.count(':') == 1:
            name, suffix = name.split(":")
        if not name in ['translate', 'rotateX', 'rotateY', 'rotateZ', 'rotateXYZ', 'rotateXZY', 'rotateYXZ', 'rotateYZX', 'rotateZXY', 'rotateZYX', 'orient', 'scale', 'transform']:
            error(f"not supported operator: {name}")
        operator = create_xform_op(prim, name, suffix, eval(f'UsdGeom.Xform(prim).Add{name[0].upper()+name[1:]}Op'))

        value = op[1]
        if value:
            if name in ['translate', 'rotateXYZ', 'rotateXZY', 'rotateYXZ', 'rotateYZX', 'rotateZXY', 'rotateZYX']:
                ensure_vector(value, 3)
                operator.Set(Gf.Vec3d(*value))
            elif name == 'orient':
                ensure_vector(value, 4)
                operator.Set(Gf.Quatf(*value))
            elif name == 'scale':
                ensure_vector(value, 3)
                operator.Set(resolve_gfvec3(value, operator.GetPrecision()))
            elif name == 'transform':
                ensure_matrix(value, 4)
                operator.Set(Gf.Matrix4d(value))
            elif name in ['rotateX', 'rotateY', 'rotateZ']:
                ensure_scalar(value)
                operator.Set(value)

def get_total_xform(prim):
    total_xform = Gf.Matrix4d(1)
    for name in UsdGeom.Xform(prim).GetXformOpOrderAttr().Get():
        total_xform = UsdGeom.XformOp(prim.GetAttribute(name)).GetOpTransform(Usd.TimeCode.Default()) * total_xform
    return total_xform


# mainly for the camera, which will have problems if it's not translate-rotateXYZ/rotateYXZ-scale order, compatibility with different Kit versions

def set_xlate_xyz_from_prim_xform(target_prim, source_prim):
    xform = get_total_xform(source_prim)
    xlate, xyz = get_xlate_and_xyz_from_xform(xform)
    get_xform_op(target_prim, 'translate').Set(xlate)
    get_xform_op(target_prim, 'rotateXYZ').Set(xyz)

def set_xlate_yxz_from_prim_xform(target_prim, source_prim):
    xform = get_total_xform(source_prim)
    xlate, yxz = get_xlate_and_yxz_from_xform(xform)
    get_xform_op(target_prim, 'translate').Set(xlate)
    get_xform_op(target_prim, 'rotateYXZ').Set(yxz)

def show_ops(prim, i=0):
    LOG()
    LOG(UsdGeom.Xform(prim).GetXformOpOrderAttr().Get())
    for attr in prim.GetAttributes():
        if "xformOp:" in attr.GetName():
            LOG([attr.GetName(), attr.Get()])
    LOG(f'{prim.GetPath()}, ---{str(i)}----')