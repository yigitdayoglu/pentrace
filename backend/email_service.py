"""Mail gonderim servisi.

SMTP yapilandirilmamissa (settings.smtp_host bos) DEV-MOD calisir: dogrulama
kodu konsola yazdirilir ve `dev_mails.log` dosyasina eklenir. SMTP env'leri
verildiginde otomatik olarak gercek mail gonderimine gecer — kod degisikligi
gerekmez.
"""
from __future__ import annotations

import smtplib
from email.message import EmailMessage
from pathlib import Path

from config import settings

DEV_MAIL_LOG = Path(__file__).parent / "dev_mails.log"


def _verification_body(code: str) -> tuple[str, str]:
    subject = "PentraCe — Hesap Dogrulama Kodu"
    body = (
        f"PentraCe hesabinizi dogrulamak icin kod:\n\n    {code}\n\n"
        f"Bu kod {settings.verification_code_ttl_minutes} dakika gecerlidir.\n"
        f"Bu istegi siz yapmadiysaniz bu maili yok sayin."
    )
    return subject, body


def send_verification_email(to_email: str, code: str) -> None:
    subject, body = _verification_body(code)

    if not settings.smtp_host:
        # DEV-MOD
        line = f"[DEV-MAIL] -> {to_email} | dogrulama kodu: {code}"
        print(line, flush=True)
        try:
            with open(DEV_MAIL_LOG, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass
        return

    # GERCEK SMTP
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
    msg.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
        if settings.smtp_starttls:
            server.starttls()
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)
