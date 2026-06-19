import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules import vulnscan as v


async def main():
    async def log(level, msg):
        print(f"[{level}] {msg}")

    res = await v.run_vulnscan(["http://127.0.0.1:8099/"], log=log)
    print("=== TOTAL FINDINGS:", len(res))
    for f in sorted(res, key=lambda x: x["severity"]):
        print(f"  [{f['severity']}] {f['title']} -> {f['target']}")

    titles = " ".join(f["title"] for f in res)
    expect = {
        "SQLi": "SQL Injection" in titles,
        "XSS": "XSS" in titles,
        "OpenRedirect": "Open Redirect" in titles,
        "DirBrute(.env)": ".env" in titles,
        "SecHeaders": "HSTS" in titles or "Content-Security" in titles,
    }
    print("=== CHECKS:")
    for k, ok in expect.items():
        print(f"  {'PASS' if ok else 'FAIL'} {k}")
    assert all(expect.values()), "Bazi kontroller tetiklenemedi!"
    print("ALL VULNSCAN CHECKS PASSED")


asyncio.run(main())
