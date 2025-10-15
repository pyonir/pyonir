import os
from datetime import datetime
from collections.abc import Generator
from typing import Optional, Union

def get_version(toml_file: str) -> str:
    import re
    from pathlib import Path
    try:
        # Try using installed metadata first
        from importlib.metadata import version
        return version("pyonir")
    except Exception:
        pass

    try:
        content = Path(toml_file).read_text()
        return re.search(r'^version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE).group(1)
    except Exception as e:
        print('Error: unable to parse pyonir version from project toml',e, toml_file)
        return 'UNKNOWN'

def parse_url_params(param_str: str) -> dict:
    """Parses a URL query string into a dictionary"""
    from urllib.parse import parse_qs
    parsed = parse_qs(param_str)
    return {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}

def process_contents(path, app_ctx=None, file_model: any = None) -> object:
    """Deserializes all files within the contents directory"""
    from pyonir.models.database import query_fs
    key = os.path.basename(path)
    res = type(key, (object,), {"__name__": key})() # generic map
    pgs = query_fs(path, app_ctx=app_ctx, model=file_model)
    for pg in pgs:
        name = getattr(pg, 'file_name')
        # pg_obj = type(name, (object,), {"__name__": name, 'file_path': pg.file_path})
        # val = cls_mapper(pg, pg_obj)
        setattr(res, name, pg.to_named_tuple())
    return res

def json_serial(obj):
    """JSON serializer for nested objects not serializable by default jsonify"""
    from datetime import datetime
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, Generator) or hasattr(obj, 'mapping'):
        return list(obj)
    elif hasattr(obj, 'to_dict'):
        return obj.to_dict()

def deserialize_datestr(
    datestr: Union[str, datetime],
    fmt: str = "%Y-%m-%d %I:%M:%S",   # %I for 12-hour format
    zone: str = "US/Eastern",
    auto_correct: bool = True
) -> Optional[datetime]:
    """
    Convert a date string into a timezone-aware datetime.

    Args:
        datestr: Input string or datetime.
        fmt: Expected datetime format (default "%Y-%m-%d %I:%M:%S %p").
        zone: Timezone name (default "US/Eastern").
        auto_correct: Whether to attempt corrections for sloppy inputs.

    Returns:
        Timezone-aware datetime (in UTC), or None if parsing fails.
    """
    import pytz

    if isinstance(datestr, datetime):
        return pytz.utc.localize(datestr) if datestr.tzinfo is None else datestr.astimezone(pytz.utc)
    if not isinstance(datestr, str):
        return None

    tz = pytz.timezone(zone)

    def correct_format(raw: str, dfmt: str) -> tuple[str, str]:
        """Try to normalize sloppy date strings like 2025/8/9 13:00."""
        try:
            raw = raw.strip().replace("/", "-")
            if 'T' in raw:
                date_part, _, time_part = raw.partition('T')
            else:
                date_part, _, time_part = raw.partition(" ")

            # Use fallback timestr if missing
            time_part = time_part or "12:00:00.0000"
            hr,*minsec = time_part.split(':')
            is_military_tme = "%H" in dfmt or int(hr) > 12
            dfmt = dfmt.replace("%I", "%H") if is_military_tme else fmt

            parts = date_part.split("-")
            if len(parts) != 3:
                return raw, dfmt

            y, m, d = parts
            # Pad month/day
            m, d = f"{int(m):02d}", f"{int(d):02d}"

            # Basic sanity check: if year looks like day
            if int(y) < int(d):
                # Swap year/day (common human error)
                y, d = d, y
                print(f"⚠️  Corrected malformed date string: {raw} → {y}-{m}-{d}")

            return f"{y}-{m}-{d} {time_part}", dfmt
        except Exception as e:
            return raw, dfmt

    try:
        # Try direct parse first
        dt = datetime.strptime(datestr, fmt)
    except ValueError:
        if not auto_correct:
            return None
        corrected, fmt = correct_format(datestr, fmt)
        if not corrected:
            return None
        try:
            dt = datetime.strptime(corrected, fmt)
        except ValueError:
            return None

    # Localize to input zone, then convert to UTC
    return tz.localize(dt).astimezone(pytz.utc)

def get_attr(row_obj, attr_path=None, default=None, rtn_none=True):
    """
    Resolves nested attribute or dictionary key paths.

    :param row_obj: deserialized object
    :param attr_path: dot-separated string or list for nested access
    :param default: fallback value if the target is None or missing
    :param rtn_none: if True, returns `None` on missing keys/attrs instead of the original object
    """
    if attr_path == None: return row_obj
    attr_path = attr_path if isinstance(attr_path, list) else attr_path.split('.')
    targetObj = None
    for key in attr_path:
        try:
            if targetObj:
                targetObj = targetObj[key]
            else:
                targetObj = row_obj.get(key)
            pass
        except (KeyError, AttributeError, TypeError) as e:
            if targetObj:
                targetObj = getattr(targetObj, key, None)
            else:
                targetObj = getattr(row_obj, key, None)
            pass
    if targetObj is None and rtn_none:
        return default or None

    return targetObj


def create_file(file_abspath: str, data: any = None, is_json: bool = False, mode='w') -> bool:
    """Creates a new file based on provided data
    Args:
        file_abspath: str = path to proposed file
        data: any = contents to write into file
        is_json: bool = strict json file
        mode: str = write mode for file w|w+|a
    Returns:
        bool: The return value if file was created successfully
    """
    def write_file(file_abspath, data, is_json=False, mode='w'):
        import json
        with open(file_abspath, mode, encoding="utf-8") as f:
            if is_json:
                json.dump(data, f, indent=2, sort_keys=True, default=json_serial)
            else:
                f.write(data)

    if not os.path.exists(os.path.dirname(file_abspath)):
        os.makedirs(os.path.dirname(file_abspath))
    try:
        is_json = is_json or file_abspath.endswith('.json')
        write_file(file_abspath, data, is_json=is_json, mode=mode)
        return True
    except Exception as e:
        print(f"Error create_file method: {str(e)}")
        return False

def copy_assets(src: str, dst: str, purge: bool = True):
    """Copies files from a source directory into a destination directory with option to purge destination"""
    import shutil
    from shutil import ignore_patterns
    # print(f"{PrntColrs.OKBLUE}Coping `{src}` resource into {dst}{PrntColrs.RESET}")
    try:
        if os.path.exists(dst) and purge:
            shutil.rmtree(dst)
        if os.path.isfile(src):
            shutil.copyfile(src, dst)
        if os.path.isdir(src):
            shutil.copytree(src, dst, ignore=ignore_patterns('__pycache__', '*.pyc', 'tmp*', 'node_modules', '.*'))
    except Exception as e:
        raise