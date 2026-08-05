# Backend

The `backend` directory contains the Python code that powers your Pyonir application.

Use this directory for application logic, including:

* Route handlers
* Database connections
* Business logic
* Services
* Data models
* Utility functions
* Custom integrations

Pyonir does not require a specific backend structure. Organize your Python modules based on your application's needs.

---

## Recommended Structure

```text
backend/
├── __init__.py
├── routes/
│   └── users.py
├── models/
│   └── user.py
├── services/
│   └── email.py
├── database/
│   └── connection.py
└── utils/
    └── helpers.py
```
