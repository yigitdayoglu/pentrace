import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import models
import report


async def main():
    scans = await models.list_scans()
    done = [s for s in scans if s["status"] == "done"]
    assert done, "Tamamlanmis tarama yok — once e2e testi calistir"
    scan_id = done[0]["id"]
    print("rapor uretiliyor, scan_id:", scan_id)

    jpath = await report.build_json(scan_id)
    ppath = await report.build_pdf(scan_id)

    jsize = os.path.getsize(jpath)
    psize = os.path.getsize(ppath)
    print(f"JSON: {jpath} ({jsize} bytes)")
    print(f"PDF : {ppath} ({psize} bytes)")

    # PDF magic header dogrula
    with open(ppath, "rb") as fh:
        head = fh.read(5)
    assert head == b"%PDF-", f"Gecersiz PDF basligi: {head!r}"
    assert jsize > 50 and psize > 1000, "Dosyalar beklenenden kucuk"

    import json
    data = json.loads(open(jpath, encoding="utf-8").read())
    assert "summary" in data and "findings" in data
    print("summary:", data["summary"])
    print("REPORT TEST PASSED")


asyncio.run(main())
