import os
import shutil

from pyonir.tests.conftest import PyonirMocks, PyonirMockUser, PyonirMockRole


def test_crud_operations(test_pyonir_db: PyonirMocks.DatabaseService):
    # Create
    test_pyonir_db.connect()
    mock_user = PyonirMockUser(**PyonirMocks.user_data)
    table_name = mock_user.__table_name__
    table_key = mock_user.__primary_key__
    test_pyonir_db.build_table_from_model(mock_user)
    user_id = test_pyonir_db.insert(mock_user)
    assert user_id

    # Read
    results: PyonirMockUser = next(test_pyonir_db.find(PyonirMockUser, {'where': f"{table_key} = '{user_id}'"}))
    assert (isinstance(results, PyonirMockUser))
    assert (results.username == mock_user.username)
    assert (results.email == mock_user.email)
    assert (results.role.rid == mock_user.role.rid)

    # Verify foreign key role
    mock_role_results = next(test_pyonir_db.find(PyonirMockRole, {'where': f"rid = '{mock_user.role.rid}'"}))
    assert (isinstance(mock_role_results, PyonirMockRole))
    assert (mock_role_results.name == mock_user.role.name)

    # Update
    updated = test_pyonir_db.update(table_name, user_id, {
        "username": "newusername",
        "email": "newemail@example.com"
    })
    assert updated

    test_pyonir_db.add_table_columns(table_name, {
        "age": "INTEGER DEFAULT 0"
    })

    # Verify update
    results = next(test_pyonir_db.find(PyonirMockUser, {'where': f"{table_key} = '{user_id}'"}))
    assert (results.username == "newusername")
    assert (results.email == "newemail@example.com")
    # assert (results.age == 0)

    # Delete
    deleted = test_pyonir_db.delete(mock_user, {'where': f"{table_key} = '{user_id}'"})
    assert deleted

    # Verify deletion
    results = list(test_pyonir_db.find(PyonirMockUser, {'where': f"{table_key} = '{user_id}'"}))
    assert (len(results) == 0)

    test_pyonir_db.disconnect()
    test_pyonir_db.destroy()
    assert not test_pyonir_db.exists()

def test_save_to_file_simple(test_app: PyonirMocks.App):
    user = PyonirMockUser(username="fileuser", email="fileuser@example.com", role=PyonirMockRole(name="pythonista"))
    temp_datastore = os.path.join(test_app.app_dirpath,'tmp_store')
    test_app.env.add('app.datastore_dirpath', temp_datastore)
    file_path = os.path.join(temp_datastore, user.__table_name__, "user.json")
    result = user.save_to_file(file_path)
    udata = PyonirMockUser.from_file(file_path, test_app.app_ctx)
    assert result
    assert os.path.exists(file_path)
    assert udata.username == user.username
    assert udata.email == user.email
    assert udata.role.name == user.role.name
    shutil.rmtree(temp_datastore)