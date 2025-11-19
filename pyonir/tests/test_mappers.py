from dataclasses import dataclass

import os, uuid
from typing import Optional, Union, List, Dict
from datetime import datetime

from pyonir import PyonirRequest, Pyonir
from pyonir.core.schemas import BaseSchema, GenericQueryModel

from pyonir.core.mapper import cls_mapper, dict_to_class
from pyonir.core.parser import DeserializeFile
from pyonir.core.utils import parse_query_model_to_object
from pyonir.libs.plugins.navigation import Menu


# ==== Sample classes to map into ====

class MockAddress:

    def __init__(self,
                 street: str,
                 zip_code: Optional[int] = None):
        self.street = street
        self.zip_code = zip_code

class MockUser:

    def __init__(self,
                 uid: int,
                 name: str,
                 email: Optional[str],
                 address: Optional[MockAddress],
                 tags: List[str],
                 meta: Dict[str, Union[str, int]]):
        self.uid = uid
        self.name = name
        self.email = email
        self.address = address
        self.tags = tags
        self.meta = meta

@dataclass
class Article:
    """Article model for testing cls_mapper with custom aliasing."""
    __alias__ = {'id': 'file_name', 'caption': 'content'}
    __frozen__ = True
    title: str
    caption: str
    alt: str
    # default factory functions called when no value provided
    id: str = uuid.uuid4
    created_on: datetime = datetime.now
    last_updated: datetime = datetime.now

article_filepath = os.path.join(os.path.dirname(__file__), 'contents', 'article.md')
# ==== Tests ====
def test_request_mapper():

    def demo_route(user_id: int, request: PyonirRequest):
        pass
    from pyonir.core.mapper import func_request_mapper
    app = Pyonir(__file__)
    pyonir_request = PyonirRequest(None, app)
    pyonir_request.path_params = dict_to_class({'user_id': '42'})
    pyonir_request.query_params = dict_to_class({})
    args = func_request_mapper(demo_route, pyonir_request)
    pass

def test_cls_mapper_menu():
    data = {
        'menu': {
            'url': '/home',
            'slug': 'home',
            'title': 'Home',
            'group': 'main',
            'rank': 1,
            'status': 'active'
        }
    }
    menu_obj = cls_mapper(data, Menu)
    assert isinstance(menu_obj, Menu)
    assert menu_obj.url == '/home'
    assert menu_obj.slug == 'home'
    assert menu_obj.title == 'Home'
    assert menu_obj.group == 'main'
    assert menu_obj.rank == 1
    assert menu_obj.status == 'active'
    assert menu_obj.name == 'Home'

def test_parsely_to_custom_mapping():
    obj = DeserializeFile(article_filepath)
    article = cls_mapper(obj, Article)
    assert isinstance(article, Article)
    assert article.id is not None
    assert article.caption == obj.data['content']


def test_no_hint_mapping():
    generic_model = GenericQueryModel('title,url,author,date:file_created_on')
    obj = {"title": "hunter", "author": "Alice", "url": "/foo", "date": None}
    genmodel = cls_mapper(obj, generic_model)
    assert genmodel.author == "Alice"
    assert genmodel.url == '/foo'

def test_scalar_mapping():
    obj = {"uid": "123", "name": "Alice", "email": None, "address": None, "tags": [], "meta": {}}
    user = cls_mapper(obj, MockUser)
    assert isinstance(user.uid, int)
    assert user.uid == 123
    assert user.name == "Alice"
    assert user.email is None

def test_optional_mapping():
    obj = {"id": 1, "name": "Bob", "email": "bob@test.com", "address": None, "tags": [], "meta": {}}
    user = cls_mapper(obj, MockUser)
    assert user.email == "bob@test.com"
    obj2 = {"id": 2, "name": "Charlie", "email": None, "address": None, "tags": [], "meta": {}}
    user2 = cls_mapper(obj2, MockUser)
    assert user2.email is None

def test_nested_object():
    addr = {"street": "Main St", "zip_code": "90210"}
    mock_address = cls_mapper(addr, MockAddress)
    obj = {
        "uid": 10, "name": "Diana", "email": "diana@test.com",
        "address": addr,
        "tags": ["admin", "staff"],
        "meta": {"age": "30", "score": 95}
    }
    user = cls_mapper(obj, MockUser)
    assert isinstance(user.address, MockAddress)
    assert user.address.street == "Main St"
    assert isinstance(user.address.zip_code, int)
    assert user.address.zip_code == 90210
    assert user.meta["score"] == 95  # int conversion
    assert user.meta["age"] == "30"  # str preserved

def test_list_mapping():
    obj = {
        "uid": 20, "name": "Eva", "email": None,
        "address": None,
        "tags": ["one", "two"],
        "meta": {}
    }
    user = cls_mapper(obj, MockUser)
    assert isinstance(user.tags, list)
    assert user.tags == ["one", "two"]

def test_dict_mapping_with_union():
    obj = {
        "uid": 30, "name": "Frank", "email": None,
        "address": None,
        "tags": [],
        "meta": {"age": 42, "nickname": "franky"}
    }
    user = cls_mapper(obj, MockUser)
    assert isinstance(user.meta["age"], int)
    assert isinstance(user.meta["nickname"], str)
