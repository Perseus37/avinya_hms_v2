"""
Zero-downtime index migration utility for PostgreSQL production deployments (N-84, N-94).

Applies foreign key and metadata indexes using PostgreSQL's `CREATE INDEX CONCURRENTLY`
mechanism, avoiding ACCESS EXCLUSIVE locks and preventing write stalls on high-volume
live patient and billing tables.

Upgrade Order on Live Production Databases:
    1. Run: python backend/scripts/build_indexes_concurrently.py --all-tenants
       This detects any invalid/interrupted indexes, drops them cleanly, and builds all
       foreign key indexes concurrently in the background without locking tables.
    2. Run: alembic upgrade head
       The migration (e1a3c7b5d902) uses `if_not_exists=True`, safely stamping the
       migration revision without duplicate index errors.

Usage:
    python backend/scripts/build_indexes_concurrently.py --database-url <postgres_url> [--dry-run]
    python backend/scripts/build_indexes_concurrently.py --all-tenants [--dry-run]
    python backend/scripts/build_indexes_concurrently.py --control-plane [--dry-run]
"""

import argparse
import sys
import time
from pathlib import Path
from typing import Sequence

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_REPO_DIR = _BACKEND_DIR.parent
if str(_REPO_DIR) not in sys.path:
    sys.path.insert(0, str(_REPO_DIR))

from sqlalchemy import MetaData, create_engine, text  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402

from backend.control_plane.models import ControlBase  # noqa: E402
from backend.core.config import settings  # noqa: E402
from backend.core.database import Base, ControlSessionLocal, TenantRegistry  # noqa: E402


def generate_concurrent_index_sqls(
    metadata: MetaData, existing_indexes: set[str]
) -> list[tuple[str, str, str]]:
    """
    Inspects SQLAlchemy metadata and returns a list of (index_name, table_name, sql)
    for indexes that do not yet exist in PostgreSQL pg_indexes.
    """
    sqls: list[tuple[str, str, str]] = []

    for table_name, table in sorted(metadata.tables.items()):
        for idx in sorted(table.indexes, key=lambda i: i.name or ""):
            idx_name = idx.name
            if not idx_name or idx_name.lower() in existing_indexes:
                continue

            columns = ", ".join(f'"{c.name}"' for c in idx.columns)
            unique_clause = "UNIQUE " if idx.unique else ""
            sql = f'CREATE {unique_clause}INDEX CONCURRENTLY IF NOT EXISTS "{idx_name}" ON "{table_name}" ({columns});'
            sqls.append((idx_name, table_name, sql))

    return sqls


def get_existing_postgres_indexes(engine: Engine) -> set[str]:
    """Queries pg_index for all existing VALID index names in the public schema."""
    if engine.dialect.name != "postgresql":
        return set()

    query = text(
        """
        SELECT c.relname
        FROM pg_index i
        JOIN pg_class c ON c.oid = i.indexrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND i.indisvalid;
        """
    )
    with engine.connect() as conn:
        result = conn.execute(query)
        return {row[0].lower() for row in result.fetchall()}


def get_invalid_postgres_indexes(engine: Engine) -> list[str]:
    """Queries pg_index for indexes in the public schema where indisvalid is false (N-94)."""
    if engine.dialect.name != "postgresql":
        return []

    query = text(
        """
        SELECT c.relname
        FROM pg_index i
        JOIN pg_class c ON c.oid = i.indexrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND NOT i.indisvalid;
        """
    )
    with engine.connect() as conn:
        result = conn.execute(query)
        return [row[0] for row in result.fetchall()]


