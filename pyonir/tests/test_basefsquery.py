import os

from pyonir import PyonirApp
from pyonir.core.database import BaseFSQuery, BasePagination
from pyonir.core.parser import DeserializeFile
from pyonir.core.schemas import GenericQueryModel
from pyonir.core.utils import parse_query_model_to_object, parse_url_params

app = PyonirApp(__file__)
test_files_dir = '/Users/hypermac/dev/pyonir/pyonir/tests/contents/pages'
query = BaseFSQuery(test_files_dir)

def test_generic_model():
    query_params = parse_url_params('where_key=file_name:=profile&model=name,avatar,uid')
    modelstr = 'name,avatar,uid'
    fspath = '/Users/hypermac/dev/finddibs/find_dibs_app_data_stores/users'
    model = GenericQueryModel(modelstr)
    collection = BaseFSQuery(fspath, app_ctx=app.app_ctx, model=model)
    cfp = collection.set_params(query_params).paginated_collection()
    item = cfp.items[0]
    assert cfp is not None
    assert hasattr(item, 'name')
    assert hasattr(item, 'avatar')
    assert hasattr(item, 'uid')
    pass

def test_init():
    assert query.order_by == 'file_created_on'
    assert query.limit == 0
    assert query.max_count == 0
    assert query.curr_page == 0
    assert query.page_nums is None
    assert query.where_key is None
    assert query.sorted_files is None

def test_set_params():
    params = {
        'order_by': 'file_name',
        'limit': '10',
        'curr_page': '1',
        'max_count': '100'
    }
    query.set_params(params)
    assert query.order_by == 'file_name'
    assert query.limit == 10
    assert query.curr_page == 1
    assert query.max_count == 100

def test_paginated_collection():
    query.limit = 2
    query.curr_page = 1
    pagination = query.paginated_collection()

    assert isinstance(pagination, BasePagination)
    assert pagination.limit == 2
    assert pagination.curr_page == 1
    assert len(pagination.items) <= query.limit

def test_where_filter():
    # Test filtering by file name
    results = list(query.where('file_name', 'contains', 'index'))
    assert all('index' in file.file_name.lower() for file in results)

def test_prev_next():
    # Create a test file
    test_file = DeserializeFile(os.path.join(test_files_dir,"index.md"))
    result = BaseFSQuery.prev_next(test_file)

    assert hasattr(result, 'next')
    assert hasattr(result, 'prev')

def test_parse_params():
    # Test various parameter parsing cases
    assert BaseFSQuery.parse_params("name:value") == {"attr": "name", "op": "=", "value": "value"}
    assert BaseFSQuery.parse_params("age:>18") == {"attr": "age", "op": ">", "value": "18"}
    assert BaseFSQuery.parse_params("price:<=100") == {"attr": "price", "op": "<=", "value": "100"}