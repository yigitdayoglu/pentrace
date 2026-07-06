"""nuclei adapter — template-tabanli zafiyet tarama (ProjectDiscovery).

Yerlesik kontrollere EK olarak calisir; binlerce topluluk template'i (CVE,
misconfig, exposure, default-cred...) ile dusuk yanlis-pozitif bulgular uretir.
Ilk calistirmada nuclei template'lerini otomatik indirir.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Awaitable, Callable

from config import settings

from .binaries import ensure_tool, run_tool

LogFn = Callable[[str, str], Awaitable[None]]

# nuclei template'leri bu surecte kuruldu mu (bir kez kontrol yeter)
_templates_ready = False


async def _noop_log(level: str, message: str) -> None:  # pragma: no cover
    return None


async def _ensure_templates(path: Path, log: LogFn) -> bool:
    """nuclei template'leri kurulu degilse indir. Templateler olmadan nuclei
    'no templates provided' deyip 0 bulgu doner."""
    global _templates_ready
    if _templates_ready:
        return True
    tdir = Path.home() / "nuclei-templates"
    if tdir.exists() and any(tdir.iterdir()):
        _templates_ready = True
        return True
    await log("info", "nuclei template'leri ilk kez indiriliyor (~50MB, biraz surebilir)...")
    await run_tool(path, ["-update-templates"], log, timeout=600)
    ok = tdir.exists() and any(tdir.iterdir())
    _templates_ready = ok
    if not ok:
        await log("warn", "nuclei template'leri kurulamadi — nuclei atlaniyor")
    return ok


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

    if not await _ensure_templates(path, log):
        return []

    await log("info", f"nuclei {len(web_targets)} hedefte calisiyor...")
    # -duc: template guncelleme kontrolunu atla (zaten kurduk)
    # -severity: 'info' seviyesini (cogunlukla teknoloji/versiyon tespiti, recon
    #   zaten yapiyor) atla -> cok daha hizli + yuksek sinyal
    args = ["-silent", "-jsonl", "-duc", "-severity", settings.nuclei_severity,
            "-c", "50", "-rl", "200"]  # eszamanlilik + rate limit -> daha hizli
    for t in web_targets:
        args += ["-u", t]

    out = await run_tool(path, args, log, timeout=settings.nuclei_timeout)
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
