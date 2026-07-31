// Cienki klient API. Ścieżki względne — w dev proxowane przez Vite, w prod ten sam origin.
const json = async (r) => {
  if (!r.ok) {
    let message = `HTTP ${r.status}`;
    try {
      const body = await r.json();
      message = body.detail || body.message || message;
    } catch {
      // Odpowiedź bez JSON — pozostaw czytelny kod HTTP.
    }
    throw new Error(message);
  }
  return r.json();
};

export const api = {
  portfolio: (refresh = false) => fetch(`/api/portfolio?refresh=${refresh}`).then(json),
  history: (benchmarkRate = 0.05, cpiSpread = 0) =>
    fetch(`/api/history?benchmark_rate=${benchmarkRate}&cpi_spread=${cpiSpread}`).then(json),
  instruments: () => fetch("/api/instruments").then(json),
  updateInstrument: (isin, body) =>
    fetch(`/api/instruments/${isin}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(json),
  importCsv: (file) => {
    const fd = new FormData();
    fd.append("file", file);
    return fetch("/api/import", { method: "POST", body: fd }).then(json);
  },
  importPrices: (isin, file, currency) => {
    const fd = new FormData();
    fd.append("isin", isin);
    fd.append("file", file);
    if (currency) fd.append("currency", currency);
    return fetch("/api/prices/import", { method: "POST", body: fd }).then(json);
  },
  refresh: () => fetch("/api/refresh", { method: "POST" }).then(json),
  backfill: () => fetch("/api/backfill", { method: "POST" }).then(json),
  refreshCpi: () => fetch("/api/cpi/refresh", { method: "POST" }).then(json),
  transactions: () => fetch("/api/transactions").then(json),
  addTransaction: (body) =>
    fetch("/api/transactions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(json),
  deleteTransaction: (id) => fetch(`/api/transactions/${id}`, { method: "DELETE" }).then(json),
  updateTransaction: (id, body) =>
    fetch(`/api/transactions/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(json),
  instrumentHistory: (isin) => fetch(`/api/instruments/${isin}/history`).then(json),
  dailyChanges: () => fetch("/api/daily-changes").then(json),
  drawdown: () => fetch("/api/drawdown").then(json),
  cash: () => fetch("/api/cash").then(json),
  addCash: (body) =>
    fetch("/api/cash", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(json),
  deleteCash: (id) => fetch(`/api/cash/${id}`, { method: "DELETE" }).then(json),
  backupNow: () => fetch("/api/backup-now", { method: "POST" }).then(json),
  backups: () => fetch("/api/backups").then(json),
  restoreBackup: (filename) =>
    fetch(`/api/backups/${encodeURIComponent(filename)}/restore`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirmation: "PRZYWRÓĆ" }),
    }).then(json),
  restoreUploadedBackup: (file) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("confirmation", "PRZYWRÓĆ");
    return fetch("/api/backups/restore-upload", { method: "POST", body: fd }).then(json);
  },
  allocation: () => fetch("/api/allocation").then(json),
  setAllocation: (targets) =>
    fetch("/api/allocation", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ targets }),
    }).then(json),
  contributionPlan: (amountPln) =>
    fetch("/api/allocation/plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ amount_pln: amountPln }),
    }).then(json),
  analytics: () => fetch("/api/analytics").then(json),
  dataQuality: () => fetch("/api/data-quality").then(json),
};
