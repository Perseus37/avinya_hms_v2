import os
import secrets
import subprocess
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES17_INTEGRATION") != "1"
    or not os.getenv("POSTGRES17_TEST_URL"),
    reason="Set RUN_POSTGRES17_INTEGRATION=1 and POSTGRES17_TEST_URL for a disposable PostgreSQL 17 instance.",
)


def test_postgresql_17_migrations_match_control_and_tenant_metadata():
    from alembic.runtime.migration import MigrationContext
    from sqlalchemy import inspect
    from alembic.autogenerate import compare_metadata

    from backend.control_plane.models import ControlBase
    from backend.core.database import Base
    from backend.scripts.migrate import (
        upgrade_control_plane_database_url,
        upgrade_tenant_database_url,
    )

    admin_url = make_url(os.environ["POSTGRES17_TEST_URL"]).set(
        drivername="postgresql+psycopg2"
    )
    admin_engine = create_engine(admin_url)
    suffix = uuid.uuid4().hex[:10]
    db_names = (f"test_cp_{suffix}", f"test_tenant_{suffix}")
    database_urls = [
        admin_url.set(database=name).render_as_string(hide_password=False)
        for name in db_names
    ]
    try:
        with admin_engine.connect().execution_options(
            isolation_level="AUTOCOMMIT"
        ) as connection:
            for name in db_names:
                connection.execute(text(f'CREATE DATABASE "{name}"'))

        upgrade_control_plane_database_url(database_urls[0])
        upgrade_tenant_database_url(database_urls[1])

        for database_url, metadata in (
            (database_urls[0], ControlBase.metadata),
            (database_urls[1], Base.metadata),
        ):
            engine = create_engine(database_url)
            try:
                with engine.connect() as connection:
                    differences = compare_metadata(
                        MigrationContext.configure(
                            connection, opts={"compare_type": True}
                        ),
                        metadata,
                    )
                    assert set(inspect(connection).get_table_names()) - {
                        "alembic_version"
                    } == set(metadata.tables)
                    assert differences == []
                    if metadata is Base.metadata:
                        audit_trigger = connection.execute(text("""
                            SELECT EXISTS (
                                SELECT 1
                                FROM pg_trigger
                                WHERE tgname = 'trg_procurement_reconciliation_notification_config_events_immutable'
                                  AND NOT tgisinternal
                            )
                        """)).scalar_one()
                        assert audit_trigger is True
            finally:
                engine.dispose()
    finally:
        with admin_engine.connect().execution_options(
            isolation_level="AUTOCOMMIT"
        ) as connection:
            for name in db_names:
                connection.execute(
                    text(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                        "WHERE datname = :db_name AND pid <> pg_backend_pid()"
                    ),
                    {"db_name": name},
                )
                connection.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
        admin_engine.dispose()


