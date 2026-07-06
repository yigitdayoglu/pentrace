"""Harici tool binary yoneticisi.

Cozum sirasi:
  1. PATH'te var mi (kullanici kendi kurmus)         -> shutil.which
  2. %APPDATA%/PentraCe/bin altinda var mi            -> onceki indirmeden
  3. tools_auto_download aciksa resmi release'den indir + SHA256 dogrula

Indirilen binary'ler kalicidir; bir kez indirilir, sonraki taramalarda hazir.
Tum indirmeler HTTPS (github releases) ve release'in kendi checksums.txt'siyle
dogrulanir. Indirme kapaliysa ya da basarisizsa None doner; cagiran taraf yerlesik
kontrole gecer.
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import os
import platform
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Awaitable, Callable

import httpx

from paths import data_dir

LogFn = Callable[[str, str], Awaitable[None]]


async def _noop_log(level: str, message: str) -> None:  # pragma: no cover
    return None


# --------------------------------------------------------------------------- #
# Tool kayitlari — surum sabitlenmis; asset adlari ProjectDiscovery release
# konvansiyonuna gore. Guncelleme: sadece "version" degistir.
# --------------------------------------------------------------------------- #
TOOLS: dict[str, dict] = {
    "subfinder": {"repo": "projectdiscovery/subfinder", "version": "2.6.6"},
    "naabu":     {"repo": "projectdiscovery/naabu",     "version": "2.3.1"},
    "nuclei":    {"repo": "projectdiscovery/nuclei",    "version": "3.3.7"},
}

_DOWNLOAD_LOCK = asyncio.Lock()
_resolved: dict[str, Path | None] = {}


def bin_dir() -> Path:
    d = data_dir() / "bin"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _exe_name(name: str) -> str:
    return f"{name}.exe" if sys.platform == "win32" else name


def _platform_asset(name: str, version: str) -> str:
    """ProjectDiscovery release asset adi: {name}_{ver}_{os}_{arch}.zip"""
    if sys.platform == "win32":
        osname = "windows"
    elif sys.platform == "darwin":
        osname = "macOS"
    else:
        osname = "linux"
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        arch = "amd64"
    elif machine in ("arm64", "aarch64"):
        arch = "arm64"
    else:
        arch = "amd64"
    return f"{name}_{version}_{osname}_{arch}.zip"


def find_tool(name: str) -> Path | None:
    """Indirmeden, sadece mevcut binary'yi bul (PATH veya bin_dir)."""
    on_path = shutil.which(name)
    if on_path:
        return Path(on_path)
    local = bin_dir() / _exe_name(name)
    if local.exists():
        return local
    return None


def _subprocess_flags() -> int:
    """Windowed .exe'de konsol penceresi acilmasin."""
    if sys.platform == "win32":
        return getattr(__import__("subprocess"), "CREATE_NO_WINDOW", 0)
    return 0


async def _download_and_verify(name: str, meta: dict, log: LogFn) -> Path | None:
    version = meta["version"]
    repo = meta["repo"]
    asset = _platform_asset(name, version)
    base = f"https://github.com/{repo}/releases/download/v{version}"
    zip_url = f"{base}/{asset}"
    sums_url = f"{base}/{name}_{version}_checksums.txt"

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=120) as client:
            await log("info", f"{name} indiriliyor ({version})...")
            zr = await client.get(zip_url)
            if zr.status_code != 200:
                await log("warn", f"{name} indirilemedi (HTTP {zr.status_code}) — yerlesik kontrole donuluyor")
                return None
            blob = zr.content

            # SHA256 dogrulama (release'in checksums.txt'si ile)
            sr = await client.get(sums_url)
            if sr.status_code == 200:
                want = None
                for line in sr.text.splitlines():
                    parts = line.split()
                    if len(parts) == 2 and parts[1].strip() == asset:
                        want = parts[0].strip().lower()
                        break
                got = hashlib.sha256(blob).hexdigest().lower()
                if want and got != want:
                    await log("error", f"{name} SHA256 uyusmadi — indirme reddedildi")
                    return None
            else:
                await log("warn", f"{name} checksums bulunamadi, dogrulama atlandi")
    except Exception as e:
        await log("warn", f"{name} indirme hatasi: {e}")
        return None

    # zip'ten binary'yi cikar
    try:
        exe = _exe_name(name)
        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            member = next((m for m in zf.namelist() if m.endswith(exe) or m.endswith(name)), None)
            if member is None:
                await log("error", f"{name} arsivinde binary bulunamadi")
                return None
            dest = bin_dir() / exe
            with zf.open(member) as src, open(dest, "wb") as out:
                shutil.copyfileobj(src, out)
        if sys.platform != "win32":
            dest.chmod(0o755)
        await log("info", f"{name} hazir -> {dest}")
        return dest
    except Exception as e:
        await log("error", f"{name} cikartma hatasi: {e}")
        return None


