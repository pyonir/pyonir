from pyonir.types import PyonirApp
from pyonir.core import PyonirPlugin
import os

class FileUploader(PyonirPlugin):
    name = "File Uploader"

    def __init__(self, app: PyonirApp):
        super().__init__(app, __file__)
        self.resolvers_dirpath = os.path.join(self.app_dirpath, 'resolvers')
