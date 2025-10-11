import json
import os
import re
from typing import Tuple

REG_ILN_LIST = r'([-$@\s*=\w.]+)(\:-)(.*)'
REG_MAP_LST = r'(^[-$@\s*=\w.]+)(\:[`:`-]?)(.*)'
REG_METH_ARGS = r"\(([^)]*)\)"
DICT_DELIM = ": "
LST_DLM = ":-"
LST_DICT_DLM = "-"
STR_DLM = ":` "
ILN_DCT_DLM = ":: "
BLOCK_DELIM = ":|"
BLOCK_PREFIX_STR = "==="
BLOCK_CODE_FENCE = "````"
SINGLE_LN_COMMENT = '#'
MULTI_LN_COMMENT = '#|'
LOOKUP_EMBED_PREFIX = '$'
LOOKUP_DIR_PREFIX = '$dir'
LOOKUP_DATA_PREFIX = '$data'
FILTER_KEY = '@filter'
EmbeddedTypes = dict()


# app_ctx = file.app_ctx
# file_contents_dirpath = file.file_contents_dirpath
# file_name = file.file_name + file.file_ext
dstr = """
name: MyApp
version: 1.0.0
config:
    host: localhost
    port: 8000
    debug: true
    database:-
        url: postgresql://localhost/db
        pool_size: 10
"""
lines = dstr.splitlines()
data = {}

def count_tabs(str_value: str, tab_width: int = 4):
    """Returns number of tabs for provided string"""
    try:
        return round(len(re.match(r'^\s+', str_value.replace('\n', '')).group()) / tab_width)
    except Exception as e:
        return 0

def update_nested(attr_path, data_src: dict, data_merge=None, data_update=None, find=None) -> tuple[bool, dict]:
    """
    Finds or updates target value based on an attribute path.

    Args:
        attr_path (list): Attribute path as list or dot-separated string.
        data_src (dict): Source data to search or update.
        data_merge (Any, optional): Value to merge.
        data_update (Any, optional): Value to replace at path.
        find (bool, optional): If True, only retrieve the value.

    Returns:
        tuple[bool, Any]: (completed, updated data or found value)
    """

    def update_value(target, val):
        """Mutates target with val depending on type compatibility."""
        if isinstance(target, list):
            if isinstance(val, list):
                target.extend(val)
            else:
                target.append(val)
        elif isinstance(target, dict) and isinstance(val, dict):
            target.update(val)
        elif isinstance(target, str) and isinstance(val, str):
            return val
        return target

    # Normalize attribute path
    if isinstance(attr_path, str):
        attr_path = attr_path.strip().split('.')
    if not attr_path:
        return True, update_value(data_src, data_merge)

    completed = len(attr_path) == 1

    # Handle list source at top-level
    if isinstance(data_src, list):
        _, merged_val = update_nested(attr_path, {}, data_merge)
        return update_nested(None, data_src, merged_val)

    # Navigate deeper if not at last key
    if not completed:
        current_data = {}
        for i, key in enumerate(attr_path):
            if find:
                current_data = (data_src.get(key) if not current_data else current_data.get(key))
            else:
                completed, current_data = update_nested(
                    attr_path[i + 1:],
                    data_src.get(key, current_data),
                    find=find,
                    data_merge=data_merge,
                    data_update=data_update
                )
                update_value(data_src, {key: current_data})
                if completed:
                    break
    else:
        # Last key operations
        key = attr_path[-1].strip()

        if find:
            return True, data_src.get(key)

        if data_update is not None:
            return completed, update_value(data_src, {key: data_update})

        # If key not in dict, wrap merge value in a dict
        if isinstance(data_src, dict) and data_src.get(key) is None:
            data_merge = {key: data_merge}

        if isinstance(data_merge, (str, int, float, bool)):
            data_src[key] = data_merge
        elif isinstance(data_src, dict):
            update_value(data_src.get(key, data_src), data_merge)
        else:
            update_value(data_src, data_merge)

    return completed, (data_src if not find else current_data)

