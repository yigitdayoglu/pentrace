# PentraCe — Otomatik Recon &amp; Zafiyet Tarama

[![License: MIT](https://img.shields.io/badge/lisans-MIT-b8ff2e.svg)](LICENSE)
![Platform](https://img.shields.io/badge/platform-Windows-0a0e0f)
![Python](https://img.shields.io/badge/Python-3.12-3776ab)
![React](https://img.shields.io/badge/React-18-61dafb)

> Bir hedef gir → otomatik keşif → zafiyet tarama → canlı dashboard + PDF rapor.

PentraCe, **kurulumsuz, sunucusuz, ücretsiz** bir masaüstü güvenlik aracıdır.
Tek `.exe` indir, çift tıkla, kullan. **Üyelik yok, login yok, abonelik yok, limit yok.**
Taramalar tamamen senin makinende çalışır; hiçbir veri dışarı çıkmaz.

![PentraCe dashboard](docs/screenshot.png)

---

## ⚠️ Etik ve Yasal Uyarı

PentraCe'yi **yalnızca sana ait veya açık yazılı izin verdiğin** sistemlerde kullan.
Yetkisiz tarama çoğu ülkede suçtur ve tüm sorumluluk kullanıcıya aittir. Bu proje
eğitim ve yetkili güvenlik testleri içindir.

---

## Ne yapar

| Aşama | İçerik |
|-------|--------|
| **Recon** | Subdomain keşfi (crt.sh + wordlist), asyncio port tarama, HTTP başlık &amp; teknoloji parmak izi |
| **Zafiyet Tarama** | SQL injection, XSS, open redirect, dizin bruteforce, SSRF, eksik güvenlik başlıkları |
| **Dashboard** | Server-Sent Events ile canlı log, severity grafiği, bulgu kartları |
| **Rapor** | Önem derecesine göre skorlama → PDF / JSON |

Port tarama saf `asyncio` ile yapılır — harici `nmap` gerekmez.

---

## Kurulum

**İndir, çift tıkla:** [Releases](../../releases/latest) sayfasından `PentraCe.exe`'yi indir.
Kurulum sihirbazı yok; aç → karşılama ekranı → kullan. Tüm veri `%APPDATA%\PentraCe`
altında tutulur (DB + raporlar).

> İmzasız bir `.exe` olduğu için Windows SmartScreen uyarısı çıkabilir:
> *Daha fazla bilgi → Yine de çalıştır*.

---

## Geliştirme

```powershell
# Backend (Python 3.12)
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# Masaüstü uygulamasını paketlemeden çalıştır:
.\.venv\Scripts\python.exe desktop.py

# Veya web modunda geliştir (anlık yenileme):
.\.venv\Scripts\python.exe -m uvicorn main:app --port 8000   # 1. pencere
cd ..\frontend; npm install; npm run dev                      # 2. pencere → http://localhost:5173
```

### `.exe` build

```powershell
.\build-desktop.ps1            # üretim (penceresiz)
# .\build-desktop.ps1 -Console # hata ayıklama (konsollu)
```

Çıktı: **`backend/dist/PentraCe.exe`**. Backend + arayüz + SQLite tek dosyada;
Windows'un yerleşik **WebView2**'sinde native pencerede açılır.

---

## Proje Yapısı

```
pentrace/
├── build-desktop.ps1       # tek komut .exe build
├── backend/
│   ├── desktop.py          # masaüstü launcher (PyWebView + uvicorn thread)
│   ├── main.py             # FastAPI: scan CRUD + SSE + rapor + statik servis
│   ├── pipeline.py         # async orchestrator (recon → vulnscan → DB)
│   ├── models.py           # ORM (Scan/Asset/Finding) + repository
│   ├── report.py           # PDF + JSON rapor
│   ├── db.py · config.py · paths.py
│   ├── modules/
│   │   ├── recon.py        # subdomain, port, fingerprint
│   │   └── vulnscan.py     # SQLi, XSS, redirect, dir-brute, SSRF, headers
│   ├── wordlists/
│   └── tests/
└── frontend/
    └── src/
        ├── App.jsx         # welcome → dashboard
        ├── Welcome.jsx     # ilk açılış ekranı
        ├── Dashboard.jsx   # tarama + canlı akış + sonuçlar
        ├── ResultsViz.jsx  # severity grafiği + özet
        ├── api.js · main.jsx · styles.css
```

---

## Lisans

MIT — bkz. [LICENSE](LICENSE). Yalnızca yetkili güvenlik testleri için kullanın.
