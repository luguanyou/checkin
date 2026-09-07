import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from attendance_api.db import get_db
from attendance_api.main import create_app


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    database_url = os.environ.get(
        "DATABASE_URL",
        "mysql+pymysql://attendance:attendance@127.0.0.1:33307/attendance_test",
    )
    test_engine = create_engine(database_url, pool_pre_ping=True)
    try:
        yield test_engine
    finally:
        test_engine.dispose()


@pytest.fixture
def db_session(engine: Engine) -> Iterator[Session]:
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    app = create_app()

    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client
