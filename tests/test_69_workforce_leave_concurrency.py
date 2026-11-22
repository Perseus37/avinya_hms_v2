from datetime import date
from types import SimpleNamespace

import pytest

def test_leave_creation_locks_staff_user_before_overlap_lookup():
    """The stable user-row lock must precede the empty-range overlap check."""
    from types import SimpleNamespace

    from backend.domains.identity.models import User, UserStatusEnum
    from backend.domains.workforce.models import LeaveRequest
    from backend.domains.workforce.router import LeaveRequestCreate, create_leave_request

    staff = SimpleNamespace(id=41, status=UserStatusEnum.ACTIVE)

    class FakeResult:
        def __init__(self, value):
            self.value = value

        def scalar_one_or_none(self):
            return self.value

    class FakeSession:
        def __init__(self):
            self.statements = []
            self.added = []
            self.committed = False

        def execute(self, statement):
            self.statements.append(statement)
            return FakeResult(staff if len(self.statements) == 1 else None)

        def add(self, value):
            self.added.append(value)

        def commit(self):
            self.committed = True

        def refresh(self, _value):
            return None

    db = FakeSession()
    payload = LeaveRequestCreate(
        user_id=41,
        leave_type="CASUAL",
        start_date=date(2026, 12, 1),
        end_date=date(2026, 12, 2),
        reason="Personal leave",
    )

    created = create_leave_request(payload, db, SimpleNamespace(id=7))

    assert db.statements[0].column_descriptions[0]["entity"] is User
    assert db.statements[0]._for_update_arg is not None
    assert db.statements[1].column_descriptions[0]["entity"] is LeaveRequest
    assert db.added == [created]
    assert db.committed is True


def test_postgresql_staff_row_lock_serializes_leave_submission():
    """Verify the row-lock primitive used by leave creation with two PG sessions."""
    import os
    import uuid
    import pytest
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import DBAPIError

    database_url = os.getenv("TEST_POSTGRES_URL") or os.getenv("POSTGRES17_TEST_URL")
    if database_url and database_url.startswith("postgresql+psycopg://"):
        database_url = database_url.replace("postgresql+psycopg://", "postgresql+psycopg2://", 1)
    if not database_url:
        pytest.skip("Set POSTGRES17_TEST_URL or TEST_POSTGRES_URL for the PostgreSQL leave-lock proof.")

    engine = create_engine(database_url, pool_pre_ping=True)
    table = f"workforce_leave_lock_{uuid.uuid4().hex}"
    first = second = None
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(f'CREATE TABLE "{table}" (id bigint PRIMARY KEY)')
            connection.exec_driver_sql(f'INSERT INTO "{table}" (id) VALUES (41)')

        first = engine.connect()
        second = engine.connect()
        first.execute(text(f'SELECT id FROM "{table}" WHERE id = 41 FOR UPDATE')).scalar_one()

        with pytest.raises(DBAPIError) as exc_info:
            second.execute(text(f'SELECT id FROM "{table}" WHERE id = 41 FOR UPDATE NOWAIT')).scalar_one()
        original_error = exc_info.value.orig
        sqlstate = getattr(original_error, "sqlstate", None) or getattr(original_error, "pgcode", None)
        assert sqlstate == "55P03", (
            "Expected PostgreSQL lock_not_available (55P03), "
            f"received SQLSTATE {sqlstate!r}: {original_error}"
        )
        second.rollback()

        first.commit()
        second.execute(text(f'SELECT id FROM "{table}" WHERE id = 41 FOR UPDATE NOWAIT')).scalar_one()
        second.commit()
    finally:
        if first is not None:
            first.rollback()
            first.close()
        if second is not None:
            second.rollback()
            second.close()
        with engine.begin() as connection:
            connection.exec_driver_sql(f'DROP TABLE IF EXISTS "{table}"')
        engine.dispose()
