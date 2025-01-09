import ast
import math
import sys
import re
def error(msg): raise Exception(msg)

from typing import Iterable

def get_math_attrs():
    ret = set()
    for attr in dir(math):
        if not attr.startswith('_'):
            ret.add(attr)
    return ret

def get_builtin_names():
    disallowed_builtin_names = [
        "Error", "Warning", "Exception", "open", "quit", "exit", "exec", "print", "input",
        "delattr", "getattr", "setattr", "Interrupt", "SystemExit", "breakpoint", "eval"
    ]
    builtin_names = set()
    if not isinstance(__builtins__, dict):
        builtin = __builtins__.__dict__
    else:
        builtin = __builtins__

    for name, cls in builtin.items():
        if not name.startswith('_') and not any(sub in name for sub in disallowed_builtin_names):
            if callable(cls):
                builtin_names.add(name)
    return builtin_names


disallowed_arith_ops = ()
other_allowed_ops = (
    ast.Expression,
    ast.Load, ast.Call, ast.Compare, ast.IfExp,
    ast.BinOp, ast.UnaryOp, ast.BoolOp,
    ast.unaryop, ast.boolop, ast.operator, ast.cmpop,
    ast.List, ast.Tuple,
    ast.Subscript, ast.Slice,
)

allowed_math_attrs = get_math_attrs()
allowed_builtin_names = get_builtin_names()
disallowed_consts = {}

def _is_mapping_item(obj):
    return isinstance(obj, tuple) and len(obj) == 2 and isinstance(obj[0], str)

def _is_iterable(obj):
    try:
        for _ in obj: break
        return True
    except:
        return False

def _flatten(nested_iterable):
    # everything should eventually resolve to a Tuple[str, Any]
    # else the iterable is ill-formed
    if _is_mapping_item(nested_iterable):
        yield nested_iterable
        return

    if isinstance(nested_iterable, dict):
        nested_iterable = nested_iterable.items()
    if _is_iterable(nested_iterable):
        for elem in nested_iterable:
            yield from _flatten(elem)
    # discard item

def safe_eval(expr : str, allowed_names : Iterable = []):
    """
    Eval a python expression with restrictions
    """
    allowed_names = dict(_flatten(allowed_names))

    # disallow callable variables
    for name, val in allowed_names.items():
        if callable(val):
            error(f"Disallowed variable: {name} of type {type(val).__name__}")

    node = ast.parse(expr, mode = 'eval')
    def walk(node):
        if isinstance(node, (ast.BinOp, ast.UnaryOp, ast.BoolOp)):
            if type(node.op) in disallowed_arith_ops:
                error(f"Disallowed operation : {type(node.op).__name__}")
        elif isinstance(node, ast.Attribute):
            # only allow math.*
            is_math_module = isinstance(node.value, ast.Name) and node.value.id == 'math'
            if not is_math_module or node.attr not in allowed_math_attrs:
                error(f"Disallowed attribute : {node.value.id}.{node.attr}")
            return
        elif isinstance(node, ast.Name):
            if node.id not in allowed_names and node.id not in allowed_builtin_names:
                error(f"Disallowed name : {node.id}")
        elif isinstance(node, (ast.Constant)):
            if node.value in disallowed_consts:
                error(f"Disallowed constant: {node.value}")
            return
        elif isinstance(node, other_allowed_ops):
            pass
        else:
            error(f"Disallowed expression: {type(node).__name__}")

        for subnode in ast.iter_child_nodes(node):
            walk(subnode)
    walk(node)
    return eval(compile(source=node, filename="<string>", mode="eval"),
                None,
                allowed_names)

def eval_expression(expression):
    try:
        return safe_eval(expression)
    except Exception as err:
        text = 'Disallowed name : '
        err_text = str(err)
        if err_text.find(text) != -1:
            return err_text[len(text):]
        elif err_text.find('invalid syntax') != -1:
            return expression
        else:
            error(err_text)