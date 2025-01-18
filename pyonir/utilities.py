import os, itertools
import typing
from typing import Generator


def parse_all(path, app_ctx=None, file_type=None) -> object:
    from pyonir.parser import Parsely
    """Deserializes all files within the contents directory"""
    key = os.path.basename(path)
    etype = file_type or Parsely
    all_files_in_dir = allFiles(path, entry_type=etype, app_ctx=app_ctx)
    # Dynamically create a new class
    cls = type(key, (object,), {})

    # Create an instance of the class
    fileMap = cls()
    for pfile in all_files_in_dir:
        configname = getattr(pfile, 'file_name', getattr(pfile, 'name', None))
        setattr(fileMap, configname, pfile)
        pass
    return fileMap

def dict_to_class(data: dict, name: str):
    """
    Converts a dictionary into a class object with the given name.

    Args:
        data (dict): The dictionary to convert.
        name (str): The name of the class.

    Returns:
        object: An instance of the dynamically created class with attributes from the dictionary.
    """
    # Dynamically create a new class
    cls = type(name, (object,), {})

    # Create an instance of the class
    instance = cls()

    # Assign dictionary keys as attributes of the instance
    for key, value in data.items():
        setattr(instance, key, value)

    return instance


def get_attr(rowObj, attrPath=None, default=None, rtn_none=True):
    """
        @default returns a default obj when the target attr value is None
        @rtn_none returns a None obj when target attr value is None
        """
    if attrPath == None: return rowObj
    attrPath = attrPath if isinstance(attrPath, list) else attrPath.split('.')
    targetObj = None
    for key in attrPath:
        try:
            if targetObj:
                targetObj = targetObj[key]
            else:
                targetObj = rowObj.get(key)
            pass
        except Exception as TypeError:
            if targetObj:
                targetObj = getattr(targetObj, key, None)
            else:
                targetObj = getattr(rowObj, key, None)
            pass
    if (rtn_none and targetObj is None) or (default and targetObj is None):
        return default
    if not default and targetObj is None:
        return rowObj
    return targetObj


def remove_html_tags(text):
    """Remove html tags from a excerpt string"""
    import re
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)


def camel_to_snake(camel_str):
    """Converts camelcase into snake case. Thanks Chat GPT"""
    import re
    snake_str = re.sub(r'(?<!^)(?=[A-Z])', '_', camel_str).lower()
    return snake_str


def deserialize_datestr(datestr, timestr="00:00", fmt="%Y-%m-%d %H:%M:%S %p", zone="US/Eastern", auto_correct=True):
    from datetime import datetime
    import pytz
    if not isinstance(datestr, str): return datestr

    def correct_format(date_str):
        try:
            date_str = date_str.strip().replace('/', '-')
            date_str, _, timestr = date_str.partition(" ")
            timestr = timestr if timestr != "" else '12:13:14 AM'
            has_period = timestr.endswith("M")
            if not has_period:
                timestr += " AM"
            y, m, *d = date_str.split("-")
            d = "".join(d)
            fdate = f"{y}-{int(m):02d}-{d}"
            if int(y) < int(d):
                fdate = f"{d}-{int(y):02d}-{m}"
                print(f"\tIncorrect format on date string {date_str}. it should be {fdate}")
                return fdate
            return f"{fdate} {timestr}"
        except Exception as e:
            return None

    try:
        return pytz.utc.localize(datetime.strptime(datestr, fmt))
    except ValueError as e:
        # return str(e)
        if not auto_correct: return str(e)
        datestr = correct_format(datestr)
        return pytz.utc.localize(datetime.strptime(datestr, fmt)) if datestr else None


def sortBykey(listobj, sort_by_key="", limit="", reverse=True):
    """Sorts list of obj by key"""

    def get_path_object(rowObj, path):
        targetObj = None
        for key in path.split('.'):
            try:
                if targetObj:
                    targetObj = targetObj[key]
                else:
                    targetObj = rowObj[key]
                pass
            except Exception as error:
                raise error
        return targetObj

    try:
        sorted_dict = sorted(getattr(listobj, 'data', listobj), key=lambda obj: get_path_object(obj, sort_by_key),
                             reverse=reverse)
        # sorted_dict = sorted(getattr(listobj,'data', listobj), key = lambda x:x[sort_by_key], reverse=reverse)
        if limit:
            return sorted_dict[:limit]
        return sorted_dict
    except Exception as e:
        return listobj


