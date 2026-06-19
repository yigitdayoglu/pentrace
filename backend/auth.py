"""Kimlik dogrulama — bcrypt sifre hash + JWT token + FastAPI dependency'leri.

Roller: user | admin. Planlar: free | pro. Kota: gunluk tarama limiti (config).
"""
from __future__ import annotations

import datetime as _dt
import secrets

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings, daily_limit_for_plan
from db import get_session
from models import User, count_accounts_from_ip, count_scans_since

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


# --------------------------------------------------------------------------- #
# Sifre
# --------------------------------------------------------------------------- #
def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except (ValueError, TypeError):
        return False


# --------------------------------------------------------------------------- #
# JWT
# --------------------------------------------------------------------------- #
def create_access_token(user_id: int) -> str:
    now = _dt.datetime.now(_dt.timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + _dt.timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


# --------------------------------------------------------------------------- #
# Dependency'ler
# --------------------------------------------------------------------------- #
async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    return await db.get(User, user_id)


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    res = await db.execute(select(User).where(User.email == email.lower()))
    return res.scalar_one_or_none()


async def current_user(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_session),
) -> User:
    """Header'daki Bearer token'dan oturum kullanicisini coz."""
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Oturum gerekli")
    uid = decode_token(token)
    if uid is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Gecersiz token")
    user = await get_user_by_id(db, uid)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Kullanici bulunamadi")
    return user


async def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin yetkisi gerekli")
    return user


async def require_verified(user: User = Depends(current_user)) -> User:
    """Mail dogrulamasi zorunlu olan uclar icin (orn. tarama baslatma)."""
    if settings.require_email_verification and not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Once e-posta adresinizi dogrulamaniz gerekiyor.",
        )
    return user


# --------------------------------------------------------------------------- #
# Mail dogrulama
# --------------------------------------------------------------------------- #
def generate_code() -> str:
    """6 haneli kriptografik rastgele dogrulama kodu."""
    return "".join(secrets.choice("0123456789") for _ in range(6))


def can_resend(user: User) -> bool:
    """Resend cooldown gecti mi?"""
    if not user.verification_sent_at:
        return True
    sent = user.verification_sent_at
    if sent.tzinfo is None:
        sent = sent.replace(tzinfo=_dt.timezone.utc)
    elapsed = (_dt.datetime.now(_dt.timezone.utc) - sent).total_seconds()
    return elapsed >= settings.resend_cooldown_seconds


def code_is_valid(user: User, code: str) -> bool:
    """Kod dogru ve TTL icinde mi?"""
    if not user.verification_code or user.verification_code != code.strip():
        return False
    if not user.verification_sent_at:
        return False
    sent = user.verification_sent_at
    if sent.tzinfo is None:
        sent = sent.replace(tzinfo=_dt.timezone.utc)
    age_min = (_dt.datetime.now(_dt.timezone.utc) - sent).total_seconds() / 60
    return age_min <= settings.verification_code_ttl_minutes


# --------------------------------------------------------------------------- #
# IP abuse engeli
# --------------------------------------------------------------------------- #
def client_ip(request: Request) -> str:
    """Gercek istemci IP'si. Proxy arkasinda X-Forwarded-For ilk degeri."""
    if settings.trust_proxy_headers:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()
        xri = request.headers.get("x-real-ip")
        if xri:
            return xri.strip()
    return request.client.host if request.client else "unknown"


async def enforce_ip_signup_limit(ip: str) -> None:
    """Ayni IP'den cok sayida hesap acilmasini engelle (abuse)."""
    limit = settings.max_accounts_per_ip
    if limit <= 0:
        return
    since = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(hours=settings.account_ip_window_hours)
    used = await count_accounts_from_ip(ip, since)
    if used >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Bu IP adresinden son {settings.account_ip_window_hours} saatte "
                   f"cok fazla hesap olusturuldu ({used}/{limit}). Lutfen daha sonra deneyin.",
        )


# --------------------------------------------------------------------------- #
# Kota
# --------------------------------------------------------------------------- #
async def check_quota(user: User) -> dict:
    """Kullanicinin gunluk kota durumunu don. Asilmissa HTTPException firlatir."""
    limit = daily_limit_for_plan(user.plan)
    since = _dt.datetime.now(_dt.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    used = await count_scans_since(user.id, since)
    if limit and used >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Gunluk tarama kotaniz doldu ({used}/{limit}). Pro plana gecin veya yarin tekrar deneyin.",
        )
    return {"plan": user.plan, "limit": limit, "used": used}


async def quota_status(user: User) -> dict:
    """Sadece okuma — kota durumu (limit asimi firlatmaz)."""
    limit = daily_limit_for_plan(user.plan)
    since = _dt.datetime.now(_dt.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    used = await count_scans_since(user.id, since)
    return {"plan": user.plan, "limit": limit, "used": used,
            "remaining": (limit - used) if limit else None}
