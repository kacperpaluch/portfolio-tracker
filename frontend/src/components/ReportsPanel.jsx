import { useEffect, useMemo, useState } from "react";
import { cls, fmtPct, fmtPln } from "../format.js";
import { api } from "../api.js";
import MonthlyReturnsHeatmap from "./MonthlyReturnsHeatmap.jsx";
import ReportPerformanceChart from "./ReportPerformanceChart.jsx";

const iso = (day) => {
  const year = day.getFullYear();
  const month = String(day.getMonth() + 1).padStart(2, "0");
  const date = String(day.getDate()).padStart(2, "0");
  return `${year}-${month}-${date}`;
};

function presetRange(key) {
  const today = new Date();
  const year = today.getFullYear();
  const month = today.getMonth();
  if (key === "current_month") return { from: iso(new Date(year, month, 1)), to: iso(today) };
  if (key === "previous_month") return { from: iso(new Date(year, month - 1, 1)), to: iso(new Date(year, month, 0)) };
  if (key === "ytd") return { from: `${year}-01-01`, to: iso(today) };
  if (key === "previous_year") return { from: `${year - 1}-01-01`, to: `${year - 1}-12-31` };
  if (key === "rolling_year") {
    const start = new Date(today);
    start.setFullYear(start.getFullYear() - 1);
    return { from: iso(start), to: iso(today) };
  }
  return { from: iso(new Date(year, month, 1)), to: iso(today) };
}

const PRESETS = [
  ["current_month", "Bieżący miesiąc"],
  ["previous_month", "Poprzedni miesiąc"],
  ["ytd", "Bieżący rok"],
  ["previous_year", "Poprzedni rok"],
  ["rolling_year", "Ostatnie 12 miesięcy"],
  ["custom", "Własny okres"],
];

function Metric({ label, value, detail, tone }) {
  return (
    <div className="report-metric">
      <span>{label}</span>
      <strong className={tone || ""}>{value}</strong>
      {detail && <small>{detail}</small>}
    </div>
  );
}

function pct(value) {
  return value == null ? "—" : fmtPct(value * 100);
}

