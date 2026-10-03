from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
DATA_DIRECTORY = BACKEND_DIRECTORY / "data"
DATABASE_URL = f"sqlite:///{DATA_DIRECTORY / 'memora.db'}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create the local data directory and apply safe additive MVP schema updates."""
    DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)
    from app import models  # Ensure model metadata is registered before create_all.

    Base.metadata.create_all(bind=engine)
    existing_columns = {column["name"] for column in inspect(engine).get_columns("memories")}
    additions = {
        "summary": "TEXT",
        "context_inference": "TEXT",
    }
    with engine.begin() as connection:
        for column_name, column_type in additions.items():
            if column_name not in existing_columns:
                connection.execute(text(f"ALTER TABLE memories ADD COLUMN {column_name} {column_type}"))