def build_indexes_for_engine(
    engine: Engine,
    metadata: MetaData,
    target_name: str,
    dry_run: bool = False,
) -> int:
    """
    Builds missing indexes concurrently against a single PostgreSQL engine.
    Detects and drops invalid indexes, then creates missing indexes without locking tables.
    Returns the number of indexes created (or planned if dry-run).
    """
    if engine.dialect.name != "postgresql":
        print(
            f"[{target_name}] Dialect is '{engine.dialect.name}', not 'postgresql'. "
            "CREATE INDEX CONCURRENTLY is PostgreSQL-specific. Skipping.",
            file=sys.stderr,
        )
        return 0

    # N-94: Repair invalid indexes from previously interrupted or failed builds
    invalid_indexes = get_invalid_postgres_indexes(engine)
    if invalid_indexes:
        print(
            f"[{target_name}] Found {len(invalid_indexes)} invalid/broken index(es) "
            f"from interrupted builds: {invalid_indexes}"
        )

    existing = get_existing_postgres_indexes(engine)
    statements = generate_concurrent_index_sqls(metadata, existing)

    if not statements and not invalid_indexes:
        print(f"[{target_name}] All {len(existing)} indexes already present and valid. Nothing to build.")
        return 0

    print(f"[{target_name}] Found {len(statements)} missing/rebuilding indexes to build concurrently.")

    created = 0
    raw_connection = engine.raw_connection()
    try:
        # PostgreSQL CREATE INDEX CONCURRENTLY cannot run inside a transaction block
        raw_connection.connection.autocommit = True
        cursor = raw_connection.cursor()

        # Drop invalid indexes first so concurrent recreation can proceed cleanly
        for inv_idx in invalid_indexes:
            if dry_run:
                print(f"[DRY-RUN] DROP INDEX CONCURRENTLY IF EXISTS \"{inv_idx}\";")
            else:
                try:
                    print(f"[{target_name}] Dropping invalid index '{inv_idx}'...", end=" ", flush=True)
                    cursor.execute(f'DROP INDEX CONCURRENTLY IF EXISTS "{inv_idx}";')
                    print("OK")
                except Exception as drop_err:
                    print(f"FAILED to drop invalid index '{inv_idx}': {drop_err}", file=sys.stderr)

        for idx_name, table_name, sql in statements:
            if dry_run:
                print(f"[DRY-RUN] {sql}")
                created += 1
                continue

            t0 = time.monotonic()
            print(f"[{target_name}] Building '{idx_name}' on '{table_name}'...", end=" ", flush=True)
            try:
                cursor.execute(sql)
                duration = time.monotonic() - t0
                print(f"OK ({duration:.2f}s)")
                created += 1
            except Exception as build_err:
                print(f"FAILED: {build_err}", file=sys.stderr)

    finally:
        raw_connection.close()

    return created


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=None,
        help="Direct PostgreSQL connection URL to apply concurrent indexes to",
    )
    parser.add_argument(
        "--control-plane",
        action="store_true",
        help="Apply missing concurrent indexes to the Control Plane database",
    )
    parser.add_argument(
        "--all-tenants",
        action="store_true",
        help="Iterate over all active hospital tenant databases and apply concurrent indexes",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Display SQL statements without executing them",
    )
    args = parser.parse_args(argv)

    if not args.database_url and not args.control_plane and not args.all_tenants:
        parser.error("Specify at least one target: --database-url, --control-plane, or --all-tenants.")

    total_created = 0

    if args.database_url:
        engine = create_engine(args.database_url)
        try:
            total_created += build_indexes_for_engine(
                engine, Base.metadata, "custom-db", dry_run=args.dry_run
            )
        finally:
            engine.dispose()

    if args.control_plane:
        cp_url = settings.CONTROL_PLANE_DATABASE_URL
        if cp_url:
            engine = create_engine(cp_url)
            try:
                total_created += build_indexes_for_engine(
                    engine, ControlBase.metadata, "control-plane", dry_run=args.dry_run
                )
            finally:
                engine.dispose()

    if args.all_tenants:
        with ControlSessionLocal() as db:
            from sqlalchemy import select

            tenants = db.execute(
                select(TenantRegistry).where(TenantRegistry.is_active.is_(True))
            ).scalars().all()

        print(f"Discovered {len(tenants)} active tenants across fleet.")
        for tenant in tenants:
            tenant_url = settings.get_tenant_database_url(tenant.db_name)
            engine = create_engine(tenant_url)
            try:
                total_created += build_indexes_for_engine(
                    engine, Base.metadata, f"tenant:{tenant.subdomain_slug}", dry_run=args.dry_run
                )
            finally:
                engine.dispose()

    mode = "Planned" if args.dry_run else "Built"
    print(f"\nSummary: {mode} {total_created} indexes across targeted databases.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