def allFiles(abs_dirpath: str,
             app_ctx: 'IApp' = None,
             entry_type: any = None,
             rtn_attr: str = None,
             exclude_dirs: list[str] = None,
             apply_schema: bool = False,
             force_all: bool = True) -> Generator:
    """Returns a generator of files from a directory path"""
    from .parser import ParselyMedia, ParselyPage
    from .parser import ALLOWED_CONTENT_EXTENSIONS, IGNORE_FILES
    if abs_dirpath in (exclude_dirs or []): return []
    if not entry_type: entry_type = ParselyPage

    _, __, base_dir, static_dir = app_ctx

    def get_datatype(parentdir, rel_filepath, etype):
        filepath = os.path.normpath(os.path.join(parentdir, rel_filepath))
        if entry_type == 'path':
            return filepath
        ispg = filepath.endswith(ALLOWED_CONTENT_EXTENSIONS)
        isschema = hasattr(etype, 'from_path')
        p = etype.from_path(filepath, app_ctx) if isschema else etype(filepath, app_ctx) \
            if ispg else ParselyMedia(filepath, app_ctx)
        if apply_schema:
            p.set_file_schema(apply_schema)
            return p.schema.map_to_schema(p) if p.schema else p.data
        return Collection.get_attr(p, rtn_attr, None)

    def is_public(parentdir, entry=None):
        if force_all: return True
        parentdir = parentdir.replace(base_dir, "").lstrip(os.path.sep)
        is_hidden_dir = parentdir.startswith(IGNORE_FILES)
        if entry in IGNORE_FILES:
            return False
        if not entry:
            return False if is_hidden_dir else True
        else:
            is_hidden_file = entry.startswith(IGNORE_FILES)
            is_filetype = entry.endswith(ALLOWED_CONTENT_EXTENSIONS)
            return False if is_filetype and is_hidden_file or is_hidden_dir else True

    for parentdir, subs, files in os.walk(os.path.normpath(abs_dirpath)):
        folderRoot = parentdir.replace(base_dir, "").lstrip(os.path.sep)
        subFolderRoot = os.path.basename(folderRoot)
        skipRoot = (folderRoot in IGNORE_FILES
                    or folderRoot.startswith(IGNORE_FILES)
                    or subFolderRoot.startswith(IGNORE_FILES))
        skipSubs = subFolderRoot in exclude_dirs if exclude_dirs else 0
        if skipRoot or skipSubs: continue

        for filename in files:
            if not force_all and not filename.endswith(ALLOWED_CONTENT_EXTENSIONS): continue
            if not is_public(parentdir, filename) or filename in IGNORE_FILES: continue
            yield get_datatype(parentdir, filename, entry_type)


def delete_file(full_filepath):
    import shutil
    if os.path.isdir(full_filepath):
        shutil.rmtree(full_filepath)
        return True
    elif os.path.isfile(full_filepath):
        os.remove(full_filepath)
        return True
    return False


def create_file(file_abspath: str, data: any = None, is_json: bool = False, mode='w') -> bool:
    def write_file(file_abspath, data, is_json=False, mode='w'):
        import json
        with open(file_abspath, mode, encoding="utf-8") as f:
            if is_json:
                json.dump(data, f, indent=2, sort_keys=True, default=json_serial)
            else:
                f.write(data)

    """Creates a new file based on provided data
    Args:
        file_abspath: str = path to proposed file
        data: any = contents to write into file
        is_json: bool = strict json file
        mode: str = write mode for file w|w+|a
    Returns:
        bool: The return value if file was created successfully
    """
    if not os.path.exists(os.path.dirname(file_abspath)):
        os.makedirs(os.path.dirname(file_abspath))
    try:

        if is_json:
            file_abspath = file_abspath.replace(".md", ".json")
        write_file(file_abspath, data, is_json=is_json, mode=mode)

        return True
    except Exception as e:
        print(f"Error create_file method: {str(e)}")
        return False


