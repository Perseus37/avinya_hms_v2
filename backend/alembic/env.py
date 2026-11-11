from logging.config import fileConfig
from pathlib import Path
import os
import sys

from alembic import context
from sqlalchemy import create_engine, pool, text

# Resolve the repository package namespace for Alembic subprocesses.
_BACKEND_DIR = Path(__file__).resolve().parents[1]
_REPO_DIR = _BACKEND_DIR.parent
for p in (_REPO_DIR,):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from backend.core.config import settings
from backend.core.database import Base
import backend.domains.abdm.models  # noqa: F401
import backend.domains.billing.models  # noqa: F401
import backend.domains.bloodbank.models  # noqa: F401
import backend.domains.clinical.models  # noqa: F401
import backend.domains.diagnostics.models  # noqa: F401
import backend.domains.encounters.models  # noqa: F401
import backend.domains.facility.models  # noqa: F401
import backend.domains.federation.models  # noqa: F401
import backend.domains.finance.models  # noqa: F401
import backend.domains.identity.models  # noqa: F401
import backend.domains.insurance.models  # noqa: F401
import backend.domains.integrations.models  # noqa: F401
import backend.domains.patients.models  # noqa: F401
import backend.domains.pharmacy.models  # noqa: F401
import backend.domains.policies.models  # noqa: F401
import backend.domains.privacy.models  # noqa: F401
import backend.domains.procurement.models  # noqa: F401
import backend.domains.quality.models  # noqa: F401
import backend.domains.reports.models  # noqa: F401
import backend.domains.service_ops.models  # noqa: F401
import backend.domains.surgery.models  # noqa: F401
import backend.domains.workforce.models  # noqa: F401

config = context.config


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


if config.config_file_name is not None:
    fileConfig(config.config_file_name)

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url") or os.environ.get("DATABASE_URL") or settings.DATABASE_URL
    context.configure(
        url=url,
        target_metadata=Base.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = config.get_main_option("sqlalchemy.url") or os.environ.get("DATABASE_URL") or settings.DATABASE_URL
    connectable = create_engine(url, poolclass=pool.NullPool)

    try:
        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=Base.metadata,
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