import { useEffect, useRef, useState } from "react";
import { listScans, createScan, getScan, streamScan, reportUrl } from "./api.js";
import ResultsViz from "./ResultsViz.jsx";

const SEV_ORDER = ["critical", "high", "medium", "low", "info"];
const SEV_LABEL = { critical: "KRITIK", high: "YUKSEK", medium: "ORTA", low: "DUSUK", info: "BILGI" };

export default function Dashboard() {
  const [target, setTarget] = useState("");
  const [authorized, setAuthorized] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [logs, setLogs] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [history, setHistory] = useState([]);
  const [consentNudge, setConsentNudge] = useState(false);
  const termRef = useRef(null);

  async function refreshHistory() {
    try { setHistory(await listScans()); } catch { /* yoksay */ }
  }
  useEffect(() => { refreshHistory(); }, []);
  useEffect(() => {
    if (termRef.current) termRef.current.scrollTop = termRef.current.scrollHeight;
  }, [logs]);

  async function loadDetail(id) {
    try { setDetail(await getScan(id)); } catch { /* yoksay */ }
  }

  async function onSubmit(e) {
    e.preventDefault();
    setError(""); setDetail(null); setLogs([]);
    if (!target.trim()) { setError("Bir hedef gir (domain veya IP)."); return; }
    if (!authorized) {
      setError("Devam etmek için aşağıdaki izin kutusunu işaretle.");
      setConsentNudge(true);
      setTimeout(() => setConsentNudge(false), 1200);
      return;
    }

    setRunning(true);
    try {
      const res = await createScan(target.trim(), authorized);
      setActiveId(res.scan_id);
      refreshHistory();
      streamScan(res.scan_id, (ev) => setLogs((p) => [...p, ev]), async () => {
        setRunning(false);
        await loadDetail(res.scan_id);
        refreshHistory();
      });
    } catch (err) {
      setError(err.message);
      setRunning(false);
    }
  }

  function openHistory(id) { setActiveId(id); setLogs([]); loadDetail(id); }

  const findings = detail?.findings || [];
  const assetGroups = {};
  for (const a of detail?.assets || []) (assetGroups[a.type] = assetGroups[a.type] || []).push(a.value);

  return (
    <div className="grid2">
      {/* SOL */}
      <div>
        <section className="panel">
          <div className="panel-head"><h2>Yeni Tarama</h2></div>
          <div className="panel-body">
            <form onSubmit={onSubmit}>
              <label className="field">
                <span>Hedef (domain veya IP)</span>
                <input type="text" placeholder="ornek.com" value={target}
                  onChange={(e) => setTarget(e.target.value)} disabled={running} />
              </label>
              <label className={`consent${consentNudge ? " nudge" : ""}`}>
                <input type="checkbox" checked={authorized}
                  onChange={(e) => setAuthorized(e.target.checked)} disabled={running} />
                <span>Bu hedefi taramak icin yetkim oldugunu onayliyorum. Yetkisiz tarama
                  yasalara aykiridir; tum sorumluluk bana aittir.</span>
              </label>
              <button className="run" disabled={running}>
                {running ? "Taraniyor..." : "▶ Taramayi Baslat"}
              </button>
              {error && <div className="err">! {error}</div>}
            </form>
          </div>
        </section>

        <section className="panel" style={{ marginTop: 24 }}>
          <div className="panel-head">
            <h2>Canli Akis</h2>
            {running && <span className="live-dot" title="Tarama suruyor">CANLI</span>}
          </div>
          <div className="panel-body">
            <div className="terminal" ref={termRef}>
              {logs.length === 0 && <div className="empty">$ tarama loglari burada akacak...</div>}
              {logs.map((l, i) => (
                <div className="row" key={i}>
                  <span className="ts">{l.ts || ""}</span>
                  <span className={`lv ${l.level || "info"}`}>{(l.level || "info").toUpperCase()}</span>
                  <span className={`msg ${String(l.message).startsWith("===") ? "head" : ""}`}>{l.message}</span>
                </div>
              ))}
            </div>
          </div>
        </section>
      </div>

      {/* SAG */}
      <div className="results-col">
        <section className="panel">
          <div className="panel-head">
            <h2>Sonuclar</h2>
            {activeId && <span className="scan-tag">{activeId}</span>}
          </div>
          <div className="panel-body">
            {!detail && (
              <div className="empty-state">
                <div className="empty-mark">⌖</div>
                <p>Sonuçlar burada görünecek.</p>
                <span>Soldan bir hedef girip taramayı başlat, ya da geçmişten bir tarama seç.</span>
              </div>
            )}
            {detail && (
              <>
                <ResultsViz findings={findings} assets={detail.assets || []} />
                {detail.scan?.status === "done" && (
                  <div className="actions">
                    <a href={reportUrl(activeId, "pdf")} target="_blank" rel="noreferrer">↓ PDF Rapor</a>
                    <a href={reportUrl(activeId, "json")} target="_blank" rel="noreferrer">↓ JSON</a>
                  </div>
                )}
                {/* Varliklar + Bulgular birlikte tek kaydirma alaninda — ozet/donut sabit kalir */}
                <div className="results-scroll">
                  {Object.keys(assetGroups).length > 0 && (
                    <div className="assets-block">
                      <p className="section-label">Kesfedilen Varliklar</p>
                      {Object.entries(assetGroups).map(([type, vals]) => (
                        <div className="assetgroup" key={type}>
                          <div className="gtitle">{type} ({vals.length})</div>
                          <div className="chips">{vals.slice(0, 30).map((v, i) => <span className="chip" key={i}>{v}</span>)}</div>
                        </div>
                      ))}
                    </div>
                  )}
                  <div className="findings-block">
                    <p className="section-label">Bulgular ({findings.length})</p>
                    {findings.length === 0 && <div className="empty-state">Zafiyet bulgusu yok.</div>}
                    {findings.map((f, i) => (
                      <div className={`finding ${f.severity}`} key={i}
                           style={{ "--i": Math.min(i, 10) }}>
                        <div className="fhead">
                          <span className={`badge ${f.severity}`}>{SEV_LABEL[f.severity] || f.severity}</span>
                          <span className="ftitle">{f.title}</span>
                        </div>
                        {f.target && <div className="ftarget">{f.target}</div>}
                        {f.detail && <div className="fdetail">{f.detail}</div>}
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}
          </div>
        </section>
      </div>

      {/* Gecmis — tam genislik */}
      <section className="history" style={{ gridColumn: "1 / -1" }}>
        <p className="section-label">Tarama Gecmisi</p>
        {history.length === 0 && <div className="empty-state">Henuz tarama yok.</div>}
        {history.map((h) => (
          <div className="hrow" key={h.id} onClick={() => openHistory(h.id)}>
            <span className="hid">#{h.id}</span>
            <span className="htarget">{h.target}</span>
            <span className={`hstatus ${h.status}`}>{h.status}</span>
          </div>
        ))}
      </section>
    </div>
  );
}
