from pyonir.models.page import BasePage


class Page(BasePage):
    title = 'Hello World'
    tags = ['one','two','three']
    template = 'sample-pages.html'
