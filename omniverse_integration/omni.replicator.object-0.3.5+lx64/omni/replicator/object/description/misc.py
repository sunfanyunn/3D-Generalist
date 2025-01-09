import logging, os, sys, contextlib, yaml, json, re, traceback, copy, regex

# exception utilities

VERSION = '0.3.5'
EXTENSION_NAME = f'[METROPERF][omni.replicator.object:{VERSION}]'
SEMANTIC_CLASS_STRING = 'oro'

def error(msg):
    raise Exception(f"{msg}")

@contextlib.contextmanager
def CHECK(desc, log=False):
    try:
        yield None
        if desc:
            logging.info(f'{EXTENSION_NAME} {desc} - SUCCESS')

    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        if log:
            logging.error(f"[{EXTENSION_NAME}] {desc} - FAILURE: {traceback.format_exc()}")
        error(f"{desc}, {e}")

def ensure_type(key, _dict, expected_type):
    if not isinstance(_dict[key], expected_type):
        error(f'{key} is expected to have type {expected_type} but got {type(_dict[key])}')

# make sure key exists, return retrieved value
def ensured_retrieve(key, _dict, expected_type=None):
    if key not in _dict:
        error(f'"{key}" expected but not found')
    if expected_type is not None:
        ensure_type(key, _dict, expected_type)
    return _dict[key]

def ensured_retrieve_dict(key, _dict, typed_keys):
    sub_dict = ensured_retrieve(key, _dict, dict)
    for typed_key in typed_keys:
        ensured_retrieve(typed_key, sub_dict, typed_keys[typed_key])
    return sub_dict

# return retrieved value if key exists, otherwise return default
def tentative_retrieve(key, _dict, expected_type=None, default=None):
    if key not in _dict:
        return default
    if expected_type is not None:
        ensure_type(key, _dict, expected_type)
    return _dict[key]

# yaml

def read_yaml(yaml_path):
    with open(yaml_path) as yaml_file:
        data = yaml.safe_load(yaml_file)
        return data

def write_yaml(data, yaml_path):
    with open(yaml_path, 'w') as yaml_file:
        yaml.dump(data, yaml_file)

# folder

def ensure_folder(path):
    if not os.path.isdir(path):
        os.mkdir(path)

def ensure_folder_recursive(path):
    child_stack = []
    while path != '/' and path != '' and not os.path.isdir(path):
        child_stack.append(os.path.basename(path))
        path = os.path.dirname(path)
    while child_stack:
        path = os.path.join(path, child_stack.pop())
        ensure_folder(path)

def get_relative_paths_of_suffix(root_folder, suffix, is_full_path=False):
    relative_paths = []
    for (root, dirs, files) in os.walk(root_folder, topdown=False):
        for file in files:
            if file.endswith(suffix):
                full_path = os.path.join(root, file)
                if is_full_path:
                    relative_paths.append(full_path)
                else:
                    relative_paths.append(os.path.relpath(full_path, root_folder))
    return relative_paths
