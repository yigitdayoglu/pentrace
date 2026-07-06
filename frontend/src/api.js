// Backend API yardimcilari. Tek kullanicili yerel uygulama — kimlik dogrulama yok.

async function handle(r) {
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    const detail = err.detail;
    const msg = typeof detail === "string"
      ? detail
      : Array.isArray(detail)
        ? detail.map((d) => d.msg || JSON.stringify(d)).join("; ")
        : `Hata ${r.status}`;
    const e = new Error(msg);
    e.status = r.status;
    throw e;
  }
  return r.json();
}

export async function listScans() {
  return handle(await fetch("/api/scans"));
}

export async function createScan(target, authorized) {
  return handle(await fetch("/api/scans", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ target, authorized }),
  }));
}

export async function getScan(scanId) {
  return handle(await fetch(`/api/scans/${scanId}`));
}

export function reportUrl(scanId, format) {
  return `/api/scans/${scanId}/report?format=${format}`;
}

// SSE canli log akisi
export function streamScan(scanId, onEvent, onDone) {
  const es = new EventSource(`/api/scans/${scanId}/stream`);
  es.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data);
      onEvent(data);
      if (data.event === "done") { es.close(); onDone && onDone(); }
    } catch { /* keep-alive */ }
  };
  es.onerror = () => { es.close(); onDone && onDone(); };
  return es;
}
