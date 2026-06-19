const FEATURES = [
  { k: "01", t: "Recon", d: "Subdomain keşfi (crt.sh + wordlist), asyncio port tarama, HTTP teknoloji parmak izi." },
  { k: "02", t: "Zafiyet Tarama", d: "SQLi, XSS, open redirect, dizin bruteforce, SSRF ve güvenlik başlığı kontrolleri." },
  { k: "03", t: "Canlı Akış", d: "Pipeline çalışırken SSE ile anlık log akışı; her adımı gerçek zamanlı izle." },
  { k: "04", t: "Raporlama", d: "Severity skorlu bulgular, tek tıkla PDF ve JSON rapor çıktısı." },
];

const PIPELINE = ["Hedef", "Recon", "Zafiyet", "Rapor"];

export default function Landing({ onStart }) {
  return (
    <div className="landing">
      {/* Arka plan dekoratif ızgara + parıltı CSS'te */}
      <header className="landing-nav">
        <div className="brand">
          <h1>Pentra<span className="accent">Ce</span><span className="blink" /></h1>
        </div>
        <button className="landing-login" onClick={onStart}>Giriş / Kayıt</button>
      </header>

      <section className="hero">
        <div className="hero-badge">OFFENSIVE SECURITY PIPELINE</div>
        <h2 className="hero-title">
          Hedef gir,<br />
          <span className="accent">recon</span> &amp; <span className="accent">zafiyet taraması</span><br />
          otomatik olsun.
        </h2>
        <p className="hero-sub">
          PentraCe; bir domain veya IP'yi uçtan uca tarayan, sonuçları canlı bir
          panoda gösteren ve profesyonel rapor üreten modern bir güvenlik aracıdır.
        </p>
        <div className="hero-cta">
          <button className="run hero-start" onClick={onStart}>▶ Hemen Başla</button>
          <span className="hero-note">Ücretsiz hesap · 3 tarama/gün</span>
        </div>

        {/* Pipeline gorseli */}
        <div className="pipeline-viz">
          {PIPELINE.map((step, i) => (
            <div className="pipe-step-wrap" key={step}>
              <div className="pipe-step" style={{ animationDelay: `${0.15 * i}s` }}>
                <span className="pipe-idx">{String(i + 1).padStart(2, "0")}</span>
                <span className="pipe-name">{step}</span>
              </div>
              {i < PIPELINE.length - 1 && <span className="pipe-arrow">→</span>}
            </div>
          ))}
        </div>
      </section>

      <section className="features">
        {FEATURES.map((f, i) => (
          <div className="feature-card" key={f.k} style={{ animationDelay: `${0.08 * i}s` }}>
            <div className="feature-idx">{f.k}</div>
            <h3>{f.t}</h3>
            <p>{f.d}</p>
          </div>
        ))}
      </section>

      <section className="landing-foot">
        <div className="foot-cta">
          <h3>Kendi altyapını denetlemeye hazır mısın?</h3>
          <button className="run hero-start" onClick={onStart}>▶ Ücretsiz Başla</button>
        </div>
        <div className="ethics-line">
          ⚠ Yalnızca yetkili olduğun sistemlerde kullan. Yetkisiz tarama yasalara aykırıdır.
        </div>
      </section>
    </div>
  );
}
