from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy import event
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.models.base import Base


settings = get_settings()
SQLITE_TIMEOUT_SECONDS = 30
SQLITE_BUSY_TIMEOUT_MS = SQLITE_TIMEOUT_SECONDS * 1000

sqlite_connect_args = {}
if settings.database_url.startswith("sqlite"):
    sqlite_connect_args = {
        "check_same_thread": False,
        "timeout": SQLITE_TIMEOUT_SECONDS,
    }

engine = create_engine(
    settings.database_url,
    connect_args=sqlite_connect_args,
    future=True,
)

if settings.database_url.startswith("sqlite"):
    SQLITE_JOURNAL_MODES = {"DELETE", "TRUNCATE", "PERSIST", "MEMORY", "WAL", "OFF"}
    sqlite_journal_mode = settings.sqlite_journal_mode.upper()
    if sqlite_journal_mode not in SQLITE_JOURNAL_MODES:
        sqlite_journal_mode = "TRUNCATE"

    @event.listens_for(engine, "connect")
    def _configure_sqlite(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute(f"PRAGMA journal_mode={sqlite_journal_mode}")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
        cursor.close()

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    if engine.dialect.name == "sqlite":
        _ensure_sqlite_lead_quality_columns()
        _ensure_sqlite_lead_exclusion_columns()


def _ensure_sqlite_lead_quality_columns() -> None:
    columns = {
        "company_size_fit": "VARCHAR(40) NOT NULL DEFAULT 'unknown'",
        "company_size_fit_explanation": "TEXT",
        "company_size_fit_metadata_json": "TEXT NOT NULL DEFAULT '{}'",
        "trade_type": "VARCHAR(40) NOT NULL DEFAULT 'unknown'",
        "trade_type_explanation": "TEXT",
        "trade_type_metadata_json": "TEXT NOT NULL DEFAULT '{}'",
        "quality_classified_at": "DATETIME",
    }
    indexes = {
        "ix_leads_org_company_size_fit": "organization_id, company_size_fit",
        "ix_leads_org_trade_type": "organization_id, trade_type",
    }
    with engine.begin() as connection:
        existing_columns = {
            row[1]
            for row in connection.exec_driver_sql("PRAGMA table_info(leads)").fetchall()
        }
        for name, definition in columns.items():
            if name not in existing_columns:
                connection.exec_driver_sql(f"ALTER TABLE leads ADD COLUMN {name} {definition}")

        for name, column_list in indexes.items():
            connection.exec_driver_sql(
                f"CREATE INDEX IF NOT EXISTS {name} ON leads ({column_list})"
            )


def _ensure_sqlite_lead_exclusion_columns() -> None:
    columns = {
        "is_blocked": "BOOLEAN NOT NULL DEFAULT 0",
        "blocked_reason": "TEXT",
        "blocked_rule_id": "INTEGER",
        "blocked_at": "DATETIME",
    }
    indexes = {
        "ix_leads_org_is_blocked": "organization_id, is_blocked",
        "ix_leads_blocked_rule_id": "blocked_rule_id",
        "ix_leads_blocked_at": "blocked_at",
    }
    with engine.begin() as connection:
        existing_columns = {
            row[1]
            for row in connection.exec_driver_sql("PRAGMA table_info(leads)").fetchall()
        }
        for name, definition in columns.items():
            if name not in existing_columns:
                connection.exec_driver_sql(f"ALTER TABLE leads ADD COLUMN {name} {definition}")

        for name, column_list in indexes.items():
            connection.exec_driver_sql(
                f"CREATE INDEX IF NOT EXISTS {name} ON leads ({column_list})"
            )
