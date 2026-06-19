// Sonuc gorsellestirme: severity donut + ozet istatistikler. Bagimsiz SVG, kutuphane yok.

const SEV_ORDER = ["critical", "high", "medium", "low", "info"];
const SEV_LABEL = { critical: "Kritik", high: "Yüksek", medium: "Orta", low: "Düşük", info: "Bilgi" };
const SEV_COLOR = {
  critical: "var(--crit)", high: "var(--high)", medium: "var(--med)",
  low: "var(--low)", info: "var(--info)",
};

// Donut icin yay segmentleri uret
function donutSegments(counts, total, radius, stroke) {
  const C = 2 * Math.PI * radius;
  let offset = 0;
  const segs = [];
  for (const s of SEV_ORDER) {
    const val = counts[s] || 0;
    if (val === 0) continue;
    const frac = val / total;
    const len = frac * C;
    segs.push({ sev: s, dash: len, gap: C - len, offset, val });
    offset -= len;
  }
  return { segs, C };
}

export default function ResultsViz({ findings, assets }) {
  const counts = SEV_ORDER.reduce((a, s) => {
    a[s] = findings.filter((f) => f.severity === s).length;
    return a;
  }, {});
  const total = findings.length;

  // Varlik istatistikleri
  const byType = {};
  for (const a of assets) byType[a.type] = (byType[a.type] || 0) + 1;
  const stats = [
    { label: "Subdomain", value: byType.subdomain || 0 },
    { label: "Açık Port", value: byType.port || 0 },
    { label: "Web Hedefi", value: byType.tech || 0 },
    { label: "Toplam Bulgu", value: total },
  ];

  const R = 52, STROKE = 14, SIZE = 140;
  const { segs, C } = donutSegments(counts, total || 1, R, STROKE);

  // En yuksek severity (risk seviyesi etiketi)
  const topSev = SEV_ORDER.find((s) => counts[s] > 0) || "info";
  const riskLabel = total === 0 ? "TEMİZ" : SEV_LABEL[topSev].toUpperCase();

  return (
    <div className="viz">
      <div className="viz-donut">
        <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="donut-svg" role="img"
             aria-label="Severity dağılımı">
          {/* arka halka */}
          <circle cx={SIZE / 2} cy={SIZE / 2} r={R} fill="none"
                  stroke="var(--line)" strokeWidth={STROKE} />
          {/* segmentler */}
          {total > 0 && segs.map((seg, i) => (
            <circle key={seg.sev}
              cx={SIZE / 2} cy={SIZE / 2} r={R} fill="none"
              stroke={SEV_COLOR[seg.sev]} strokeWidth={STROKE}
              strokeDasharray={`${seg.dash} ${seg.gap}`}
              strokeDashoffset={seg.offset}
              transform={`rotate(-90 ${SIZE / 2} ${SIZE / 2})`}
              className="donut-seg" style={{ animationDelay: `${0.12 * i}s` }} />
          ))}
          <text x="50%" y="46%" className="donut-total" textAnchor="middle">{total}</text>
          <text x="50%" y="60%" className="donut-cap" textAnchor="middle">bulgu</text>
        </svg>
      </div>

      <div className="viz-right">
        <div className={`risk-pill ${topSev}`}>
          <span className="risk-dot" />
          EN YÜKSEK RİSK: <b>{riskLabel}</b>
        </div>

        <div className="viz-legend">
          {SEV_ORDER.map((s) => (
            <div className={`legend-row ${counts[s] === 0 ? "muted" : ""}`} key={s}>
              <span className="legend-dot" style={{ background: SEV_COLOR[s] }} />
              <span className="legend-label">{SEV_LABEL[s]}</span>
              <span className="legend-bar-track">
                <span className="legend-bar-fill"
                  style={{ width: `${total ? (counts[s] / total) * 100 : 0}%`, background: SEV_COLOR[s] }} />
              </span>
              <span className="legend-val">{counts[s]}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="viz-stats">
        {stats.map((st) => (
          <div className="stat-cell" key={st.label}>
            <div className="stat-value">{st.value}</div>
            <div className="stat-label">{st.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
