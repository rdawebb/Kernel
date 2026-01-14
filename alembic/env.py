"""Alembic environment configuration."""

from logging.config import fileConfig

import asyncio

from alembic import context

from src.core.database import metadata
from src.utils.paths import DATABASE_PATH

# Alembic Config object
config = context.config

# Logging configuration
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = metadata


def get_database_url() -> str:
    """Get the database URL from the config.

    Returns:
        str: The database URL.
    """
    db_path = DATABASE_PATH
    return f"sqlite+aiosqlite:///{db_path}"


# Set database URL dynamically
config.set_main_option("sqlalchemy.url", get_database_url().replace("+aiosqlite", ""))


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode with async support."""
    from src.core.database import create_engine

    engine = create_engine(DATABASE_PATH, echo=True)

    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await engine.dispose()


def do_run_migrations(connection) -> None:
    """Execute migrations with async connection.

    Args:
        connection: The async database connection.
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
