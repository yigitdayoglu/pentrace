"""Mail dogrulama (dev-mod) + IP abuse engeli uctan uca testi.

uvicorn (8000) + fixture (8099) calisir olmali. SMTP yapilandirilmamis olmali
(dev-mod) — kodlar dev_mails.log'a yazilir.
"""
import os
import sys
import time
import uuid

import httpx

API = "http://127.0.0.1:8000"
DEV_LOG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dev_mails.log")


def code_for(email, timeout=5):
    """dev_mails.log'dan ilgili email'in en son dogrulama kodunu oku."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.exists(DEV_LOG):
            code = None
            with open(DEV_LOG, encoding="utf-8") as f:
                for line in f:
                    if email in line and "dogrulama kodu:" in line:
                        code = line.strip().split("dogrulama kodu:")[1].strip()
            if code:
                return code
        time.sleep(0.3)
    raise AssertionError(f"{email} icin kod dev_mails.log'da bulunamadi")


def main():
    email = f"verify_{uuid.uuid4().hex[:8]}@test.com"
    pw = "password123"
    # Bu kullaniciyi benzersiz forged IP ile kaydet (localhost butcesini tuketmesin)
    own_ip = {"X-Forwarded-For": f"198.51.100.{uuid.uuid4().int % 200 + 1}"}

    # --- register: kullanici unverified olmali ---
    r = httpx.post(f"{API}/api/auth/register", json={"email": email, "password": pw},
                   headers=own_ip, timeout=10)
    assert r.status_code == 200, f"register: {r.status_code} {r.text}"
    data = r.json()
    token = data["token"]
    H = {"Authorization": f"Bearer {token}"}
    assert data["user"]["is_verified"] is False, "yeni kullanici verified olmamali"
    print("register OK, is_verified=False")

    # --- dogrulanmamis kullanici tarama baslatamaz (403) ---
    r = httpx.post(f"{API}/api/scans", json={"target": "127.0.0.1", "authorized": True}, headers=H, timeout=10)
    assert r.status_code == 403, f"dogrulanmamis tarama engeli yok: {r.status_code}"
    print("dogrulanmamis kullanici tarama baslatamadi (403) OK")

    # --- yanlis kod reddedilmeli ---
    r = httpx.post(f"{API}/api/auth/verify", json={"code": "000000"}, headers=H, timeout=10)
    assert r.status_code == 400, f"yanlis kod kabul edildi: {r.status_code}"
    print("yanlis kod reddedildi (400) OK")

    # --- dogru kod ile dogrula ---
    code = code_for(email)
    print("dev_mails.log'dan kod alindi:", code)
    r = httpx.post(f"{API}/api/auth/verify", json={"code": code}, headers=H, timeout=10)
    assert r.status_code == 200 and r.json()["user"]["is_verified"] is True
    print("dogrulama OK, is_verified=True")

    # --- artik tarama baslatabilir ---
    r = httpx.post(f"{API}/api/scans", json={"target": "127.0.0.1", "authorized": True}, headers=H, timeout=10)
    assert r.status_code == 200, f"dogrulanmis tarama baslatilamadi: {r.status_code} {r.text}"
    print("dogrulanmis kullanici tarama baslatti OK")

    # --- IP abuse engeli: ayni IP'den max N hesap (config default 3) ---
    # Benzersiz forged IP ile izole test: ilk N basarili, sonrasi 429.
    abuse_ip = {"X-Forwarded-For": f"203.0.113.{uuid.uuid4().int % 200 + 1}"}
    ok_count, blocked = 0, False
    for i in range(8):
        e = f"abuse_{uuid.uuid4().hex[:8]}@test.com"
        rr = httpx.post(f"{API}/api/auth/register", json={"email": e, "password": pw},
                        headers=abuse_ip, timeout=10)
        if rr.status_code == 200:
            ok_count += 1
        elif rr.status_code == 429:
            blocked = True
            print(f"IP limiti devreye girdi: {ok_count} hesap acildi, sonra 429:",
                  rr.json()["detail"][:70])
            break
    assert blocked, "IP abuse engeli devreye girmedi!"
    assert ok_count >= 1, "hic hesap acilamadi"
    print(f"IP abuse engeli OK ({ok_count} hesap sonrasi blok)")

    print("\nE2E VERIFY + IP-LIMIT TEST PASSED")


if __name__ == "__main__":
    main()
