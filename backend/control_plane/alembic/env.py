from logging.config import fileConfig
from pathlib import Path
import os
import sys

from alembic import context
from sqlalchemy import engine_from_config, pool, text
from sqlalchemy.engine import make_url

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = BACKEND_DIR.parent
for path in (REPO_DIR,):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from backend.control_plane.models import ControlBase
from backend.core.config import settings

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = ControlBase.metadata


def _configure_postgresql_migration_limits(connection) -> None:
    """Apply transaction-local safety limits to this migration connection."""
    connection.execute(
        text("SELECT set_config('lock_timeout', :value, true)"),
        {"value": os.environ.get("ALEMBIC_LOCK_TIMEOUT", "5s").strip()},
    )
    connection.execute(
        text("SELECT set_config('statement_timeout', :value, true)"),
        {"value": os.environ.get("ALEMBIC_STATEMENT_TIMEOUT", "30min").strip()},
    )


def get_database_url() -> str:
    # Programmatic callers target individual databases through this config.
    configured_url = config.get_main_option("sqlalchemy.url")
    if configured_url:
        return configured_url

    env_url = os.environ.get("DATABASE_URL")
    if env_url:
        return env_url

    return make_url(settings.DATABASE_URL).set(
        database=settings.CONTROL_PLANE_DB_NAME
    ).render_as_string(hide_password=False)


def run_migrations_offline() -> None:
    url = get_database_url()
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    config.set_main_option(
        "sqlalchemy.url",
        get_database_url().replace("%", "%%"),
    )
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    try:
        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
            )
            with context.begin_transaction():
                if connection.dialect.name == "postgresql":
                    _configure_postgresql_migration_limits(connection)
                    connection.execute(
                        text("SELECT pg_advisory_xact_lock(:lock_key)"),
                        {"lock_key": 0x4156594E414D4947},
                    )
                context.run_migrations()
    finally:
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
