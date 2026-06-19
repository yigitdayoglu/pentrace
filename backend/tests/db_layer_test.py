import asyncio
import os
import sys

# Test icin izole bir DB kullan
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_db_layer.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import datetime as dt
from db import AsyncSessionLocal, init_db, engine
import models


async def main():
    # temiz baslangic
    if os.path.exists("test_db_layer.db"):
        os.remove("test_db_layer.db")
    await init_db()

    # kullanici olustur
    async with AsyncSessionLocal() as db:
        u = models.User(email="t@x.com", password_hash="x", role="user", plan="free")
        db.add(u)
        await db.commit()
        await db.refresh(u)
        uid = u.id
    print("user id:", uid)

    # tarama + asset + finding
    sid = await models.create_scan("example.com", uid)
    print("scan id:", sid)
    await models.set_status(sid, "running")
    await models.add_asset(sid, "subdomain", "www.example.com", {"ip": "1.2.3.4"})
    await models.add_finding(sid, "vulnscan", "high", "Test SQLi", "detay", "http://x/y")
    await models.set_status(sid, "done")

    # okuma
    scan = await models.get_scan(sid)
    assert scan["status"] == "done" and scan["user_id"] == uid
    assets = await models.get_assets(sid)
    findings = await models.get_findings(sid)
    assert len(assets) == 1 and len(findings) == 1
    print("assets:", assets)
    print("findings:", findings)

    # sahiplik filtreli liste
    mine = await models.list_scans(user_id=uid)
    all_scans = await models.list_scans()
    assert len(mine) == 1 and len(all_scans) == 1

    # kota sayaci
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)
    cnt = await models.count_scans_since(uid, since)
    assert cnt == 1, f"kota sayaci yanlis: {cnt}"
    print("son 1 gun tarama sayisi:", cnt)

    await engine.dispose()
    os.remove("test_db_layer.db")
    print("DB LAYER TEST PASSED")


asyncio.run(main())
