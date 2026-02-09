import os

from pyonir.core.database import CollectionQuery, BasePagination
from pyonir.core.parser import DeserializeFile
from pyonir.core.utils import parse_url_params

def test_generic_model(test_app, mock_collection):
    query_params = parse_url_params('where_key=file_name:=test&model=title,url,content')
    cfp = mock_collection.set_params(query_params).paginated_collection()
    item = cfp.items[0]
    assert cfp is not None
    pass

def test_init(test_app, mock_collection):
    assert mock_collection.order_by == 'file_created_on'
    assert mock_collection.limit == 0
    assert mock_collection.max_count == 1
    assert mock_collection.curr_page == 0
    assert mock_collection.page_nums is None
    assert mock_collection.where_key == 'file_name:=test'

def test_set_params(test_app, mock_collection):
    params = {
        'order_by': 'file_name',
        'limit': '10',
        'curr_page': '1',
        'max_count': '100'
    }
    mock_collection.set_params(params)
    assert mock_collection.order_by == 'file_name'
    assert mock_collection.limit == 10
    assert mock_collection.curr_page == 1
    assert mock_collection.max_count == 100

def test_paginated_collection(test_app, mock_collection):
    mock_collection.limit = 2
    mock_collection.curr_page = 1
    pagination = mock_collection.paginated_collection()

    assert isinstance(pagination, BasePagination)
    assert pagination.limit == 2
    assert pagination.curr_page == 1
    assert len(pagination.items) <= mock_collection.limit

def test_where_filter(test_app, mock_collection):
    # Test filtering by file name
    results = list(mock_collection.where('file_name', 'contains', 'index'))
    assert all('index' in file.file_name.lower() for file in results)

def test_prev_next(test_app):
    # Create a test file
    test_file = DeserializeFile(os.path.join(test_app.pages_dirpath, "index.md"))
    result = CollectionQuery.prev_next(test_file)

    assert hasattr(result, 'next')
    assert hasattr(result, 'prev')

def test_parse_params(test_app):
    # Test various parameter parsing cases
    assert CollectionQuery.parse_params("name:value") == {"attr": "name", "op": "=", "value": "value"}
    assert CollectionQuery.parse_params("age:>18") == {"attr": "age", "op": ">", "value": "18"}
    assert CollectionQuery.parse_params("price:<=100") == {"attr": "price", "op": "<=", "value": "100"}