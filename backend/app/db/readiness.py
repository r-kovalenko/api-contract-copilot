from pathlib import Path

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, text


def database_ready(engine: Engine) -> bool:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    required = set(ScriptDirectory.from_config(config).get_heads())
    with engine.connect() as connection:
        applied = set(MigrationContext.configure(connection).get_current_heads())
        vector_enabled = connection.scalar(
            text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
        )
    return applied == required and bool(vector_enabled)