def serializer(json_map: dict, namespace: list = [], inline_mode: bool = False, filter_params=None) -> str:
    """Converts python dictionary into parsely string"""

    if filter_params is None:
        filter_params = {}
    mode = 'INLINE' if inline_mode else 'NESTED'
    lines = []
    multi_line_keys = []
    is_block_str = False

    def pair_map(key, val, tabs):
        is_multiline = isinstance(val, str) and len(val.split("\n")) > 2
        if is_multiline or key in filter_params.get('_blob_keys', []):
            multi_line_keys.append((f"==={key.replace('content', '')}{filter_params.get(key, '')}", val.strip()))
            return
        if mode == 'INLINE':
            ns = ".".join(namespace)
            value = f"{ns}.{key}: {val}" if bool(namespace) else f"{key}: {val.strip()}"
            lines.append(value)
        else:
            if key:
                lines.append(f"{tabs}{key}: {val}")
            else:
                lines.append(f"{tabs}{val}")

    if isinstance(json_map, (str, bool, int, float)):
        tabs = '    ' * len(namespace)
        return f"{tabs}{json_map}"

    for k, val in json_map.items():
        tab_count = len(namespace) if namespace is not None else 0
        tabs = '    ' * tab_count
        if isinstance(val, (str, int, bool, float)):
            pair_map(k, val, tabs)

        elif isinstance(val, (dict, list)):
            delim = ':' if isinstance(val, dict) else ':-'
            if len(namespace) > 0:
                namespace = namespace + [k]
            else:
                namespace = [k]

            if mode == 'INLINE' and isinstance(val, list):
                ns = ".".join(namespace)
                lines.append(f"{ns}{delim}")
            elif mode == 'NESTED':
                lines.append(f"{tabs}{k}{delim}")

            if isinstance(val, dict):
                nested_value = serializer(json_map=val, namespace=namespace, inline_mode=inline_mode)
                lines.append(f"{nested_value}")
            else:
                maxl = len(val) - 1
                has_scalar = any([isinstance(it, (str, int, float, bool)) for it in val])
                for i, item in enumerate(val):
                    list_value = serializer(json_map=item, namespace=namespace, inline_mode=False)
                    lines.append(f"{list_value}")
                    if i < maxl and not has_scalar:
                        lines.append(f"    -")
            namespace.pop()

    if multi_line_keys:
        [lines.append(f"{mlk}\n{mlv}") for mlk, mlv in multi_line_keys]
    return "\n".join(lines)

def process_lookups(value_str: str, app_ctx: list = None, file_contents_dirpath: str = None, file_name: str = None):

    def parse_ref_to_files(filepath, as_dir=0):
        from pyonir.models.database import BaseFSQuery, DeserializeFile
        from pyonir.utilities import get_attr, import_module, parse_query_model_to_object

        if as_dir:
            # use proper app context for path reference outside of scope is always the root level
            # Ref parameters with model will return a generic model to represent the data value
            model = None
            generic_model_properties = query_params.get('model')
            return_all_files = query_params.get('limit','') == '*'
            if generic_model_properties:
                if '.' in generic_model_properties:
                    pkg, mod = os.path.splitext(generic_model_properties)
                    mod = mod[1:]
                    model = import_module(pkg, callable_name=mod)
                if not model:
                    model = parse_query_model_to_object(generic_model_properties)
            collection = BaseFSQuery(filepath, app_ctx=app_ctx,
                                  model=model,
                                  exclude_names=(file_name, 'index.md'),
                                  force_all=return_all_files)
            data = collection.set_params(query_params).paginated_collection()
        else:
            rtn_key = has_attr_path or 'data'
            p = DeserializeFile(filepath, app_ctx=app_ctx)
            data = get_attr(p, rtn_key) or p
        return data

    raw_value = value_str.strip()
    value_str = value_str.strip()
    has_lookup = value_str.startswith((LOOKUP_DIR_PREFIX, LOOKUP_DATA_PREFIX))

    if has_lookup:
        from pyonir.models.utils import parse_url_params
        base_path = app_ctx[-1:][0] if value_str.startswith(LOOKUP_DATA_PREFIX) else file_contents_dirpath
        _query_params = value_str.split("?").pop() if "?" in value_str else False
        query_params = parse_url_params(_query_params) if _query_params else ''
        has_attr_path = value_str.split("#")[-1] if "#" in value_str else ''
        value_str = value_str.replace(f"{LOOKUP_DIR_PREFIX}/", "") \
            .replace(f"{LOOKUP_DATA_PREFIX}/", "") \
            .replace(f"?{_query_params}", "") \
            .replace(f'#{has_attr_path}', '')

        value_str = value_str.replace('../', '').replace('/*', '')
        lookup_fpath = os.path.join(base_path, *value_str.split("/"))
        if not os.path.exists(lookup_fpath):
            print({
                'ISSUE': f'FileNotFound while processing {raw_value}',
                'SOLUTION': f'Make sure the `{lookup_fpath}` file exists. Note that only valid md and json files can be processed.'
            })
            return None
        return parse_ref_to_files(lookup_fpath, os.path.isdir(lookup_fpath))
    return value_str

