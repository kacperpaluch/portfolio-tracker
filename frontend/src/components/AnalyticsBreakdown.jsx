import { cls, fmtPln } from "../format.js";

export default function AnalyticsBreakdown({ analytics, allocation, onOpen }) {
  if (!analytics) return <div className="spinner">Trwa przygotowywanie analizy…</div>;
  const contributions = analytics.contributions || [];

  return (
    <>
      <div className="analysis-columns">
        <div>
          <h3>Wynik według klas aktywów</h3>
          <table>
            <thead><tr><th>Klasa</th><th>Wartość</th><th>Wynik</th><th>Udział w wyniku</th></tr></thead>
            <tbody>
              {analytics.categories.map((row) => (
                <tr key={row.category}>
                  <td>{row.category}<div className="tag">{row.instruments} instr.</div></td>
                  <td>{fmtPln(row.value_pln)}</td>
                  <td className={cls(row.total_pl_pln)}>{fmtPln(row.total_pl_pln)}</td>
                  <td>{row.contribution_pct == null ? "—" : `${row.contribution_pct.toFixed(1)}%`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div>
          <h3>Plan vs rzeczywistość</h3>
          <table>
            <thead><tr><th>Klasa</th><th>Plan</th><th>Aktualnie</th><th>Odchylenie</th></tr></thead>
            <tbody>
              {(allocation?.groups || []).map((row) => (
                <tr key={row.category}>
                  <td>{row.category}</td>
                  <td>{row.target_pct == null ? "—" : `${row.target_pct.toFixed(1)}%`}</td>
                  <td>{row.actual_pct == null ? "—" : `${row.actual_pct.toFixed(1)}%`}</td>
                  <td className={row.drift_pp == null ? "muted" : Math.abs(row.drift_pp) < 2 ? "pos" : "neg"}>
                    {row.drift_pp == null ? "—" : `${row.drift_pp > 0 ? "+" : ""}${row.drift_pp.toFixed(1)} pp`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="analysis-block">
        <h3>Instrumenty, które budują wynik</h3>
        <table>
          <thead><tr><th>Instrument</th><th>Niezrealizowany</th><th>Zrealizowany</th><th>Łącznie</th><th>Udział w wyniku</th></tr></thead>
          <tbody>
            {analytics.instruments.map((row) => (
              <tr key={row.isin}>
                <td>
                  <button className="instrument-link" onClick={() => onOpen?.(row.isin)}>{row.name}</button>
                  <div className="tag">{row.ticker || row.isin} · {row.category}</div>
                </td>
                <td className={cls(row.unrealized_pl_pln)}>{fmtPln(row.unrealized_pl_pln)}</td>
                <td className={cls(row.realized_pl_pln)}>{fmtPln(row.realized_pl_pln)}</td>
                <td className={cls(row.total_pl_pln)}>{fmtPln(row.total_pl_pln)}</td>
                <td>{row.contribution_pct == null ? "—" : `${row.contribution_pct.toFixed(1)}%`}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="analysis-columns secondary-analysis">
        <div>
          <h3>Historia wpłat</h3>
          {contributions.length ? (
            <table>
              <thead><tr><th>Miesiąc</th><th>Wpłaty</th><th>Wypłaty</th><th>Netto</th></tr></thead>
              <tbody>
                {contributions.slice(-12).reverse().map((row) => (
                  <tr key={row.month}>
                    <td>{row.month}</td>
                    <td>{fmtPln(row.deposits_pln)}</td>
                    <td>{fmtPln(row.withdrawals_pln)}</td>
                    <td className={cls(row.net_pln)}>{fmtPln(row.net_pln)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <div className="quality-empty">Brak zarejestrowanych wpłat i wypłat.</div>}
        </div>
        <div className="activity-summary">
          <h3>Aktywność inwestycyjna</h3>
          <div className="activity-facts">
            <div><span>Transakcje</span><strong>{analytics.activity.transactions}</strong></div>
            <div><span>Kupna / sprzedaże</span><strong>{analytics.activity.buys} / {analytics.activity.sells}</strong></div>
            <div><span>Prowizje</span><strong>{fmtPln(analytics.activity.commissions_pln)}</strong></div>
            <div><span>Pierwsza operacja</span><strong>{analytics.activity.first_transaction?.slice(0, 10) || "—"}</strong></div>
          </div>
        </div>
      </div>
    </>
  );
}