def copy_assets(src: str, dst: str, purge: bool = True):
    """Copies files from a source directory into a destination directory with option to purge destination"""
    import shutil
    from shutil import ignore_patterns
    print(f"\033[92mCoping `{src}` theme assets into {dst}")
    try:
        if os.path.exists(dst) and purge:
            shutil.rmtree(dst)
        shutil.copytree(src, dst, ignore=ignore_patterns('*.pyc', 'tmp*', 'node_modules', '.*'))
    except NotADirectoryError as e:
        shutil.copyfile(src, dst)
    except Exception as e:
        raise


def tupleconverter(tuple_name, fileobj):
    """Converts dicts into tuples"""
    if isinstance(fileobj, tuple): return fileobj
    from .parser import PROTECTED_FIELD_PREFIX, Parsely
    def tupleConverter(named, v):
        named = named.replace(' ', '_').replace('-', '_')
        if isinstance(v, dict):
            return tupleconverter(named, v)
        elif isinstance(v, Parsely):
            return tupleConverter(named, v.data)
        elif isinstance(v, list):
            return [tupleConverter(named, item) for item in v]
        else:
            return v

    def sanitize(field):
        f = field.replace(' ', '_').replace('-', '_')
        fkw = 'class, for, return, global, pass, print, raise'.split(', ')
        if f in fkw:
            print(f'WARNING: reserved keyword {f} is not allowed and has changed to {f}_ ')
            f = f + '_'
        return f

    try:
        keys = [sanitize(key) for key in fileobj.keys() if not key.startswith(PROTECTED_FIELD_PREFIX)]

        from collections import namedtuple
        return namedtuple(tuple_name, keys)(
            *tuple(tupleConverter(n, v) for n, v in fileobj.items() if
                   not n.startswith(PROTECTED_FIELD_PREFIX))
        )
    except Exception as e:
        print(f"tuple_converter: {tuple_name} {str(e)}")
        return fileobj


def json_serial(obj):
    """JSON serializer for nested objects not serializable by default jsonify"""
    from datetime import datetime
    # from pycasso.utilities import Collection
    from .parser import Parsely, ParselySchema
    if isinstance(obj, (datetime)):
        return obj.isoformat()
    elif isinstance(obj, Collection):
        return list(obj.collection)
    elif isinstance(obj, (ParselySchema, Parsely)):
        return obj.data
    elif hasattr(obj, 'parsely_extenstion'):
        schema_data = obj.schema.map_to_schema(obj) if not obj.data and obj.schema else None
        return schema_data or obj.data
    else:
        return None


def secure_upload_filename(filename):
    import re
    # Strip leading and trailing whitespace from the filename
    filename = filename.strip()

    # Replace spaces with underscores
    filename = filename.replace(' ', '_')

    # Remove any remaining unsafe characters using a regular expression
    # Allow only alphanumeric characters, underscores, hyphens, dots, and slashes
    filename = re.sub(r'[^a-zA-Z0-9_.-]', '', filename)

    # Ensure the filename doesn't contain multiple consecutive dots (.) or start with one
    filename = re.sub(r'\.+', '.', filename).lstrip('.')

    # Return the filename as lowercase for consistency
    return filename.lower()