function attributionTable(rows, keyName, label) {
  return (
    <table>
      <thead><tr><th>{label}</th><th>Walory</th><th>Wynik</th><th>Udział</th></tr></thead>
      <tbody>
        {(rows || []).map((row) => (
          <tr key={row[keyName]}>
            <td>{row[keyName]}</td>
            <td>{row.instruments}</td>
            <td className={cls(row.total_pl_pln)}>{fmtPln(row.total_pl_pln)}</td>
            <td>{row.contribution_pct == null ? "—" : `${row.contribution_pct.toFixed(1)}%`}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function ReportsPanel({ benchmarkRate, cpiSpread, onOpen }) {
  const initial = useMemo(() => presetRange("current_month"), []);
  const [preset, setPreset] = useState("current_month");
  const [range, setRange] = useState(initial);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    const timer = window.setTimeout(() => {
      setLoading(true);
      setError(null);
      api.report(range.from, range.to, benchmarkRate / 100, cpiSpread / 100, controller.signal)
        .then((data) => { if (active) setReport(data); })
        .catch((err) => {
          if (active && err.name !== "AbortError") setError(err.message);
        })
        .finally(() => { if (active) setLoading(false); });
    }, 250);
    return () => {
      active = false;
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [range.from, range.to, benchmarkRate, cpiSpread]);

  const selectPreset = (key) => {
    setPreset(key);
    if (key !== "custom") setRange(presetRange(key));
  };
  const updateDate = (field, value) => {
    setPreset("custom");
    setRange((current) => ({ ...current, [field]: value }));
  };
  const csvUrl = api.reportCsvUrl(range.from, range.to, benchmarkRate / 100, cpiSpread / 100);

  return (
    <div className="report-workspace report-print-root">
      <section className="surface report-controls no-print">
        <div className="panel-head">
          <div>
            <div className="eyebrow">Zakres raportu</div>
            <h2>Wybierz okres kalendarzowy</h2>
            <span className="sub">Porównanie dobierze automatycznie poprzedni miesiąc, rok albo równy zakres.</span>
          </div>
        </div>
        <div className="report-presets">
          {PRESETS.map(([key, label]) => <button key={key} className={preset === key ? "active" : ""} onClick={() => selectPreset(key)}>{label}</button>)}
        </div>
        <div className="report-range">
          <label>Od <input type="date" value={range.from} max={range.to} onChange={(event) => updateDate("from", event.target.value)} /></label>
          <label>Do <input type="date" value={range.to} min={range.from} max={iso(new Date())} onChange={(event) => updateDate("to", event.target.value)} /></label>
          <a className="secondary btn" href={csvUrl}>Eksportuj CSV</a>
          <button className="primary" onClick={() => window.print()} disabled={!report || loading}>Zapisz jako PDF</button>
        </div>
      </section>

      {loading && !report && <section className="surface"><div className="spinner">Przygotowujemy raport okresowy…</div></section>}
      {error && <section className="surface"><div className="inline-error">{error}</div></section>}
      {report && (
        <ReportBody report={report} benchmarkRate={benchmarkRate} cpiSpread={cpiSpread} onOpen={onOpen} loading={loading} />
      )}
    </div>
  );
}

function ReportBody({ report, benchmarkRate, cpiSpread, onOpen, loading }) {
  const period = report.period;
  const comparison = report.comparison;
  const attribution = period.attribution;
  const flows = period.flows.totals;
  const quality = report.quality;
  return (
    <>
      <section className="surface report-cover">
        <div>
          <div className="eyebrow">Raport okresowy</div>
          <h2>{period.from} — {period.to}</h2>
          <p>Wygenerowano {report.generated_at} · wszystkie wartości w PLN</p>
        </div>
        <span className={`report-quality ${quality.status}`}>{quality.status === "good" ? "Dane kompletne" : `${quality.summary.issues} uwag do danych`}</span>
        {loading && <span className="report-updating no-print">Aktualizuję…</span>}
      </section>

      <section className="report-metrics-grid">
        <Metric label="Wynik okresu" value={fmtPln(period.result_pln)} detail={`${period.days} dni`} tone={cls(period.result_pln)} />
        <Metric label="TWR" value={pct(period.twr)} detail="bez wpływu wpłat" tone={cls(period.twr)} />
        <Metric label="XIRR" value={pct(period.xirr)} detail="rocznie, z timingiem wpłat" tone={cls(period.xirr)} />
        <Metric label="Wartość końcowa" value={fmtPln(period.closing_value_pln)} detail={`początek ${fmtPln(period.opening_value_pln)}`} />
        <Metric label={`Ponad benchmark ${benchmarkRate}%`} value={period.excess_fixed_pp == null ? "—" : `${period.excess_fixed_pp > 0 ? "+" : ""}${period.excess_fixed_pp.toFixed(2)} pp`} tone={cls(period.excess_fixed_pp)} />
        <Metric label={`Ponad inflację +${cpiSpread}%`} value={period.excess_inflation_pp == null ? "—" : `${period.excess_inflation_pp > 0 ? "+" : ""}${period.excess_inflation_pp.toFixed(2)} pp`} tone={cls(period.excess_inflation_pp)} />
        <Metric label="Zrealizowany" value={fmtPln(attribution.totals.realized_pl_pln)} tone={cls(attribution.totals.realized_pl_pln)} />
        <Metric label="Zmiana niezrealizowanego" value={fmtPln(attribution.totals.unrealized_change_pln)} tone={cls(attribution.totals.unrealized_change_pln)} />
      </section>

      <section className="surface">
        <div className="panel-head"><div><div className="eyebrow">Efektywność</div><h2>Portfel i punkty odniesienia</h2><span className="sub">Skumulowany TWR od początku wybranego okresu.</span></div></div>
        <ReportPerformanceChart rows={period.series} benchmarkRate={benchmarkRate} cpiSpread={cpiSpread} />
      </section>

      <section className="surface">
        <div className="panel-head"><div><div className="eyebrow">Porównanie</div><h2>Wybrany okres vs poprzedni</h2><span className="sub">Miesiące i lata są dopasowane kalendarzowo; własny zakres zachowuje tę samą długość.</span></div></div>
        {comparison ? (
          <table className="period-comparison">
            <thead><tr><th>Miara</th><th>{period.from} — {period.to}</th><th>{comparison.from} — {comparison.to}</th><th>Różnica</th></tr></thead>
            <tbody>
              <tr><td>Wynik PLN</td><td className={cls(period.result_pln)}>{fmtPln(period.result_pln)}</td><td className={cls(comparison.result_pln)}>{fmtPln(comparison.result_pln)}</td><td className={cls(period.result_pln - comparison.result_pln)}>{fmtPln(period.result_pln - comparison.result_pln)}</td></tr>
              <tr><td>TWR</td><td>{pct(period.twr)}</td><td>{pct(comparison.twr)}</td><td>{period.twr == null || comparison.twr == null ? "—" : `${((period.twr - comparison.twr) * 100).toFixed(2)} pp`}</td></tr>
              <tr><td>XIRR roczny</td><td>{pct(period.xirr)}</td><td>{pct(comparison.xirr)}</td><td>{period.xirr == null || comparison.xirr == null ? "—" : `${((period.xirr - comparison.xirr) * 100).toFixed(2)} pp`}</td></tr>
              <tr><td>Kapitał netto</td><td>{fmtPln(period.net_capital_pln)}</td><td>{fmtPln(comparison.net_capital_pln)}</td><td>{fmtPln(period.net_capital_pln - comparison.net_capital_pln)}</td></tr>
            </tbody>
          </table>
        ) : <div className="quality-empty">Brak wcześniejszej historii do porównania.</div>}
      </section>

      <section className="surface">
        <div className="panel-head"><div><div className="eyebrow">Atrybucja</div><h2>Co zbudowało wynik</h2><span className="sub">Wynik rynkowy po neutralizacji zakupów i sprzedaży; prowizje pokazujemy osobno.</span></div></div>
        <div className="analysis-columns report-attribution-groups">
          <div><h3>Klasy aktywów</h3>{attributionTable(attribution.categories, "category", "Klasa")}</div>
          <div><h3>Waluty notowania</h3>{attributionTable(attribution.currencies, "currency", "Waluta")}</div>
        </div>
        <div className="analysis-block">
          <h3>Wynik według walorów</h3>
          <table>
            <thead><tr><th>Instrument</th><th>Początek</th><th>Koniec</th><th>Zrealizowany</th><th>Zmiana niezrealizowanego</th><th>Łącznie</th></tr></thead>
            <tbody>{attribution.instruments.map((row) => (
              <tr key={row.isin}>
                <td><button className="instrument-link no-print-action" onClick={() => onOpen?.(row.isin)}>{row.name}</button><div className="tag">{row.ticker || row.isin} · {row.currency}</div></td>
                <td>{fmtPln(row.opening_value_pln)}</td><td>{fmtPln(row.closing_value_pln)}</td>
                <td className={cls(row.realized_pl_pln)}>{fmtPln(row.realized_pl_pln)}</td>
                <td className={cls(row.unrealized_change_pln)}>{fmtPln(row.unrealized_change_pln)}</td>
                <td className={cls(row.total_pl_pln)}>{fmtPln(row.total_pl_pln)}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
        <div className="analysis-columns secondary-analysis">
          <div><h3>Najlepsze walory</h3><RankedRows rows={attribution.winners.filter((row) => row.total_pl_pln > 0)} /></div>
          <div><h3>Najsłabsze walory</h3><RankedRows rows={attribution.losers.filter((row) => row.total_pl_pln < 0)} /></div>
        </div>
      </section>

      <section className="surface">
        <div className="panel-head"><div><div className="eyebrow">Przepływy</div><h2>Kapitał i aktywność</h2><span className="sub">Wpłaty i wypłaty są zewnętrzne; zakupy i sprzedaże przesuwają środki wewnątrz portfela.</span></div></div>
        <div className="report-flow-grid">
          <Metric label="Wpłaty" value={fmtPln(flows.deposits_pln)} />
          <Metric label="Wypłaty" value={fmtPln(flows.withdrawals_pln)} />
          <Metric label="Zakupy" value={fmtPln(flows.purchases_pln)} />
          <Metric label="Sprzedaże" value={fmtPln(flows.sales_pln)} />
          <Metric label="Prowizje" value={fmtPln(period.activity.commissions_pln)} />
          <Metric label="Gotówka na koniec" value={fmtPln(period.cash.closing_pln)} detail={`początek ${fmtPln(period.cash.opening_pln)}`} />
        </div>
        {period.flows.monthly.length ? (
          <table><thead><tr><th>Miesiąc</th><th>Wpłaty</th><th>Wypłaty</th><th>Zakupy</th><th>Sprzedaże</th><th>Kapitał netto</th></tr></thead>
            <tbody>{period.flows.monthly.map((row) => <tr key={row.month}><td>{row.month}</td><td>{fmtPln(row.deposits_pln)}</td><td>{fmtPln(row.withdrawals_pln)}</td><td>{fmtPln(row.purchases_pln)}</td><td>{fmtPln(row.sales_pln)}</td><td className={cls(row.net_external_pln)}>{fmtPln(row.net_external_pln)}</td></tr>)}</tbody>
          </table>
        ) : <div className="quality-empty">Brak przepływów w wybranym okresie.</div>}
      </section>

      <section className="surface">
        <div className="panel-head"><div><div className="eyebrow">Kalendarz wyników</div><h2>Miesięczne stopy zwrotu</h2><span className="sub">TWR w miesiącach i latach, bez wpływu dopłat oraz wypłat.</span></div></div>
        <MonthlyReturnsHeatmap rows={report.monthly_returns} />
      </section>

      <section className="surface report-data-quality">
        <div><div className="eyebrow">Jakość raportu</div><h2>{quality.status === "good" ? "Dane kompletne" : "Raport zawiera uwagi do danych"}</h2><p>Kontrola: {quality.checked_at}. Ostatnia cena: {quality.stats.latest_price_date || "brak"}; ostatni kurs FX: {quality.stats.latest_fx_date || "nie dotyczy"}.</p></div>
        <div className="report-quality-facts"><span>Błędy <strong>{quality.summary.errors}</strong></span><span>Ostrzeżenia <strong>{quality.summary.warnings}</strong></span><span>Pełna wycena <strong>{quality.stats.fully_valued ? "Tak" : "Nie"}</strong></span></div>
      </section>
    </>
  );
}

function RankedRows({ rows }) {
  if (!rows.length) return <div className="quality-empty">Brak pozycji w tej grupie.</div>;
  return <div className="ranked-report-rows">{rows.map((row, index) => <div key={row.isin}><span>{index + 1}</span><strong>{row.name}</strong><em className={cls(row.total_pl_pln)}>{fmtPln(row.total_pl_pln)}</em></div>)}</div>;
}
