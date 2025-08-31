import uuid
from datetime import datetime
from typing import Type, TypeVar, Dict

from pyonir.utilities import json_serial, deserialize_datestr

T = TypeVar("T")
class BaseSchema:
    """
    Interface for immutable dataclass models with CRUD and session support.
    Provides per-instance validation and session helpers.
    _private_keys - list of field names to be hidden publically
    """

    def __init__(self):
        # Each instance gets its own validation error list
        self._errors: list[str] = []
        self._deleted: bool = False
        self._private_keys: list[str] = []

    @staticmethod
    def generate_date(date_value: str = None) -> datetime:
        return deserialize_datestr(date_value or datetime.now())

    @staticmethod
    def generate_id():
        return uuid.uuid4().hex

    def is_valid(self) -> bool:
        """Returns True if there are no validation errors."""
        return not self._errors

    def validate(self):
        """
        Validates fields by calling `validate_<fieldname>()` if defined.
        Clears previous errors on every call.
        """
        for name in self.__dict__.keys():
            if name.startswith("_"):
                continue
            validator_fn = getattr(self, f"validate_{name}", None)
            if callable(validator_fn):
                validator_fn()

    def __post_init__(self):
        """
        Called automatically in dataclasses after initialization.
        Ensures validation runs for each instance.
        """
        # Reset errors for new instance
        self._errors = []
        self.validate()

    # --- Database helpers ---
    def save_to_file(self, file_path: str) -> bool:
        """Saves the user data to a file in JSON format"""
        from pyonir.utilities import create_file
        return create_file(file_path, self.to_dict(obfuscate=False))

    def save_to_session(self, request: 'PyonirRequest', key: str = None, value: any = None) -> None:
        """Convert instance to a serializable dict."""
        request.server_request.session[key or self.__class__.__name__.lower()] = value

    @classmethod
    def create(cls: Type[T], **data) -> T:
        """Create and return a new instance (validation runs in __post_init__)."""
        instance = cls(**data)
        return instance

    @classmethod
    def from_file(cls: Type[T], file_path: str, app_ctx) -> T:
        """Create an instance from a file path."""
        from pyonir.parser import Parsely
        parsely = Parsely(file_path, app_ctx=app_ctx)
        return parsely.map_to_model(cls)

    @classmethod
    def from_dict(cls, data: Dict) -> 'BaseSchema':
        """Instantiate entity from dict."""
        from pyonir.parser import Parsely
        values = data if isinstance(data, dict) else data.data if isinstance(data, Parsely) else data
        return cls(**values)

    @classmethod
    def create_table(cls) -> str:
        """Return SQL query to create the table for this entity."""
        columns = []
        for attr, typ in cls.__annotations__.items():
            if typ == str:
                columns.append(f"{attr} TEXT")
            elif typ == int:
                columns.append(f"{attr} INTEGER")
            else:
                columns.append(f"{attr} TEXT")  # fallback
        columns_sql = ", ".join(columns)
        return f"CREATE TABLE IF NOT EXISTS {cls.__name__.lower()} (id INTEGER PRIMARY KEY AUTOINCREMENT, {columns_sql})"



    def to_dict(self, obfuscate = True):
        """Returns the instance as a dict"""
        def process_value(key, value):
            if obfuscate and hasattr(self,'_private_keys') and key in self._private_keys:
                return '***'
            if hasattr(value, 'to_dict'):
                return value.to_dict(obfuscate=obfuscate)
            return value
        return {key: process_value(key,value) for key, value in self.__dict__.items() if key[0] != '_'}

    def to_json(self, obfuscate = True) -> str:
        """Returns the user data as a JSON serializable dictionary"""
        from pyonir.utilities import json_serial
        import json
        return json.dumps(self.to_dict(obfuscate))