@pytest.mark.skipif(
    not os.getenv("POSTGRES17_DOCKER_CONTAINER"),
    reason="Set POSTGRES17_DOCKER_CONTAINER to exercise pg_dump/GPG/pg_restore round-trip.",
)
def test_postgresql_17_encrypted_custom_dump_restores_into_isolated_database():
    admin_url = make_url(os.environ["POSTGRES17_TEST_URL"]).set(
        drivername="postgresql+psycopg2"
    )
    admin_engine = create_engine(admin_url)
    suffix = uuid.uuid4().hex[:10]
    source_name = f"test_backup_{suffix}"
    target_name = f"test_restore_{suffix}"
    container = os.environ["POSTGRES17_DOCKER_CONTAINER"]
    container_port = os.getenv("POSTGRES17_CONTAINER_PORT", "5432")
    passphrase = secrets.token_urlsafe(32)
    created_databases = []

    def docker_exec(*args, input_bytes=None):
        return subprocess.run(
            ["docker", "exec", *args],
            input=input_bytes,
            capture_output=True,
            check=True,
        )

    try:
        with admin_engine.connect().execution_options(
            isolation_level="AUTOCOMMIT"
        ) as connection:
            for database_name in (source_name, target_name):
                connection.execute(text(f'CREATE DATABASE "{database_name}"'))
                created_databases.append(database_name)

        source_engine = create_engine(
            admin_url.set(database=source_name).render_as_string(
                hide_password=False
            )
        )
        try:
            with source_engine.begin() as connection:
                connection.execute(
                    text(
                        "CREATE TABLE backup_probe "
                        "(id integer PRIMARY KEY, value text NOT NULL)"
                    )
                )
                connection.execute(
                    text("INSERT INTO backup_probe (id, value) VALUES (1, 'ok')")
                )
        finally:
            source_engine.dispose()

        pg_dump = docker_exec(
            "-e",
            f"PGPASSWORD={admin_url.password or ''}",
            container,
            "pg_dump",
            "-h",
            "127.0.0.1",
            "-p",
            container_port,
            "-U",
            admin_url.username or "postgres",
            "--format=custom",
            "--no-owner",
            "--no-acl",
            source_name,
        ).stdout
        assert pg_dump

        encrypt = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--interactive",
                "--env",
                f"TEST_GPG_PASSPHRASE={passphrase}",
                "alpine:3.21",
                "sh",
                "-ec",
                "apk add --no-cache gnupg >/dev/null; "
                "printf '%s' \"$TEST_GPG_PASSPHRASE\" > /tmp/pass; "
                "gpg --batch --quiet --yes --pinentry-mode loopback "
                "--symmetric --cipher-algo AES256 "
                "--passphrase-file /tmp/pass --output /tmp/backup.gpg; "
                "cat /tmp/backup.gpg",
            ],
            input=pg_dump,
            capture_output=True,
            check=True,
        ).stdout

        decrypt = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--interactive",
                "--env",
                f"TEST_GPG_PASSPHRASE={passphrase}",
                "alpine:3.21",
                "sh",
                "-ec",
                "apk add --no-cache gnupg >/dev/null; "
                "printf '%s' \"$TEST_GPG_PASSPHRASE\" > /tmp/pass; "
                "cat > /tmp/backup.gpg; "
                "gpg --batch --quiet --pinentry-mode loopback --decrypt "
                "--passphrase-file /tmp/pass /tmp/backup.gpg",
            ],
            input=encrypt,
            capture_output=True,
            check=True,
        ).stdout
        assert decrypt == pg_dump

        docker_exec(
            "--interactive",
            "-e",
            f"PGPASSWORD={admin_url.password or ''}",
            container,
            "pg_restore",
            "--exit-on-error",
            "--no-owner",
            "--no-acl",
            "-h",
            "127.0.0.1",
            "-p",
            container_port,
            "-U",
            admin_url.username or "postgres",
            "--dbname",
            target_name,
            input_bytes=decrypt,
        )
        target_engine = create_engine(
            admin_url.set(database=target_name).render_as_string(
                hide_password=False
            )
        )
        try:
            with target_engine.connect() as connection:
                restored = connection.execute(
                    text("SELECT id, value FROM backup_probe")
                ).one()
            assert restored == (1, "ok")
        finally:
            target_engine.dispose()
    finally:
        with admin_engine.connect().execution_options(
            isolation_level="AUTOCOMMIT"
        ) as connection:
            for database_name in created_databases:
                connection.execute(
                    text(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                        "WHERE datname = :db_name AND pid <> pg_backend_pid()"
                    ),
                    {"db_name": database_name},
                )
                connection.execute(
                    text(f'DROP DATABASE IF EXISTS "{database_name}"')
                )
        admin_engine.dispose()

