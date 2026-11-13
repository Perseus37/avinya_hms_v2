"""Migrate three disposable PostgreSQL databases and capture independent catalogs.

This is an AUD-004 characterization proof, not a grant generator or production
migration runner. It requires an isolated PostgreSQL 17 CI service and synthetic
credentials supplied by the workflow.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import psycopg2
from sqlalchemy import create_engine, inspect

ROOT = Path(__file__).resolve().parents[2]
DATABASES = {
    "control_plane": "aud004_catalog_control_plane",
    "tenant_a": "aud004_catalog_tenant_a",
    "tenant_b": "aud004_catalog_tenant_b",
}


def _database_url(database: str) -> str:
    from urllib.parse import quote_plus

    user = quote_plus(os.environ["AUD004_PGUSER"])
    password = quote_plus(os.environ["AUD004_PGPASSWORD"])
    host = os.environ["AUD004_PGHOST"]
    port = os.environ["AUD004_PGPORT"]
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"


def _base_environment() -> dict[str, str]:
    env = os.environ.copy()
    # Values below satisfy application Settings construction during Alembic
    # model imports. They are disposable CI values and are not used to seed data.
    env.update(
        {
            "ENVIRONMENT": "testing",
            "DEVELOPMENT_AUTO_CREATE_SCHEMA": "false",
            "PLATFORM_NAME": "AUD004 disposable proof",
            "BASE_DOMAIN": "invalid.test",
            "DEFAULT_TENANT_SLUG": "aud004",
            "DEFAULT_HOSPITAL_NAME": "AUD004 Synthetic Hospital",
            "DEFAULT_BRANCH_CODE": "AUD004",
            "VERSION": "aud004-ci",
            "API_PORT": "8000",
            "API_SERVICE_HOST": "127.0.0.1",
            "CONTROL_PLANE_PORT": "8080",
            "GUNICORN_WORKERS": "1",
            "TENANT_DATABASE_PREFIX": "aud004_",
            "APP_TIMEZONE": "UTC",
            "POSTGRES_USER": os.environ["AUD004_PGUSER"],
            "POSTGRES_PASSWORD": os.environ["AUD004_PGPASSWORD"],
            "POSTGRES_DB": "postgres",
            "POSTGRES_HOST": os.environ["AUD004_PGHOST"],
            "POSTGRES_PORT": os.environ["AUD004_PGPORT"],
            "CONTROL_PLANE_DB_NAME": DATABASES["control_plane"],
            "REDIS_HOST": "127.0.0.1",
            "REDIS_PORT": "6379",
            "REDIS_DB": "0",
            "REDIS_PASSWORD": "aud004-not-used",
            "SECRET_KEY": "aud004-synthetic-secret-key-at-least-32",
            "MASTER_ONBOARDING_KEY": "aud004-synthetic-master-key",
            "ALGORITHM": "HS256",
            "ACCESS_TOKEN_EXPIRE_MINUTES": "30",
            "CORS_ORIGINS": "http://localhost",
            "SEED_ADMIN_EMAIL": "aud004@example.invalid",
            "SEED_ADMIN_PASSWORD": "aud004-not-used",
            "ENVELOPE_ENCRYPTION_SALT": "aud004-synthetic-envelope-salt",
            "BACKUP_ENCRYPTION_SALT": "aud004-synthetic-backup-salt",
            "MAIL_PROVIDER": "smtp",
            "SMTP_PORT": "25",
            "SMTP_FROM": "aud004@example.invalid",
            "MAX_PAGE_SIZE": "50",
            "MIGRATION_PREVIEW_ROWS": "5",
            "MIGRATION_PREVIEW_ERROR_LIMIT": "10",
            "MIGRATION_MAX_UPLOAD_BYTES": "1048576",
            "MAX_ATTACHMENT_UPLOAD_BYTES": "1048576",
            "MIGRATION_MAX_EXPRESSION_DEPTH": "10",
            "MIGRATION_MAX_INPUTS": "10",
            "BACKUP_INTERVAL_SECONDS": "3600",
            "BACKUP_OUTPUT_DIR": "/tmp/aud004-backups",
            "VAULT_POLL_INTERVAL_SECONDS": "60",
            "PRIVACY_ALLOW_AUDIT_ONLY": "false",
            "PRIVACY_ALLOW_RETENTION_DRY_RUN": "false",
            "PRIVACY_ALLOW_RETENTION_EXECUTE": "false",
        }
    )
    return env


def _create_empty_databases() -> None:
    conn = psycopg2.connect(
        host=os.environ["AUD004_PGHOST"],
        port=int(os.environ["AUD004_PGPORT"]),
        dbname="postgres",
        user=os.environ["AUD004_PGUSER"],
        password=os.environ["AUD004_PGPASSWORD"],
        connect_timeout=5,
        application_name="aud004-migrated-catalog-proof",
    )
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            for database in DATABASES.values():
                cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database,))
                if cur.fetchone():
                    raise RuntimeError(
                        f"Refusing to reuse pre-existing disposable database {database}"
                    )
                cur.execute(f'CREATE DATABASE "{database}"')
    finally:
        conn.close()


def _run_alembic(config_path: str, database: str) -> None:
    env = _base_environment()
    env["DATABASE_URL"] = _database_url(database)
    command = [
        sys.executable,
        "-m",
        "alembic",
        "-c",
        str(ROOT / config_path),
        "upgrade",
        "heads",
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=900,
        check=False,
    )
    if completed.returncode:
        raise AssertionError(
            f"Alembic migration failed for {database} ({config_path}):\n"
            f"{completed.stdout[-16000:]}"
        )


def _capture_catalog(database: str) -> dict:
    engine = create_engine(_database_url(database), pool_pre_ping=True)
    try:
        inspector = inspect(engine)
        schemas = [
            schema
            for schema in inspector.get_schema_names()
            if schema not in {"information_schema", "pg_catalog"}
        ]
        tables = sorted(
            f"{schema}.{table}"
            for schema in schemas
            for table in inspector.get_table_names(schema=schema)
        )
        views = sorted(
            f"{schema}.{view}"
            for schema in schemas
            for view in inspector.get_view_names(schema=schema)
        )
        materialized_views = sorted(
            f"{schema}.{view}"
            for schema in schemas
            for view in inspector.get_materialized_view_names(schema=schema)
        )
        with engine.connect() as conn:
            rows = conn.exec_driver_sql(
                """
                SELECT
                  (SELECT count(*) FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace
                   WHERE t.typtype='e' AND n.nspname NOT IN ('pg_catalog','information_schema')) AS enum_count,
                  (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                   WHERE c.relkind='S' AND n.nspname NOT IN ('pg_catalog','information_schema')) AS sequence_count,
                  (SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
                   JOIN pg_namespace n ON n.oid=c.relnamespace
                   WHERE NOT t.tgisinternal AND n.nspname NOT IN ('pg_catalog','information_schema')) AS trigger_count,
                  (SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
                   WHERE n.nspname NOT IN ('pg_catalog','information_schema')) AS function_count,
                  (SELECT count(*) FROM pg_extension) AS extension_count,
                  (SELECT count(*) FROM pg_largeobject_metadata) AS large_object_count,
                  (SELECT count(*) FROM pg_policies) AS rls_policy_count,
                  (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                   WHERE c.relkind IN ('r','p','v','m','S','f')
                   AND n.nspname NOT IN ('pg_catalog','information_schema')) AS relation_count
                """
            ).mappings().one()
            versions = conn.exec_driver_sql(
                "SELECT version_num FROM alembic_version ORDER BY version_num"
            ).scalars().all()
            owners = conn.exec_driver_sql(
                """
                SELECT n.nspname, c.relname, pg_get_userbyid(c.relowner)
                FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname NOT IN ('pg_catalog','information_schema')
                  AND c.relkind IN ('r','p','v','m','S','f')
                ORDER BY n.nspname,c.relname
                """
            ).all()
            columns = conn.exec_driver_sql(
                """
                SELECT table_schema, table_name, ordinal_position, column_name,
                       data_type, udt_name, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_schema NOT IN ('pg_catalog','information_schema')
                ORDER BY table_schema,table_name,ordinal_position
                """
            ).all()
            constraints = conn.exec_driver_sql(
                """
                SELECT n.nspname, t.relname, c.conname, c.contype,
                       pg_get_constraintdef(c.oid, true)
                FROM pg_constraint c
                JOIN pg_class t ON t.oid=c.conrelid
                JOIN pg_namespace n ON n.oid=t.relnamespace
                WHERE n.nspname NOT IN ('pg_catalog','information_schema')
                ORDER BY n.nspname,t.relname,c.conname
                """
            ).all()
            indexes = conn.exec_driver_sql(
                """
                SELECT schemaname, tablename, indexname, indexdef
                FROM pg_indexes
                WHERE schemaname NOT IN ('pg_catalog','information_schema')
                ORDER BY schemaname,tablename,indexname
                """
            ).all()
            enums = conn.exec_driver_sql(
                """
                SELECT n.nspname, t.typname, e.enumsortorder, e.enumlabel
                FROM pg_type t JOIN pg_enum e ON e.enumtypid=t.oid
                JOIN pg_namespace n ON n.oid=t.typnamespace
                WHERE n.nspname NOT IN ('pg_catalog','information_schema')
                ORDER BY n.nspname,t.typname,e.enumsortorder
                """
            ).all()
            routines = conn.exec_driver_sql(
                """
                SELECT n.nspname, p.proname, pg_get_function_identity_arguments(p.oid),
                       p.prosecdef, p.proconfig, pg_get_userbyid(p.proowner),
                       pg_get_functiondef(p.oid)
                FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
                WHERE n.nspname NOT IN ('pg_catalog','information_schema')
                ORDER BY n.nspname,p.proname
                """
            ).all()
            triggers = conn.exec_driver_sql(
                """
                SELECT n.nspname, t.relname, tr.tgname, pg_get_triggerdef(tr.oid, true),
                       p.proname, p.prosecdef, p.proconfig, pg_get_userbyid(p.proowner)
                FROM pg_trigger tr
                JOIN pg_class t ON t.oid=tr.tgrelid
                JOIN pg_namespace n ON n.oid=t.relnamespace
                JOIN pg_proc p ON p.oid=tr.tgfoid
                WHERE NOT tr.tgisinternal
                  AND n.nspname NOT IN ('pg_catalog','information_schema')
                ORDER BY n.nspname,t.relname,tr.tgname
                """
            ).all()
            policies = conn.exec_driver_sql(
                """
                SELECT schemaname, tablename, policyname, permissive, roles,
                       cmd, qual, with_check
                FROM pg_policies
                ORDER BY schemaname,tablename,policyname
                """
            ).all()
            grants = conn.exec_driver_sql(
                """
                SELECT table_schema, table_name, grantee, privilege_type, is_grantable
                FROM information_schema.role_table_grants
                WHERE table_schema NOT IN ('pg_catalog','information_schema')
                ORDER BY table_schema,table_name,grantee,privilege_type
                """
            ).all()
            # Catalog ACL expansion preserves explicit PUBLIC grants and grants
            # that information_schema.role_table_grants can hide from the
            # inspecting role. Keep ownership separate from explicit ACLs.
            relation_acls = conn.exec_driver_sql(
                """
                SELECT n.nspname, c.relname, c.relkind,
                       CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                            ELSE pg_get_userbyid(acl.grantee) END,
                       pg_get_userbyid(acl.grantor), acl.privilege_type,
                       acl.is_grantable
                FROM pg_class c
                JOIN pg_namespace n ON n.oid=c.relnamespace
                CROSS JOIN LATERAL aclexplode(c.relacl) AS acl
                WHERE c.relacl IS NOT NULL
                  AND n.nspname NOT IN ('pg_catalog','information_schema')
                ORDER BY n.nspname,c.relname,acl.grantee,acl.privilege_type
                """
            ).all()
            column_acls = conn.exec_driver_sql(
                """
                SELECT n.nspname, c.relname, a.attname,
                       CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                            ELSE pg_get_userbyid(acl.grantee) END,
                       pg_get_userbyid(acl.grantor), acl.privilege_type,
                       acl.is_grantable
                FROM pg_attribute a
                JOIN pg_class c ON c.oid=a.attrelid
                JOIN pg_namespace n ON n.oid=c.relnamespace
                CROSS JOIN LATERAL aclexplode(a.attacl) AS acl
                WHERE a.attnum > 0 AND NOT a.attisdropped
                  AND a.attacl IS NOT NULL
                  AND n.nspname NOT IN ('pg_catalog','information_schema')
                ORDER BY n.nspname,c.relname,a.attnum,acl.grantee,acl.privilege_type
                """
            ).all()
            routine_acls = conn.exec_driver_sql(
                """
                SELECT n.nspname, p.proname,
                       pg_get_function_identity_arguments(p.oid),
                       CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                            ELSE pg_get_userbyid(acl.grantee) END,
                       pg_get_userbyid(acl.grantor), acl.privilege_type,
                       acl.is_grantable
                FROM pg_proc p
                JOIN pg_namespace n ON n.oid=p.pronamespace
                CROSS JOIN LATERAL aclexplode(p.proacl) AS acl
                WHERE p.proacl IS NOT NULL
                  AND n.nspname NOT IN ('pg_catalog','information_schema')
                ORDER BY n.nspname,p.proname,acl.grantee,acl.privilege_type
                """
            ).all()
            type_acls = conn.exec_driver_sql(
                """
                SELECT n.nspname, t.typname,
                       CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                            ELSE pg_get_userbyid(acl.grantee) END,
                       pg_get_userbyid(acl.grantor), acl.privilege_type,
                       acl.is_grantable
                FROM pg_type t
                JOIN pg_namespace n ON n.oid=t.typnamespace
                CROSS JOIN LATERAL aclexplode(t.typacl) AS acl
                WHERE t.typacl IS NOT NULL
                  AND n.nspname NOT IN ('pg_catalog','information_schema')
                ORDER BY n.nspname,t.typname,acl.grantee,acl.privilege_type
                """
            ).all()
            role_attributes = conn.exec_driver_sql(
                """
                SELECT rolname, rolsuper, rolcreaterole, rolcreatedb, rolcanlogin,
                       rolreplication, rolbypassrls, rolconnlimit, rolvaliduntil
                FROM pg_roles
                ORDER BY rolname
                """
            ).all()
            default_acls = conn.exec_driver_sql(
                """
                SELECT pg_get_userbyid(d.defaclrole), n.nspname, d.defaclobjtype,
                       d.defaclacl::text
                FROM pg_default_acl d
                LEFT JOIN pg_namespace n ON n.oid=d.defaclnamespace
                ORDER BY 1,2,3
                """
            ).all()
            memberships = conn.exec_driver_sql(
                """
                SELECT member.rolname, granted.rolname, m.admin_option
                FROM pg_auth_members m
                JOIN pg_roles granted ON granted.oid=m.roleid
                JOIN pg_roles member ON member.oid=m.member
                ORDER BY member.rolname,granted.rolname
                """
            ).all()
            database_acl = conn.exec_driver_sql(
                """
                SELECT datname, pg_get_userbyid(datdba), datacl::text
                FROM pg_database WHERE datname=current_database()
                """
            ).all()
            schema_acl = conn.exec_driver_sql(
                """
                SELECT nspname, pg_get_userbyid(nspowner), nspacl::text
                FROM pg_namespace
                WHERE nspname NOT IN ('pg_catalog','information_schema')
                ORDER BY nspname
                """
            ).all()
            extensions = conn.exec_driver_sql(
                """
                SELECT e.extname, e.extversion, n.nspname, pg_get_userbyid(e.extowner)
                FROM pg_extension e
                JOIN pg_namespace n ON n.oid=e.extnamespace
                ORDER BY e.extname
                """
            ).all()
            return {
                "database": database,
                "schemas": sorted(schemas),
                "tables": tables,
                "views": views,
                "materialized_views": materialized_views,
                "migration_versions": versions,
                "catalog_counts": dict(rows),
                "object_owners": [list(row) for row in owners],
                "columns": [list(row) for row in columns],
                "constraints": [list(row) for row in constraints],
                "indexes": [list(row) for row in indexes],
                "enum_labels": [list(row) for row in enums],
                "routines": [list(row) for row in routines],
                "triggers": [list(row) for row in triggers],
                "rls_policies": [list(row) for row in policies],
                "table_grants_information_schema": [list(row) for row in grants],
                "relation_acls_expanded": [list(row) for row in relation_acls],
                "column_acls_expanded": [list(row) for row in column_acls],
                "routine_acls_expanded": [list(row) for row in routine_acls],
                "type_acls_expanded": [list(row) for row in type_acls],
                "role_attributes": [list(row) for row in role_attributes],
                "default_acls": [list(row) for row in default_acls],
                "role_memberships": [list(row) for row in memberships],
                "database_acl": [list(row) for row in database_acl],
                "schema_acl": [list(row) for row in schema_acl],
                "extensions": [list(row) for row in extensions],
            }
    finally:
        engine.dispose()


def _metadata_manifest() -> dict:
    # Import exactly the same model modules as the tenant Alembic env.
    from backend.core.database import Base
    import backend.domains.abdm.models  # noqa: F401
    import backend.domains.audit.models  # noqa: F401
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
    from backend.control_plane.models import ControlBase

    def describe(metadata) -> dict:
        result = {}
        for table in sorted(metadata.tables.values(), key=lambda item: (item.schema or "public", item.name)):
            key = f"{table.schema or 'public'}.{table.name}"
            result[key] = {
                "columns": sorted(column.name for column in table.columns),
                "primary_key": sorted(column.name for column in table.primary_key.columns),
                "foreign_keys": sorted(
                    f"{fk.parent.name}->{fk.target_fullname}" for fk in table.foreign_keys
                ),
                "unique_constraints": sorted(
                    tuple(sorted(column.name for column in constraint.columns))
                    for constraint in table.constraints
                    if constraint.__class__.__name__ == "UniqueConstraint"
                ),
                "indexes": sorted(
                    (index.name or "", tuple(column.name for column in index.columns), bool(index.unique))
                    for index in table.indexes
                ),
            }
        return result

    return {
        "tenant": describe(Base.metadata),
        "control_plane": describe(ControlBase.metadata),
    }


def _column_deltas(metadata_tables: dict, catalog: dict) -> dict:
    """Report ORM-vs-live column name differences without declaring them acceptable."""
    catalog_columns: dict[str, set[str]] = {}
    for row in catalog["columns"]:
        schema, table, _ordinal, column_name = row[:4]
        catalog_columns.setdefault(f"{schema}.{table}", set()).add(column_name)

    missing_from_catalog = {}
    extra_in_catalog = {}
    for table_name in sorted(set(metadata_tables) | set(catalog_columns)):
        expected = set(metadata_tables.get(table_name, {}).get("columns", []))
        actual = catalog_columns.get(table_name, set())
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        if missing:
            missing_from_catalog[table_name] = missing
        if extra:
            extra_in_catalog[table_name] = extra
    return {
        "metadata_columns_missing_from_catalog": missing_from_catalog,
        "catalog_columns_missing_from_metadata": extra_in_catalog,
    }


def test_migrate_and_capture_three_independent_postgres_catalogs(tmp_path: Path) -> None:
    """Run real migration graphs only against three newly-created CI databases."""
    os.environ.update(_base_environment())
    _create_empty_databases()
    _run_alembic("backend/control_plane/alembic.ini", DATABASES["control_plane"])
    _run_alembic("backend/alembic.ini", DATABASES["tenant_a"])
    _run_alembic("backend/alembic.ini", DATABASES["tenant_b"])

    metadata = _metadata_manifest()
    catalogs = {
        name: _capture_catalog(database)
        for name, database in DATABASES.items()
    }

    # Both tenant databases must independently reach the same migration state.
    assert catalogs["tenant_a"]["migration_versions"] == catalogs["tenant_b"]["migration_versions"]
    assert catalogs["control_plane"]["migration_versions"], "CP Alembic version row missing"
    assert catalogs["tenant_a"]["migration_versions"], "Tenant A Alembic version row missing"
    assert catalogs["tenant_b"]["migration_versions"], "Tenant B Alembic version row missing"

    report = {
        "proof": "AUD-004 disposable PostgreSQL migration/catalog characterization",
        "postgresql_target": "PostgreSQL 17 CI service",
        "databases": catalogs,
        "metadata_counts": {
            name: len(tables) for name, tables in metadata.items()
        },
        "metadata": metadata,
        "table_deltas": {
            "control_plane_missing_from_catalog": sorted(
                set(metadata["control_plane"]) - set(catalogs["control_plane"]["tables"])
            ),
            "tenant_a_missing_from_catalog": sorted(
                set(metadata["tenant"]) - set(catalogs["tenant_a"]["tables"])
            ),
            "tenant_b_missing_from_catalog": sorted(
                set(metadata["tenant"]) - set(catalogs["tenant_b"]["tables"])
            ),
            "control_plane_migration_only": sorted(
                set(catalogs["control_plane"]["tables"]) - set(metadata["control_plane"])
            ),
            "tenant_migration_only": sorted(
                set(catalogs["tenant_a"]["tables"]) - set(metadata["tenant"])
            ),
        },
        "column_deltas": {
            "control_plane": _column_deltas(metadata["control_plane"], catalogs["control_plane"]),
            "tenant_a": _column_deltas(metadata["tenant"], catalogs["tenant_a"]),
            "tenant_b": _column_deltas(metadata["tenant"], catalogs["tenant_b"]),
        },
        "limitations": [
            "This is a characterization artifact, not a least-privilege acceptance test.",
            "No application rows are inserted or exported.",
            "Object owners, table grants, database/schema ACLs, default ACLs, and role memberships are captured but not interpreted or asserted.",
            "Explicit relation, column, routine, and type ACL entries (including PUBLIC grantees) and role attributes are captured, but are not interpreted or asserted; implicit ownership rights and cluster-wide settings still require separate review.",
            "Trigger and routine definitions/security settings are captured but not evaluated; raw SQL append-only denial is not tested.",
            "No backup/restore parity is asserted by this test.",
        ],
    }
    output = Path(os.environ.get("AUD004_CATALOG_REPORT", tmp_path / "aud004-catalog-report.json"))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True, default=list) + "\n", encoding="utf-8")
    print(f"AUD004 catalog report written: {output}")
    print(json.dumps(report["table_deltas"], indent=2))
