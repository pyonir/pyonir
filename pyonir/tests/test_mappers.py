import pytest, os
from typing import Optional, Union, List, Dict

from pyonir.models.mapper import cls_mapper
from pyonir.models.parser import DeserializeFile
from pyonir.utilities import parse_query_model_to_object


# ==== Sample classes to map into ====

class Address:
    street: str
    zip_code: Optional[int]

    def __init__(self, street: str, zip_code: Optional[int] = None):
        self.street = street
        self.zip_code = zip_code

class User:
    id: int
    name: str
    email: Optional[str]
    address: Optional[Address]
    tags: List[str]
    meta: Dict[str, Union[str, int]]

    def __init__(self, id: int, name: str, email: Optional[str],
                 address: Optional[Address], tags: List[str], meta: Dict[str, Union[str, int]]):
        self.id = id
        self.name = name
        self.email = email
        self.address = address
        self.tags = tags
        self.meta = meta

class Article:
    """a media post."""

    _orm_options = {'mapper': {'id': 'file_name', 'caption': 'content'},'frozen': True}
    """dict: Internal mapping of model fields to source attributes."""

    def __init__(self, caption: str = None, title: str = None, alt: str = None):
        from datetime import datetime
        import uuid
        self.title: str = title
        self.caption: str = caption
        self.alt: str = alt
        self.id: str = uuid.uuid4().hex
        self.created_on: datetime = datetime.now()
        self.last_updated: datetime = datetime.now()

generic_model = parse_query_model_to_object('title,url,author,date:file_created_on')
article_filepath = os.path.join(os.path.dirname(__file__), 'contents', 'article.md')
# ==== Tests ====

def test_parsely_to_custom_mapping():
    obj = DeserializeFile(article_filepath)
    article = cls_mapper(obj, Article)
    assert isinstance(article, Article)
    assert article.id is not None
    assert article.caption == obj.data['content']


def test_no_hint_mapping():
    obj = {"title": "hunter", "author": "Alice", "url": "/foo", "date": None}
    genmodel = cls_mapper(obj, generic_model)
    assert genmodel.author == "Alice"
    assert genmodel.url == '/foo'

def test_scalar_mapping():
    obj = {"id": "123", "name": "Alice", "email": None, "address": None, "tags": [], "meta": {}}
    user = cls_mapper(obj, User)
    assert isinstance(user.id, int)
    assert user.id == 123
    assert user.name == "Alice"
    assert user.email is None

def test_optional_mapping():
    obj = {"id": 1, "name": "Bob", "email": "bob@test.com", "address": None, "tags": [], "meta": {}}
    user = cls_mapper(obj, User)
    assert user.email == "bob@test.com"
    obj2 = {"id": 2, "name": "Charlie", "email": None, "address": None, "tags": [], "meta": {}}
    user2 = cls_mapper(obj2, User)
    assert user2.email is None

def test_nested_object():
    obj = {
        "id": 10, "name": "Diana", "email": "diana@test.com",
        "address": {"street": "Main St", "zip_code": "90210"},
        "tags": ["admin", "staff"],
        "meta": {"age": "30", "score": 95}
    }
    user = cls_mapper(obj, User)
    assert isinstance(user.address, Address)
    assert user.address.street == "Main St"
    assert isinstance(user.address.zip_code, int)
    assert user.address.zip_code == 90210
    assert user.meta["score"] == 95  # int conversion
    assert user.meta["age"] == "30"  # str preserved

def test_list_mapping():
    obj = {
        "id": 20, "name": "Eva", "email": None,
        "address": None,
        "tags": ["one", "two"],
        "meta": {}
    }
    user = cls_mapper(obj, User)
    assert isinstance(user.tags, list)
    assert user.tags == ["one", "two"]

def test_dict_mapping_with_union():
    obj = {
        "id": 30, "name": "Frank", "email": None,
        "address": None,
        "tags": [],
        "meta": {"age": 42, "nickname": "franky"}
    }
    user = cls_mapper(obj, User)
    assert isinstance(user.meta["age"], int)
    assert isinstance(user.meta["nickname"], str)
