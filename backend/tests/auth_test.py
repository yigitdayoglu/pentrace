import asyncio
import os
import sys

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_auth.db"
os.environ["FREE_DAILY_SCANS"] = "2"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import auth
from db import AsyncSessionLocal, init_db, engine
import models


async def main():
    if os.path.exists("test_auth.db"):
        os.remove("test_auth.db")
    await init_db()

    # --- sifre hash ---
    h = auth.hash_password("hunter2")
    assert h != "hunter2"
    assert auth.verify_password("hunter2", h)
    assert not auth.verify_password("wrong", h)
    print("sifre hash/verify OK")

    # --- JWT ---
    tok = auth.create_access_token(42)
    assert auth.decode_token(tok) == 42
    assert auth.decode_token("garbage") is None
    print("JWT encode/decode OK")

    # --- kota (free=2) ---
    async with AsyncSessionLocal() as db:
        u = models.User(email="q@x.com", password_hash=h, role="user", plan="free")
        db.add(u)
        await db.commit()
        await db.refresh(u)

    # 2 tarama olustur -> 3.'de kota dolmali
    await models.create_scan("a.com", u.id)
    st = await auth.quota_status(u)
    print("kota durumu:", st)
    assert st["used"] == 1 and st["limit"] == 2

    await auth.check_quota(u)  # 2. izin verilmeli
    await models.create_scan("b.com", u.id)

    try:
        await auth.check_quota(u)  # 3. -> 429
        raise SystemExit("kota asimi yakalanmadi!")
    except Exception as e:
        from fastapi import HTTPException
        assert isinstance(e, HTTPException) and e.status_code == 429
        print("kota asimi dogru sekilde engellendi (429)")

    await engine.dispose()
    os.remove("test_auth.db")
    print("AUTH TEST PASSED")


asyncio.run(main())
