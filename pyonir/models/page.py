from datetime import datetime
import os, pytz
from pathlib import Path


class PageStatus(str):
    UNKNOWN = 'unknown'
    """Read only by the system often used for temporary and unknown files"""

    PROTECTED = 'protected'
    """Requires authentication and authorization. can be READ and WRITE."""

    FORBIDDEN = 'forbidden'
    """System only access. READ ONLY"""

    PUBLIC = 'public'
    """Access external and internal with READ and WRITE."""


class BasePage:
    """Represents a single page returned from a web request"""
    content: str = ''
    template: str = 'pages.html'
    status: str = PageStatus.PUBLIC

    def __init__(self, path: str = None):
        self.file_path = path or str(__file__)
        self.file_name = os.path.basename(self.file_path)
        self.file_dirpath = os.path.dirname(self.file_path)

    @property
    def file_status(self) -> str:  # String
        return PageStatus.PROTECTED if self.file_name.startswith('_') else \
            PageStatus.FORBIDDEN if self.file_name.startswith('.') else PageStatus.PUBLIC

    @property
    def url(self): return f'/{self.slug}'

    @property
    def slug(self): return

    @property
    def canonical(self):
        from pyonir import Site
        return f"{Site.domain}{self.url}" if Site else self.url

    @property
    def created_on(self):  # Datetime
        return datetime.fromtimestamp(os.path.getctime(self.file_path), tz=pytz.UTC)

    @property
    def modified_on(self):  # Datetime
        return datetime.fromtimestamp(os.path.getmtime(self.file_path), tz=pytz.UTC)


class BaseMedia(BasePage):

    def __init__(self, path: str):
        super().__init__(path)
        self.path = path
        self.width = None
        self.height = None
        self.thumbnails = dict()

    @property
    def captions(self):
        """returns caption within file name {name}|{caption}.{ext}"""
        return

    def open_image(self, file_path):
        """Opens selected image into memory to retrieve dimensions"""
        from PIL import Image
        from pyonir.utilities import get_attr
        raw_img = Image.open(file_path)
        self.width = get_attr(raw_img, "width", None)
        self.height = get_attr(raw_img, "height", None)
        return raw_img

    def resize(self, sizes=None):
        '''
        Resize each image and save to the upload path in corresponding image size and paths
        This happens after full size images are saved to the filesystem
        '''
        from PIL import Image
        from pyonir import Site
        raw_img = self.open_image()
        if sizes is None:
            sizes = [Site.THUMBNAIL_DEFAULT]
        try:
            for dimensions in sizes:
                width, height = dimensions
                self._sizes.append(dimensions)
                img = raw_img.resize((width, height), Image.Resampling.BICUBIC)
                file_name = f'{self.file_name}--{width}x{height}'
                img_dirpath = os.path.dirname(self.file_path)
                # self.createImagefolders(img_dirpath)
                filepath = os.path.join(img_dirpath, Site.UPLOADS_THUMBNAIL_DIRNAME, file_name + '.' + self.file_ext)
                if not os.path.exists(filepath): img.save(filepath)
        except Exception as e:
            raise

    def generate_thumb(self, width, height) -> str:
        """Generates an image accordion to width and height parameters and returns url to the new resized image"""
        self._sizes.append((width, height))
        if not self.thumbnails.get(f'{width}x{height}'): self.resize([(width, height)])
        return self.thumbnails.get(f'{width}x{height}')

    def get_all_thumbnails(self) -> dict:
        """Collects thumbnails for the image"""
        from pyonir.utilities import query_files
        from pyonir import Site
        if not Site: return {}
        # if self.group != Site.UPLOADS_DIRNAME:
        #     self.group = f'{Site.UPLOADS_DIRNAME}/{self.group}'
        # thumbs_dir = os.path.join(self.file_dirpath, self.group, Site.UPLOADS_THUMBNAIL_DIRNAME)
        # files = query_files(str(thumbs_dir), app_ctx=self.app_ctx, model=BaseMedia)
        # target_name = self.file_name
        # thumbs = {}
        # # filter files based on name
        # for file in files:
        #     if file.file_name[:len(target_name)] != target_name: continue
        #     w = file.width
        #     h = file.height
        #     thumbs[f'{w}x{h}'] = file
        #     pass
        # return thumbs

    @staticmethod
    async def save_upload(file, img_folder_abspath) -> str:
        """Saves base64 file contents into file system"""
        file_name, file_ext = os.path.splitext(file.filename)
        new_dir_path = Path(img_folder_abspath)
        new_dir_path.mkdir(parents=True, exist_ok=True)
        new_file_path = os.path.join(img_folder_abspath, file_name + file_ext)
        file_contents = await file.read()
        with open(str(new_file_path), 'wb') as f:
            f.write(file_contents)
        return new_file_path