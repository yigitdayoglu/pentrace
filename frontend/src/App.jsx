import { useEffect, useState } from "react";
import { getToken, setToken, fetchMe, fetchConfig, localLogin } from "./api.js";
import Landing from "./Landing.jsx";
import Auth from "./Auth.jsx";
import VerifyGate from "./VerifyGate.jsx";
import Welcome from "./Welcome.jsx";
import Dashboard from "./Dashboard.jsx";
import Admin from "./Admin.jsx";
import UpgradeModal from "./UpgradeModal.jsx";

const WELCOMED_KEY = "pentrace_welcomed";

export default function App() {
  const [user, setUser] = useState(null);
  const [quota, setQuota] = useState(null);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState("dashboard"); // dashboard | admin
  const [showUpgrade, setShowUpgrade] = useState(false);
  const [showAuth, setShowAuth] = useState(false); // landing -> auth gecisi
  const [billing, setBilling] = useState(true);    // plan/kota sistemi acik mi
  const [authEnabled, setAuthEnabled] = useState(true); // login gerekli mi
  const [welcomed, setWelcomed] = useState(!!localStorage.getItem(WELCOMED_KEY));

  async function bootstrap() {
    let cfg = { auth_enabled: true, billing_enabled: true };
    try {
      cfg = await fetchConfig();
      setBilling(cfg.billing_enabled);
      setAuthEnabled(cfg.auth_enabled);
    } catch { /* varsayilan acik */ }

    // Auth kapali (masaustu): login'siz otomatik yerel oturum
    if (cfg.auth_enabled === false && !getToken()) {
      try {
        const res = await localLogin();
        setToken(res.token);
      } catch { /* yine de devam */ }
    }

    if (!getToken()) { setLoading(false); return; }
    try {
      const me = await fetchMe();
      setUser(me.user);
      setQuota(me.quota);
    } catch {
      setToken(null);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { bootstrap(); }, []);

  function dismissWelcome() {
    localStorage.setItem(WELCOMED_KEY, "1");
    setWelcomed(true);
  }

  async function refreshQuota() {
    try { const me = await fetchMe(); setQuota(me.quota); setUser(me.user); } catch { /* */ }
  }

  function onAuth(token, u) {
    setToken(token);
    setUser(u);
    setLoading(true);
    bootstrap();
  }

  function logout() {
    setToken(null); setUser(null); setQuota(null); setView("dashboard"); setShowAuth(false);
  }

  if (loading) {
    return <div className="boot">PentraCe yukleniyor<span className="blink" /></div>;
  }

  // --- Auth KAPALI (masaustu): login yok; ilk acilista welcome, sonra dashboard ---
  if (!authEnabled) {
    if (!welcomed) {
      return <Welcome onStart={dismissWelcome} />;
    }
    // user otomatik yerel oturumla set edildi; degilse boot beklenir
    if (!user) {
      return <div className="boot">PentraCe yukleniyor<span className="blink" /></div>;
    }
    // dashboard'a dus (asagidaki ana render)
  } else {
    // --- Auth ACIK (web/SaaS): landing -> auth -> dogrulama ---
    if (!user) {
      return showAuth
        ? <Auth onAuth={onAuth} onBack={() => setShowAuth(false)} />
        : <Landing onStart={() => setShowAuth(true)} />;
    }
    if (user.is_verified === false) {
      return (
        <VerifyGate
          email={user.email}
          onVerified={(u) => { setUser(u); refreshQuota(); }}
          onLogout={logout}
        />
      );
    }
  }

  const limitLabel = quota?.limit === 0 || quota?.limit == null
    ? "∞"
    : `${quota.used}/${quota.limit}`;

  return (
    <div className="shell">
      <header className="masthead">
        <div>
          <div className="brand">
            <h1>Pentra<span className="accent">Ce</span><span className="blink" /></h1>
          </div>
          <div className="tagline">Recon &amp; Zafiyet Tarama Pipeline'i</div>
        </div>
        <div className="user-area">
          {billing && (
            <div className="quota-chip">
              <span className={`plan-badge ${user.plan}`}>{user.plan.toUpperCase()}</span>
              <span className="quota-num">bugun: {limitLabel}</span>
            </div>
          )}
          {billing && user.plan === "free" && (
            <button className="upgrade-btn" onClick={() => setShowUpgrade(true)}>
              ★ Pro'ya Geç
            </button>
          )}
          {/* Tek gorunum normal kullanicida nav gereksiz; yalnizca admin'de goster */}
          {user.role === "admin" && (
            <nav className="nav">
              <button className={view === "dashboard" ? "active" : ""} onClick={() => setView("dashboard")}>
                Dashboard
              </button>
              <button className={view === "admin" ? "active" : ""} onClick={() => setView("admin")}>
                Admin
              </button>
            </nav>
          )}
          {authEnabled && (
            <div className="whoami">
              <span className="email">{user.email}</span>
              <button className="logout" onClick={logout}>cikis</button>
            </div>
          )}
        </div>
      </header>

      {view === "dashboard" && (
        <Dashboard
          isAdmin={user.role === "admin"}
          onActivity={refreshQuota}
          onQuotaExceeded={billing ? () => setShowUpgrade(true) : undefined}
        />
      )}
      {view === "admin" && user.role === "admin" && <Admin />}

      {billing && showUpgrade && (
        <UpgradeModal
          onClose={() => setShowUpgrade(false)}
          onUpgraded={(u, q) => { setUser(u); setQuota(q); setShowUpgrade(false); }}
        />
      )}
    </div>
  );
}