def deserialize_line(line_value: str, container_type: any = None):
    """Deserialize string value to appropriate object type"""

    if not isinstance(line_value, str):
        return line_value

    def is_num(valstr):
        valstr = valstr.strip().replace(',', '')
        if valstr.isdigit():
            return int(valstr)
        try:
            return float(valstr)
        except ValueError:
            return 'NAN'

    line_value = line_value.strip()
    has_inline_dict_expression = DICT_DELIM in line_value and ', ' not in line_value

    if has_inline_dict_expression:
        v = parse_line(line_value)
        return group_tuples_to_objects([v], parent_container=dict())

    if EmbeddedTypes.get(line_value):
        return EmbeddedTypes.get(line_value)
    is_num = is_num(line_value)
    if is_num != 'NAN':
        return is_num
    if line_value.strip().lower() == "false":
        return False
    elif line_value.strip().lower() == "true":
        return True
    elif isinstance(container_type, list):
        return [deserialize_line(v)  for v in line_value.split(', ')]
    # elif line_value.strip().startswith('$'):
    #     if '{' in line_value:
    #         line_value = file.process_site_filter('pyformat', (line_value if line_value.startswith((LOOKUP_DIR_PREFIX, LOOKUP_DATA_PREFIX)) else line_value[1:]), file.__dict__)
    #     return process_lookups(line_value)
    return line_value.lstrip('$')

def get_container_type(delim):
    if LST_DLM == delim:
        return list()
    elif DICT_DELIM == delim or DICT_DELIM.strip() == delim:
        return dict()
    else:
        return str()

def parse_line(line: str, from_block_str: bool = False) -> tuple:
    """partition key value pairs"""

    try:
        start_fence_block = line.startswith((BLOCK_CODE_FENCE, BLOCK_PREFIX_STR))
        is_end_fence = line.strip().endswith(BLOCK_CODE_FENCE) or (start_fence_block and from_block_str)
        if is_end_fence:
            return count_tabs(line), None, None, None, None
        iln_delim = None
        if not from_block_str:
            if line.endswith(DICT_DELIM.strip()): # normalize dict delim
                line = line[:-1] + DICT_DELIM
            iln_delim = [x for x in (
                (line.find(BLOCK_DELIM), BLOCK_DELIM),
                (line.find(STR_DLM), STR_DLM),
                (line.find(LST_DLM), LST_DLM),
                (line.find(DICT_DELIM), DICT_DELIM),
            ) if x[0] != -1]
        key, delim, value = line.partition(iln_delim[0][1]) if iln_delim else (None, None, line)
        line_type = get_container_type(delim) if delim else str()
        is_parent = not value and key is not None
        is_str_block = is_parent and isinstance(line_type, str)
        if start_fence_block:
            line = line.replace(BLOCK_CODE_FENCE, '').replace(BLOCK_PREFIX_STR, '')
            fence_key, *alias_key = line.split(' ', 1)
            key = alias_key[0] if alias_key else fence_key or 'content'
            value = None
            is_str_block = True
            is_parent = True
        if not from_block_str:
            key = key.strip() if key else None
            value = deserialize_line(value, container_type=line_type) if value else None
        elif value:
            value += '\n'
        return count_tabs(line), key, line_type, value or None, (is_str_block, is_parent)
    except Exception as e:
        return None, None, line.strip(), None, None

