import os
from datetime import datetime
from typing import Optional

from sqlmodel import Field

from pyonir import PyonirApp
from pyonir.models.schemas import BaseSchema
from pyonir.models.database import DatabaseService


class User(BaseSchema, table_name='pyonir_users', primary_key='uid'):
    username: str
    email: str
    created_at: datetime = datetime.now()
    uid: str = Field(default_factory=BaseSchema.generate_id, primary_key=False)


class MockDataService(DatabaseService):

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

    def insert(self, table: str, entity: User) -> int:
        return super().insert(table, entity)

    def find(self, entity_cls: BaseSchema, filter: dict = None) -> list:
        return super().find(entity_cls, filter)

    def update(self, table: str, id: int, data: dict) -> bool:
        if self.driver == "sqlite":
            set_clause = ', '.join(f"{k} = ?" for k in data.keys())
            query = f"UPDATE {table} SET {set_clause} WHERE id = {id}"
            values = list(data.values()) #+ [id]
            cursor = self.connection.cursor()
            cursor.execute(query, values)
            self.connection.commit()
            return cursor.rowcount > 0
        return False

    def delete(self, table: str, id: int) -> bool:
        if self.driver == "sqlite":
            cursor = self.connection.cursor()
            cursor.execute(f"DELETE FROM {table} WHERE id = ?", (id,))
            self.connection.commit()
            return cursor.rowcount > 0
        return False


app = PyonirApp(__file__, False)  # Placeholder for PyonirApp instance
db = (MockDataService(app, "pyonir_test.db")
        .set_driver("sqlite").set_database())

def test_crud_operations():
    # Create
    db.connect()
    user = User(username="testuser", email="test@example.com")
    table_name = User.__tablename__
    db.create_table(user.generate_sql())
    user_id = db.insert(table_name, user)
    assert user_id

    # Read
    results = db.find(table_name, {"id": user_id})
    assert (len(results) == 1)
    assert (results[0]["username"] == "testuser")
    assert (results[0]["email"] == "test@example.com")

    # Update
    updated = db.update(table_name, user_id, {
        "username": "newusername",
        "email": "newemail@example.com"
    })
    assert updated

    # Verify update
    results = db.find(table_name, {"id": user_id})
    assert (results[0]["username"] == "newusername")
    assert (results[0]["email"] == "newemail@example.com")

    # Delete
    deleted = db.delete(table_name, user_id)
    assert (deleted)

    # Verify deletion
    results = db.find(table_name, {"id": user_id})
    assert (len(results) == 0)

    db.disconnect()
    db.destroy()
    assert not os.path.exists(db.database)