"""Opt-in PostgreSQL database-per-tenant ACL proof; synthetic fixtures only."""
import os

import psycopg2
import pytest
from psycopg2 import sql

HOST = os.getenv("AUD004_PGHOST", "127.0.0.1")
PORT = int(os.getenv("AUD004_PGPORT", "55439"))
DATABASES = {
    "a": ("aud004_tenant_a", "tenant_a_api_test", "aud004-a-api-test-only"),
    "b": ("aud004_tenant_b", "tenant_b_api_test", "aud004-b-api-test-only"),
    "cp": ("aud004_control_plane", "control_plane_test", "aud004-cp-test-only"),
}


def connect(target: str):
    database, user, password = DATABASES[target]
    return psycopg2.connect(
        host=HOST, port=PORT, dbname=database, user=user, password=password,
        connect_timeout=3, application_name="aud004-disposable-proof",
    )


def marker(target: str) -> str:
    with connect(target) as conn:
        with conn.cursor() as cur:
            table = "control_marker" if target == "cp" else "tenant_marker"
            cur.execute(sql.SQL("SELECT marker FROM synthetic.{}").format(sql.Identifier(table)))
            return cur.fetchone()[0]


def assert_connect_denied(target: str):
    with pytest.raises(psycopg2.OperationalError) as exc:
        connect(target)
    assert getattr(exc.value, "pgcode", None) == "42501", (
        f"Expected PostgreSQL CONNECT denial (42501), got {getattr(exc.value, 'pgcode', None)!r}; "
        "DNS, server, missing-database and password failures are not isolation passes."
    )


def test_tenant_a_can_read_own_synthetic_database():
    assert marker("a") == "TENANT_A_SYNTHETIC_ONLY"


def test_tenant_b_can_read_own_synthetic_database():
    assert marker("b") == "TENANT_B_SYNTHETIC_ONLY"


def test_tenant_a_cannot_connect_to_tenant_b():
    assert_connect_denied("b")


def test_tenant_b_cannot_connect_to_tenant_a():
    assert_connect_denied("a")


def test_control_plane_can_read_only_its_synthetic_database():
    assert marker("cp") == "CONTROL_PLANE_SYNTHETIC_ONLY"


@pytest.mark.parametrize("target", ["a", "b"])
def test_control_plane_cannot_connect_to_tenant_databases(target):
    assert_connect_denied(target)


@pytest.mark.parametrize("target", ["a", "b", "cp"])
def test_runtime_login_is_not_privileged(target):
    with connect(target) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT rolsuper, rolcreatedb, rolcreaterole "
                "FROM pg_roles WHERE rolname = current_user"
            )
            assert cur.fetchone() == (False, False, False)
