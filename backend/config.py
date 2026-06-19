"""Uygulama yapilandirmasi — 12-factor, ortam degiskenleriyle.

DATABASE_URL ile yerelde SQLite, Docker'da PostgreSQL kullanilir:
  sqlite+aiosqlite:///./pentrace.db          (yerel varsayilan)
  postgresql+asyncpg://user:pass@db:5432/pentrace   (docker)
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Veritabani
    database_url: str = "sqlite+aiosqlite:///./pentrace.db"

    # JWT
    secret_key: str = "dev-secret-CHANGE-ME-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 saat

    # Plan kotalari (gunluk tarama limiti). 0 = sinirsiz.
    free_daily_scans: int = 3
    pro_daily_scans: int = 0  # sinirsiz

    # Kimlik dogrulama (uyelik/login) acik mi? Kapaliysa (masaustu): login yok,
    # otomatik tek yerel kullanici, dogrudan kullanima baslanir.
    auth_enabled: bool = True

    # Faturalandirma/plan sistemi acik mi? Kapaliysa: Pro/kota/yukseltme yok,
    # herkes sinirsiz. Masaustu (.exe) surumunde kapalidir (merkezi yonetim yok).
    billing_enabled: bool = True

    # auth kapaliyken kullanilacak tek yerel kullanici
    local_user_email: str = "local@pentrace.local"

    # Demo: odeme entegrasyonu yokken kullanici kendini Pro'ya yukseltebilsin.
    # Production'da False yapilip gercek odeme akisina baglanmali.
    allow_demo_upgrade: bool = True

    # Ilk acilista olusturulacak admin (bos birakilirsa olusturulmaz)
    admin_email: str = "admin@pentrace.local"
    admin_password: str = "admin12345"

    # Mail dogrulama
    require_email_verification: bool = True
    verification_code_ttl_minutes: int = 30
    resend_cooldown_seconds: int = 60

    # IP abuse engeli: ayni IP'den belirli sürede acilabilecek max hesap
    max_accounts_per_ip: int = 3
    account_ip_window_hours: int = 24
    # nginx/proxy arkasinda gercek IP'yi X-Forwarded-For'dan al
    trust_proxy_headers: bool = True

    # SMTP — bos ise DEV-MOD: dogrulama kodu konsola + dev_mails.log'a yazilir
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@pentrace.local"
    smtp_starttls: bool = True


settings = Settings()


def daily_limit_for_plan(plan: str) -> int:
    """Plan icin gunluk tarama limiti (0 = sinirsiz)."""
    return settings.pro_daily_scans if plan == "pro" else settings.free_daily_scans
