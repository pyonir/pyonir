from abc import ABC
from typing import Optional

import pytest, os

from pyonir import Pyonir, BaseSchema
from pyonir.core.database import PyonirDatabaseService, CollectionQuery
from pyonir.core.authorizer import RequestInput
from pyonir.core.parser import DeserializeFile

app_setup_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'libs', 'app_setup')

class PyonirMockRole(BaseSchema, table_name='roles_table', primary_key='rid'):
    rid: str = BaseSchema.generate_id
    name: str

    @classmethod
    def from_value(cls, value):
        return cls(**{"name":value})

class PyonirMockUser(BaseSchema, table_name='pyonir_users', primary_key='uid', foreign_keys={PyonirMockRole}, fk_options={"role": {"ondelete": "RESTRICT", "onupdate": "RESTRICT"}}):
    username: str
    email: str
    gender: Optional[str] = "godly"
    uid: str = BaseSchema.generate_id
    role: PyonirMockRole = lambda: PyonirMockRole(value="pythonista")


class PyonirMockDataBaseService(PyonirDatabaseService, ABC):

    name = "test_data_service"
    version = "0.1.0"
    endpoint = "/testdata"

    def __init__(self, app):
        super().__init__(app)


class PyonirMocks:
    """Class to hold mock data for tests."""
    DatabaseService = PyonirMockDataBaseService
    App = Pyonir
    user_data = {
        "auth_from": "basic",
        "avatar": "avatar.jpg?t=1761745512",
        "about_you": "Blessed and Highly Favored",
        "age": 0,
        "first_name": "Fine",
        "last_name": "Pyonista",
        "gender": "",
        "height": 0,
        "weight": 0,
        "phone": "",
        "email": "pyonir@site.com",
        "role": {"name": "pythonista"},
        "username": "pyonir",
        "password": "123",
        "profile_splash": None,
        "uid": "NDYzZjBhNTUwYjQ2",
        "verified_email": False
    }


@pytest.fixture
def request_input():
    """Provide a RequestInput instance matching the test module's usage.

    This constructs the object the same way you had in `test_user.py`:
    RequestInput(**valid_credentials)
    """
    creds = {"email": "test@example.com", "password": "secure123", "flow": "session"}
    return RequestInput(**creds)


@pytest.fixture(scope="session")
def test_pyonir_db(test_app) -> PyonirMockDataBaseService:
    """
    Session-scoped fixture providing a global mock database service.
    Other test modules can simply request `test_pyonir_db` to reuse this instance.
    """
    db = (PyonirMockDataBaseService(test_app)
          .set_driver("sqlite").set_dbname("test_pyonir"))
    yield db

    db.destroy()

@pytest.fixture(scope="session")
def test_app():
    """
    Session-scoped fixture providing a global Pyonir test app.
    Other test modules can simply request `test_app` to reuse this instance.
    """
    app = Pyonir(os.path.join(app_setup_path, 'main.py'), use_themes=False)
    app.env.add('app.datastore_dirpath', os.path.join(app.app_dirpath))

    yield app

@pytest.fixture(scope="session")
def mock_collection(test_app):
    """Provide mock data for tests from the package init module."""
    return CollectionQuery(test_app.pages_dirpath)

@pytest.fixture(scope="session")
def mock_file():
    """Provide mock data for tests from the package init module."""
    return DeserializeFile(os.path.join(app_setup_path,'contents', 'pages', 'test.md'))

@pytest.fixture(scope="session")
def mock_data():
    """Provide mock data for tests from the package init module."""
    return PyonirMocks.user_data
