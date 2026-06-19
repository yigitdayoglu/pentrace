"""Pipeline orchestrator — recon -> vulnscan -> sonuclari DB'ye yaz.

Canli log akisi: her tarama icin bir asyncio.Queue tutulur. SSE endpoint'i bu
kuyruktan okur. Pipeline log mesajlarini hem kuyruga (canli) hem de gerektiginde
DB'ye yazar.
"""
from __future__ import annotations

import asyncio
import datetime as _dt
import json
from typing import Any

import models
from modules import recon, vulnscan

# scan_id -> canli olay kuyrugu
_queues: dict[str, asyncio.Queue] = {}
# Tamamlanan taramalar (kuyruk kapatildi)
_done: set[str] = set()


def get_queue(scan_id: str) -> asyncio.Queue:
    if scan_id not in _queues:
        _queues[scan_id] = asyncio.Queue()
    return _queues[scan_id]


def is_done(scan_id: str) -> bool:
    return scan_id in _done


async def _emit(scan_id: str, level: str, message: str, event: str = "log") -> None:
    """Canli olay yayinla (SSE icin kuyruga koy)."""
    q = get_queue(scan_id)
    payload = {
        "event": event,
        "level": level,
        "message": message,
        "ts": _dt.datetime.now(_dt.timezone.utc).strftime("%H:%M:%S"),
    }
    await q.put(payload)


def _make_logger(scan_id: str):
    async def log(level: str, message: str) -> None:
        await _emit(scan_id, level, message)
    return log


async def run_pipeline(scan_id: str, target: str) -> None:
    """Bir taramanin tam yasam dongusu. Arka plan task olarak calistirilir."""
    log = _make_logger(scan_id)
    try:
        await models.set_status(scan_id, "running")
        await _emit(scan_id, "info", f"Tarama basladi: {target}", event="status")

        # --- 1. RECON ---
        await _emit(scan_id, "info", "=== RECON ASAMASI ===")
        recon_result = await recon.run_recon(target, log)

        for sub in recon_result["subdomains"]:
            await models.add_asset(scan_id, "subdomain", sub["host"], {"ip": sub["ip"]})
        for host, ports in recon_result["ports"].items():
            for p in ports:
                await models.add_asset(scan_id, "port", f"{host}:{p['port']}", {"service": p["service"]})
        for host, fps in recon_result["http"].items():
            for fp in fps:
                await models.add_asset(scan_id, "tech", fp["url"], {
                    "technologies": fp["technologies"], "server": fp["server"],
                    "title": fp["title"], "status": fp["status"],
                })

        await _emit(scan_id, "info",
                    f"Recon ozeti: {len(recon_result['subdomains'])} subdomain, "
                    f"{len(recon_result['web_targets'])} web hedefi")

        # --- 2. VULN SCAN ---
        await _emit(scan_id, "info", "=== ZAFIYET TARAMA ASAMASI ===")
        findings = await vulnscan.run_vulnscan(recon_result["web_targets"], log)

        for f in findings:
            await models.add_finding(
                scan_id, module="vulnscan", severity=f["severity"],
                title=f["title"], detail=f["detail"], target=f["target"],
            )

        # Severity ozeti
        sev_count: dict[str, int] = {}
        for f in findings:
            sev_count[f["severity"]] = sev_count.get(f["severity"], 0) + 1
        summary = ", ".join(f"{k}: {v}" for k, v in sev_count.items()) or "bulgu yok"
        await _emit(scan_id, "info", f"Bulgu ozeti -> {summary}")

        await models.set_status(scan_id, "done")
        await _emit(scan_id, "info", "Tarama tamamlandi", event="done")

    except Exception as e:  # pragma: no cover
        await models.set_status(scan_id, "failed")
        await _emit(scan_id, "error", f"Tarama hatasi: {e}", event="done")
    finally:
        _done.add(scan_id)
        # SSE tarafina kapanis sinyali
        await get_queue(scan_id).put({"event": "close"})


def start_scan_task(scan_id: str, target: str) -> asyncio.Task:
    """Pipeline'i arka plan task olarak baslat."""
    return asyncio.create_task(run_pipeline(scan_id, target))
