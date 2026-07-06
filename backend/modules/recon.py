"""Recon modulu — pasif + aktif kesif.

Adimlar:
  1. Subdomain kesfi  : crt.sh sertifika seffaflik + wordlist DNS denemesi
  2. Port tarama       : saf asyncio TCP connect (harici nmap yok)
  3. HTTP parmak izi    : basliklar + HTML pattern -> teknoloji tahmini

Her adim, ilerlemeyi disari bildirmek icin opsiyonel bir `log` callback kullanir.
"""
from __future__ import annotations

import asyncio
import socket
import ssl
from pathlib import Path
from typing import Awaitable, Callable

import httpx

from modules.tools import naabu, subfinder

LogFn = Callable[[str, str], Awaitable[None]]  # (level, message)

import sys as _sys, os as _os
def _wordlist_dir() -> Path:
    base = getattr(_sys, "_MEIPASS", None)
    if base:
        return Path(base) / "backend" / "wordlists"   # PyInstaller bundle
    return Path(__file__).parent.parent / "wordlists"  # gelistirme
WORDLIST_DIR = _wordlist_dir()

# En yaygin servis portlari (asyncio connect scan icin makul varsayilan set)
DEFAULT_PORTS = [
    21, 22, 23, 25, 53, 80, 110, 111, 135, 139, 143, 443, 445,
    993, 995, 1723, 3000, 3306, 3389, 5000, 5432, 5900, 6379,
    8000, 8080, 8099, 8443, 8888, 9200, 27017,
]

PORT_SERVICE = {
    21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp", 53: "dns", 80: "http",
    110: "pop3", 135: "msrpc", 139: "netbios", 143: "imap", 443: "https",
    445: "smb", 993: "imaps", 995: "pop3s", 1723: "pptp", 3306: "mysql",
    3389: "rdp", 5432: "postgresql", 5900: "vnc", 6379: "redis",
    8000: "http-alt", 8080: "http-proxy", 8443: "https-alt",
    9200: "elasticsearch", 27017: "mongodb",
}

# Teknoloji parmak izi: (kaynak, regex/pattern, teknoloji adi)
TECH_HEADER_HINTS = {
    "server": {
        "nginx": "Nginx", "apache": "Apache", "iis": "Microsoft IIS",
        "cloudflare": "Cloudflare", "litespeed": "LiteSpeed", "caddy": "Caddy",
    },
    "x-powered-by": {
        "php": "PHP", "asp.net": "ASP.NET", "express": "Express.js",
        "next.js": "Next.js",
    },
}
TECH_BODY_HINTS = {
    "wp-content": "WordPress", "wp-includes": "WordPress",
    "/_next/": "Next.js", "drupal": "Drupal", "joomla": "Joomla",
    "csrf-token": "Laravel/Rails", "__nuxt": "Nuxt.js",
    "react": "React", "ng-version": "Angular", "vue": "Vue.js",
}


async def _noop_log(level: str, message: str) -> None:  # pragma: no cover
    pass


def _normalize_target(target: str) -> str:
    """Sema/path temizle, sadece host don."""
    t = target.strip()
    for prefix in ("https://", "http://"):
        if t.startswith(prefix):
            t = t[len(prefix):]
    return t.split("/")[0].split(":")[0]


# --------------------------------------------------------------------------- #
# 1. Subdomain kesfi
# --------------------------------------------------------------------------- #
async def _crtsh_subdomains(domain: str, client: httpx.AsyncClient) -> set[str]:
    found: set[str] = set()
    try:
        r = await client.get(
            "https://crt.sh/", params={"q": f"%.{domain}", "output": "json"}, timeout=20
        )
        if r.status_code == 200:
            for entry in r.json():
                for name in entry.get("name_value", "").splitlines():
                    name = name.strip().lstrip("*.").lower()
                    if name.endswith(domain) and "@" not in name:
                        found.add(name)
    except Exception:
        pass
    return found


async def _resolve(host: str) -> str | None:
    """DNS cozumleme — thread pool uzerinden (getaddrinfo bloklayici)."""
    try:
        loop = asyncio.get_running_loop()
        infos = await loop.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        return infos[0][4][0] if infos else None
    except Exception:
        return None


async def discover_subdomains(domain: str, log: LogFn = _noop_log) -> list[dict]:
    """crt.sh adaylari + wordlist adaylarini DNS ile dogrula."""
    candidates: set[str] = {domain}

    async with httpx.AsyncClient(verify=False) as client:
        await log("info", f"crt.sh sorgulaniyor: {domain}")
        candidates |= await _crtsh_subdomains(domain, client)

    # subfinder (varsa) — pasif kaynaklardan ek adaylar
    candidates |= set(await subfinder.discover(domain, log))

    wl = WORDLIST_DIR / "subdomains.txt"
    if wl.exists():
        for line in wl.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                candidates.add(f"{line}.{domain}")

    await log("info", f"{len(candidates)} aday subdomain DNS ile dogrulaniyor")

    sem = asyncio.Semaphore(50)

    async def check(host: str) -> dict | None:
        async with sem:
            ip = await _resolve(host)
            return {"host": host, "ip": ip} if ip else None

    results = await asyncio.gather(*(check(h) for h in candidates))
    live = [r for r in results if r]
    await log("info", f"{len(live)} canli subdomain bulundu")
    return sorted(live, key=lambda x: x["host"])


