"""ORM modelleri (Scan, Asset, Finding) + async repository fonksiyonlari.

Tek kullanicili yerel masaustu uygulamasi — kullanici/oturum/kimlik dogrulama yok.
"""
from __future__ import annotations

import datetime as _dt
import json
import uuid
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, func, select
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import AsyncSessionLocal, Base

_TS = DateTime(timezone=True)

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
VALID_STATUS = {"pending", "running", "done", "failed"}


def _now() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


# --------------------------------------------------------------------------- #
# ORM
# --------------------------------------------------------------------------- #
class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[str] = mapped_column(String(12), primary_key=True)
    target: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[_dt.datetime] = mapped_column(_TS, default=_now)
    finished_at: Mapped[_dt.datetime | None] = mapped_column(_TS, nullable=True)

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
# Serializasyon
# --------------------------------------------------------------------------- #
def scan_dict(s: Scan) -> dict[str, Any]:
    return {
        "id": s.id, "target": s.target, "status": s.status,
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
# Repository
# --------------------------------------------------------------------------- #
async def create_scan(target: str) -> str:
    scan_id = uuid.uuid4().hex[:12]
    async with AsyncSessionLocal() as db:
        db.add(Scan(id=scan_id, target=target, status="pending"))
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


async def list_scans() -> list[dict[str, Any]]:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(Scan).order_by(Scan.created_at.desc()))).scalars().all()
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
