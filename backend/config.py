"""Uygulama yapilandirmasi — ortam degiskenleriyle.

Tek kullanicili yerel masaustu uygulamasi. DATABASE_URL ile DB yolu degistirilebilir.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Veritabani — masaustunde %APPDATA%/PentraCe/pentrace.db (desktop.py ayarlar)
    database_url: str = "sqlite+aiosqlite:///./pentrace.db"

    # Harici tool entegrasyonu (ProjectDiscovery: nuclei/subfinder/naabu).
    # external_tools: acikken PATH'te ya da %APPDATA%/PentraCe/bin'de tool aranir,
    #   varsa yerlesik kontrollere ek/alternatif olarak kullanilir.
    # tools_auto_download: tool bulunamazsa resmi GitHub release'inden indir (SHA256 dogrulamali).
    external_tools: bool = True
    tools_auto_download: bool = True
    # nuclei kapsami: 'info' seviyesi cok sayida + dusuk sinyal (teknoloji/versiyon
    # tespiti) oldugu icin varsayilan disi. Tam kapsam istersen "info,low,medium,high,critical".
    nuclei_severity: str = "low,medium,high,critical"
    nuclei_timeout: float = 300.0  # streaming: sinira ulasilirsa o ana kadarki bulgular korunur


settings = Settings()
