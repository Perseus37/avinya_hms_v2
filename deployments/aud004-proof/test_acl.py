"""Single-identity PostgreSQL proof; each container receives only its own secret mounts."""
import os
from pathlib import Path

import psycopg2
import pytest

HOST = os.getenv("AUD004_PGHOST", "127.0.0.1")
PORT = int(os.getenv("AUD004_PGPORT", "55439"))
SECRET_DIR = Path("/run/secrets")
EXPECTED_SECRET_FILES = {"db_user", "db_password"}
USER = (SECRET_DIR / "db_user").read_text(encoding="utf-8").strip()
PASSWORD = (SECRET_DIR / "db_password").read_text(encoding="utf-8").strip()
OWN_DATABASE = os.environ["AUD004_OWN_DATABASE"]
FOREIGN_DATABASES = [
    value for value in os.environ["AUD004_FOREIGN_DATABASES"].split(",") if value
]
EXPECTED_MARKER = os.environ["AUD004_EXPECTED_MARKER"]
MARKER_TABLE = os.environ["AUD004_MARKER_TABLE"]


def connect(database: str = OWN_DATABASE):
    return psycopg2.connect(
        host=HOST,
        port=PORT,
        dbname=database,
        user=USER,
        password=PASSWORD,
        connect_timeout=3,
        application_name="aud004-single-identity-proof",
    )


def test_container_mounts_only_its_own_database_secret_pair():
    assert {entry.name for entry in SECRET_DIR.iterdir()} == EXPECTED_SECRET_FILES
    assert USER and PASSWORD


def test_identity_can_read_only_its_own_synthetic_marker():
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT marker FROM synthetic.{MARKER_TABLE}")
            assert cur.fetchone()[0] == EXPECTED_MARKER


@pytest.mark.parametrize("foreign_database", FOREIGN_DATABASES)
def test_identity_cannot_connect_to_any_foreign_database(foreign_database):
    with pytest.raises(psycopg2.OperationalError) as exc:
        connect(foreign_database)

    message = str(exc.value)
    assert f'permission denied for database "{foreign_database}"' in message, (
        f"Expected explicit PostgreSQL CONNECT denial for {foreign_database!r}; "
        f"received a different connection failure: {message!r}"
    )
    assert "User does not have CONNECT privilege." in message, (
        "Failure was not PostgreSQL's explicit CONNECT ACL denial: "
        f"{message!r}"
    )


def test_runtime_login_is_not_privileged():
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT rolsuper, rolcreatedb, rolcreaterole, "
                "rolreplication, rolbypassrls "
                "FROM pg_roles WHERE rolname = current_user"
            )
            assert cur.fetchone() == (False, False, False, False, False)


def test_runtime_cannot_assume_setup_identity():
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pg_has_role(current_user, 'aud004_setup', 'MEMBER')"
            )
            assert cur.fetchone()[0] is False


def test_runtime_has_only_database_connect_privilege():
    with connect() as conn:
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


def test_public_has_no_connect_or_temp_on_runtime_database():
    with connect() as conn:
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


def test_runtime_has_no_membership_in_predefined_or_privileged_roles():
    with connect() as conn:
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
            assert cur.fetchall() == []

def test_runtime_has_select_only_on_its_synthetic_marker():
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    has_schema_privilege(current_user, 'synthetic', 'USAGE'),
                    has_schema_privilege(current_user, 'synthetic', 'CREATE'),
                    has_table_privilege(
                        current_user,
                        'synthetic.' || %s,
                        'SELECT'
                    ),
                    has_table_privilege(
                        current_user,
                        'synthetic.' || %s,
                        'INSERT'
                    ),
                    has_table_privilege(
                        current_user,
                        'synthetic.' || %s,
                        'UPDATE'
                    ),
                    has_table_privilege(
                        current_user,
                        'synthetic.' || %s,
                        'DELETE'
                    ),
                    has_table_privilege(
                        current_user,
                        'synthetic.' || %s,
                        'TRUNCATE'
                    ),
                    has_table_privilege(
                        current_user,
                        'synthetic.' || %s,
                        'REFERENCES'
                    ),
                    has_table_privilege(
                        current_user,
                        'synthetic.' || %s,
                        'TRIGGER'
                    )
                """,
                (MARKER_TABLE,) * 7,
            )
            assert cur.fetchone() == (
                True, False, True, False, False, False, False, False, False
            )


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO synthetic.{table} (marker) VALUES ('UNAUTHORIZED_WRITE')",
        "UPDATE synthetic.{table} SET marker = 'UNAUTHORIZED_WRITE'",
        "DELETE FROM synthetic.{table}",
        "TRUNCATE TABLE synthetic.{table}",
    ],
)
def test_runtime_cannot_mutate_its_synthetic_marker(statement):
    # MARKER_TABLE is a fixed identifier supplied by the checked-in CI Compose
    # definition, not user input. Validate it before interpolation.
    assert MARKER_TABLE.replace("_", "").isalnum()
    with connect() as conn:
        with conn.cursor() as cur:
            with pytest.raises(psycopg2.errors.InsufficientPrivilege):
                cur.execute(statement.format(table=MARKER_TABLE))
        conn.rollback()


def test_runtime_cannot_create_schema_or_table():
    with connect() as conn:
        with conn.cursor() as cur:
            with pytest.raises(psycopg2.errors.InsufficientPrivilege):
                cur.execute("CREATE SCHEMA aud004_runtime_must_not_create")
        conn.rollback()
        with conn.cursor() as cur:
            with pytest.raises(psycopg2.errors.InsufficientPrivilege):
                cur.execute(
                    "CREATE TABLE synthetic.aud004_runtime_must_not_create "
                    "(id integer)"
                )
        conn.rollback()