class pcolors:
    RESET = '\033[0m'
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class Collection:
    @property
    def is_bool(self):
        return isinstance(self.where, list) and len(self.where) == 1

    @property
    def count(self):
        from sortedcontainers import SortedList
        return self.collection._len if isinstance(self.collection, SortedList) else len(self.collection)

    def __init__(self, targetIterator, sortBy: str = 'date', where: list = [], reverse=False):
        from sortedcontainers import SortedList
        self.reverse = reverse
        self.sortBy = sortBy
        self.where = where
        self.collection = SortedList(targetIterator, key=lambda x: self.get_attr(x, sortBy))
        pass

    def where_condition(self, target):
        """Evaluates if a property is true or false."""
        from datetime import datetime, timedelta
        from pyonir import Site
        if not self.where: return True
        try:
            if self.is_bool:
                return self.get_attr(target, self.where) != True
            else:
                attr_path, oper, rcon = self.where
                target = target.data if not isinstance(target, dict) else target
                lvalue = self.get_attr(target, attr_path)
                # case handling for dates
                if isinstance(lvalue, datetime):
                    if isinstance(rcon, str):
                        rcon = int(rcon)
                    if oper == '>':  # future dates
                        return lvalue > rcon
                    elif oper == '<':  # past dates
                        return lvalue < rcon
                    elif oper == 'in_last':  # within days
                        current_date = Site.system().get('current_date')
                        day_margin = timedelta(days=rcon)
                        return (current_date - day_margin) <= lvalue <= current_date + day_margin
                elif isinstance(lvalue, str):
                    # Case handling for strings
                    if oper == 'in':
                        return lvalue.find(rcon) > -1
        except Exception as e:
            # raise
            return False
        pass

    @staticmethod
    def get_attr(rowObj, attrPath=None, default=None, rtn_none=True):
        """
        @default returns a default obj when the target attr value is None
        @rtn_none returns a None obj when target attr value is None
        """
        if attrPath == None: return rowObj
        attrPath = attrPath if isinstance(attrPath, list) else attrPath.split('.')
        targetObj = None
        for key in attrPath:
            try:
                if targetObj:
                    targetObj = targetObj[key]
                else:
                    targetObj = rowObj.get(key)
                pass
            except Exception as TypeError:
                if targetObj:
                    targetObj = getattr(targetObj, key, None)
                else:
                    targetObj = getattr(rowObj, key, None)
                pass
        if (rtn_none and targetObj is None) or (default and targetObj is None):
            return default
        if not default and targetObj is None:
            return rowObj
        return targetObj
        # return targetObj if not targetObj and rtn_empty else rowObj

    def groupedBy(self, keyname, where=None, targetField=None):
        """Returns dictionary groupings based on object keyname from a list"""
        from collections import defaultdict
        results = defaultdict(list)
        if where: self.where = where
        for item in self.collection:
            item = self.get_attr(item, targetField)
            groupname = self.get_attr(item, keyname)
            try:
                if not self.where_condition(item): continue
            except NameError:
                raise Exception('`item` was not found in the groupdedBy where argument')
            if isinstance(groupname, list):
                for tag in groupname:
                    results[tag.lower().strip()].append(item)
            elif groupname is not None and isinstance(groupname, str):
                results[groupname.lower().strip()].append(item)
        return results

    def paginate(self, start: int = 0, end: int = None, reverse: bool = None, where: list = None,
                 attr_path: str = None):
        from sortedcontainers import SortedList
        if where: self.where = where
        end = self.count if end is None else end
        begin = start
        stop = end
        if begin > stop or begin == self.count or not isinstance(self.collection, SortedList): return False
        for obj in self.collection.islice(start, end, reverse=reverse or self.reverse):
            if self.where and not self.where_condition(obj): continue
            obj.set_file_schema()
            if obj.schema: obj = obj.schema.map_to_schema(obj)
            yield self.get_attr(obj, attr_path, rtn_none=False)


def get_module(pkg_path: str, callable_name: str) -> tuple[any, typing.Callable]:
    from importlib import util
    pkg = util.spec_from_file_location(callable_name, pkg_path).loader.load_module(callable_name)
    func = getattr(pkg, callable_name)

    return (pkg, func)


def generate_id():
    import uuid
    return str(uuid.uuid1())


