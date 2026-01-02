import os

from typing import Optional, Type
import shutil
import json

from pyonir import Pyonir
from pyonir.core.schemas import BaseSchema
from pyonir.core.database import DatabaseService

class MockRole(BaseSchema, table_name='roles_table', primary_key='rid'):
    rid: str = BaseSchema.generate_id
    value: str

class MockUser(BaseSchema, table_name='pyonir_users', primary_key='uid', foreign_keys={MockRole}):
    username: str
    email: str
    uid: str = BaseSchema.generate_id
    role: MockRole = lambda: MockRole(value="pythonista")


class MockDataService(DatabaseService):

    def create_table_from_model(self, model: Type[BaseSchema]) -> 'DatabaseService':
        pass

    name = "test_data_service"
    version = "0.1.0"
    endpoint = "/testdata"

    def create_table(self, sql_create: str) -> 'DatabaseService':
        return super().create_table(sql_create)

    def destroy(self):
        super().destroy()

    def connect(self) -> None:
        super().connect()

    def disconnect(self) -> None:
        super().disconnect()

    def insert(self, table: str, entity: MockUser) -> int:
        return super().insert(table, entity)

    def find(self, table: str, filter: dict = None) -> list:
        return super().find(table, filter)

    def update(self, table: str, id: int, data: dict) -> bool:
        if self.driver == "sqlite":
            pk = self.get_pk(table)
            set_clause = ', '.join(f"{k} = ?" for k in data.keys())
            query = f"UPDATE {table} SET {set_clause} WHERE {pk} = ?"
            values = list(data.values()) + [id]
            cursor = self.connection.cursor()
            cursor.execute(query, values)
            self.connection.commit()
            return cursor.rowcount > 0
        return False

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
app.env.data_dirpath = temp_datastore
db = (MockDataService(app, "pyonir_test.db")
        .set_driver("sqlite").set_database(os.path.join(app.app_dirpath,'tmp_store')))

def test_crud_operations():
    # Create
    db.connect()
    mock_user = MockUser(username="testuser", email="test@example.com")
    table_name = mock_user.__table_name__
    table_key = mock_user.__primary_key__
    db.create_table(mock_user._sql_create_table)
    user_id = db.insert(table_name, mock_user)
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
    assert not os.path.exists(db.database)

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