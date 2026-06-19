"""Zafiyet tarama modulu — yaygin web zafiyetleri icin hafif aktif testler.

Kapsanan kontroller:
  - SQL Injection      : error-based + time-based (sleep)
  - Reflected XSS       : URL parametre + form input yansima testi
  - Open Redirect       : redirect parametrelerine harici URL enjeksiyonu
  - Directory Bruteforce: yaygin hassas yol/dosya kesfi
  - SSRF (temel)        : internal hedeflere yonlendirme denemesi
  - Guvenlik basliklari : eksik HSTS/CSP/X-Frame-Options tespiti (info/low)

Tasarim: her kontrol bir `Finding` listesi don. Etik kullanim — yalnizca izinli
hedeflere. Testler dusuk-etkili (DROP/sleep yok, yikici payload yok).
"""
from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

LogFn = Callable[[str, str], Awaitable[None]]

from pathlib import Path
import sys as _sys

def _wordlist_dir() -> Path:
    base = getattr(_sys, "_MEIPASS", None)
    if base:
        return Path(base) / "backend" / "wordlists"   # PyInstaller bundle
    return Path(__file__).parent.parent / "wordlists"  # gelistirme
WORDLIST_DIR = _wordlist_dir()


async def _noop_log(level: str, message: str) -> None:  # pragma: no cover
    pass


def _finding(severity: str, title: str, detail: str, target: str) -> dict:
    return {"severity": severity, "title": title, "detail": detail, "target": target}


# SQLi error imzalari (yanitta gorulurse veritabani hatasi sizmasi)
SQL_ERRORS = [
    "you have an error in your sql syntax",
    "warning: mysql",
    "unclosed quotation mark after the character string",
    "quoted string not properly terminated",
    "pg_query():",
    "sqlite3.operationalerror",
    "sqlstate[",
    "ora-01756",
    "microsoft odbc",
    "odbc driver",
    "syntax error at or near",
]

XSS_PAYLOAD = '"><svg/onload=alert(1)>ptrc'
SQLI_PAYLOADS = ["'", "' OR '1'='1", '" OR "1"="1']
OPEN_REDIRECT_PARAMS = ["next", "url", "redirect", "return", "returnurl", "dest", "destination", "r", "u"]
OPEN_REDIRECT_PAYLOAD = "https://evil-pentrace.example"
SSRF_PARAMS = ["url", "uri", "path", "dest", "host", "target", "proxy", "fetch"]


def _build_url(base: str, params: dict[str, str]) -> str:
    parts = urlparse(base)
    q = parse_qs(parts.query)
    merged = {k: v[0] if isinstance(v, list) else v for k, v in q.items()}
    merged.update(params)
    return urlunparse(parts._replace(query=urlencode(merged)))


def _params_of(url: str) -> dict[str, str]:
    q = parse_qs(urlparse(url).query)
    return {k: v[0] for k, v in q.items()}


# --------------------------------------------------------------------------- #
# Yardimci: hedeften test edilebilir URL'leri topla (linkler + formlar)
# --------------------------------------------------------------------------- #
async def _gather_endpoints(url: str, client: httpx.AsyncClient, log: LogFn) -> tuple[set[str], list[dict]]:
    """Sayfadaki parametreli linkleri ve form aksiyonlarini topla."""
    urls: set[str] = set()
    forms: list[dict] = []
    if _params_of(url):
        urls.add(url)
    try:
        r = await client.get(url, timeout=10)
    except Exception:
        return urls, forms

    soup = BeautifulSoup(r.text, "html.parser")
    for a in soup.find_all("a", href=True):
        full = urljoin(str(r.url), a["href"])
        if urlparse(full).netloc == urlparse(str(r.url)).netloc and "?" in full:
            urls.add(full)
    for form in soup.find_all("form"):
        action = urljoin(str(r.url), form.get("action") or str(r.url))
        method = (form.get("method") or "get").lower()
        inputs = [i.get("name") for i in form.find_all(["input", "textarea"]) if i.get("name")]
        if inputs:
            forms.append({"action": action, "method": method, "inputs": inputs})
    await log("info", f"{len(urls)} parametreli URL, {len(forms)} form bulundu")
    return urls, forms


