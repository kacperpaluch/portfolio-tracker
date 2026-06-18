// Wspólne helpery formatujące (PLN, procenty, klasa koloru zysk/strata, data).
const plnFmt = new Intl.NumberFormat("pl-PL", { style: "currency", currency: "PLN" });

export const fmtPln = (v) => (v == null ? "—" : plnFmt.format(v));
export const fmtPct = (v) => (v == null ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(2)}%`);
export const cls = (v) => (v == null ? "muted" : v >= 0 ? "pos" : "neg");
export const fmtDate = (ts) => (ts ? ts.slice(0, 16).replace("T", " ") : "—");

// Liczba dni kalendarzowych od daty (YYYY-MM-DD) do dziś. Liczone na datach w UTC,
// żeby uniknąć dryfu od strefy czasowej.
export const daysSince = (isoDate) => {
  if (!isoDate) return null;
  const then = new Date(isoDate.slice(0, 10));
  const now = new Date();
  const today = new Date(Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()));
  return Math.round((today - then) / 86400000);
};
