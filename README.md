# PentraCe — Otomatik Recon & Zafiyet Tarama Platformu

[![Release](https://img.shields.io/github/v/release/yigitdayoglu/pentrace?color=b8ff2e&label=s%C3%BCr%C3%BCm)](https://github.com/yigitdayoglu/pentrace/releases/latest)
[![License: MIT](https://img.shields.io/badge/lisans-MIT-b8ff2e.svg)](LICENSE)
![Platform](https://img.shields.io/badge/platform-Windows-0a0e0f)
![Python](https://img.shields.io/badge/Python-3.12-3776ab)
![React](https://img.shields.io/badge/React-18-61dafb)

🌐 **Tanıtım sayfası:** [yigitdayoglu.github.io/pentrace](https://yigitdayoglu.github.io/pentrace/) · ⬇️ **[İndir](https://github.com/yigitdayoglu/pentrace/releases/latest)**

> Bir hedef gir → otomatik keşif → zafiyet tarama → canlı dashboard + rapor.

PentraCe, uçtan uca bir offensive-security pipeline'ıdır. Bir domain veya IP
verildiğinde keşif (subdomain, port, teknoloji) ve aktif zafiyet taraması (SQLi,
XSS, open redirect, dizin bruteforce, SSRF, güvenlik başlıkları) yapar; sonuçları
canlı bir dashboard'da gösterir ve PDF/JSON rapor üretir.

**Kurulumsuz, sunucusuz, ücretsiz bir masaüstü uygulamasıdır:** tek `.exe` indir,
çift tıkla, kullan. **Üyelik yok, login yok, abonelik yok, limit yok** — taramalar
tamamen senin makinende çalışır, hiçbir veri dışarı çıkmaz.

➡️ **[PentraCe.exe indir (Releases)](https://github.com/yigitdayoglu/pentrace/releases/latest)**

![Terminal Noir dashboard](docs/screenshot.png)

---

## ⚠️ Etik ve Yasal Uyarı

**PentraCe yalnızca açık yazılı izniniz olan sistemlerde kullanılmalıdır.**
Yetkisiz tarama çoğu ülkede suçtur (TR: 5237 sayılı TCK md. 243–245). Araç,
her tarama öncesi izin onayı ister. Üçüncü taraf sistemlere izinsiz tarama
yapmaktan doğacak tüm sorumluluk kullanıcıya aittir. Bu proje eğitim, kendi
altyapınızın denetimi ve yetkili sızma testleri için tasarlanmıştır.

---

## Mimari

```
Hedef (domain / IP)
   │
   ▼
[1] Recon       subdomain (crt.sh + wordlist) → port (asyncio TCP) → teknoloji parmak izi
   │
   ▼
[2] Vuln Scan   SQLi · XSS · Open Redirect · Dir Brute · SSRF · Güvenlik başlıkları
   │
   ▼
[3] Rapor       severity skorlama → PDF (reportlab) + JSON
   │
   ▼
[4] Dashboard   SSE canlı log · bulgu kartları · rapor indirme
```

> Masaüstü sürümünde **kimlik doğrulama / üyelik yoktur** — aç, kullan. (Çok kullanıcılı
> bir sunucuya deploy etmek istersen, kodda opsiyonel olarak kapalı duran auth/plan
> katmanı `AUTH_ENABLED=true` ile açılabilir — bkz. *Gelişmiş: Docker* bölümü.)

**Backend:** Python 3.12 / FastAPI · SQLAlchemy 2.0 async · PostgreSQL (asyncpg) /
SQLite (aiosqlite) · JWT (PyJWT) · bcrypt · httpx · BeautifulSoup · reportlab
**Frontend:** React + Vite · elle yazılmış "Terminal Noir" CSS · SSE
**Altyapı:** Docker Compose (postgres + backend + nginx)

**Tasarım notları:**
- Port tarama saf `asyncio` ile yapılır — harici `nmap` gerekmez.
- DB katmanı `DATABASE_URL` ile değiştirilebilir: yerelde SQLite, Docker'da PostgreSQL
  (aynı kod, 12-factor yapılandırma).

---

## Kullanım — Masaüstü (önerilen)

En basit yol: **[Releases](https://github.com/yigitdayoglu/pentrace/releases/latest)**
sayfasından `PentraCe.exe`'yi indir, çift tıkla. Login/kurulum yok; aç → karşılama
ekranı → kullan. Detay ve kaynaktan build için aşağıdaki *Masaüstü Uygulaması* bölümüne bak.

---

## Gelişmiş: Docker (çok-kullanıcılı / SaaS modu — opsiyonel)

Aynı kodu bir sunucuya, **üyelik + plan sistemi açık** olarak deploy etmek istersen:

```bash
cp .env.example .env      # gizli değerleri düzenleyin (SECRET_KEY, ADMIN_PASSWORD!)
docker compose up --build
```

Arayüz: **http://localhost:8080** · Varsayılan admin: `.env` içindeki `ADMIN_EMAIL` / `ADMIN_PASSWORD`.
Servisler: `db` (PostgreSQL 16) · `backend` (FastAPI :8000) · `frontend` (nginx :8080).

> Bu modda JWT üyelik, e-posta doğrulama, IP kötüye-kullanım engeli ve plan/kota
> katmanı aktiftir (`AUTH_ENABLED`/`BILLING_ENABLED=true`). Masaüstü sürümünde hepsi kapalıdır.

---

## Geliştirme (yerel — SQLite)

### Backend

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --port 8000
```

Backend `http://127.0.0.1:8000` (Swagger: `/docs`). DB varsayılan olarak yerel
`pentrace.db` (SQLite). İlk açılışta `config.py`'deki admin otomatik oluşturulur.

> Not: `asyncpg`/`greenlet` C-uzantıları için **Python 3.12** kullanın (3.14'te
> henüz wheel yok). Docker imajı da 3.12 tabanlıdır.

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Dashboard `http://localhost:5173` (API'ye `/api` proxy ile bağlanır).

---

## Masaüstü Uygulaması (tek `.exe`)

Backend + arayüz + SQLite tek bir `.exe`'ye paketlenir; native pencerede (Windows'un
yerleşik **WebView2**'si) açılır. Sunucu/hosting gerekmez.

**Son kullanıcı:** [Releases](https://github.com/yigitdayoglu/pentrace/releases/latest)'ten
`PentraCe.exe`'yi indir, çift tıkla. (Build gerektirmez.)

**Kaynaktan build (geliştirici):**

```powershell
# Bağımlılıklar (bir kez):
cd backend
.\.venv\Scripts\python.exe -m pip install pywebview pyinstaller pillow

# Build (frontend + exe, tek komut):
cd ..
.\build-desktop.ps1            # üretim (penceresiz)
# .\build-desktop.ps1 -Console # hata ayıklama (konsollu)
```

Çıktı: **`backend/dist/PentraCe.exe`** (~37 MB). Çift tıkla çalışır.

**Masaüstü modu davranışı:**
- **Login/üyelik yok** (`AUTH_ENABLED=false`): aç → **bir kez karşılama ekranı** →
  doğrudan kullanım. Arka planda tek yerel kullanıcı otomatik oluşturulur.
- **Plan/abonelik sistemi tamamen kapalı** (`BILLING_ENABLED=false`): Pro tier, günlük
  kota, "Pro'ya Geç" yok — **sınırsız**. (Yerel kurulumda merkezi abonelik/üyelik
  yönetimi mümkün olmadığı için.)
- Mail doğrulama ve IP limiti de kapalı.
- Tüm veri **`%APPDATA%\PentraCe`** altında: `pentrace.db`, raporlar, `secret.key`
- Taramalar **kendi makinenin IP'sinden** çıkar (pentest için doğru olan)
- Geliştirmede paketlemeden çalıştırmak için: `cd backend; .\.venv\Scripts\python.exe desktop.py`

> Aynı kod tabanı üç şekilde çalışır: **web (dev)**, **Docker (SaaS)**, **masaüstü (.exe)** —
> davranış `AUTH_ENABLED`, `BILLING_ENABLED`, `REQUIRE_EMAIL_VERIFICATION`,
> `MAX_ACCOUNTS_PER_IP`, `DATABASE_URL` env'leriyle ayarlanır. Üyelik + plan sistemi
> yalnızca merkezi (Docker/SaaS) dağıtımda anlamlı olduğu için orada açık,
> masaüstünde kapalıdır.

---

## API

> Aşağıdaki auth/admin uçları **yalnızca çok-kullanıcılı modda** (`AUTH_ENABLED=true`,
> Docker/SaaS) geçerlidir. **Masaüstü sürümünde login yoktur** — tarama uçları
> arka planda otomatik yerel oturumla çağrılır.

Tarama ve admin uçları **JWT gerektirir** (`Authorization: Bearer <token>`).
SSE ve rapor indirme, tarayıcı kısıtları nedeniyle `?token=` query-param ile auth olur.

| Method | Endpoint                       | Açıklama                              |
|--------|--------------------------------|---------------------------------------|
| POST   | `/api/auth/register`           | Kayıt (`{email, password}`) → token (IP limitli) |
| POST   | `/api/auth/verify`             | E-posta doğrula (`{code}`)            |
| POST   | `/api/auth/resend`             | Doğrulama kodunu tekrar gönder        |
| POST   | `/api/auth/login`              | Giriş (OAuth2 form) → token           |
| GET    | `/api/auth/me`                 | Profil + kota durumu                  |
| GET    | `/api/scans`                   | Kendi taramaların (admin: hepsi)      |
| POST   | `/api/scans`                   | Yeni tarama (kota kontrollü)          |
| GET    | `/api/scans/{id}`              | Tarama detayı (sahip veya admin)      |
| GET    | `/api/scans/{id}/stream`       | SSE canlı log (query-param token)     |
| GET    | `/api/scans/{id}/report`       | Rapor indir (`format=pdf\|json`)      |
| GET    | `/api/admin/users`             | Kullanıcı listesi (admin)             |
| PATCH  | `/api/admin/users/{id}`        | Rol/plan değiştir (admin)             |

---

## E-posta Doğrulama ve IP Limiti (yalnızca çok-kullanıcılı / Docker modu)

> Masaüstü sürümünde geçerli değildir (login + üyelik kapalı).

- **Kayıt akışı:** kullanıcı kayıt olur → 6 haneli kod üretilir → mail "gönderilir"
  → kullanıcı doğrulanana kadar **tarama başlatamaz** (`/api/scans` → 403).
- **Dev-mod (varsayılan):** `SMTP_HOST` boşsa kod gerçek mail yerine **backend
  konsoluna** ve `backend/dev_mails.log` dosyasına yazılır. Geliştirme/test için.
- **Gerçek mail:** `.env`'e `SMTP_HOST/PORT/USER/PASSWORD` girilince otomatik olarak
  gerçek SMTP'ye geçer (kod değişikliği gerekmez). Böylece yalnızca **gerçek aktif
  bir maile** erişimi olan kişi hesabı doğrulayabilir.
- **IP abuse engeli:** aynı IP'den `MAX_ACCOUNTS_PER_IP` (varsayılan 3) /
  `ACCOUNT_IP_WINDOW_HOURS` (varsayılan 24) penceresinde fazla hesap açılırsa
  kayıt **429** ile reddedilir. nginx arkasında gerçek IP `X-Forwarded-For`'dan alınır.

İlgili env değişkenleri `.env.example` içinde.

---

## Testler

Yerel, kasıtlı-savunmasız bir fixture sunucusuna karşı deterministik testler:

```powershell
cd backend
# Birim testler (servis gerektirmez)
.\.venv\Scripts\python.exe tests\db_layer_test.py        # SQLAlchemy katmanı + kota/IP sayacı
.\.venv\Scripts\python.exe tests\auth_test.py            # hash/JWT/kota 429
.\.venv\Scripts\python.exe tests\run_vulnscan_test.py    # 5 zafiyet kontrolü (fixture gerekli)

# Uçtan uca (fixture :8099 + uvicorn :8000 çalışıyor olmalı)
.\.venv\Scripts\python.exe tests\vuln_fixture.py         # 1. pencere
.\.venv\Scripts\python.exe -m uvicorn main:app --port 8000  # 2. pencere
.\.venv\Scripts\python.exe tests\e2e_auth_test.py        # auth + doğrulama + tarama akışı
.\.venv\Scripts\python.exe tests\e2e_verify_test.py      # mail doğrulama + IP limit
.\.venv\Scripts\python.exe tests\report_test.py          # PDF + JSON
```

---

## Proje Yapısı

```
pentrace/
├── docker-compose.yml      # postgres + backend + frontend
├── build-desktop.ps1       # masaüstü .exe build scripti
├── .env.example            # ortam değişkenleri şablonu
├── backend/
│   ├── Dockerfile
│   ├── main.py             # FastAPI app: auth + scans + admin + SSE + rapor
│   ├── config.py           # pydantic-settings (DATABASE_URL, JWT, kotalar)
│   ├── db.py               # SQLAlchemy async engine + session
│   ├── models.py           # ORM (User/Scan/Asset/Finding) + repository
│   ├── auth.py             # bcrypt + JWT + roller + kota + IP limit + kod
│   ├── email_service.py    # mail gönderimi (dev-mod log / SMTP)
│   ├── desktop.py          # masaüstü launcher (PyWebView + uvicorn thread)
│   ├── paths.py            # bundle/yazılabilir yol çözücü (PyInstaller-aware)
│   ├── pipeline.py         # async orchestrator (recon → vulnscan → DB)
│   ├── report.py           # PDF + JSON rapor
│   ├── modules/
│   │   ├── recon.py        # subdomain, port, fingerprint
│   │   └── vulnscan.py     # SQLi, XSS, redirect, dir-brute, SSRF, headers
│   ├── wordlists/          # subdomains.txt, dirs.txt
│   └── tests/              # fixture + birim + e2e testleri
└── frontend/
    ├── Dockerfile          # multi-stage: vite build → nginx
    ├── nginx.conf          # SPA + /api proxy (SSE uyumlu)
    └── src/
        ├── App.jsx         # auth orchestrator + header
        ├── Auth.jsx        # giriş / kayıt ekranı
        ├── VerifyGate.jsx  # e-posta doğrulama kapısı (kod + resend)
        ├── Dashboard.jsx   # tarama + canlı akış + sonuçlar
        ├── Admin.jsx       # kullanıcı yönetim paneli
        ├── api.js          # token'lı fetch + SSE yardımcıları
        └── styles.css      # Terminal Noir tema
```

---

## Yol Haritası (gelecek geliştirmeler)

- [x] ~~Kimlik doğrulamalı dashboard (çok kullanıcı)~~
- [x] ~~Docker ile dağıtım~~
- [x] ~~E-posta doğrulama (6 haneli kod, dev-mod + SMTP-ready)~~
- [x] ~~IP bazlı hesap kötüye-kullanım engeli~~
- [x] ~~Masaüstü uygulaması (PyWebView + PyInstaller, tek `.exe`, self-contained)~~
- [ ] Gerçek SMTP bağlama + şifre sıfırlama
- [ ] Eşzamanlı çoklu tarama kuyruğu (Celery/RQ)
- [ ] CVE eşleştirme (servis sürümü → NVD)
- [ ] Tarama profilleri (hızlı / derin) + özel wordlist yükleme
- [ ] Ödeme entegrasyonu (gerçek pro plan)
