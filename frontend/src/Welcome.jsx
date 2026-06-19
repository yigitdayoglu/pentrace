// Ilk acilis karsilama ekrani (masaustu / login'siz). Bir kez gosterilir.
const FEATURES = [
  ["⌖", "Otomatik Keşif", "Subdomain, port ve teknoloji tespiti tek tıkla."],
  ["⚡", "Zafiyet Tarama", "SQLi, XSS, open redirect, dizin ve daha fazlası."],
  ["▤", "Profesyonel Rapor", "Bulguları PDF / JSON olarak dışa aktar."],
];

export default function Welcome({ onStart }) {
  return (
    <div className="welcome-wrap">
      <div className="welcome-card">
        <div className="welcome-brand">
          Pentra<span className="accent">Ce</span>
          <span className="blink" />
        </div>
        <p className="welcome-tagline">
          Recon &amp; Zafiyet Tarama Pipeline'i — kurulumsuz, sınırsız, tamamen senin makinende.
        </p>

        <div className="welcome-features">
          {FEATURES.map(([icon, title, desc]) => (
            <div className="welcome-feature" key={title}>
              <span className="wf-icon">{icon}</span>
              <div>
                <div className="wf-title">{title}</div>
                <div className="wf-desc">{desc}</div>
              </div>
            </div>
          ))}
        </div>

        <div className="welcome-warn">
          <b>⚠ Yalnızca yetkili hedefler.</b> PentraCe'yi yalnızca sana ait veya açık
          izin verdiğin sistemlerde kullan. Yetkisiz tarama yasalara aykırıdır; tüm
          sorumluluk sana aittir.
        </div>

        <button className="run welcome-start" onClick={onStart}>
          ▶ Kullanmaya Başla
        </button>
      </div>
    </div>
  );
}