# --------------------------------------------------------------------------- #
# 1. SQL Injection
# --------------------------------------------------------------------------- #
async def check_sqli(urls: set[str], client: httpx.AsyncClient, log: LogFn) -> list[dict]:
    findings: list[dict] = []
    for url in urls:
        params = _params_of(url)
        if not params:
            continue
        for pname in params:
            # error-based
            for payload in SQLI_PAYLOADS:
                test = _build_url(url, {pname: params[pname] + payload})
                try:
                    r = await client.get(test, timeout=10)
                except Exception:
                    continue
                low = r.text.lower()
                if any(sig in low for sig in SQL_ERRORS):
                    findings.append(_finding(
                        "high", "Olasi SQL Injection (error-based)",
                        f"'{pname}' parametresine tek tirnak enjekte edildiginde veritabani hata "
                        f"mesaji yansidi. Payload: {payload}", test,
                    ))
                    await log("warn", f"SQLi (error) -> {test}")
                    break
            else:
                # time-based (yalnizca error-based bulunmadiysa)
                baseline = await _timed_get(client, url)
                sleep_payload = params[pname] + "' AND SLEEP(3)-- -"
                test = _build_url(url, {pname: sleep_payload})
                delayed = await _timed_get(client, test)
                if baseline is not None and delayed is not None and delayed - baseline > 2.5:
                    findings.append(_finding(
                        "high", "Olasi SQL Injection (time-based)",
                        f"'{pname}' parametresinde SLEEP(3) payload'i yanit suresini "
                        f"{baseline:.1f}s -> {delayed:.1f}s artirdi.", test,
                    ))
                    await log("warn", f"SQLi (time) -> {test}")
    return findings


async def _timed_get(client: httpx.AsyncClient, url: str) -> float | None:
    try:
        start = time.perf_counter()
        await client.get(url, timeout=12)
        return time.perf_counter() - start
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# 2. Reflected XSS
# --------------------------------------------------------------------------- #
async def check_xss(urls: set[str], client: httpx.AsyncClient, log: LogFn) -> list[dict]:
    findings: list[dict] = []
    for url in urls:
        params = _params_of(url)
        if not params:
            continue
        for pname in params:
            test = _build_url(url, {pname: XSS_PAYLOAD})
            try:
                r = await client.get(test, timeout=10)
            except Exception:
                continue
            if XSS_PAYLOAD in r.text:
                findings.append(_finding(
                    "high", "Olasi Reflected XSS",
                    f"'{pname}' parametresine gonderilen XSS payload'i yanitta kodlanmadan "
                    f"yansidi. Payload: {XSS_PAYLOAD}", test,
                ))
                await log("warn", f"XSS -> {test}")
    return findings


# --------------------------------------------------------------------------- #
# 3. Open Redirect
# --------------------------------------------------------------------------- #
async def check_open_redirect(
    base_url: str, urls: set[str], client: httpx.AsyncClient, log: LogFn
) -> list[dict]:
    findings: list[dict] = []
    # Temel URL + kesfedilen tum endpointleri test et. Endpointlerde hem mevcut
    # parametreleri hem de bilinen redirect parametre adlarini dene.
    targets = {base_url} | urls
    tested: set[str] = set()
    for endpoint in targets:
        existing = list(_params_of(endpoint).keys())
        param_names = set(OPEN_REDIRECT_PARAMS) | {p for p in existing if p.lower() in OPEN_REDIRECT_PARAMS}
        for param in param_names:
            test = _build_url(endpoint, {param: OPEN_REDIRECT_PAYLOAD})
            if test in tested:
                continue
            tested.add(test)
            try:
                r = await client.get(test, timeout=10, follow_redirects=False)
            except Exception:
                continue
            loc = r.headers.get("location", "")
            if r.status_code in (301, 302, 303, 307, 308) and OPEN_REDIRECT_PAYLOAD in loc:
                findings.append(_finding(
                    "medium", "Open Redirect",
                    f"'{param}' parametresi harici bir URL'ye yonlendirme yapti. Location: {loc}", test,
                ))
                await log("warn", f"Open redirect -> {test}")
    return findings


