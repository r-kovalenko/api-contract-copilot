from alembic import context
from app.db.models import Base
from app.db.session import create_database_engine, database_url

target_metadata = Base.metadata


def run_migrations() -> None:
    if context.is_offline_mode():
        context.configure(
            dialect_name="postgresql", target_metadata=target_metadata, literal_binds=True
        )
        with context.begin_transaction():
            context.run_migrations()
        return

    # Tests can supply their isolated connection without changing process-wide settings.
    connection = context.config.attributes.get("connection")
    if connection is not None:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
        return

    engine = create_database_engine(database_url())
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


run_migrations()
