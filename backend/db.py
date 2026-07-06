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


def _legacy_schema(sync_conn) -> bool:
    """Eski (auth'lu) semayi tespit et: scans tablosunda artik olmayan
    user_id kolonu varsa DB eski surumden kalmadir ve yeni kodla uyumsuzdur."""
    from sqlalchemy import inspect
    insp = inspect(sync_conn)
    if "scans" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("scans")}
        return "user_id" in cols
    return False


async def init_db() -> None:
    """Tablolari olustur (idempotent). models import edilmis olmali.

    Eski auth semasindan kalma uyumsuz bir DB varsa (scans.user_id NOT NULL),
    tarama baslatirken 500 verir. Bu durumda tablolari sifirla — masaustu
    surumunde tarama verisi geçicidir, kayip onemsizdir.
    """
    import models  # noqa: F401 — modelleri Base'e kaydet
    async with engine.begin() as conn:
        if await conn.run_sync(_legacy_schema):
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency — istek basina session."""
    async with AsyncSessionLocal() as session:
        yield session
