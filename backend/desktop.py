"""PentraCe — masaustu surumu (self-contained, tek kullanicili).

FastAPI backend'i arka plan thread'de calistirir, native bir pencerede (PyWebView /
Windows'ta WebView2) acar. Her sey yereldir: SQLite DB + raporlar %APPDATA%/PentraCe
altinda. Kimlik dogrulama / uyelik yok.

Calistirma (gelistirme):  python desktop.py
Paketleme:                PyInstaller (bkz. build-desktop.ps1)
"""
from __future__ import annotations

import os
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
    override = os.environ.get("PENTRACE_DATA_DIR")
    if override:
        d = Path(override)
    else:
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        d = Path(base) / "PentraCe"
    d.mkdir(parents=True, exist_ok=True)
    return d


DATA = _data_dir()
os.environ["PENTRACE_DATA_DIR"] = str(DATA)
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{(DATA / 'pentrace.db').as_posix()}")

# KRITIK: --windowed (penceresiz) paketlenmis .exe cift tiklanarak acildiginda
# sys.stdout/sys.stderr None olur. uvicorn'un loglamasi None akisa yazmaya
# calisinca sunucu thread'i sessizce coker ve pencere hic acilmaz. Bunu onlemek
# icin None olan akislari gercek bir dosyaya yonlendir.
if sys.stdout is None or sys.stderr is None:
    try:
        _rt = open(DATA / "runtime.log", "a", encoding="utf-8", buffering=1)
    except Exception:
        _rt = open(os.devnull, "w")
    if sys.stdout is None:
        sys.stdout = _rt
    if sys.stderr is None:
        sys.stderr = _rt


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
# 3. Loglama — paketlenmis (.exe) surumde stdout/stderr yok; her sey dosyaya.
#    NOT: logging modulu KULLANILMAZ; uvicorn onu yeniden yapilandirip handler'i
#    eziyor. Dogrudan dosyaya yaz + aninda flush.
# --------------------------------------------------------------------------- #
LOG_FILE = DATA / "startup.log"
try:
    LOG_FILE.write_text("", encoding="utf-8")
except Exception:
    pass


class _Log:
    def info(self, msg, *args):
        try:
            line = (msg % args) if args else msg
        except Exception:
            line = f"{msg} {args}"
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as fh:
                fh.write(f"{time.strftime('%H:%M:%S')} {line}\n")
                fh.flush()
        except Exception:
            pass

    error = info

    def exception(self, msg, *args):
        import traceback
        self.info((msg % args) if args else msg)
        self.info(traceback.format_exc())


log = _Log()


# --------------------------------------------------------------------------- #
# 4. Ana akis
# --------------------------------------------------------------------------- #
def main() -> None:
    log.info("PentraCe baslatiliyor. data=%s port=%s frozen=%s", DATA, PORT, getattr(sys, "frozen", False))

    t = threading.Thread(target=_run_server, daemon=True)
    t.start()

    if not _wait_ready():
        log.error("Sunucu 25sn icinde hazir olmadi — cikiliyor.")
        sys.exit(1)
    log.info("Sunucu hazir: %s", BASE_URL)

    if os.environ.get("PENTRACE_HEADLESS") == "1":
        print(f"HEADLESS READY {BASE_URL}", flush=True)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        return

    # WebView2'nin kullanici-veri klasorunu ACIKCA yazilabilir bir yere sabitle.
    # Paketlenmis .exe onefile'da varsayilan gecici dizin sorun cikarabiliyor; bu
    # sabitleme pencerenin acilip hemen kapanmasi hatasini onler.
    storage = DATA / "webview"
    storage.mkdir(parents=True, exist_ok=True)

    try:
        import webview
        log.info("pywebview import edildi, pencere olusturuluyor...")
        webview.create_window("PentraCe", BASE_URL, width=1320, height=860, min_size=(960, 640))
        log.info("webview.start() cagriliyor (storage=%s)", storage)
        webview.start(storage_path=str(storage))
        log.info("webview.start() dondu — pencere kapandi, cikiliyor.")
    except Exception:
        log.exception("WEBVIEW HATASI — pencere acilamadi:")
        raise
    finally:
        if _server is not None:
            _server.should_exit = True

    # Onefile'da arka plan thread'leri surecin kapanmasini geciktirebilir; garanti cikis.
    os._exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        log.exception("BASLATMA HATASI:")
        raise
