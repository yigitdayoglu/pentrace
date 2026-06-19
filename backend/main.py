"""PentraCe FastAPI uygulamasi — auth + roller + kotalar.

Auth:
  POST /api/auth/register   -> kayit + token
  POST /api/auth/login      -> token (OAuth2 form: username=email)
  GET  /api/auth/me         -> profil + kota

Taramalar (auth gerekli):
  GET  /api/scans                -> kendi taramalar (admin: hepsi)
  POST /api/scans                -> kota kontrollu yeni tarama
  GET  /api/scans/{id}           -> detay (sahip veya admin)
  GET  /api/scans/{id}/stream    -> SSE (query-param token)
  GET  /api/scans/{id}/report    -> rapor (query-param token)

Admin:
  GET   /api/admin/users         -> kullanici listesi
  PATCH /api/admin/users/{id}    -> rol/plan degistir
"""
from __future__ import annotations

import asyncio
import json
import secrets
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

import re

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

import auth
import email_service
import models
import pipeline
from config import settings
from db import AsyncSessionLocal, get_session, init_db
from models import User


_DEFAULT_SECRET = "dev-secret-CHANGE-ME-in-production"


def _warn_insecure_defaults() -> None:
    """Auth acikken (web/SaaS) zayif varsayilan secret/sifre kullaniliyorsa uyar."""
    if not settings.auth_enabled:
        return  # masaustu: auth kapali, secret rastgele uretilir
    import sys
    if settings.secret_key == _DEFAULT_SECRET:
        print("UYARI: SECRET_KEY varsayilan deger! Production'da MUTLAKA ortam "
              "degiskeniyle degistirin (JWT taklit edilebilir).", file=sys.stderr, flush=True)
    if settings.admin_password == "admin12345":
        print("UYARI: ADMIN_PASSWORD varsayilan ('admin12345')! Production'da degistirin.",
              file=sys.stderr, flush=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    _warn_insecure_defaults()
    if settings.auth_enabled:
        await _ensure_admin()
    else:
        await _ensure_local_user()
    yield


async def _ensure_admin() -> None:
    """Config'deki admin yoksa olustur (yalnizca auth acikken)."""
    if not settings.admin_email:
        return
    async with AsyncSessionLocal() as db:
        existing = await auth.get_user_by_email(db, settings.admin_email)
        if existing:
            return
        db.add(User(
            email=settings.admin_email.lower(),
            password_hash=auth.hash_password(settings.admin_password),
            role="admin", plan="pro", is_verified=True,
        ))
        await db.commit()


async def _ensure_local_user() -> None:
    """Auth kapaliyken: tek yerel kullaniciyi olustur (login gerektirmez)."""
    async with AsyncSessionLocal() as db:
        existing = await auth.get_user_by_email(db, settings.local_user_email)
        if existing:
            return
        db.add(User(
            email=settings.local_user_email.lower(),
            password_hash=auth.hash_password(secrets.token_urlsafe(16)),
            role="user", plan="pro", is_verified=True,
        ))
        await db.commit()


app = FastAPI(title="PentraCe", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"], allow_headers=["*"],
)


# --------------------------------------------------------------------------- #
# Semalar
# --------------------------------------------------------------------------- #
class RegisterRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _valid_email(cls, v: str) -> str:
        v = v.strip().lower()
        # Temel format kontrolu; .local gibi dahili domainlere de izin verilir.
        if not _EMAIL_RE.match(v):
            raise ValueError("Gecerli bir e-posta adresi girin.")
        return v


class ScanRequest(BaseModel):
    target: str
    authorized: bool = False


class UserPatch(BaseModel):
    role: str | None = None
    plan: str | None = None


class VerifyRequest(BaseModel):
    code: str


def _user_public(u: User) -> dict:
    return {"id": u.id, "email": u.email, "role": u.role, "plan": u.plan,
            "is_verified": u.is_verified,
            "created_at": u.created_at.isoformat() if u.created_at else None}


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "pentrace"}


@app.get("/api/config")
async def public_config() -> dict:
    """Auth oncesi istemci yapilandirmasi — UI'nin login/plan/dogrulama
    ozelliklerini gosterip gostermeyecegini belirler."""
    return {
        "auth_enabled": settings.auth_enabled,
        "billing_enabled": settings.billing_enabled,
        "require_email_verification": settings.require_email_verification,
    }


