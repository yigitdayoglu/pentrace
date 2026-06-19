// Backend API yardimcilari. Vite dev proxy /api -> 127.0.0.1:8000
// Token localStorage'da tutulur; tum istekler Authorization header'i gonderir.

const TOKEN_KEY = "pentrace_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(t) {
  if (t) localStorage.setItem(TOKEN_KEY, t);
  else localStorage.removeItem(TOKEN_KEY);
}

function authHeaders(extra = {}) {
  const t = getToken();
  return t ? { ...extra, Authorization: `Bearer ${t}` } : extra;
}

function detailToMessage(detail, status) {
  if (!detail) return `Hata ${status}`;
  if (typeof detail === "string") return detail;
  // pydantic 422: detail = [{loc, msg, ...}, ...]
  if (Array.isArray(detail)) {
    return detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
  }
  return JSON.stringify(detail);
}

async function handle(r) {
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    const e = new Error(detailToMessage(err.detail, r.status));
    e.status = r.status;
    throw e;
  }
  return r.json();
}

// ---- Public config (auth oncesi) ----
export async function fetchConfig() {
  try {
    return await handle(await fetch("/api/config"));
  } catch {
    return { billing_enabled: true, require_email_verification: true };
  }
}

// ---- Auth ----
export async function register(email, password) {
  return handle(await fetch("/api/auth/register", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  }));
}

export async function login(email, password) {
  // OAuth2 form: username = email
  const body = new URLSearchParams({ username: email, password });
  return handle(await fetch("/api/auth/login", {
    method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  }));
}

export async function fetchMe() {
  return handle(await fetch("/api/auth/me", { headers: authHeaders() }));
}

// Login'siz yerel oturum (masaustu / auth kapali)
export async function localLogin() {
  return handle(await fetch("/api/auth/local", { method: "POST" }));
}

export async function verifyEmail(code) {
  return handle(await fetch("/api/auth/verify", {
    method: "POST", headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ code }),
  }));
}

export async function resendCode() {
  return handle(await fetch("/api/auth/resend", {
    method: "POST", headers: authHeaders(),
  }));
}

// ---- Billing ----
export async function upgradePlan() {
  return handle(await fetch("/api/billing/upgrade", {
    method: "POST", headers: authHeaders(),
  }));
}
export async function downgradePlan() {
  return handle(await fetch("/api/billing/downgrade", {
    method: "POST", headers: authHeaders(),
  }));
}

// ---- Taramalar ----
export async function listScans() {
  return handle(await fetch("/api/scans", { headers: authHeaders() }));
}

export async function createScan(target, authorized) {
  return handle(await fetch("/api/scans", {
    method: "POST", headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ target, authorized }),
  }));
}

export async function getScan(scanId) {
  return handle(await fetch(`/api/scans/${scanId}`, { headers: authHeaders() }));
}

export function reportUrl(scanId, format) {
  return `/api/scans/${scanId}/report?format=${format}&token=${encodeURIComponent(getToken() || "")}`;
}

// SSE — EventSource header gonderemez; token query-param ile.
export function streamScan(scanId, onEvent, onDone) {
  const url = `/api/scans/${scanId}/stream?token=${encodeURIComponent(getToken() || "")}`;
  const es = new EventSource(url);
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

// ---- Admin ----
export async function adminListUsers() {
  return handle(await fetch("/api/admin/users", { headers: authHeaders() }));
}
export async function adminPatchUser(userId, patch) {
  return handle(await fetch(`/api/admin/users/${userId}`, {
    method: "PATCH", headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(patch),
  }));
}
