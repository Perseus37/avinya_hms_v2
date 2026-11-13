"""Execute the production role-bootstrap function against disposable PostgreSQL."""
import ast
import logging
import os
from pathlib import Path
from types import SimpleNamespace

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP_SOURCE = ROOT / "backend" / "scripts" / "bootstrap.py"


def _load_production_role_function():
    """Compile only the real function; avoid unrelated bootstrap imports/side effects."""
    source = ast.parse(BOOTSTRAP_SOURCE.read_text(encoding="utf-8"))
    function = next(
        node for node in source.body
        if isinstance(node, ast.FunctionDef) and node.name == "apply_database_roles"
    )
    namespace = {
        "_REPO_DIR": ROOT,
        "logging": logging,
        "logger": logging.getLogger("aud004.production-bootstrap-proof"),
        "psycopg2": psycopg2,
        "ISOLATION_LEVEL_AUTOCOMMIT": ISOLATION_LEVEL_AUTOCOMMIT,
        "settings": SimpleNamespace(
            POSTGRES_USER=os.environ["AUD004_SETUP_USER"],
            POSTGRES_PASSWORD=os.environ["AUD004_SETUP_PASSWORD"],
            POSTGRES_HOST=os.environ["AUD004_PGHOST"],
            POSTGRES_PORT=int(os.environ["AUD004_PGPORT"]),
        ),
    }
    module = ast.Module(body=[function], type_ignores=[])
    exec(compile(module, str(BOOTSTRAP_SOURCE), "exec"), namespace)
    return namespace["apply_database_roles"]


def _admin_connection():
    return psycopg2.connect(
        host=os.environ["AUD004_PGHOST"],
        port=int(os.environ["AUD004_PGPORT"]),
        dbname="postgres",
        user=os.environ["AUD004_SETUP_USER"],
        password=os.environ["AUD004_SETUP_PASSWORD"],
        connect_timeout=5,
        application_name="aud004-production-role-bootstrap-proof",
    )


def test_actual_production_role_bootstrap_exposes_current_acl_gaps():
    # This job uses a brand-new, disposable PostgreSQL service. Create only
    # synthetic HMS-like databases; never point this test at a shared server.
    conn = _admin_connection()
    try:
        # Set autocommit before entering a connection context; CREATE DATABASE
        # is prohibited inside a transaction block.
        conn.autocommit = True
        with conn.cursor() as cur:
            for database in ("aud004_control_plane", "aud004_tenant_a", "aud004_tenant_b"):
                cur.execute("CREATE DATABASE " + '"' + database + '"')
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = 'hms_app'")
            assert cur.fetchone() is None, "Expected a fresh PostgreSQL role catalog"
    finally:
        conn.close()

    apply_database_roles = _load_production_role_function()
    apply_database_roles()

    with _admin_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, "
                "rolreplication, rolbypassrls, rolpassword "
                "FROM pg_authid WHERE rolname IN "
                "('hms_app','hms_migrator','hms_backup','hms_exporter') ORDER BY rolname"
            )
            roles = {row[0]: row[1:] for row in cur.fetchall()}
            assert set(roles) == {"hms_app", "hms_migrator", "hms_backup", "hms_exporter"}
            for role_name, attributes in roles.items():
                assert attributes[:5] == (False, False, False, False, False), role_name
                assert attributes[5] is None, f"{role_name} unexpectedly has a password"

            cur.execute("SELECT pg_has_role('hms_backup', 'pg_read_all_data', 'MEMBER')")
            assert cur.fetchone()[0] is True, "Expected the production script's cluster-wide backup role grant"

            cur.execute(
                "SELECT has_database_privilege('hms_app', 'aud004_tenant_a', 'CONNECT'), "
                "has_database_privilege('hms_app', 'aud004_control_plane', 'CONNECT')"
            )
            assert cur.fetchone() == (True, True), (
                "The fresh cluster's default PUBLIC CONNECT remains effective for app login; "
                "the production role script does not revoke it or scope tenant DB access."
            )

            # Prove IF NOT EXISTS does not reconcile a pre-existing unsafe role.
            cur.execute("ALTER ROLE hms_app SUPERUSER CREATEDB CREATEROLE")

    apply_database_roles()

    with _admin_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT rolsuper, rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname='hms_app'")
            assert cur.fetchone() == (True, True, True), (
                "The current production bootstrap uses IF NOT EXISTS and leaves unsafe pre-existing attributes unchanged."
            )

