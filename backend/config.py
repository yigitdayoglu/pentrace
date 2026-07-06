"""Uygulama yapilandirmasi — ortam degiskenleriyle.

Tek kullanicili yerel masaustu uygulamasi. DATABASE_URL ile DB yolu degistirilebilir.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Veritabani — masaustunde %APPDATA%/PentraCe/pentrace.db (desktop.py ayarlar)
    database_url: str = "sqlite+aiosqlite:///./pentrace.db"


settings = Settings()
