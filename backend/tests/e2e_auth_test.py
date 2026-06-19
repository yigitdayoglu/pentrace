"""Auth-farkinda uctan uca test. uvicorn (8000) + fixture (8099) calisir olmali."""
import json
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
    raise AssertionError(f"{email} icin kod bulunamadi")


def verify_user(email, headers):
    """Kullaniciyi dev-mod kodu ile dogrula."""
    code = code_for(email)
    r = httpx.post(f"{API}/api/auth/verify", json={"code": code}, headers=headers, timeout=10)
    assert r.status_code == 200, f"verify: {r.status_code} {r.text}"


def sse_until_done(token, scan_id, timeout=120):
    events = []
    url = f"{API}/api/scans/{scan_id}/stream?token={token}"
    with httpx.stream("GET", url, timeout=timeout) as resp:
        assert resp.status_code == 200, f"SSE auth basarisiz: {resp.status_code}"
        for line in resp.iter_lines():
            if not line or not line.startswith("data:"):
                continue
            data = json.loads(line[5:].strip())
            events.append(data)
            if data.get("event") == "done":
                break
    return events


def main():
    email = f"user_{uuid.uuid4().hex[:8]}@test.com"
    pw = "password123"
    # IP butcesini tuketmemek icin benzersiz forged IP
    ip_hdr = {"X-Forwarded-For": f"192.0.2.{uuid.uuid4().int % 200 + 1}"}

    # --- auth gerekli: token'siz istek 401 ---
    r = httpx.get(f"{API}/api/scans", timeout=10)
    assert r.status_code == 401, f"auth zorunlulugu yok: {r.status_code}"
    print("token'siz erisim engellendi (401) OK")

    # --- register ---
    r = httpx.post(f"{API}/api/auth/register", json={"email": email, "password": pw},
                   headers=ip_hdr, timeout=10)
    assert r.status_code == 200, f"register: {r.status_code} {r.text}"
    token = r.json()["token"]
    H = {"Authorization": f"Bearer {token}"}
    assert r.json()["user"]["is_verified"] is False
    print("register OK, role:", r.json()["user"]["role"], "plan:", r.json()["user"]["plan"])

    # --- e-posta dogrula (dev-mod kodu) ---
    verify_user(email, H)
    print("e-posta dogrulandi (dev-mod)")

    # --- login ---
    r = httpx.post(f"{API}/api/auth/login",
                   data={"username": email, "password": pw}, timeout=10)
    assert r.status_code == 200, f"login: {r.status_code} {r.text}"
    token = r.json()["token"]
    H = {"Authorization": f"Bearer {token}"}

    # yanlis sifre
    r = httpx.post(f"{API}/api/auth/login", data={"username": email, "password": "wrong"}, timeout=10)
    assert r.status_code == 401
    print("login OK + yanlis sifre 401 OK")

    # --- me + kota ---
    me = httpx.get(f"{API}/api/auth/me", headers=H, timeout=10).json()
    print("me quota:", me["quota"])
    assert me["quota"]["plan"] == "free" and me["quota"]["limit"] == 3

    # --- izin onaysiz tarama 403 ---
    r = httpx.post(f"{API}/api/scans", json={"target": "127.0.0.1", "authorized": False}, headers=H, timeout=10)
    assert r.status_code == 403
    print("izin onaysiz tarama engellendi (403) OK")

    # --- tarama baslat ---
    r = httpx.post(f"{API}/api/scans", json={"target": "127.0.0.1", "authorized": True}, headers=H, timeout=10)
    assert r.status_code == 200, f"scan: {r.status_code} {r.text}"
    scan_id = r.json()["scan_id"]
    print("scan baslatildi:", scan_id)

    # --- SSE (query-param token) ---
    events = sse_until_done(token, scan_id)
    assert any(e.get("event") == "done" for e in events), "done gelmedi"
    print("SSE akisi tamamlandi, olay sayisi:", len(events))

    # --- detay (sahiplik) ---
    time.sleep(0.5)
    detail = httpx.get(f"{API}/api/scans/{scan_id}", headers=H, timeout=10).json()
    findings = detail["findings"]
    titles = " ".join(f["title"] for f in findings)
    assert detail["scan"]["status"] == "done"
    assert "SQL Injection" in titles and "XSS" in titles
    print("detay OK, bulgu:", len(findings), "| status:", detail["scan"]["status"])

    # --- baska kullanici bu taramayi goremez ---
    other = f"other_{uuid.uuid4().hex[:8]}@test.com"
    other_ip = {"X-Forwarded-For": f"192.0.2.{uuid.uuid4().int % 50 + 50}"}
    rt = httpx.post(f"{API}/api/auth/register", json={"email": other, "password": pw},
                    headers=other_ip, timeout=10).json()["token"]
    r = httpx.get(f"{API}/api/scans/{scan_id}", headers={"Authorization": f"Bearer {rt}"}, timeout=10)
    assert r.status_code == 403, f"sahiplik izolasyonu yok: {r.status_code}"
    print("baska kullanici erisimi engellendi (403) OK")

    # --- admin login + kullanici listesi + plan yukselt ---
    ad = httpx.post(f"{API}/api/auth/login",
                    data={"username": "admin@pentrace.local", "password": "admin12345"}, timeout=10)
    assert ad.status_code == 200, f"admin login: {ad.text}"
    aH = {"Authorization": f"Bearer {ad.json()['token']}"}
    users = httpx.get(f"{API}/api/admin/users", headers=aH, timeout=10).json()
    assert len(users) >= 2
    # test kullanicisini pro yap
    me_id = me["user"]["id"]
    r = httpx.patch(f"{API}/api/admin/users/{me_id}", json={"plan": "pro"}, headers=aH, timeout=10)
    assert r.status_code == 200 and r.json()["plan"] == "pro"
    print("admin: kullanici listesi", len(users), "+ plan yukseltme OK")

    # --- normal kullanici admin endpoint'ine erisemez ---
    r = httpx.get(f"{API}/api/admin/users", headers=H, timeout=10)
    assert r.status_code == 403
    print("normal kullanici admin'e erisemiyor (403) OK")

    print("\nE2E AUTH TEST PASSED")


if __name__ == "__main__":
    main()