async def ensure_tool(name: str, log: LogFn = _noop_log, allow_download: bool = True) -> Path | None:
    """Tool binary'sini dondur; gerekirse (ve izinliyse) indir. Yoksa None."""
    if name in _resolved:
        return _resolved[name]
    found = find_tool(name)
    if found:
        _resolved[name] = found
        return found
    if not allow_download or name not in TOOLS:
        _resolved[name] = None
        return None
    async with _DOWNLOAD_LOCK:
        # kilit beklerken baskasi indirmis olabilir
        found = find_tool(name)
        if found:
            _resolved[name] = found
            return found
        path = await _download_and_verify(name, TOOLS[name], log)
        _resolved[name] = path
        return path


async def _drain(stream, sink: list[str]) -> None:
    """Bir akisi satir satir oku (streaming; buffer dolup kilitlenmesin)."""
    if stream is None:
        return
    while True:
        line = await stream.readline()
        if not line:
            break
        sink.append(line.decode("utf-8", "replace"))


async def run_tool(
    path: Path, args: list[str], log: LogFn = _noop_log,
    timeout: float = 300.0, stdin_data: str | None = None,
) -> str | None:
    """Tool'u calistir, stdout'u string dondur.

    STREAMING: cikti satir satir okunur. Timeout'ta surec oldurulur ama O ANA
    KADAR toplanan cikti KORUNUR (nuclei gibi akan tool'lar icin kritik — zaman
    siniri icinde bulunan bulgular kaybolmaz). Calistirma hatasinda None doner.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            str(path), *args,
            stdin=asyncio.subprocess.PIPE if stdin_data is not None else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            creationflags=_subprocess_flags(),
        )
    except Exception as e:
        await log("warn", f"{path.name} calistirilamadi: {e}")
        return None

    out_lines: list[str] = []
    err_lines: list[str] = []
    if stdin_data is not None and proc.stdin is not None:
        try:
            proc.stdin.write(stdin_data.encode("utf-8", "replace"))
            await proc.stdin.drain()
            proc.stdin.close()
        except Exception:
            pass

    readers = asyncio.gather(_drain(proc.stdout, out_lines), _drain(proc.stderr, err_lines))
    try:
        await asyncio.wait_for(readers, timeout=timeout)
        rc = await proc.wait()
    except asyncio.TimeoutError:
        # wait_for zaten readers'i iptal etti; surec oldur, kismi ciktiyi koru
        try:
            proc.kill()
        except Exception:
            pass
        try:
            await readers
        except (asyncio.CancelledError, Exception):
            pass
        await log("warn", f"{path.name} zaman asimina ugradi ({timeout:.0f}s) — o ana kadarki sonuclar kullaniliyor")
        return "".join(out_lines)  # kismi cikti korunur

    if rc not in (0, None) and not out_lines:
        tail = [l for l in "".join(err_lines).strip().splitlines() if l.strip()]
        await log("warn", f"{path.name} hata dondu: {(tail[-1] if tail else 'bilinmeyen')}")
        return None
    return "".join(out_lines)
