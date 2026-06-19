import { useState } from "react";
import { verifyEmail, resendCode } from "./api.js";

export default function VerifyGate({ email, onVerified, onLogout }) {
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [busy, setBusy] = useState(false);
  const [cooldown, setCooldown] = useState(0);

  async function submit(e) {
    e.preventDefault();
    setError(""); setInfo(""); setBusy(true);
    try {
      const res = await verifyEmail(code.trim());
      onVerified(res.user);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function resend() {
    setError(""); setInfo("");
    try {
      await resendCode();
      setInfo("Yeni kod gonderildi. (Dev-mod: backend konsoluna / dev_mails.log'a yazildi)");
      // basit 60sn cooldown gostergesi
      setCooldown(60);
      const id = setInterval(() => {
        setCooldown((c) => {
          if (c <= 1) { clearInterval(id); return 0; }
          return c - 1;
        });
      }, 1000);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="auth-wrap">
      <div className="auth-card panel">
        <div className="panel-head">
          <h2>E-posta Dogrulama</h2>
          <span className="idx">✓</span>
        </div>
        <div className="panel-body">
          <div className="auth-brand">
            Pentra<span className="accent">Ce</span>
            <div className="auth-sub">Hesabinizi dogrulayin</div>
          </div>
          <p className="verify-note">
            <b>{email}</b> adresine 6 haneli bir dogrulama kodu gonderildi.
            Kodu girerek hesabinizi aktiflestirin.
          </p>
          <form onSubmit={submit}>
            <label className="field">
              <span>Dogrulama Kodu</span>
              <input
                type="text"
                inputMode="numeric"
                maxLength={6}
                placeholder="______"
                className="code-input"
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
              />
            </label>
            <button className="run" disabled={busy || code.length !== 6}>
              {busy ? "..." : "✓ Dogrula"}
            </button>
            {error && <div className="err">! {error}</div>}
            {info && <div className="info-msg">{info}</div>}
          </form>
          <div className="auth-switch">
            <button onClick={resend} disabled={cooldown > 0}>
              {cooldown > 0 ? `Tekrar gonder (${cooldown}s)` : "Kodu tekrar gonder"}
            </button>
            <span style={{ margin: "0 8px", color: "var(--fg-faint)" }}>·</span>
            <button onClick={onLogout}>Cikis</button>
          </div>
        </div>
      </div>
    </div>
  );
}
