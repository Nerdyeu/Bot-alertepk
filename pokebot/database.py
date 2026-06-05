"""Couche base de donnees (SQLite via SQLAlchemy 2.0)."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, echo=False, future=True, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def init_db() -> None:
    """Cree les tables si elles n'existent pas."""
    from . import models  # noqa: F401  (enregistre les modeles sur Base)

    Base.metadata.create_all(engine)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Session transactionnelle : commit a la sortie, rollback en cas d'erreur."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
