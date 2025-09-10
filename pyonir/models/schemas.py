import uuid
from datetime import datetime
from typing import Type, TypeVar, Dict, Iterable, Any

from sqlmodel import SQLModel
from sqlmodel.main import SQLModelMetaclass

from pyonir.utilities import deserialize_datestr

T = TypeVar("T")
class SchemaTable(SQLModelMetaclass):
    def __new__(cls, name, bases, namespace, **kwargs):
        # Grab frozen option (default False)
        is_frozen = kwargs.pop("frozen", None)
        is_frozen = is_frozen if is_frozen is not None else False

        # Build default model_config
        default_config = {
            "frozen": is_frozen,
            "from_attributes": False if is_frozen else True,
            "extra": "forbid" if is_frozen else "allow",
        }

        # Allow per-model override via namespace or kwargs
        user_config = namespace.pop("model_config", {})
        merged_config = {**default_config, **user_config}

        # Build the class
        new_cls = super().__new__(cls, name, bases, namespace, **kwargs)

        # Attach the merged config
        setattr(new_cls, "model_config", merged_config)

        return new_cls

class BaseSchema(SQLModel, metaclass=SchemaTable):
    """
    Interface for immutable dataclass models with CRUD and session support.
    """
    _errors: list[dict[str, Any]]

    def model_post_init(self, __context):
        object.__setattr__(self, "_errors", [])
        self.validate_fields()

    def __post_init__(self):
        self._errors = []
        self.validate_fields()


    def save_to_file(self, file_path: str) -> bool:
        """Saves the user data to a file in JSON format"""
        from pyonir.models.utils import create_file
        return create_file(file_path, self.to_dict(obfuscate=False))

    def save_to_session(self, request: 'PyonirRequest', key: str = None, value: any = None) -> None:
        """Convert instance to a serializable dict."""
        request.server_request.session[key or self.__class__.__name__.lower()] = value

    def to_dict(self, obfuscate = True):
        """Dictionary representing the instance"""

        obfuscated = lambda attr: obfuscate and hasattr(self,'_private_keys') and attr in (self._private_keys or [])
        is_ignored = lambda attr: attr.startswith("_") or callable(getattr(self, attr)) or obfuscated(attr)
        def process_value(key, value):
            if hasattr(value, 'to_dict'):
                return value.to_dict(obfuscate=obfuscate)
            if isinstance(value, property):
                return getattr(self, key)
            if isinstance(value, (tuple, list, set)):
                return [process_value(key, v) for v in value]
            return value
        fields = self.__class__.model_fields.keys() if hasattr(self.__class__, 'model_fields') else dir(self)
        return {key: process_value(key, getattr(self, key)) for key in fields if not is_ignored(key) and not obfuscated(key)}

    def to_json(self, obfuscate = True) -> str:
        """Returns a JSON serializable dictionary"""
        import json
        return json.dumps(self.to_dict(obfuscate))

    def is_valid(self) -> bool:
        """Returns True if there are no validation errors."""
        return not self._errors

    def validate_fields(self, field_name: str = None):
        """
        Validates fields by calling `validate_<fieldname>()` if defined.
        Clears previous errors on every call.
        """
        if field_name is not None:
            validator_fn = getattr(self, f"validate_{field_name}", None)
            if callable(validator_fn):
                validator_fn()
            return
        for name in self.__dict__.keys():
            if name.startswith("_"):
                continue
            validator_fn = getattr(self, f"validate_{name}", None)
            if callable(validator_fn):
                validator_fn()

    @classmethod
    def from_file(cls: Type[T], file_path: str, app_ctx=None) -> T:
        """Create an instance from a file path."""
        from pyonir.models.parser import DeserializeFile
        from pyonir.models.mapper import cls_mapper
        prsfile = DeserializeFile(file_path, app_ctx=app_ctx)
        return cls_mapper(prsfile, cls)

    @staticmethod
    def generate_date(date_value: str = None) -> datetime:
        return deserialize_datestr(date_value or datetime.now())

    @staticmethod
    def generate_id():
        return uuid.uuid4().hex