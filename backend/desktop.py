"""PentraCe — masaustu surumu (self-contained).

FastAPI backend'i arka plan thread'de calistirir, native bir pencerede (PyWebView /
Windows'ta WebView2) acar. Her sey yereldir: SQLite DB + raporlar %APPDATA%/PentraCe
altinda. Mail dogrulama ve IP limiti masaustu modunda kapalidir.

Calistirma (gelistirme):  python desktop.py
Paketleme:                PyInstaller (bkz. build-desktop.ps1)
"""
from __future__ import annotations

import os
import secrets
import socket
import sys
import threading
import time
import urllib.request
from pathlib import Path


# --------------------------------------------------------------------------- #
# 1. Ortami app import edilMEDEN once hazirla
# --------------------------------------------------------------------------- #
def _data_dir() -> Path:
    # Override varsa onu kullan (test/portable); yoksa %APPDATA%/PentraCe.
    override = os.environ.get("PENTRACE_DATA_DIR")
    if override:
        d = Path(override)
    else:
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        d = Path(base) / "PentraCe"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _stable_secret(data: Path) -> str:
    """Kurulum basina sabit JWT secret (oturumlar yeniden baslatmada kalsin)."""
    f = data / "secret.key"
    if f.exists():
        return f.read_text(encoding="utf-8").strip()
    s = secrets.token_urlsafe(48)
    f.write_text(s, encoding="utf-8")
    return s


DATA = _data_dir()
os.environ["PENTRACE_DATA_DIR"] = str(DATA)  # DB + raporlar ayni dizinde tutarli
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{(DATA / 'pentrace.db').as_posix()}")
os.environ.setdefault("AUTH_ENABLED", "false")               # yerel: login yok
os.environ.setdefault("REQUIRE_EMAIL_VERIFICATION", "false")  # yerel: dogrulama yok
os.environ.setdefault("MAX_ACCOUNTS_PER_IP", "0")             # yerel: IP limiti yok
os.environ.setdefault("BILLING_ENABLED", "false")            # yerel: Pro/kota yok
os.environ.setdefault("FREE_DAILY_SCANS", "0")               # yerel: sinirsiz tarama
os.environ.setdefault("SECRET_KEY", _stable_secret(DATA))


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


PORT = int(os.environ.get("PENTRACE_PORT") or 0) or _free_port()
BASE_URL = f"http://127.0.0.1:{PORT}"

# --------------------------------------------------------------------------- #
# 2. Sunucu (arka plan thread)
# --------------------------------------------------------------------------- #
import uvicorn  # noqa: E402
import main as app_module  # noqa: E402  (env'ler ayarlandiktan SONRA import)

_server: uvicorn.Server | None = None


def _run_server() -> None:
    global _server
    config = uvicorn.Config(app_module.app, host="127.0.0.1", port=PORT, log_level="warning")
    _server = uvicorn.Server(config)
    _server.run()


def _wait_ready(timeout: float = 25.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{BASE_URL}/api/health", timeout=1) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.2)
    return False


# --------------------------------------------------------------------------- #
# 3. Ana akis
# --------------------------------------------------------------------------- #
def main() -> None:
    t = threading.Thread(target=_run_server, daemon=True)
    t.start()

    if not _wait_ready():
        print("PentraCe sunucusu baslatilamadi.", file=sys.stderr)
        sys.exit(1)

    # Test/headless kanca: pencere acmadan sunucuyu ayakta tut
    if os.environ.get("PENTRACE_HEADLESS") == "1":
        print(f"HEADLESS READY {BASE_URL}", flush=True)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        return

    import webview  # gec import — yalnizca pencere gerektiginde
    webview.create_window(
        "PentraCe",
        BASE_URL,
        width=1320, height=860, min_size=(960, 640),
    )
    webview.start()  # bloklar; pencere kapaninca doner

    if _server is not None:
        _server.should_exit = True


if __name__ == "__main__":
    main()
