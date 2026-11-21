from pathlib import Path

from sqlalchemy import Engine, URL, create_engine, event
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


database_path = Path(__file__).resolve().parents[2] / "kahvecell.db"
engine = create_engine(
    URL.create("sqlite", database=str(database_path)),
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def enable_sqlite_foreign_keys(connection, _connection_record) -> None:
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_db_and_tables(target_engine: Engine = engine) -> None:
    from app.models import entities  # noqa: F401

    Base.metadata.create_all(bind=target_engine)
