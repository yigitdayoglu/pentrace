"""SQLAlchemy 2.0 async engine + session yonetimi."""
from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession, async_sessionmaker, create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from config import settings


class Base(DeclarativeBase):
    pass


# SQLite icin connect_args; Postgres'te gerekmez.
_connect_args = {}
if settings.database_url.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}
    # SQLite dosyasinin ust dizini yoksa olustur (desktop/yeni veri dizini icin).
    import re as _re
    from pathlib import Path as _Path
    _m = _re.search(r"sqlite\+aiosqlite:///(.+)", settings.database_url)
    if _m:
        _dbfile = _m.group(1)
        if _dbfile and _dbfile != ":memory:":
            _Path(_dbfile).expanduser().parent.mkdir(parents=True, exist_ok=True)

engine = create_async_engine(settings.database_url, echo=False, connect_args=_connect_args)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    """Tablolari olustur (idempotent). models import edilmis olmali."""
    import models  # noqa: F401 — modelleri Base'e kaydet
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency — istek basina session."""
    async with AsyncSessionLocal() as session:
        yield session
