"""Rapor motoru — tarama sonuclarini PDF ve JSON olarak uretir.

PDF: reportlab ile baslik, ozet tablosu, asset listesi, severity'e gore bulgular.
JSON: makine-okunabilir tam dokum.
"""
from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

import models
from paths import data_dir

REPORT_DIR = data_dir() / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

SEVERITY_COLORS = {
    "critical": colors.HexColor("#7c1d1d"),
    "high": colors.HexColor("#b91c1c"),
    "medium": colors.HexColor("#c2620a"),
    "low": colors.HexColor("#a16207"),
    "info": colors.HexColor("#475569"),
}
SEVERITY_HEX = {
    "critical": "#7c1d1d", "high": "#b91c1c", "medium": "#c2620a",
    "low": "#a16207", "info": "#475569",
}
SEVERITY_LABEL = {
    "critical": "KRITIK", "high": "YUKSEK", "medium": "ORTA",
    "low": "DUSUK", "info": "BILGI",
}


async def _collect(scan_id: str) -> dict:
    scan = await models.get_scan(scan_id)
    if not scan:
        raise ValueError("Tarama bulunamadi")
    return {
        "scan": scan,
        "assets": await models.get_assets(scan_id),
        "findings": await models.get_findings(scan_id),
    }


def _severity_summary(findings: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for f in findings:
        out[f["severity"]] = out.get(f["severity"], 0) + 1
    return out


async def build_json(scan_id: str) -> str:
    data = await _collect(scan_id)
    data["summary"] = _severity_summary(data["findings"])
    path = REPORT_DIR / f"pentrace_{scan_id}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)


async def build_pdf(scan_id: str) -> str:
    data = await _collect(scan_id)
    scan, assets, findings = data["scan"], data["assets"], data["findings"]
    summary = _severity_summary(findings)

    path = REPORT_DIR / f"pentrace_{scan_id}.pdf"
    doc = SimpleDocTemplate(
        str(path), pagesize=A4,
        topMargin=2 * cm, bottomMargin=2 * cm, leftMargin=2 * cm, rightMargin=2 * cm,
        title=f"PentraCe Raporu {scan_id}",
    )
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], textColor=colors.HexColor("#0f172a"))
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], textColor=colors.HexColor("#1e293b"),
                        spaceBefore=16)
    body = ParagraphStyle("body", parent=styles["BodyText"], alignment=TA_LEFT, fontSize=9)
    small = ParagraphStyle("small", parent=styles["BodyText"], fontSize=8,
                           textColor=colors.HexColor("#64748b"))

    elems = []
    elems.append(Paragraph("PentraCe — Guvenlik Tarama Raporu", h1))
    elems.append(Paragraph(
        f"Hedef: <b>{scan['target']}</b> &nbsp;|&nbsp; Tarama ID: {scan_id} &nbsp;|&nbsp; "
        f"Durum: {scan['status']}", small))
    elems.append(Paragraph(f"Olusturulma: {scan['created_at']}", small))
    elems.append(Spacer(1, 0.4 * cm))

    # --- Ozet tablosu ---
    elems.append(Paragraph("Bulgu Ozeti", h2))
    sev_rows = [["Severity", "Adet"]]
    for sev in ("critical", "high", "medium", "low", "info"):
        sev_rows.append([SEVERITY_LABEL[sev], str(summary.get(sev, 0))])
    sev_table = Table(sev_rows, colWidths=[6 * cm, 3 * cm])
    sev_style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
    ]
    for i, sev in enumerate(("critical", "high", "medium", "low", "info"), start=1):
        sev_style.append(("TEXTCOLOR", (0, i), (0, i), SEVERITY_COLORS[sev]))
    sev_table.setStyle(TableStyle(sev_style))
    elems.append(sev_table)

    # --- Kesfedilen varliklar ---
    elems.append(Paragraph("Kesfedilen Varliklar", h2))
    if assets:
        by_type: dict[str, list[str]] = {}
        for a in assets:
            by_type.setdefault(a["type"], []).append(a["value"])
        for t, vals in by_type.items():
            elems.append(Paragraph(f"<b>{t}</b> ({len(vals)})", body))
            elems.append(Paragraph(", ".join(vals[:40]), small))
            elems.append(Spacer(1, 0.15 * cm))
    else:
        elems.append(Paragraph("Varlik bulunamadi.", small))

    # --- Bulgular ---
    elems.append(Paragraph("Bulgular", h2))
    if not findings:
        elems.append(Paragraph("Zafiyet bulgusu yok.", small))
    for f in findings:
        sev = f["severity"]
        badge = SEVERITY_LABEL.get(sev, sev.upper())
        elems.append(Paragraph(
            f'<font color="{SEVERITY_HEX.get(sev, "#475569")}">[{badge}]</font> '
            f'<b>{f["title"]}</b>', body))
        if f.get("target"):
            elems.append(Paragraph(f"Hedef: {f['target']}", small))
        if f.get("detail"):
            elems.append(Paragraph(f["detail"], small))
        elems.append(Spacer(1, 0.25 * cm))

    elems.append(Spacer(1, 0.6 * cm))
    elems.append(Paragraph(
        "Bu rapor PentraCe tarafindan otomatik uretilmistir. Yalnizca yetkili guvenlik "
        "testleri icin kullanilmalidir.", small))

    doc.build(elems)
    return str(path)
