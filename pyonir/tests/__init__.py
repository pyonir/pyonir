from pyonir.utilities import get_module, load_modules_from, get_all_files_from_dir
from pyonir import init
if __name__=='__main__':
    App = init('/Users/hypermac/dev/pyonir/pyonir/libs/app_setup/main.py')
    path = '/Users/hypermac/dev/pyonir/pyonir/libs/jinja/filters'
    json_dirpath = '/Users/hypermac/dev/pyonir/pyonir/libs/plugins/ecommerce/contents/orders/paypal'
    md_dirpath = '/Users/hypermac/dev/pyonir/pyonir/libs/plugins/ecommerce/contents/api'
    plugin_ctx = ['ecommerce', '/my-shop', '/Users/hypermac/dev/pyonir/pyonir/libs/plugins/ecommerce/contents', '/Users/hypermac/dev/pyonir/pyonir/libs/plugins/ecommerce/static_site']
    # x = load_modules_from(path)
    # x = list(get_all_files_from_dir(json_dirpath, app_ctx=plugin_ctx))
    # y = list(get_all_files_from_dir(md_dirpath, app_ctx=plugin_ctx))
    data = {"page":{"data": {"status": "GOOD"}}}
    dstr = "the status is {page[data][status]}"
    res = App.parse_pyformat(dstr, data)

    pass