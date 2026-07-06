"""Harici guvenlik tool'lari entegrasyonu (ProjectDiscovery: subfinder/naabu/nuclei).

Her tool icin bir adapter: binary'yi bul (PATH > %APPDATA%/PentraCe/bin > indir),
calistir, ciktisini PentraCe'nin veri modeline cevir. Tool yoksa cagiran taraf
yerlesik kontrole geri doner (fallback).
"""
