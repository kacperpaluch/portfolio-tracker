// Wspólne helpery formatujące (PLN, procenty, klasa koloru zysk/strata, data).
const plnFmt = new Intl.NumberFormat("pl-PL", { style: "currency", currency: "PLN" });

export const fmtPln = (v) => (v == null ? "—" : plnFmt.format(v));
// Liczba z polskim przecinkiem dziesiętnym (bez grupowania tysięcy).
export const fmtNum = (v, digits = 1) => v.toFixed(digits).replace(".", ",");
export const fmtPct = (v) => (v == null ? "—" : `${v > 0 ? "+" : ""}${fmtNum(v, 2)}%`);
// Zero nie jest zyskiem — zostaje neutralne, żeby „0,00 zł" nie świeciło na zielono.
export const cls = (v) => (v == null || v === 0 ? "muted" : v > 0 ? "pos" : "neg");
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
