// Cienki klient API. Ścieżki względne — w dev proxowane przez Vite, w prod ten sam origin.
const json = async (r) => {
  if (!r.ok) {
    let message = `HTTP ${r.status}`;
    let detail;
    try {
      const body = await r.json();
      detail = body.detail;
      message = (typeof detail === "string" ? detail : detail?.message) || body.message || message;
    } catch {
      // Odpowiedź bez JSON — pozostaw czytelny kod HTTP.
    }
    const error = new Error(message);
    error.status = r.status;
    error.detail = detail;
    throw error;
  }
  return r.json();
};

// Widok konta: "" = cały portfel. Stan modułu, bo dotyczy wszystkich odczytów naraz —
// przełącznik w nagłówku ustawia go przed przeładowaniem danych.
let accountScope = "";
export const setAccountScope = (id) => { accountScope = id || ""; };
const scoped = (url) => (accountScope ? `${url}${url.includes("?") ? "&" : "?"}account=${accountScope}` : url);
const send = (method, url, body) =>
  fetch(url, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).then(json);

export const api = {
  accounts: () => fetch("/api/accounts").then(json),
  saveAccount: (id, body) => (id ? send("PUT", `/api/accounts/${id}`, body) : send("POST", "/api/accounts", body)),
  portfolio: (refresh = false) => fetch(scoped(`/api/portfolio?refresh=${refresh}`)).then(json),
  history: (benchmarkRate = 0.05, cpiSpread = 0) =>
    fetch(scoped(`/api/history?benchmark_rate=${benchmarkRate}&cpi_spread=${cpiSpread}`)).then(json),
  instruments: () => fetch("/api/instruments").then(json),
  searchProviderSymbols: (source, query) => {
    const params = new URLSearchParams({ source, query });
    return fetch(`/api/providers/search?${params}`).then(json);
  },
  updateInstrument: (isin, body) =>
    fetch(`/api/instruments/${isin}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(json),
  saveBrokerInstrumentMappings: (mappings) =>
    fetch("/api/broker-instrument-mappings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mappings }),
    }).then(json),
  importTransactions: (file, accountId) => {
    const fd = new FormData();
    fd.append("file", file);
    if (accountId) fd.append("account_id", accountId);
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
  transactions: () => fetch(scoped("/api/transactions")).then(json),
  addTransaction: (body) =>
    fetch("/api/transactions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(json),
  addBondPurchase: (body) =>
    fetch("/api/bonds", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(json),
  importBondTable: (file) => {
    const fd = new FormData();
    fd.append("file", file);
    return fetch("/api/bonds/tables", { method: "POST", body: fd }).then(json);
  },
  deleteTransaction: (id) => fetch(`/api/transactions/${id}`, { method: "DELETE" }).then(json),
  updateTransaction: (id, body) =>
    fetch(`/api/transactions/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(json),
  instrumentHistory: (isin) => fetch(scoped(`/api/instruments/${isin}/history`)).then(json),
  dailyChanges: () => fetch(scoped("/api/daily-changes")).then(json),
  drawdown: () => fetch(scoped("/api/drawdown")).then(json),
  cash: () => fetch(scoped("/api/cash")).then(json),
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
  allocation: () => fetch(scoped("/api/allocation")).then(json),
  setAllocation: (targets) =>
    fetch("/api/allocation", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ targets }),
    }).then(json),
  contributionPlan: (amountPln) =>
    fetch(scoped("/api/allocation/plan"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ amount_pln: amountPln }),
    }).then(json),
  analytics: () => fetch(scoped("/api/analytics")).then(json),
  report: (fromDate, toDate, benchmarkRate = 0.05, cpiSpread = 0, signal) => {
    const params = new URLSearchParams({
      from_date: fromDate,
      to_date: toDate,
      benchmark_rate: String(benchmarkRate),
      cpi_spread: String(cpiSpread),
    });
    return fetch(scoped(`/api/reports?${params}`), { signal }).then(json);
  },
  reportCsvUrl: (fromDate, toDate, benchmarkRate = 0.05, cpiSpread = 0) => {
    const params = new URLSearchParams({
      from_date: fromDate,
      to_date: toDate,
      benchmark_rate: String(benchmarkRate),
      cpi_spread: String(cpiSpread),
    });
    return scoped(`/api/reports.csv?${params}`);
  },
  dataQuality: () => fetch(scoped("/api/data-quality")).then(json),
};
