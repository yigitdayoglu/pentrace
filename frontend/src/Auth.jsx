import { useState } from "react";
import { login, register } from "./api.js";

export default function Auth({ onAuth, onBack }) {
  const [mode, setMode] = useState("login"); // login | register
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError(""); setBusy(true);
    try {
      const fn = mode === "login" ? login : register;
      if (mode === "register" && password.length < 8) {
        throw new Error("Sifre en az 8 karakter olmali.");
      }
      const res = await fn(email.trim(), password);
      onAuth(res.token, res.user);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-wrap">
      <div className="auth-card panel">
        <div className="panel-head">
          <h2>
            {onBack && <button className="back-link" onClick={onBack} title="Geri">←</button>}
            {mode === "login" ? "Giris" : "Kayit"}
          </h2>
          <span className="idx">{mode === "login" ? "//" : "++"}</span>
        </div>
        <div className="panel-body">
          <div className="auth-brand">
            Pentra<span className="accent">Ce</span>
            <div className="auth-sub">Recon &amp; Zafiyet Tarama Pipeline'i</div>
          </div>
          <form onSubmit={submit}>
            <label className="field">
              <span>E-posta</span>
              <input type="text" autoComplete="username" placeholder="sen@ornek.com"
                value={email} onChange={(e) => setEmail(e.target.value)} />
            </label>
            <label className="field">
              <span>Sifre {mode === "register" && "(min 8 karakter)"}</span>
              <input type="password" autoComplete={mode === "login" ? "current-password" : "new-password"}
                placeholder="••••••••" value={password} onChange={(e) => setPassword(e.target.value)} />
            </label>
            <button className="run" disabled={busy}>
              {busy ? "..." : mode === "login" ? "▶ Giris Yap" : "+ Hesap Olustur"}
            </button>
            {error && <div className="err">! {error}</div>}
          </form>
          <div className="auth-switch">
            {mode === "login" ? (
              <>Hesabin yok mu? <button onClick={() => { setMode("register"); setError(""); }}>Kayit ol</button></>
            ) : (
              <>Zaten uye misin? <button onClick={() => { setMode("login"); setError(""); }}>Giris yap</button></>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
