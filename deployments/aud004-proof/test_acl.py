"""Opt-in PostgreSQL database-per-tenant ACL proof; synthetic fixtures only."""
import os

import psycopg2
import pytest
from psycopg2 import sql

HOST = os.getenv("AUD004_PGHOST", "127.0.0.1")
PORT = int(os.getenv("AUD004_PGPORT", "55439"))
IDENTITIES = {
    "a": ("tenant_a_api_test", "aud004-a-api-test-only"),
    "b": ("tenant_b_api_test", "aud004-b-api-test-only"),
    "cp": ("control_plane_test", "aud004-cp-test-only"),
}
TARGET_DATABASES = {
    "a": "aud004_tenant_a",
    "b": "aud004_tenant_b",
    "cp": "aud004_control_plane",
}


def connect(identity: str, target_database: str | None = None):
    user, password = IDENTITIES[identity]
    database = TARGET_DATABASES[target_database or identity]
    return psycopg2.connect(
        host=HOST, port=PORT, dbname=database, user=user, password=password,
        connect_timeout=3, application_name="aud004-disposable-proof",
    )


def marker(identity: str) -> str:
    with connect(identity) as conn:
        with conn.cursor() as cur:
            table = "control_marker" if identity == "cp" else "tenant_marker"
            cur.execute(sql.SQL("SELECT marker FROM synthetic.{}").format(sql.Identifier(table)))
            return cur.fetchone()[0]


def assert_connect_denied(identity: str, target_database: str):
    # PostgreSQL rejects CONNECT during startup. psycopg2 exposes this FATAL
    # response as OperationalError without a pgcode, even for SQLSTATE 42501.
    with pytest.raises(psycopg2.OperationalError) as exc:
        connect(identity, target_database)

    message = str(exc.value)
    expected_database = TARGET_DATABASES[target_database]
    assert f'permission denied for database "{expected_database}"' in message, (
        f"Expected PostgreSQL to deny CONNECT to {expected_database!r}; "
        f"received a different connection failure: {message!r}"
    )
    assert "User does not have CONNECT privilege." in message, (
        "Connection failed, but not with PostgreSQL's explicit CONNECT ACL denial: "
        f"{message!r}"
    )


def test_tenant_a_can_read_own_synthetic_database():
    assert marker("a") == "TENANT_A_SYNTHETIC_ONLY"


def test_tenant_b_can_read_own_synthetic_database():
    assert marker("b") == "TENANT_B_SYNTHETIC_ONLY"


def test_tenant_a_identity_cannot_connect_to_tenant_b():
    assert_connect_denied("a", "b")


def test_tenant_b_identity_cannot_connect_to_tenant_a():
    assert_connect_denied("b", "a")


def test_control_plane_can_read_its_synthetic_database():
    assert marker("cp") == "CONTROL_PLANE_SYNTHETIC_ONLY"


@pytest.mark.parametrize("target", ["a", "b"])
def test_control_plane_cannot_connect_to_tenant_databases(target):
    assert_connect_denied("cp", target)


@pytest.mark.parametrize("identity", ["a", "b", "cp"])
def test_runtime_login_is_not_privileged(identity):
    with connect(identity) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT rolsuper, rolcreatedb, rolcreaterole "
                "FROM pg_roles WHERE rolname = current_user"
            )
            assert cur.fetchone() == (False, False, False)



@pytest.mark.parametrize("identity", ["a", "b", "cp"])
def test_runtime_cannot_assume_setup_identity(identity):
    with connect(identity) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_has_role(current_user, 'aud004_setup', 'MEMBER')")
            assert cur.fetchone()[0] is False


@pytest.mark.parametrize("identity", ["a", "b"])
def test_tenant_runtime_has_only_read_access_to_synthetic_marker(identity):
    with connect(identity) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT has_schema_privilege(current_user, 'synthetic', 'CREATE'), "
                "has_table_privilege(current_user, 'synthetic.tenant_marker', 'INSERT'), "
                "has_table_privilege(current_user, 'synthetic.tenant_marker', 'UPDATE'), "
                "has_table_privilege(current_user, 'synthetic.tenant_marker', 'DELETE')"
            )
            assert cur.fetchone() == (False, False, False, False)


@pytest.mark.parametrize("identity", ["a", "b", "cp"])
def test_runtime_has_no_cluster_admin_or_replication_attributes(identity):
    with connect(identity) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls "
                "FROM pg_roles WHERE rolname = current_user"
            )
            assert cur.fetchone() == (False, False, False, False, False)

@pytest.mark.parametrize("identity", ["a", "b", "cp"])
def test_runtime_has_only_database_connect_privilege(identity):
    with connect(identity) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    has_database_privilege(current_user, current_database(), 'CONNECT'),
                    has_database_privilege(current_user, current_database(), 'CREATE'),
                    has_database_privilege(current_user, current_database(), 'TEMPORARY')
                """
            )
            assert cur.fetchone() == (True, False, False)


@pytest.mark.parametrize("identity", ["a", "b", "cp"])
def test_public_has_no_connect_or_temp_on_runtime_database(identity):
    with connect(identity) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COALESCE(bool_or(privilege_type = 'CONNECT'), FALSE),
                    COALESCE(bool_or(privilege_type = 'TEMPORARY'), FALSE)
                FROM pg_database AS d
                CROSS JOIN LATERAL aclexplode(d.datacl) AS acl
                WHERE d.datname = current_database()
                  AND acl.grantee = 0
                """
            )
            assert cur.fetchone() == (False, False)


@pytest.mark.parametrize("identity", ["a", "b", "cp"])
def test_runtime_has_no_membership_in_predefined_or_privileged_roles(identity):
    with connect(identity) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT r.rolname
                FROM pg_roles AS r
                WHERE r.rolname LIKE 'pg!_%' ESCAPE '!'
                  AND r.rolname <> 'pg_database_owner'
                  AND pg_has_role(current_user, r.oid, 'MEMBER')
                UNION
                SELECT r.rolname
                FROM pg_roles AS r
                WHERE (r.rolsuper OR r.rolcreatedb OR r.rolcreaterole
                       OR r.rolreplication OR r.rolbypassrls)
                  AND r.rolname <> current_user
                  AND pg_has_role(current_user, r.oid, 'MEMBER')
                ORDER BY 1
                """
            )
            memberships = [row[0] for row in cur.fetchall()]
            assert memberships == [], (
                "Runtime login inherits predefined or elevated role membership: "
                f"{memberships!r}"
            )