def test_postgresql_pacs_write_serializes_with_terminal_task_transition():
    """A PACS writer waiting behind verification/cancellation must observe terminal task state."""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    import time

    engine_url = make_url(os.environ["POSTGRES17_TEST_URL"]).set(
        drivername="postgresql+psycopg2"
    )
    engine = create_engine(engine_url, pool_size=4)
    suffix = uuid.uuid4().hex[:12]
    orders = f"pacs_lock_orders_{suffix}"
    tasks = f"pacs_lock_tasks_{suffix}"
    metadata = f"pacs_lock_metadata_{suffix}"

    try:
        with engine.begin() as connection:
            connection.execute(text(
                f'CREATE TABLE "{orders}" (id bigint PRIMARY KEY, status text NOT NULL)'
            ))
            connection.execute(text(
                f'CREATE TABLE "{tasks}" (id bigint PRIMARY KEY, order_id bigint NOT NULL '
                f'REFERENCES "{orders}"(id), status text NOT NULL)'
            ))
            connection.execute(text(
                f'CREATE TABLE "{metadata}" (task_id bigint PRIMARY KEY '
                f'REFERENCES "{tasks}"(id), impression text)'
            ))
            connection.execute(
                text(f'INSERT INTO "{orders}" (id, status) VALUES (1, \'ACTIVE\'), (2, \'ACTIVE\')')
            )
            connection.execute(
                text(f'INSERT INTO "{tasks}" (id, order_id, status) VALUES (11, 1, \'PENDING\'), (22, 2, \'PENDING\')')
            )

        def exercise_terminal_race(order_id: int, task_id: int, terminal_status: str):
            order_locked = Event()
            pacs_attempting_lock = Event()
            allow_terminal_commit = Event()
            pacs_backend_pid = []

            def terminal_transition():
                with engine.begin() as connection:
                    connection.execute(
                        text(f'SELECT id FROM "{orders}" WHERE id = :id FOR UPDATE'),
                        {"id": order_id},
                    ).one()
                    order_locked.set()
                    assert allow_terminal_commit.wait(timeout=10), "PACS race did not start"
                    connection.execute(
                        text(f'UPDATE "{tasks}" SET status = :status WHERE id = :id'),
                        {"status": terminal_status, "id": task_id},
                    )

            def pacs_write():
                assert order_locked.wait(timeout=10), "terminal transaction did not acquire order lock"
                with engine.begin() as connection:
                    pacs_backend_pid.append(
                        connection.execute(text("SELECT pg_backend_pid()")).scalar_one()
                    )
                    pacs_attempting_lock.set()
                    connection.execute(
                        text(f'SELECT id FROM "{orders}" WHERE id = :id FOR UPDATE'),
                        {"id": order_id},
                    ).one()
                    task_status = connection.execute(
                        text(f'SELECT status FROM "{tasks}" WHERE id = :id FOR UPDATE'),
                        {"id": task_id},
                    ).scalar_one()
                    if task_status not in {"VERIFIED", "CANCELLED"}:
                        connection.execute(
                            text(f'INSERT INTO "{metadata}" (task_id, impression) VALUES (:id, \'PACS result\')'),
                            {"id": task_id},
                        )
                    return task_status

            with ThreadPoolExecutor(max_workers=2) as executor:
                terminal_future = executor.submit(terminal_transition)
                pacs_future = executor.submit(pacs_write)
                assert pacs_attempting_lock.wait(timeout=10), "PACS writer did not attempt its parent lock"
                deadline = time.monotonic() + 5
                was_blocked_by_terminal_writer = False
                while time.monotonic() < deadline:
                    with engine.connect() as monitor:
                        was_blocked_by_terminal_writer = monitor.execute(
                            text("SELECT cardinality(pg_blocking_pids(:pid)) > 0"),
                            {"pid": pacs_backend_pid[0]},
                        ).scalar_one()
                    if was_blocked_by_terminal_writer:
                        break
                    time.sleep(0.01)
                allow_terminal_commit.set()
                assert was_blocked_by_terminal_writer, "PACS transaction was not observed waiting on the terminal-state lock"
                terminal_future.result(timeout=15)
                observed_status = pacs_future.result(timeout=15)

            assert observed_status == terminal_status
            with engine.connect() as connection:
                persisted_status = connection.execute(
                    text(f'SELECT status FROM "{tasks}" WHERE id = :id'),
                    {"id": task_id},
                ).scalar_one()
                metadata_count = connection.execute(
                    text(f'SELECT count(*) FROM "{metadata}" WHERE task_id = :id'),
                    {"id": task_id},
                ).scalar_one()
            assert persisted_status == terminal_status
            assert metadata_count == 0

        exercise_terminal_race(1, 11, "VERIFIED")
        exercise_terminal_race(2, 22, "CANCELLED")
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP TABLE IF EXISTS "{metadata}"'))
            connection.execute(text(f'DROP TABLE IF EXISTS "{tasks}"'))
            connection.execute(text(f'DROP TABLE IF EXISTS "{orders}"'))
        engine.dispose()