@app.post("/api/auth/local")
async def local_session(db: AsyncSession = Depends(get_session)) -> dict:
    """Login'siz yerel oturum — yalnizca auth kapaliyken (masaustu).
    Otomatik olusturulan tek yerel kullanici icin token doner."""
    if settings.auth_enabled:
        raise HTTPException(status_code=404, detail="Bu surumde login gereklidir.")
    user = await auth.get_user_by_email(db, settings.local_user_email)
    if not user:  # lifespan'da olusur; yine de guvence
        user = User(
            email=settings.local_user_email.lower(),
            password_hash=auth.hash_password(secrets.token_urlsafe(16)),
            role="user", plan="pro", is_verified=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return {"token": auth.create_access_token(user.id), "user": _user_public(user)}


@app.post("/api/auth/register")
async def register(req: RegisterRequest, request: Request,
                   db: AsyncSession = Depends(get_session)) -> dict:
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Sifre en az 8 karakter olmali.")
    if await auth.get_user_by_email(db, req.email):
        raise HTTPException(status_code=409, detail="Bu e-posta zaten kayitli.")

    # IP abuse engeli — ayni IP'den cok hesap acilmasini durdur
    ip = auth.client_ip(request)
    await auth.enforce_ip_signup_limit(ip)

    # Dogrulama kodu uret + "gonder" (dev-mod: konsola yazar)
    code = auth.generate_code()
    user = User(
        email=req.email.lower(), password_hash=auth.hash_password(req.password),
        role="user", plan="free", signup_ip=ip,
        is_verified=not settings.require_email_verification,
        verification_code=code,
        verification_sent_at=models._now(),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    if settings.require_email_verification:
        email_service.send_verification_email(user.email, code)

    return {"token": auth.create_access_token(user.id), "user": _user_public(user)}


@app.post("/api/auth/verify")
async def verify_email(req: VerifyRequest, user: User = Depends(auth.current_user),
                       db: AsyncSession = Depends(get_session)) -> dict:
    if user.is_verified:
        return {"user": _user_public(user), "message": "Hesap zaten dogrulanmis."}
    fresh = await db.get(User, user.id)
    if not auth.code_is_valid(fresh, req.code):
        raise HTTPException(status_code=400, detail="Kod hatali veya suresi dolmus.")
    fresh.is_verified = True
    fresh.verification_code = None
    await db.commit()
    await db.refresh(fresh)
    return {"user": _user_public(fresh), "message": "E-posta dogrulandi."}


@app.post("/api/auth/resend")
async def resend_code(user: User = Depends(auth.current_user),
                      db: AsyncSession = Depends(get_session)) -> dict:
    fresh = await db.get(User, user.id)
    if fresh.is_verified:
        return {"message": "Hesap zaten dogrulanmis."}
    if not auth.can_resend(fresh):
        raise HTTPException(status_code=429,
                            detail=f"Cok sik kod istegi. {settings.resend_cooldown_seconds} sn bekleyin.")
    code = auth.generate_code()
    fresh.verification_code = code
    fresh.verification_sent_at = models._now()
    await db.commit()
    email_service.send_verification_email(fresh.email, code)
    return {"message": "Yeni dogrulama kodu gonderildi."}


@app.post("/api/auth/login")
async def login(form: OAuth2PasswordRequestForm = Depends(),
                db: AsyncSession = Depends(get_session)) -> dict:
    user = await auth.get_user_by_email(db, form.username)
    if not user or not auth.verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=401, detail="E-posta veya sifre hatali.")
    return {"token": auth.create_access_token(user.id), "user": _user_public(user)}


@app.get("/api/auth/me")
async def me(user: User = Depends(auth.current_user)) -> dict:
    return {"user": _user_public(user), "quota": await auth.quota_status(user)}


@app.post("/api/billing/upgrade")
async def upgrade_plan(user: User = Depends(auth.current_user),
                       db: AsyncSession = Depends(get_session)) -> dict:
    """Pro plana gec. Demo-mod: odeme entegrasyonu yokken aninda yukseltir.
    allow_demo_upgrade kapaliysa gercek odeme akisina yonlendirilmeli (501)."""
    if not settings.billing_enabled:
        raise HTTPException(status_code=404, detail="Plan sistemi bu surumde devre disi.")
    if not settings.allow_demo_upgrade:
        raise HTTPException(status_code=501,
                            detail="Odeme entegrasyonu henuz aktif degil. Yakinda.")
    fresh = await db.get(User, user.id)
    fresh.plan = "pro"
    await db.commit()
    await db.refresh(fresh)
    return {"user": _user_public(fresh), "quota": await auth.quota_status(fresh)}


@app.post("/api/billing/downgrade")
async def downgrade_plan(user: User = Depends(auth.current_user),
                         db: AsyncSession = Depends(get_session)) -> dict:
    """Free plana don (test/demo amacli)."""
    fresh = await db.get(User, user.id)
    fresh.plan = "free"
    await db.commit()
    await db.refresh(fresh)
    return {"user": _user_public(fresh), "quota": await auth.quota_status(fresh)}


# --------------------------------------------------------------------------- #
# Yardimci: query-param token ile kullanici coz (SSE / rapor indirme icin)
# --------------------------------------------------------------------------- #
async def _user_from_query_token(token: str | None) -> User:
    if not token:
        raise HTTPException(status_code=401, detail="token parametresi gerekli")
    uid = auth.decode_token(token)
    if uid is None:
        raise HTTPException(status_code=401, detail="Gecersiz token")
    async with AsyncSessionLocal() as db:
        u = await db.get(User, uid)
    if not u:
        raise HTTPException(status_code=401, detail="Kullanici bulunamadi")
    return u


async def _owned_scan_or_404(scan_id: str, user: User) -> dict:
    scan = await models.get_scan(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Tarama bulunamadi.")
    if user.role != "admin" and scan["user_id"] != user.id:
        raise HTTPException(status_code=403, detail="Bu taramaya erisim yetkiniz yok.")
    return scan


# --------------------------------------------------------------------------- #
# Taramalar
# --------------------------------------------------------------------------- #
@app.get("/api/scans")
async def list_scans(user: User = Depends(auth.current_user)) -> list[dict]:
    # admin tum taramalari gorur, normal kullanici yalnizca kendininkini
    return await models.list_scans(user_id=None if user.role == "admin" else user.id)


@app.post("/api/scans")
async def create_scan(req: ScanRequest, user: User = Depends(auth.require_verified)) -> dict:
    if not req.authorized:
        raise HTTPException(status_code=403,
                            detail="Bu hedefe tarama izniniz oldugunu onaylamaniz gerekir.")
    target = req.target.strip()
    if not target:
        raise HTTPException(status_code=400, detail="Hedef bos olamaz.")

    await auth.check_quota(user)  # kota dolmussa 429

    scan_id = await models.create_scan(target, user.id)
    pipeline.start_scan_task(scan_id, target)
    return {"scan_id": scan_id, "target": target, "status": "running"}


@app.get("/api/scans/{scan_id}")
async def scan_detail(scan_id: str, user: User = Depends(auth.current_user)) -> dict:
    scan = await _owned_scan_or_404(scan_id, user)
    return {
        "scan": scan,
        "assets": await models.get_assets(scan_id),
        "findings": await models.get_findings(scan_id),
    }


@app.get("/api/scans/{scan_id}/stream")
async def scan_stream(scan_id: str, token: str | None = None):
    user = await _user_from_query_token(token)
    await _owned_scan_or_404(scan_id, user)

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
async def scan_report(scan_id: str, format: str = "pdf", token: str | None = None):
    user = await _user_from_query_token(token)
    await _owned_scan_or_404(scan_id, user)

    import report
    if format == "json":
        path = await report.build_json(scan_id)
        return FileResponse(path, media_type="application/json", filename=f"pentrace_{scan_id}.json")
    path = await report.build_pdf(scan_id)
    return FileResponse(path, media_type="application/pdf", filename=f"pentrace_{scan_id}.pdf")


# --------------------------------------------------------------------------- #
# Admin
# --------------------------------------------------------------------------- #
@app.get("/api/admin/users")
async def admin_users(_: User = Depends(auth.require_admin),
                      db: AsyncSession = Depends(get_session)) -> list[dict]:
    from sqlalchemy import select
    rows = (await db.execute(select(User).order_by(User.created_at.desc()))).scalars().all()
    return [_user_public(u) for u in rows]


@app.patch("/api/admin/users/{user_id}")
async def admin_patch_user(user_id: int, patch: UserPatch,
                           _: User = Depends(auth.require_admin),
                           db: AsyncSession = Depends(get_session)) -> dict:
    u = await db.get(User, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="Kullanici bulunamadi.")
    if patch.role in ("user", "admin"):
        u.role = patch.role
    if patch.plan in ("free", "pro"):
        u.plan = patch.plan
    await db.commit()
    await db.refresh(u)
    return _user_public(u)


# --------------------------------------------------------------------------- #
# Statik frontend servisi (yalnizca frontend/dist varsa — desktop/standalone).
# Dev (Vite) ve Docker (nginx) bu blogu kullanmaz; dist olmadigi icin atlanir.
# --------------------------------------------------------------------------- #
from fastapi.staticfiles import StaticFiles  # noqa: E402
from paths import resource_path  # noqa: E402

_DIST = resource_path("frontend/dist")
if _DIST.is_dir():
    _DIST_ROOT = _DIST.resolve()
    app.mount("/assets", StaticFiles(directory=str(_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def _spa_fallback(full_path: str):
        # Bilinmeyen /api yollari icin SPA degil 404 don
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Bulunamadi.")
        if full_path:
            candidate = (_DIST / full_path).resolve()
            # Path traversal korumasi: yalnizca dist dizini icindeki dosyalar
            if candidate.is_file() and candidate.is_relative_to(_DIST_ROOT):
                return FileResponse(str(candidate))
        return FileResponse(str(_DIST / "index.html"))
