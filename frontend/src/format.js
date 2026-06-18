// Wspólne helpery formatujące (PLN, procenty, klasa koloru zysk/strata, data).
const plnFmt = new Intl.NumberFormat("pl-PL", { style: "currency", currency: "PLN" });

export const fmtPln = (v) => (v == null ? "—" : plnFmt.format(v));
export const fmtPct = (v) => (v == null ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(2)}%`);
export const cls = (v) => (v == null ? "muted" : v >= 0 ? "pos" : "neg");
export const fmtDate = (ts) => (ts ? ts.slice(0, 16).replace("T", " ") : "—");
