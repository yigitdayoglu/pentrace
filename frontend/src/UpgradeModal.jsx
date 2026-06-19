import { useState } from "react";
import { upgradePlan } from "./api.js";

export default function UpgradeModal({ onClose, onUpgraded }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function activate() {
    setError(""); setBusy(true);
    try {
      const res = await upgradePlan();
      onUpgraded(res.user, res.quota);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal panel" onClick={(e) => e.stopPropagation()}>
        <div className="panel-head">
          <h2>PentraCe Pro</h2>
          <button className="modal-x" onClick={onClose}>✕</button>
        </div>
        <div className="panel-body">
          <div className="plan-compare">
            <div className="plan-col">
              <div className="plan-name">FREE</div>
              <ul>
                <li>Gunde 3 tarama</li>
                <li>Recon + zafiyet tarama</li>
                <li>PDF / JSON rapor</li>
              </ul>
            </div>
            <div className="plan-col pro">
              <div className="plan-name pro">PRO ★</div>
              <ul>
                <li><b>Sinirsiz</b> tarama</li>
                <li>Recon + zafiyet tarama</li>
                <li>PDF / JSON rapor</li>
                <li>Oncelikli pipeline</li>
              </ul>
            </div>
          </div>

          <div className="demo-note">
            ⓘ Demo mod: odeme entegrasyonu henuz eklenmedi. Pro'yu test icin
            ucretsiz aninda aktiflestirebilirsin.
          </div>

          <button className="run" onClick={activate} disabled={busy}>
            {busy ? "Aktiflestiriliyor..." : "★ Pro'yu Aktiflestir (Demo)"}
          </button>
          {error && <div className="err">! {error}</div>}
        </div>
      </div>
    </div>
  );
}
