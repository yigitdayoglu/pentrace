"""subfinder adapter — pasif subdomain kesfi (ProjectDiscovery).

crt.sh + wordlist'e EK olarak calisir; sonuclar aday havuzuna eklenir, sonra
mevcut DNS dogrulama sureci hepsini dogrular.
"""
from __future__ import annotations

from typing import Awaitable, Callable

from config import settings

from .binaries import ensure_tool, run_tool

LogFn = Callable[[str, str], Awaitable[None]]


async def _noop_log(level: str, message: str) -> None:  # pragma: no cover
    return None


async def discover(domain: str, log: LogFn = _noop_log) -> list[str]:
    """Domain icin subfinder subdomain adaylarini dondur (hostname listesi).

    Tool yoksa/basarisizsa bos liste doner (cagiran yerlesik kesfe devam eder).
    """
    if not settings.external_tools:
        return []
    path = await ensure_tool("subfinder", log, settings.tools_auto_download)
    if not path:
        return []
    await log("info", f"subfinder calisiyor: {domain}")
    out = await run_tool(path, ["-d", domain, "-silent"], log, timeout=180)
    if not out:
        return []
    hosts = {line.strip().lower() for line in out.splitlines() if line.strip()}
    await log("info", f"subfinder {len(hosts)} aday buldu")
    return sorted(hosts)
