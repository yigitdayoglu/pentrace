"""naabu adapter — hizli port tarama (ProjectDiscovery).

Windows'ta Npcap/driver GEREKTIRMEYEN connect-scan (-s c) kullanilir. Varsa
yerlesik asyncio port tarayicinin yerine gecer (daha hizli + daha genis).
"""
from __future__ import annotations

import json
from typing import Awaitable, Callable

from config import settings

from .binaries import ensure_tool, run_tool

LogFn = Callable[[str, str], Awaitable[None]]


async def _noop_log(level: str, message: str) -> None:  # pragma: no cover
    return None


async def scan(host: str, log: LogFn = _noop_log) -> list[dict] | None:
    """host icin acik portlari dondur: [{"port": int, "service": str}].

    Tool yoksa/basarisizsa None doner -> cagiran yerlesik tarayiciya gecer.
    """
    if not settings.external_tools:
        return None
    path = await ensure_tool("naabu", log, settings.tools_auto_download)
    if not path:
        return None
    await log("info", f"naabu calisiyor: {host}")
    # -s c: connect scan (root/npcap gerekmez), -tp 1000: en yaygin 1000 port
    out = await run_tool(
        path, ["-host", host, "-silent", "-json", "-s", "c", "-tp", "1000"],
        log, timeout=240,
    )
    if out is None:
        return None

    from modules.recon import PORT_SERVICE  # gec import: dongusel bagimliligi onle

    ports: list[dict] = []
    seen: set[int] = set()
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        p = obj.get("port")
        if isinstance(p, int) and p not in seen:
            seen.add(p)
            ports.append({"port": p, "service": PORT_SERVICE.get(p, "unknown")})
    ports.sort(key=lambda x: x["port"])
    await log("info", f"naabu {host}: {len(ports)} acik port")
    return ports
