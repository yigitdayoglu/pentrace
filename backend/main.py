"""PentraCe FastAPI uygulamasi — tek kullanicili yerel masaustu tarayici.

Kimlik dogrulama / uyelik YOKTUR. Endpointler:
  GET  /api/health
  GET  /api/scans                -> tum taramalar
  POST /api/scans                -> yeni tarama {target, authorized}
  GET  /api/scans/{id}           -> detay (assets + findings)
  GET  /api/scans/{id}/stream    -> SSE canli log
  GET  /api/scans/{id}/report    -> PDF / JSON rapor
Ek olarak frontend/dist statik olarak servis edilir (paketlenmis masaustu).
"""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import models
import pipeline
from db import init_db
from paths import resource_path


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="PentraCe", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"], allow_headers=["*"],
)


class ScanRequest(BaseModel):
    target: str
    authorized: bool = False


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "pentrace"}


@app.get("/api/scans")
async def list_scans() -> list[dict]:
    return await models.list_scans()


@app.post("/api/scans")
async def create_scan(req: ScanRequest) -> dict:
    if not req.authorized:
        raise HTTPException(status_code=403,
                            detail="Bu hedefe tarama izniniz oldugunu onaylamaniz gerekir.")
    target = req.target.strip()
    if not target:
        raise HTTPException(status_code=400, detail="Hedef bos olamaz.")
    scan_id = await models.create_scan(target)
    pipeline.start_scan_task(scan_id, target)
    return {"scan_id": scan_id, "target": target, "status": "running"}


@app.get("/api/scans/{scan_id}")
async def scan_detail(scan_id: str) -> dict:
    scan = await models.get_scan(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Tarama bulunamadi.")
    return {
        "scan": scan,
        "assets": await models.get_assets(scan_id),
        "findings": await models.get_findings(scan_id),
    }


@app.get("/api/scans/{scan_id}/stream")
async def scan_stream(scan_id: str):
    if not await models.get_scan(scan_id):
        raise HTTPException(status_code=404, detail="Tarama bulunamadi.")

    async def event_gen():
        q = pipeline.get_queue(scan_id)
        if pipeline.is_done(scan_id) and q.empty():
            yield f"data: {json.dumps({'event': 'done', 'message': 'Tarama daha once tamamlandi'})}\n\n"
            return
        while True:
            try:
                item = await asyncio.wait_for(q.get(), timeout=30)
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"
                continue
            if item.get("event") == "close":
                break
            yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/scans/{scan_id}/report")
async def scan_report(scan_id: str, format: str = "pdf"):
    if not await models.get_scan(scan_id):
        raise HTTPException(status_code=404, detail="Tarama bulunamadi.")
    import report
    if format == "json":
        path = await report.build_json(scan_id)
        return FileResponse(path, media_type="application/json", filename=f"pentrace_{scan_id}.json")
    path = await report.build_pdf(scan_id)
    return FileResponse(path, media_type="application/pdf", filename=f"pentrace_{scan_id}.pdf")


# --------------------------------------------------------------------------- #
# Statik frontend (frontend/dist varsa — paketlenmis masaustu surumu)
# --------------------------------------------------------------------------- #
_DIST = resource_path("frontend/dist")
if _DIST.is_dir():
    _DIST_ROOT = _DIST.resolve()
    app.mount("/assets", StaticFiles(directory=str(_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def _spa_fallback(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Bulunamadi.")
        if full_path:
            candidate = (_DIST / full_path).resolve()
            if candidate.is_file() and candidate.is_relative_to(_DIST_ROOT):
                return FileResponse(str(candidate))
        return FileResponse(str(_DIST / "index.html"))