class PyonirMod:
    """Pyonir module object storing path and module class to be used later during runtime"""

    def __init__(self, path):
        from importlib import util
        from pyonir import PYONIR_DIRPATH
        assert (os.path.exists(path)), "Module path doesn't exist"

        # init_file_path = path if path.endswith('.py') else os.path.join(path, '__init__.py')
        self.class_module = None
        self.package = os.path.dirname(path) \
            .replace(os.path.dirname(PYONIR_DIRPATH), "") \
            .replace(os.path.sep, ".").lstrip(".")
        self.callable_name = os.path.basename(path).split('.py')[0]
        self.import_str = f"{self.package}.{self.callable_name}.{self.callable_name}"
        self.origin = os.path.join(path, self.callable_name + ".py") if not path.endswith('.py') else path
        if not os.path.exists(self.origin): self.origin = os.path.join(path, '__init__.py')
        try:  # Importing the module from file_path expects callable_name
            self.class_module = getattr(
                util.spec_from_file_location(self.callable_name, self.origin).loader.load_module(), self.callable_name)
        except AttributeError as e:
            raise
            # self.class_module = importlib.util.spec_from_file_location(self.callable_name, file_path).loader.load_module()
        except Exception as e:
            raise
            # print(f"{__name__} {self.origin}: {str(e)}")