# --------------------------------------------------------------------------- #
# 2. Port tarama (asyncio TCP connect)
# --------------------------------------------------------------------------- #
async def scan_ports(
    host: str, ports: list[int] | None = None, log: LogFn = _noop_log
) -> list[dict]:
    ports = ports or DEFAULT_PORTS
    await log("info", f"{host} icin {len(ports)} port taraniyor")
    sem = asyncio.Semaphore(100)
    open_ports: list[dict] = []

    async def probe(port: int) -> None:
        async with sem:
            try:
                fut = asyncio.open_connection(host, port)
                reader, writer = await asyncio.wait_for(fut, timeout=2.0)
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass
                open_ports.append({"port": port, "service": PORT_SERVICE.get(port, "unknown")})
            except (asyncio.TimeoutError, OSError):
                pass

    await asyncio.gather(*(probe(p) for p in ports))
    open_ports.sort(key=lambda x: x["port"])
    await log("info", f"{host}: {len(open_ports)} acik port")
    return open_ports


# --------------------------------------------------------------------------- #
# 3. HTTP parmak izi
# --------------------------------------------------------------------------- #
WEB_PORTS = {80: "http", 443: "https", 8080: "http", 8000: "http", 8443: "https", 8099: "http", 8888: "http", 3000: "http", 5000: "http"}


def _web_endpoints(host: str, open_ports: list[dict] | None) -> list[str]:
    """Acik web portlarindan denenecek URL listesi uret."""
    endpoints: list[str] = []
    ports = {p["port"] for p in (open_ports or [])}
    # Acik bilinen web portlari
    for port, scheme in WEB_PORTS.items():
        if open_ports is not None and port not in ports:
            continue
        if port in (80, 443):
            endpoints.append(f"{scheme}://{host}")
        else:
            endpoints.append(f"{scheme}://{host}:{port}")
    # open_ports bilinmiyorsa varsayilan 443/80
    if not endpoints:
        endpoints = [f"https://{host}", f"http://{host}"]
    return endpoints


async def fingerprint_http(host: str, log: LogFn = _noop_log, open_ports: list[dict] | None = None) -> list[dict]:
    """Acik web portlarinin TUMUNU dene; her yanit veren endpoint icin sonuc don.

    Bir host birden cok portta farkli web uygulamasi sunabilir; hepsini parmak izler.
    """
    results: list[dict] = []
    for url in _web_endpoints(host, open_ports):
        try:
            async with httpx.AsyncClient(verify=False, follow_redirects=True, timeout=10) as client:
                r = await client.get(url)
        except Exception:
            continue

        headers = {k.lower(): v for k, v in r.headers.items()}
        body = r.text[:50_000].lower()
        techs: set[str] = set()

        for header, mapping in TECH_HEADER_HINTS.items():
            val = headers.get(header, "").lower()
            for needle, tech in mapping.items():
                if needle in val:
                    techs.add(tech)
        for needle, tech in TECH_BODY_HINTS.items():
            if needle in body:
                techs.add(tech)

        title = ""
        if "<title" in body:
            try:
                title = r.text.split("<title", 1)[1].split(">", 1)[1].split("</title")[0].strip()[:120]
            except Exception:
                title = ""

        result = {
            "url": str(r.url),
            "status": r.status_code,
            "server": headers.get("server", ""),
            "title": title,
            "technologies": sorted(techs),
            "headers": {
                k: headers.get(k, "")
                for k in ("server", "x-powered-by", "content-type")
                if headers.get(k)
            },
        }
        await log("info", f"{url} -> {r.status_code} | {', '.join(techs) or 'teknoloji tespit edilemedi'}")
        results.append(result)

    if not results:
        await log("warn", f"{host}: HTTP/HTTPS yanit vermedi")
    return results


# --------------------------------------------------------------------------- #
# Ust seviye recon akisi
# --------------------------------------------------------------------------- #
async def run_recon(target: str, log: LogFn = _noop_log) -> dict:
    """Tum recon adimlarini calistir, yapilandirilmis sonuc don."""
    domain = _normalize_target(target)
    await log("info", f"Recon basladi: {domain}")

    subdomains = await discover_subdomains(domain, log)

    # Ana hedef + en fazla 5 canli subdomain'i derinlemesine tara (sure kontrolu)
    scan_hosts = [s["host"] for s in subdomains][:6]
    if domain not in scan_hosts:
        scan_hosts.insert(0, domain)

    ports_by_host: dict[str, list[dict]] = {}
    http_by_host: dict[str, list[dict]] = {}
    web_targets: list[str] = []

    for host in scan_hosts:
        # naabu (varsa) yerlesik tarayicinin yerine gecer; None ise fallback
        naabu_ports = await naabu.scan(host, log)
        ports_by_host[host] = naabu_ports if naabu_ports is not None else await scan_ports(host, log=log)
        fps = await fingerprint_http(host, log, open_ports=ports_by_host[host])
        if fps:
            http_by_host[host] = fps
            web_targets.extend(fp["url"] for fp in fps)

    await log("info", "Recon tamamlandi")
    return {
        "domain": domain,
        "subdomains": subdomains,
        "ports": ports_by_host,
        "http": http_by_host,
        "web_targets": web_targets,
    }
