import os
from pyonir.tests.conftest import PyonirMocks, PyonirMockUser, PyonirMockRole, PyonirMockRoles


def test_crud_operations(test_pyonir_db: PyonirMocks.DatabaseService):
    # Create
    from_db_data = {
        'created_by': 'pyonir_system',
        'created_on': '2026-02-12 07:44:04.529264+00:00',
        'email': 'mocks@pyonir.dev',
        'gender': 'binary(literally)',
        'role': '{"created_on":"2026-02-12 07:44:11.195533+00:00","name":"pythonista","rid":"f69482429b65446d9e24cee6723d4fcf","created_by":"pyonir_system"}',
        'uid': '959111dad9184541914cc6beb0ba633f',
        'username': 'pyonir'
    }
    test_pyonir_db.connect()
    mock_user = PyonirMockUser(**PyonirMocks.user_data)
    test_pyonir_db.build_table_from_model(mock_user)
    mock_role = PyonirMockUser(**from_db_data)
    table_name = mock_user.__table_name__
    table_key = mock_user.__primary_key__
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

def test_lookup_tables(test_app: PyonirMocks.App, test_pyonir_db: PyonirMocks.DatabaseService):
    test_pyonir_db.build_fs_dirs_from_model(PyonirMockRole)

    req_data = {'email': 'fileuser@example.com', 'gender': None, 'role': PyonirMockRoles.GUEST_TESTER.name, 'username': 'fileuser'}
    req_user = PyonirMockUser(**req_data)
    req_user.save_to_file(file_path=os.path.join(test_pyonir_db.datastore_path, req_user.__table_name__, "user.json"))

    req_user.role = PyonirMockRoles.ADMIN_TESTER
    req_user.save_to_file(file_path=os.path.join(test_pyonir_db.datastore_path, req_user.__table_name__, "user.json"))

def test_save_to_file_simple(test_app: PyonirMocks.App, test_pyonir_db: PyonirMocks.DatabaseService):
    temp_datastore = test_pyonir_db.datastore_path

    user = PyonirMockUser(username="fileuser", email="fileuser@example.com", role=PyonirMockRole(name="guest_tester"))

    file_path = os.path.join(temp_datastore, user.__table_name__, "user.json")
    result = user.save_to_file(file_path)
    udata = PyonirMockUser.from_file(file_path, test_app.app_ctx)

    assert result
    assert os.path.exists(file_path)
    assert udata.username == user.username
    assert udata.email == user.email
    assert udata.role.name == user.role.name

    user._file_path = file_path
    user.role = PyonirMockRoles.ADMIN_TESTER
    user.save_to_file()
    udata = PyonirMockUser.from_file(file_path, test_app.app_ctx)

    assert udata.role.name == user.role.name
