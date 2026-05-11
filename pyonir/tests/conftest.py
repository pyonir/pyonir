import shutil
from abc import ABC
from typing import Optional

import pytest, os

from pyonir import Pyonir, BaseSchema, PyonirRequest
from pyonir.core.database import PyonirDatabaseService, CollectionQuery
from pyonir.core.server import PyonirRequestInput
from pyonir.core.parser import DeserializeFile

app_setup_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'libs', 'app_setup')
user_meta_data = {
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
    "username": "pyonir",
    "password": "123",
}
user_data = {
    "gender": "binary(literally)",
    "role": "pythonista",
    "email": "mocks@pyonir.dev",
    "username": "pyonir",
    "password": "123abc",
    "name": "pyonir"
}

class PyonirMockRole(BaseSchema, table_name='roles_table', primary_key='rid', lookup_table='name'):
    rid: str = lambda : BaseSchema.generate_uuid()
    name: str

    @classmethod
    def sql_after_create(cls, dbc: PyonirDatabaseService):
        """Sets up the database with the role's permissions"""
        for role in PyonirMockRoles.all():
            _file_dirpath = str(os.path.join(dbc.datastore_path, role.__table_name__))
            role._file_path = os.path.join(_file_dirpath, role.name+'.json')
            dbc.insert(role)
            if not os.path.exists(role.file_path):
                role.save_to_file()

    @classmethod
    def from_value(cls, value: any):
        if isinstance(value, DeserializeFile):
            value = value.data
        if callable(value):
            return value()
        return cls(**{"name":value}) if isinstance(value, str) else cls(**value)

class PyonirMockRoles:
    GUEST_TESTER = PyonirMockRole(name='guest_tester')
    ADMIN_TESTER = PyonirMockRole(name='admin_tester')

    @classmethod
    def all(cls):
        return [role for role in vars(cls).values() if isinstance(role, PyonirMockRole)]

class PyonirMockStatus(BaseSchema, table_name='statuses_table', primary_key='sid', lookup_table='name'):
    sid: str = BaseSchema.generate_uuid
    name: str = lambda : "unknown"

    @classmethod
    def sql_after_create(cls, dbc: 'PyonirDatabaseService'):
        """Sets up the database with the status entries"""
        for status in PyonirMockStatuses.all():
            _file_dirpath = str(os.path.join(dbc.datastore_path, status.__table_name__))
            status._file_path = os.path.join(_file_dirpath, status.name+'.json')
            if not os.path.exists(status.file_path):
                status.save_to_file()

class PyonirMockStatuses:
    ACTIVE = PyonirMockStatus(name='active')
    INACTIVE = PyonirMockStatus(name='inactive')
    BANNED = PyonirMockStatus(name='banned')

    @classmethod
    def all(cls):
        return [status for status in vars(cls).values() if isinstance(status, PyonirMockStatus)]

class PyonirMockUser(BaseSchema, table_name='pyonir_users', primary_key='uid', foreign_keys={PyonirMockRole}, fk_options={"role": {"ondelete": "RESTRICT", "onupdate": "RESTRICT"}}):
    uid: str = BaseSchema.generate_uuid
    username: str
    email: str
    gender: Optional[str] = "godly"
    role: PyonirMockRole = lambda: PyonirMockRole(name="pythonista")
    status: PyonirMockStatus = lambda: PyonirMockStatuses.BANNED


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
    user_data = user_data
    user_meta_data = user_meta_data


@pytest.fixture
def request_input():
    """Provide a PyonirRequestInput instance matching the test module's usage.

    This constructs the object the same way you had in `test_user.py`:
    PyonirRequestInput(**valid_credentials)
    """
    creds = {"email": "test@example.com", "password": "secure123", "flow": "session"}
    return PyonirRequestInput(**creds)


def pytest_configure(config):
    config.option.asyncio_mode = "auto"

async def mock_request(
    test_app,
    method: str = "GET",
    path: str = "/",
    headers: dict | None = None,
    query: dict | None = None,
    body: dict | bytes | None = None,
    session: dict | bytes | None = None,
) -> PyonirRequest:
    from starlette.requests import Request as StarletteRequest
    import json
    from urllib.parse import urlencode

    csrf_config = {'csrf_secret': 'test_secret', 'csrf_field_name': 'csrf_token'}
    if isinstance(body, dict):
        body_bytes = json.dumps({**body}).encode()
    elif isinstance(body, bytes):
        body_bytes = body
    else:
        body_bytes = b""

    async def receive():
        return {
            "type": "http.request",
            "body": body_bytes,
            "more_body": False,
        }

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "path": path,
        "scheme": "http",
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
        "headers": [
            (k.lower().encode(), v.encode())
            for k, v in (headers or {}).items()
        ],
        "state":{"csrf_config": csrf_config},
        "query_string": urlencode(query or {}).encode(),
        "session": session or {},
    }

    req = PyonirRequest(StarletteRequest(scope, receive), test_app)
    await req.set_request_input()
    return req

@pytest.fixture(scope="module")
def test_pyonir_db(test_app) -> PyonirMockDataBaseService:
    """
    Session-scoped fixture providing a global mock database service.
    Other test modules can simply request `test_pyonir_db` to reuse this instance.
    """
    db = (PyonirMockDataBaseService(test_app)
          .set_driver("sqlite").set_dbname("test_pyonir"))
    db.build_fs_dirs_from_model(PyonirMockRole)
    yield db

    db.destroy()
    shutil.rmtree(db.datastore_path)

@pytest.fixture(scope="session")
def test_app():
    """
    Session-scoped fixture providing a global Pyonir test app.
    Other test modules can simply request `test_app` to reuse this instance.
    """
    app = Pyonir(os.path.join(app_setup_path, 'main.py'), use_themes=False)
    app.env.add('app.datastore_dirpath', os.path.join(app.app_dirpath, 'test_pyonir_datastore'))

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
