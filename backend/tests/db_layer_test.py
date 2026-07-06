import asyncio
import os
import sys

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_db_layer.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import engine, init_db
import models


async def main():
    if os.path.exists("test_db_layer.db"):
        os.remove("test_db_layer.db")
    await init_db()

    sid = await models.create_scan("example.com")
    print("scan id:", sid)
    await models.set_status(sid, "running")
    await models.add_asset(sid, "subdomain", "www.example.com", {"ip": "1.2.3.4"})
    await models.add_finding(sid, "vulnscan", "high", "Test SQLi", "detay", "http://x/y")
    await models.set_status(sid, "done")

    scan = await models.get_scan(sid)
    assert scan["status"] == "done"
    assets = await models.get_assets(sid)
    findings = await models.get_findings(sid)
    assert len(assets) == 1 and len(findings) == 1
    print("assets:", assets)
    print("findings:", findings)

    all_scans = await models.list_scans()
    assert len(all_scans) == 1

    await engine.dispose()
    os.remove("test_db_layer.db")
    print("DB LAYER TEST PASSED")


asyncio.run(main())
