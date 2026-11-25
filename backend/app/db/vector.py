"""Minimal pgvector text binding; values remain SQL parameters."""

import json

from sqlalchemy.dialects.postgresql.base import ischema_names
from sqlalchemy.types import UserDefinedType


class Vector(UserDefinedType):
    cache_ok = True

    def get_col_spec(self, **kw):
        return "VECTOR"

    def bind_processor(self, dialect):
        return lambda value: json.dumps(value, allow_nan=False)

    def result_processor(self, dialect, coltype):
        return lambda value: json.loads(value) if isinstance(value, str) else value


# Allow Alembic reflection to compare the extension type with model metadata.


ischema_names["vector"] = Vector
