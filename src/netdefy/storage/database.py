"""NETDEFY — Database Connection & Engine Configuration (Phase 6).

Initializes SQLAlchemy connection pools with SQLite (WAL mode) for local dev
and PostgreSQL connection string compatibility for production.
"""

from __future__ import annotations

import logging
from collections.abc import Generator
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from netdefy.storage.models import Base

logger = logging.getLogger(__name__)

DEFAULT_SQLITE_PATH = Path("reports") / "netdefy_soc.db"


def configure_sqlite_pragmas(dbapi_con: Any, _con_record: Any) -> None:
    """Enable SQLite WAL mode, foreign keys, and synchronous NORMAL for high throughput."""
    cursor = dbapi_con.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_engine(db_url: str | None = None) -> Engine:
    """Create SQLAlchemy engine with appropriate pooling and dialect pragmas."""
    if not db_url:
        DEFAULT_SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
        db_url = f"sqlite:///{DEFAULT_SQLITE_PATH}"

    is_sqlite = db_url.startswith("sqlite")
    engine = create_engine(
        db_url,
        echo=False,
        connect_args={"check_same_thread": False} if is_sqlite else {},
    )

    if is_sqlite:
        event.listen(engine, "connect", configure_sqlite_pragmas)

    return engine


def init_db(engine: Engine) -> None:
    """Create all database tables defined in ORM metadata."""
    Base.metadata.create_all(bind=engine)
    logger.info("Initialized database tables on %s", engine.url)


def get_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create session factory bound to given engine."""
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


class DatabaseManager:
    """Convenience context manager for database sessions."""

    def __init__(self, db_url: str | None = None) -> None:
        self.engine = get_engine(db_url)
        init_db(self.engine)
        self.session_factory = get_session_factory(self.engine)

    def get_session(self) -> Generator[Session, None, None]:
        """Provide a transactional database session."""
        session: Session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
