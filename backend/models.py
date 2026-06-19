"""ORM modelleri (User, Scan, Asset, Finding) + async repository fonksiyonlari.

Repository fonksiyonlari kendi session'larini yonetir; pipeline ve report bunlari
dogrudan cagirir. API katmani genelde dependency ile session alir.
"""
from __future__ import annotations

import datetime as _dt
import uuid
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

# Tum zaman damgalari timezone-aware (Postgres TIMESTAMPTZ + SQLite uyumlu)
_TS = DateTime(timezone=True)

from db import AsyncSessionLocal, Base

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
VALID_STATUS = {"pending", "running", "done", "failed"}


def _now() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


# --------------------------------------------------------------------------- #
# ORM
# --------------------------------------------------------------------------- #
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="user")   # user | admin
    plan: Mapped[str] = mapped_column(String(20), default="free")   # free | pro
    created_at: Mapped[_dt.datetime] = mapped_column(_TS, default=_now)

    # Mail dogrulama
    is_verified: Mapped[bool] = mapped_column(default=False)
    verification_code: Mapped[str | None] = mapped_column(String(6), nullable=True)
    verification_sent_at: Mapped[_dt.datetime | None] = mapped_column(_TS, nullable=True)

    # IP abuse engeli — kaydin yapildigi IP
    signup_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)  # IPv6 max 45

    scans: Mapped[list["Scan"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[str] = mapped_column(String(12), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    target: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[_dt.datetime] = mapped_column(_TS, default=_now)
    finished_at: Mapped[_dt.datetime | None] = mapped_column(_TS, nullable=True)

    user: Mapped["User"] = relationship(back_populates="scans")
    assets: Mapped[list["Asset"]] = relationship(cascade="all, delete-orphan")
    findings: Mapped[list["Finding"]] = relationship(cascade="all, delete-orphan")


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    scan_id: Mapped[str] = mapped_column(ForeignKey("scans.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(20))
    value: Mapped[str] = mapped_column(String(512))
    meta: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(primary_key=True)
    scan_id: Mapped[str] = mapped_column(ForeignKey("scans.id", ondelete="CASCADE"), index=True)
    module: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(255))
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    target: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[_dt.datetime] = mapped_column(_TS, default=_now)


# --------------------------------------------------------------------------- #
# Serializasyon yardimcilari
# --------------------------------------------------------------------------- #
import json


def scan_dict(s: Scan) -> dict[str, Any]:
    return {
        "id": s.id, "user_id": s.user_id, "target": s.target, "status": s.status,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "finished_at": s.finished_at.isoformat() if s.finished_at else None,
    }


def asset_dict(a: Asset) -> dict[str, Any]:
    return {
        "id": a.id, "scan_id": a.scan_id, "type": a.type, "value": a.value,
        "meta": json.loads(a.meta) if a.meta else None,
    }


def finding_dict(f: Finding) -> dict[str, Any]:
    return {
        "id": f.id, "scan_id": f.scan_id, "module": f.module, "severity": f.severity,
        "title": f.title, "detail": f.detail, "target": f.target,
    }


# --------------------------------------------------------------------------- #
# Repository fonksiyonlari (kendi session'ini acar)
# --------------------------------------------------------------------------- #
async def create_scan(target: str, user_id: int) -> str:
    scan_id = uuid.uuid4().hex[:12]
    async with AsyncSessionLocal() as db:
        db.add(Scan(id=scan_id, user_id=user_id, target=target, status="pending"))
        await db.commit()
    return scan_id


async def set_status(scan_id: str, status: str) -> None:
    if status not in VALID_STATUS:
        raise ValueError(f"gecersiz durum: {status}")
    async with AsyncSessionLocal() as db:
        scan = await db.get(Scan, scan_id)
        if scan:
            scan.status = status
            if status in ("done", "failed"):
                scan.finished_at = _now()
            await db.commit()


async def add_asset(scan_id: str, type_: str, value: str, meta: dict | None = None) -> None:
    async with AsyncSessionLocal() as db:
        db.add(Asset(scan_id=scan_id, type=type_, value=value,
                     meta=json.dumps(meta) if meta else None))
        await db.commit()


async def add_finding(scan_id: str, module: str, severity: str, title: str,
                      detail: str = "", target: str = "") -> None:
    if severity not in SEVERITY_ORDER:
        severity = "info"
    async with AsyncSessionLocal() as db:
        db.add(Finding(scan_id=scan_id, module=module, severity=severity,
                       title=title, detail=detail, target=target))
        await db.commit()


async def get_scan(scan_id: str) -> dict[str, Any] | None:
    async with AsyncSessionLocal() as db:
        scan = await db.get(Scan, scan_id)
        return scan_dict(scan) if scan else None


async def list_scans(user_id: int | None = None) -> list[dict[str, Any]]:
    """user_id verilirse yalnizca o kullanicininkiler; None ise hepsi (admin)."""
    async with AsyncSessionLocal() as db:
        stmt = select(Scan).order_by(Scan.created_at.desc())
        if user_id is not None:
            stmt = stmt.where(Scan.user_id == user_id)
        rows = (await db.execute(stmt)).scalars().all()
        return [scan_dict(s) for s in rows]


async def get_assets(scan_id: str) -> list[dict[str, Any]]:
    async with AsyncSessionLocal() as db:
        stmt = select(Asset).where(Asset.scan_id == scan_id).order_by(Asset.type, Asset.value)
        rows = (await db.execute(stmt)).scalars().all()
        return [asset_dict(a) for a in rows]


async def get_findings(scan_id: str) -> list[dict[str, Any]]:
    async with AsyncSessionLocal() as db:
        stmt = select(Finding).where(Finding.scan_id == scan_id)
        rows = (await db.execute(stmt)).scalars().all()
    out = [finding_dict(f) for f in rows]
    out.sort(key=lambda f: SEVERITY_ORDER.get(f["severity"], 99))
    return out


async def count_scans_since(user_id: int, since: _dt.datetime) -> int:
    """Kota icin: kullanicinin `since`'dan beri baslattigi tarama sayisi."""
    async with AsyncSessionLocal() as db:
        stmt = select(func.count()).select_from(Scan).where(
            Scan.user_id == user_id, Scan.created_at >= since
        )
        return int((await db.execute(stmt)).scalar() or 0)


async def count_accounts_from_ip(ip: str, since: _dt.datetime) -> int:
    """IP abuse engeli: bir IP'den `since`'dan beri acilan hesap sayisi."""
    async with AsyncSessionLocal() as db:
        stmt = select(func.count()).select_from(User).where(
            User.signup_ip == ip, User.created_at >= since
        )
        return int((await db.execute(stmt)).scalar() or 0)
