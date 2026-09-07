from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from attendance_api.config import get_settings

engine = create_engine(get_settings().database_url, pool_pre_ping=True, pool_recycle=1800)
SessionFactory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    with SessionFactory() as session:
        yield session
