import os
from abc import ABC

from typing import Optional, Type
import shutil
import json

from pyonir import Pyonir
from pyonir.core.schemas import BaseSchema
from pyonir.core.database import PyonirDatabaseService

class MockRole(BaseSchema, table_name='roles_table', primary_key='rid'):
    rid: str = BaseSchema.generate_id
    value: str

class MockUser(BaseSchema, table_name='pyonir_users', primary_key='uid', foreign_keys={MockRole}, fk_options={"role": {"ondelete": "RESTRICT", "onupdate": "RESTRICT"}}):
    username: str
    email: str
    gender: Optional[str] = "godly"
    uid: str = BaseSchema.generate_id
    role: MockRole = lambda: MockRole(value="pythonista")


class MockDataService(PyonirDatabaseService, ABC):

    name = "test_data_service"
    version = "0.1.0"
    endpoint = "/testdata"

    def delete(self, table: str, id: int) -> bool:
        if self.driver == "sqlite":
            pk = self.get_pk(table)
            cursor = self.connection.cursor()
            cursor.execute(f"DELETE FROM {table} WHERE {pk} = ?", (id,))
            self.connection.commit()
            return cursor.rowcount > 0
        return False

app = Pyonir(__file__, False)  # Placeholder for PyonirApp instance
temp_datastore = os.path.join(app.app_dirpath,'tmp_store')
os.makedirs(temp_datastore, exist_ok=True)
app.env.datastore_dirpath = temp_datastore
db = (MockDataService(app)
        .set_driver("sqlite").set_dbname("pyonir_test"))

def test_crud_operations():
    # Create
    db.connect()
    mock_user = MockUser(username="testuser", email="test@example.com")
    table_name = mock_user.__table_name__
    table_key = mock_user.__primary_key__
    db.build_table_from_model(mock_user)
    user_id = db.insert(mock_user)
    assert user_id

    # Read
    results = db.find(table_name, {table_key: user_id})
    mock_role_results = db.find(mock_user.role.__table_name__, {"rid": mock_user.role.rid})
    assert (len(results) == 1)
    assert (results[0]["username"] == "testuser")
    assert (results[0]["email"] == "test@example.com")
    assert (results[0]["role"] == mock_user.role.rid)
    # Verify foreign key role
    assert (len(mock_role_results) == 1)
    assert (mock_role_results[0]["value"] == mock_user.role.value)

    # Update
    updated = db.update(table_name, user_id, {
        "username": "newusername",
        "email": "newemail@example.com"
    })
    assert updated

    db.add_table_columns(table_name, {
        "age": "INTEGER DEFAULT 0"
    })

    # Verify update
    results = db.find(table_name, {table_key: user_id})
    assert (results[0]["username"] == "newusername")
    assert (results[0]["email"] == "newemail@example.com")
    assert (results[0]["age"] == 0)

    # Delete
    deleted = db.delete(table_name, user_id)
    assert deleted

    # Verify deletion
    results = db.find(table_name, {table_key: user_id})
    assert (len(results) == 0)

    db.disconnect()
    db.destroy()
    assert not db.exists()

def test_save_to_file_simple():
    user = MockUser(username="fileuser", email="fileuser@example.com")
    file_path = os.path.join(temp_datastore, user.__table_name__, "user.json")
    result = user.save_to_file(file_path)
    assert result
    assert os.path.exists(file_path)
    with open(file_path, "r") as f:
        data = json.load(f)
    assert data["username"] == "fileuser"
    assert data["email"] == "fileuser@example.com"
    shutil.rmtree(temp_datastore)