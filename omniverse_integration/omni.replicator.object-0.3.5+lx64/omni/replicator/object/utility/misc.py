import logging, os, sys, contextlib, yaml, json, re, traceback, copy, carb

# exception utilities


VERSION = '0.3.5'
EXTENSION_NAME = f'[METROPERF][omni.replicator.object:{VERSION}]'
SEMANTIC_CLASS_STRING = 'oro'

def error(msg):
    #raise Exception(f"{EXTENSION_NAME} {msg}")
    raise Exception(f"{msg}")

@contextlib.contextmanager
def CHECK(desc, log=False):
    try:
        yield None
        if desc:
            logging.info(f'{EXTENSION_NAME} {desc} - SUCCESS')

    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        #fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        #error_str = f'{e}, TYPE: {exc_type}, FILE NAME: {fname}, LINE #{exc_tb.tb_lineno}, STACK: {traceback.format_exc()}'
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

# indexed values

# def resolve_mapped_string(string, mapping):
#     for r in re.findall(r'\$\[.*?\]', string):
#         key = r.strip("$[]")
#         if not key in mapping:
#             error(f"xformOp value {string} has unrecognized mapping variable {key}")
#         if not isinstance(mapping[key], (int, float)):
#             error(f"a numeric value is expected for the mapping variable {key}")
#         string = string.replace(r, str(mapping[key]))
#     return string

# def resolve_mapped_value_inner(value, mapping):
#     if isinstance(value, str):
#         return eval(resolve_mapped_string(value, mapping))
#     elif isinstance(value, (float, int)):
#         return value
#     else:
#         error(f"not supported xformOp value type: {type(value)}")

# def resolve_mapped_value(value, mapping):
#     if isinstance(value, list):
#         if len(value) > 0 and isinstance(value[0], list):
#             return [[resolve_mapped_value_inner(sub_value, mapping) for sub_value in row] for row in value]
#         else:
#             return [resolve_mapped_value_inner(sub_value, mapping) for sub_value in value]
#     else:
#         return resolve_mapped_value_inner(value, mapping)

# path resolution

class MacroStringPair:
    def __init__(self, macro_string, actual_string):
        self.macro_string = macro_string
        self.actual_string = actual_string

    def __repr__(self):
        return self.actual_string

    def __str__(self):
        return self.actual_string

    def __eq__(self, string):
        if not isinstance(string, str):
            error(f"str type is expected for comparison, got {type(string)}")
        return self.actual_string == string

# for string substitution
def replace_macro(string, config):
    # find strings enclosed in ${}
    for r in re.findall(r'\$\{.*?\}', string):
        key = r.strip("${{}}")
        #ensure_key(key, config, "configuration file")
        macro_actual_value = ensured_retrieve(key, config, str)
        if isinstance(macro_actual_value, MacroStringPair):
            macro_actual_value = macro_actual_value.macro_string # nested macro is not supported, to avoid loop nesting
        elif not isinstance(macro_actual_value, str):
            error('macro value must be str')
        string = string.replace(r, macro_actual_value)
    return string

def get_relative_paths_of_suffix(root_folder, suffix):
    relative_paths = []
    for (root, dirs, files) in os.walk(root_folder, topdown=False):
        for file in files:
            if file.endswith(suffix):
                full_path = os.path.join(root, file)
                relative_paths.append(os.path.relpath(full_path, root_folder))
    return relative_paths

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

def resolve_string(s):
    if isinstance(s, MacroStringPair):
        return s.actual_string
    elif isinstance(s, str):
        return s
    else:
        error(f'{s} is not a str or MacroStringPair')

def resolve_mutable_name(name, is_mesh_name=True):
    splitter = '~~~'
    if splitter in name:
        if is_mesh_name:
            return name.split(splitter)[1]
        else:
            return name.split(splitter)[0]
    else:
        return name


# yaml

def read_yaml(yaml_path):
    with open(yaml_path) as yaml_file:
        data = yaml.safe_load(yaml_file)
        return data

def read_description(yaml_path):
    _dict = read_yaml(yaml_path)
    description = ensured_retrieve("omni.replicator.object", _dict, dict)
    version = ensured_retrieve("version", description)
    if version != VERSION:
        error(f"incompatible version number: {version}, expecting {VERSION}")
    return description

def read_yaml_recursive(yaml_path):
    config = read_description(yaml_path)
    while 'parent_config' in config:
        parent_config = read_description(f"{os.path.dirname(yaml_path)}/{config.pop('parent_config')}.yaml")
        parent_config.update(config)
        config = parent_config
    return config

def write_yaml(data, yaml_path):
    with open(yaml_path, 'w') as yaml_file:
        yaml.dump(data, yaml_file)

# json

def read_json(path):
    with open(path) as infile:
        json_data = json.load(infile)
        return json_data

def write_json(data, path, no_sort=None):
    with open(path, 'w') as outfile:
        #sometimes we don't need to sort or indent
        if no_sort is not None and no_sort:
            json_data = json.dumps(data)
        else:
            json_data = json.dumps(data, sort_keys=True, indent=4)
        outfile.write(json_data)

# util

def disentangle(d):
    for key, value in d.items():
        d[key] = copy.deepcopy(value)

def to_array(mat):
    return [[i for i in row] for row in mat]

def get_base_name(path):
    return os.path.basename(path).split('.')[0]

def get_path_with_token(path):
    return carb.tokens.get_tokens_interface().resolve(path)

def get_tmp_dir():
    return get_path_with_token("${temp}")

default_log = f'{get_path_with_token("${cache}")}/omni.replicator.object_debug_log.txt'
default_log = '/tmp/omni.replicator.object_debug_log.txt'

def CLEAR(path=default_log):
    with open(path, 'w') as f:
        pass

def LOG(*args, path=default_log):
    with open(path, 'a') as f:
        print(*args, file=f)

def global_message(msg):
    msg = f"{EXTENSION_NAME}: {msg}"
    print(msg)
    LOG(msg)
    logging.info(msg)