"""nuclei adapter — template-tabanli zafiyet tarama (ProjectDiscovery).

Yerlesik kontrollere EK olarak calisir; binlerce topluluk template'i (CVE,
misconfig, exposure, default-cred...) ile dusuk yanlis-pozitif bulgular uretir.
Ilk calistirmada nuclei template'lerini otomatik indirir.
"""
from __future__ import annotations

import json
from typing import Awaitable, Callable

from config import settings

from .binaries import ensure_tool, run_tool

LogFn = Callable[[str, str], Awaitable[None]]


async def _noop_log(level: str, message: str) -> None:  # pragma: no cover
    return None


# nuclei severity -> PentraCe severity
_SEV = {
    "critical": "critical", "high": "high", "medium": "medium",
    "low": "low", "info": "info", "unknown": "info",
}


async def scan(web_targets: list[str], log: LogFn = _noop_log) -> list[dict]:
    """web_targets uzerinde nuclei calistir, PentraCe finding formatinda dondur.

    Tool yoksa/basarisizsa bos liste doner (yerlesik kontroller zaten calisti).
    """
    if not settings.external_tools or not web_targets:
        return []
    path = await ensure_tool("nuclei", log, settings.tools_auto_download)
    if not path:
        return []

    await log("info", f"nuclei {len(web_targets)} hedefte calisiyor (template'ler ilk seferde indirilebilir)...")
    args = ["-silent", "-jsonl", "-duc"]  # -duc: her calistirmada template guncelleme kontrolunu atla
    for t in web_targets:
        args += ["-u", t]

    out = await run_tool(path, args, log, timeout=900)
    if not out:
        return []

    findings: list[dict] = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        info = obj.get("info", {}) or {}
        sev = _SEV.get(str(info.get("severity", "info")).lower(), "info")
        name = info.get("name") or obj.get("template-id") or "nuclei bulgusu"
        matched = obj.get("matched-at") or obj.get("host") or ""
        tid = obj.get("template-id", "")
        desc = (info.get("description") or "").strip()
        detail = f"[{tid}] {desc}".strip() if desc else f"nuclei template: {tid}"
        findings.append({
            "severity": sev,
            "title": name,
            "detail": detail,
            "target": matched,
        })
    await log("info", f"nuclei {len(findings)} bulgu dondu")
    return findings
