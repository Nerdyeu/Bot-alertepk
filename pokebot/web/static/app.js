// Helpers partages : appels API, format, bouton de scan, notifications.

async function api(method, url, body) {
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(url, opts);
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch (e) {}
    throw new Error(detail);
  }
  return res.status === 204 ? null : res.json();
}
const apiGet = (u) => api("GET", u);
const apiPost = (u, b) => api("POST", u, b);
const apiPut = (u, b) => api("PUT", u, b);
const apiDel = (u) => api("DELETE", u);

function money(v, cur = "EUR") {
  if (v === null || v === undefined) return "—";
  return v.toFixed(2) + " " + (cur === "EUR" ? "€" : cur);
}
function pct(v) { return v === null || v === undefined ? "—" : v.toFixed(1) + " %"; }
function fmtDate(s) { return s ? new Date(s).toLocaleString("fr-FR") : "—"; }

function toast(msg, ok = true) {
  let t = document.getElementById("toast");
  if (!t) { t = document.createElement("div"); t.id = "toast"; t.className = "toast"; document.body.appendChild(t); }
  t.textContent = msg;
  t.className = "toast show " + (ok ? "ok" : "err");
  setTimeout(() => { t.className = "toast " + (ok ? "ok" : "err"); }, 2800);
}

// --- Bouton "Scanner maintenant" + statut ---
let scanPoll = null;
async function refreshStatus() {
  try {
    const s = await apiGet("/api/summary");
    const el = document.getElementById("scan-status");
    if (s.scanning) {
      el.textContent = "⏳ scan en cours…";
      if (!scanPoll) scanPoll = setInterval(refreshStatus, 3000);
    } else {
      if (scanPoll) { clearInterval(scanPoll); scanPoll = null; if (window.onScanComplete) window.onScanComplete(); }
      const ls = s.last_scan;
      el.textContent = ls ? `dernier scan : ${fmtDate(ls.finished_at || ls.started_at)} (${ls.status})` : "aucun scan";
    }
  } catch (e) {}
}

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("scan-now");
  if (btn) {
    btn.addEventListener("click", async () => {
      try {
        const r = await apiPost("/api/scan");
        toast(r.status === "started" ? "Scan lance" : "Scan deja en cours");
        setTimeout(refreshStatus, 600);
      } catch (e) { toast("Erreur: " + e.message, false); }
    });
  }
  refreshStatus();
});
