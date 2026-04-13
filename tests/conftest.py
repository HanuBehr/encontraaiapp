from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.api.deps import get_app_settings, get_db_session
from app.api.main import app
from app.config import Settings
from app.models.base import Base


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    TestingSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )
    Base.metadata.create_all(bind=engine)
    try:
        yield TestingSessionLocal
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def db_session(session_factory) -> Session:
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(session_factory) -> TestClient:
    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    def override_settings() -> Settings:
        return Settings(
            APP_ENV="test",
            DATABASE_URL="sqlite://",
            EXPORT_DIR="./data/exports",
            GOOGLE_API_KEY="",
        )

    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_app_settings] = override_settings
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