def collect_block_lines(lines: list, curr_tabs: int, is_str_block: tuple[bool, bool] = None, parent_container: any = None) -> Tuple[list, int]:
    """Collects lines until stop string is found"""
    collected_lines = []
    cursor = 0
    is_list_dict = False
    pis_str_block, pis_parent = is_str_block or (False, False)
    while cursor < len(lines):
        ln = lines[cursor]
        lt, lk, ld, lv, lb = parse_line(ln, from_block_str=pis_str_block)
        if lb is None:
            break
        lis_block_str, lis_parent = lb
        is_nested = lt > curr_tabs
        end_data_block = not is_nested and not pis_str_block
        end_nested_str_block = (curr_tabs > 0 and pis_str_block) and not is_nested
        if end_nested_str_block or end_data_block: break

        if not is_list_dict:
            is_list_dict = lv==LST_DICT_DLM and not ld
        if lis_parent:
            lv, _curs = collect_block_lines(lines[cursor+1:], curr_tabs=lt, is_str_block=lb, parent_container=ld)
            cursor = cursor + _curs
        cursor += 1
        collected_lines.append((lt, lk, ld, lv, lb))

    # Finalize block collection
    if is_list_dict:
        collected_lines = group_tuples_to_objects(collected_lines)
    elif parent_container is not None:
        collected_lines = group_tuples_to_objects(collected_lines, parent_container=parent_container, compress_strings=curr_tabs>0)
    return collected_lines, cursor

def group_tuples_to_objects(items: list[tuple], parent_container: any = None, use_grouped: bool = False, compress_strings: bool = False) -> list[dict]:
    """Groups list of tuples into list of objects or other container types """

    grouped = []
    current = {}
    is_str = isinstance(parent_container, str)
    is_list = isinstance(parent_container, list)
    is_dict = isinstance(parent_container, dict)
    for tab_count, key, data_type, value, is_string_block in items:
        if is_str:
            parent_container += value.strip() if compress_strings else value or ''
            continue
        elif is_list:
            value = {key: deserialize_line(value)} if isinstance(data_type, dict) else deserialize_line(value)
            parent_container.append(value)
            continue
        elif is_dict:
            # parent_container[key] = value
            update_nested(key, data_src=parent_container, data_merge=value)
            continue
        if value == LST_DICT_DLM:  # separator → start a new object
            if current:
                grouped.append(current)
                current = {}
            continue

        # Normalize value for nested lists (e.g. child elements)
        if isinstance(value, list) and all(isinstance(v, tuple) for v in value):
            value = group_tuples_to_objects(value, parent_container=data_type)

        current[key] = value

    # append last object if not empty
    if current:
        grouped.append(current)

    return grouped or parent_container

def process_lines(file_lines, cursor: int = 0, data_container: any = None):
    """Process single line"""
    if not len(file_lines): return data_container
    line = file_lines.pop(0)
    if line.startswith((SINGLE_LN_COMMENT, MULTI_LN_COMMENT)):
        cursor += 1
    else:
        line_tabs, line_key, line_type, line_value, is_str_block = parse_line(line)
        if line_value is None:
            line_value, _cursor = collect_block_lines(file_lines, curr_tabs=line_tabs, is_str_block=is_str_block, parent_container=line_type)
            cursor = (_cursor + cursor + 1) if line_tabs else _cursor
            file_lines = file_lines[cursor:]
        else:
            cursor += 1
        update_nested(line_key, data_container, data_merge=line_value)

        if line_key and line_key.startswith('$'): # commit embedded types to cache
            EmbeddedTypes[line_key] = line_value

    return process_lines(file_lines, cursor=cursor, data_container=data_container)


t = process_lines(lines, cursor=0, data_container=data)
print(t)