class DB:
    def __init__(self):
        pass

    def connect(self, dbname: str, dbuser: str, dbpass: str, dbport: int, dbhost: str):
        pass

    @staticmethod
    async def upload_documents(documents: list['RequestFile'] = None, upload_root_dirpath: str = None):
        """Uploads files sent by server request"""
        from . import IMAGE_SIZES, UPLOADS_ROUTE, ALLOWED_UPLOAD_EXTENSIONS
        from .server import RequestFile

        async def saveMedia(file: RequestFile, foldername: str = None) -> str:

            def clean_up_path(filepath):
                return filepath.replace(file.uploads_dirpath, UPLOADS_ROUTE)

            def createImagefolder(folderpath, with_thumbs=None):
                if not os.path.exists(folderpath):
                    os.makedirs(folderpath)

                '''create separate folders for smaller sizes'''
                if with_thumbs:
                    for sizename in IMAGE_SIZES:
                        if not os.path.exists(os.path.join(folderpath, sizename)) and sizename != 'original':
                            # make the path
                            os.makedirs(os.path.join(folderpath, sizename))
                return folderpath

            def resize(filedirpath, imageFile):
                from PIL import Image
                '''
                Resize each image and save to the upload path in corresponding image size and paths
                This happens after full size images are saved to the filesystem
                '''

                try:
                    for sizename, dimensions in IMAGE_SIZES.items():
                        origimage = os.path.join(filedirpath, imageFile)
                        img = Image.open(origimage)
                        imgfilesize = os.path.getsize(origimage)
                        # img = img.resize(dimensions, Image.ANTIALIAS)
                        img.thumbnail(dimensions, Image.ANTIALIAS)
                        folderpath = os.path.join(filedirpath, sizename)
                        if not os.path.exists(folderpath):
                            os.makedirs(folderpath)
                        img.save(os.path.join(filedirpath, sizename, imageFile))

                except Exception as e:
                    pass

            def secureFile(filename):
                """ @return bool if file is allowed to upload """

                def allowed_file(filename):
                    # This function checks a given string extension
                    return '.' in filename and \
                        filename.rsplit('.', 1)[1] in ALLOWED_UPLOAD_EXTENSIONS

                return secure_upload_filename(filename) if allowed_file(filename) else None

            file_ext = file.filename.split('.').pop()
            upload_folder = os.path.join("documents", foldername) if file_ext in ("pdf", "zip") else foldername
            allowedFile = secureFile(file.filename)
            is_image = file_ext not in ('pdf', 'zip')
            if allowedFile:
                upload_dir = os.path.join(file.uploads_dirpath, upload_folder)
                folderpath = upload_dir.replace(' ', '-')
                createImagefolder(folderpath, with_thumbs=is_image)
                file.filepath = os.path.join(folderpath, allowedFile)
                # save original file
                await file.save()
                # resize original file
                if is_image: resize(file.uploads_dirpath, allowedFile)
                # save base64
                return clean_up_path(file.filepath)
            return 'file named {} was not allowed'.format(file.filename)

        upload_response = {'files': [], 'status': ''}
        try:
            upload_response['files'] = [await saveMedia(doc, upload_root_dirpath) for doc in documents]
            upload_response['status'] = "successfully uploaded {} files".format(len(documents))
        except Exception as e:
            raise
        return upload_response

    @staticmethod
    def find(
            select,
            where: str = None,
            target: str = None,
            entry_type: any = None,
            allow_all=False):
        from .parser import Parsely
        if not entry_type: entry_type = Parsely
        result = None
        selected = allFiles(select, entry_type=entry_type)
        if where and target and selected:
            for file in selected:
                if Collection.get_attr(file, where) == target:
                    result = file.file_schema.map_to_schema(file)
                    # result = file.to_dict() if rtn_file_as!='file' else file
        else:
            result = list(selected)
        return result

    @staticmethod
    def get_menus(active_page=''):
        """site navigations based on all index.md files and any file within the pages directory"""
        from pyonir import Site as app
        if app is None: return None
        assert hasattr(app, 'pages_dirpath'), "Get menus 'app' parameter does not have a pages dirpath property"

        pages = {}
        subpages = {}

        def get_nav(app):
            """Gets page nav based on file contents"""
            file_list = allFiles(app.pages_dirpath, apply_schema='menu',
                                 app_ctx=app.files_ctx)  # return files using menu schema model

            for page in file_list:
                pstatus = page.get('status')
                purl = page.get('url')
                menu_group = page.get('menu')  # parent level menu item
                menu_parent = page.get('menu_parent')  # child level menu item
                if pstatus == 'hidden' or (not menu_group and not menu_parent): continue
                page['active'] = active_page == page.get('url')
                if menu_group:
                    pages[purl] = page
                elif menu_parent:
                    _ref = subpages.get(menu_parent)
                    if not _ref:
                        subpages[menu_parent] = [page]
                    else:
                        _ref.append(page)

            if subpages:
                for k, m in subpages.items():
                    pmenu = pages.get(k)
                    if not pmenu: continue
                    pmenu.update({"sub_menu": m})

        # site navigation
        get_nav(app)
        # Collect any plugins navigation
        # if hasattr(app, 'Resolvers'):
        #     for iplg_id, iplg in app.Resolvers.__dict__.items():
        #         if not hasattr(iplg, 'app_extension') or not iplg.is_enabled: continue
        #         get_nav(iplg)

        return Collection(pages.values(), sortBy='order').groupedBy('menu')

    @staticmethod
    def tags(searchStr="", model="title,url,tag,tags"):
        import re
        """Attempts to return a dictionary of tags based on file propterties"""
        try:
            # passing a path of '/' will return all files. expensive operation here
            from . import Site
            allfiles = allFiles(Site.content_dirpath, model=model, post_process=False)
            # tagerror = "Tag named `{}` was not found".format(searchStr)
            tags_collection = {}
            query_search_wordList = searchStr.lower().replace(' ', ',').split(',') if searchStr != '' else None

            def tagContains(tagname):
                """search exact match """
                if searchStr:
                    for term in query_search_wordList:
                        # print(tagname+' <---> '+term)
                        if not term in tagname:
                            return False
                    return True

            if not query_search_wordList:
                for fileObj in allfiles:
                    fileTags = fileObj.data.get('tags', fileObj.data.get('tag'))
                    if not fileTags: continue
                    for queryWord in fileTags:
                        queryWord = queryWord.strip()
                        if not tags_collection.get(queryWord):
                            tags_collection[queryWord] = [fileObj.data]
                        else:
                            tags_collection[queryWord].append(fileObj.data)
                return tags_collection
            else:
                for fileObj in allfiles:
                    fileTags = fileObj.data.get('tags', [])
                    fileTitle = fileObj.data.get('title', '').lower().split(' ')
                    fileName = fileObj.file_name.lower().replace('-', ' ').replace('_', ' ').split(' ')
                    wordList = list(itertools.chain(fileTags, fileTitle, fileName))
                    url = fileObj.data.get('url')
                    for queryWord in query_search_wordList:
                        if tags_collection.get(url): continue
                        if queryWord not in wordList: continue
                        tags_collection.update({url: fileObj.data})
                return list(tags_collection.values())
        except Exception as e:
            raise