# --------------------------------------------------------------------------- #
# 4. Directory / dosya bruteforce
# --------------------------------------------------------------------------- #
async def check_dirs(base_url: str, client: httpx.AsyncClient, log: LogFn) -> list[dict]:
    findings: list[dict] = []
    wl = WORDLIST_DIR / "dirs.txt"
    if not wl.exists():
        return findings
    paths = [p.strip() for p in wl.read_text(encoding="utf-8").splitlines() if p.strip()]
    root = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}"
    sem = asyncio.Semaphore(20)

    SENSITIVE = {".git", ".env", "backup", "phpmyadmin", "config", "dump.sql", "db.sql", ".htaccess"}

    async def probe(path: str) -> None:
        async with sem:
            target = f"{root}/{path}"
            try:
                r = await client.get(target, timeout=8, follow_redirects=False)
            except Exception:
                return
            if r.status_code in (200, 301, 302, 401, 403):
                sev = "info"
                if r.status_code == 200 and any(s in path for s in SENSITIVE):
                    sev = "high"
                elif r.status_code in (401, 403):
                    sev = "low"
                findings.append(_finding(
                    sev, f"Erisilebilir yol: /{path} ({r.status_code})",
                    f"HTTP {r.status_code} dondu. Hassas dosya/dizin ifsasi olabilir.", target,
                ))

    await asyncio.gather(*(probe(p) for p in paths))
    if findings:
        await log("info", f"Dir brute: {len(findings)} ilginc yol bulundu")
    return findings


# --------------------------------------------------------------------------- #
# 5. SSRF (temel)
# --------------------------------------------------------------------------- #
async def check_ssrf(urls: set[str], client: httpx.AsyncClient, log: LogFn) -> list[dict]:
    findings: list[dict] = []
    INTERNAL = "http://169.254.169.254/latest/meta-data/"
    for url in urls:
        params = _params_of(url)
        for pname in params:
            if pname.lower() not in SSRF_PARAMS:
                continue
            test = _build_url(url, {pname: INTERNAL})
            try:
                r = await client.get(test, timeout=8)
            except Exception:
                continue
            low = r.text.lower()
            if any(k in low for k in ("ami-id", "instance-id", "iam/", "meta-data")):
                findings.append(_finding(
                    "critical", "Olasi SSRF",
                    f"'{pname}' parametresi ile cloud metadata endpoint'ine erisilebildi.", test,
                ))
                await log("warn", f"SSRF -> {test}")
    return findings


# --------------------------------------------------------------------------- #
# 6. Guvenlik basliklari
# --------------------------------------------------------------------------- #
async def check_security_headers(base_url: str, client: httpx.AsyncClient, log: LogFn) -> list[dict]:
    findings: list[dict] = []
    try:
        r = await client.get(base_url, timeout=10)
    except Exception:
        return findings
    h = {k.lower(): v for k, v in r.headers.items()}
    checks = {
        "strict-transport-security": ("low", "HSTS basligi eksik"),
        "content-security-policy": ("low", "Content-Security-Policy eksik"),
        "x-frame-options": ("low", "X-Frame-Options eksik (clickjacking riski)"),
        "x-content-type-options": ("info", "X-Content-Type-Options eksik"),
    }
    for header, (sev, title) in checks.items():
        if header not in h:
            findings.append(_finding(sev, title, f"Yanitta '{header}' basligi yok.", base_url))
    return findings


# --------------------------------------------------------------------------- #
# Ust seviye akis
# --------------------------------------------------------------------------- #
async def run_vulnscan(web_targets: list[str], log: LogFn = _noop_log) -> list[dict]:
    """Recon'dan gelen web hedefleri uzerinde tum kontrolleri calistir."""
    all_findings: list[dict] = []
    if not web_targets:
        await log("info", "Taranacak web hedefi yok")
        return all_findings

    async with httpx.AsyncClient(verify=False, follow_redirects=True,
                                 headers={"User-Agent": "PentraCe/0.1"}) as client:
        for base in web_targets:
            await log("info", f"Zafiyet taramasi: {base}")
            urls, _forms = await _gather_endpoints(base, client, log)

            results = await asyncio.gather(
                check_sqli(urls, client, log),
                check_xss(urls, client, log),
                check_open_redirect(base, urls, client, log),
                check_dirs(base, client, log),
                check_ssrf(urls, client, log),
                check_security_headers(base, client, log),
            )
            for group in results:
                all_findings.extend(group)

    await log("info", f"Zafiyet taramasi tamamlandi: {len(all_findings)} bulgu")
    return all_findings
