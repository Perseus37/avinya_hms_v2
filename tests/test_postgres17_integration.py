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
                        pharmacy_adjustment_trigger = connection.execute(text("""
                            SELECT EXISTS (
                                SELECT 1
                                FROM pg_trigger
                                WHERE tgname = 'trg_inventory_stock_adjustment_logs_immutable'
                                  AND NOT tgisinternal
                            )
                        """)).scalar_one()
                        assert pharmacy_adjustment_trigger is True
                        supplier_credit_triggers = connection.execute(text("""
                            SELECT COUNT(*) = 2
                            FROM pg_trigger AS trigger_row
                            JOIN pg_class AS table_row ON table_row.oid = trigger_row.tgrelid
                            WHERE trigger_row.tgname IN (
                                'trg_procurement_supplier_credit_notes_immutable',
                                'trg_procurement_supplier_credit_allocations_immutable'
                            )
                              AND table_row.relname IN (
                                'procurement_supplier_credit_notes',
                                'procurement_supplier_credit_allocations'
                            )
                              AND NOT trigger_row.tgisinternal
                        """)).scalar_one()
                        assert supplier_credit_triggers is True
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


def test_postgresql_operative_record_write_serializes_with_terminal_surgery_transition():
    """Operative-record writers must wait for, then observe, terminal surgery state."""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    import time

    engine_url = make_url(os.environ["POSTGRES17_TEST_URL"]).set(
        drivername="postgresql+psycopg2"
    )
    engine = create_engine(engine_url, pool_size=4)
    suffix = uuid.uuid4().hex[:12]
    schedules = f"surgery_lock_schedules_{suffix}"
    records = f"surgery_lock_records_{suffix}"

    try:
        with engine.begin() as connection:
            connection.execute(text(
                f'CREATE TABLE "{schedules}" (id bigint PRIMARY KEY, status text NOT NULL)'
            ))
            connection.execute(text(
                f'CREATE TABLE "{records}" (surgery_id bigint PRIMARY KEY '
                f'REFERENCES "{schedules}"(id), findings text NOT NULL)'
            ))
            connection.execute(
                text(f'INSERT INTO "{schedules}" (id, status) VALUES (1, \'IN_PROGRESS\'), (2, \'IN_PROGRESS\')')
            )
            connection.execute(
                text(f'INSERT INTO "{records}" (surgery_id, findings) VALUES (1, \'Original 1\'), (2, \'Original 2\')')
            )

        def exercise_terminal_race(surgery_id: int, terminal_status: str):
            schedule_locked = Event()
            writer_attempting_lock = Event()
            allow_terminal_commit = Event()
            writer_backend_pid = []

            def terminal_transition():
                with engine.begin() as connection:
                    connection.execute(
                        text(f'SELECT id FROM "{schedules}" WHERE id = :id FOR UPDATE'),
                        {"id": surgery_id},
                    ).one()
                    schedule_locked.set()
                    assert allow_terminal_commit.wait(timeout=10), "operative writer did not start"
                    connection.execute(
                        text(f'UPDATE "{schedules}" SET status = :status WHERE id = :id'),
                        {"status": terminal_status, "id": surgery_id},
                    )

            def operative_record_write():
                assert schedule_locked.wait(timeout=10), "terminal transition did not acquire schedule lock"
                with engine.begin() as connection:
                    writer_backend_pid.append(
                        connection.execute(text("SELECT pg_backend_pid()")).scalar_one()
                    )
                    writer_attempting_lock.set()
                    schedule = connection.execute(
                        text(f'SELECT status FROM "{schedules}" WHERE id = :id FOR UPDATE'),
                        {"id": surgery_id},
                    ).scalar_one()
                    connection.execute(
                        text(f'SELECT surgery_id FROM "{records}" WHERE surgery_id = :id FOR UPDATE'),
                        {"id": surgery_id},
                    ).one()
                    if schedule not in {"COMPLETED", "CANCELLED"}:
                        connection.execute(
                            text(f'UPDATE "{records}" SET findings = \'Replacement\' WHERE surgery_id = :id'),
                            {"id": surgery_id},
                        )
                    return schedule

            with ThreadPoolExecutor(max_workers=2) as executor:
                terminal_future = executor.submit(terminal_transition)
                writer_future = executor.submit(operative_record_write)
                assert writer_attempting_lock.wait(timeout=10), "operative writer did not attempt schedule lock"
                deadline = time.monotonic() + 5
                was_blocked = False
                while time.monotonic() < deadline:
                    with engine.connect() as monitor:
                        was_blocked = monitor.execute(
                            text("SELECT cardinality(pg_blocking_pids(:pid)) > 0"),
                            {"pid": writer_backend_pid[0]},
                        ).scalar_one()
                    if was_blocked:
                        break
                    time.sleep(0.01)
                allow_terminal_commit.set()
                assert was_blocked, "operative writer was not observed waiting on terminal schedule lock"
                terminal_future.result(timeout=15)
                observed_status = writer_future.result(timeout=15)

            assert observed_status == terminal_status
            with engine.connect() as connection:
                persisted_status = connection.execute(
                    text(f'SELECT status FROM "{schedules}" WHERE id = :id'),
                    {"id": surgery_id},
                ).scalar_one()
                findings = connection.execute(
                    text(f'SELECT findings FROM "{records}" WHERE surgery_id = :id'),
                    {"id": surgery_id},
                ).scalar_one()
            assert persisted_status == terminal_status
            assert findings == f"Original {surgery_id}"

        exercise_terminal_race(1, "COMPLETED")
        exercise_terminal_race(2, "CANCELLED")
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP TABLE IF EXISTS "{records}"'))
            connection.execute(text(f'DROP TABLE IF EXISTS "{schedules}"'))
        engine.dispose()
