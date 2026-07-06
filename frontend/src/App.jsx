import { useState } from "react";
import Welcome from "./Welcome.jsx";
import Dashboard from "./Dashboard.jsx";

const WELCOMED_KEY = "pentrace_welcomed";

export default function App() {
  const [welcomed, setWelcomed] = useState(!!localStorage.getItem(WELCOMED_KEY));

  function dismissWelcome() {
    localStorage.setItem(WELCOMED_KEY, "1");
    setWelcomed(true);
  }

  if (!welcomed) {
    return <Welcome onStart={dismissWelcome} />;
  }

  return (
    <div className="shell">
      <header className="masthead">
        <div className="brand">
          <h1>Pentra<span className="accent">Ce</span><span className="blink" /></h1>
          <div className="tagline">Recon &amp; Zafiyet Tarama</div>
        </div>
      </header>
      <Dashboard />
    </div>
  );
}
