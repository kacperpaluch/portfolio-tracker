import { fmtPln, fmtPct, cls } from "../format.js";

export default function Cards({ totals }) {
  const t = totals || {};
  const accountValue = t.portfolio_value_pln ?? t.value_pln ?? t.value_pln_partial;
  return (
    <div className="cards">
      <div className="card">
        <div className="label">Wartość konta</div>
        <div className="value">{fmtPln(accountValue)}</div>
        <div className="tag">ETF {fmtPln(t.value_pln ?? t.value_pln_partial)} + gotówka {fmtPln(t.cash_pln)}</div>
      </div>
      <div className="card">
        <div className="label">Zysk całkowity</div>
        <div className={`value ${cls(t.total_pl_pln)}`}>{fmtPln(t.total_pl_pln)}</div>
        <div className="tag">
          niezreal. <span className={cls(t.unrealized_pl_pln)}>{fmtPln(t.unrealized_pl_pln)}</span>
          {" · "}zreal. <span className={cls(t.realized_pl_pln)}>{fmtPln(t.realized_pl_pln)}</span>
        </div>
      </div>
      <div className="card">
        <div className="label">XIRR</div>
        <div className={`value ${cls(t.xirr)}`}>{t.xirr == null ? "—" : fmtPct(t.xirr * 100)}</div>
        <div className="tag">zwrot z Twojego kapitału (z timingiem wpłat)</div>
      </div>
      <div className="card">
        <div className="label">TWR</div>
        <div className={`value ${cls(t.twr)}`}>{t.twr == null ? "—" : fmtPct(t.twr * 100)}</div>
        <div className="tag">wynik portfela (bez wpływu timingu wpłat)</div>
      </div>
      <div className="card">
        <div className="label">Gotówka</div>
        <div className="value">{fmtPln(t.cash_pln)}</div>
        <div className="tag">wpłacono netto {fmtPln(t.net_deposits_pln)}</div>
      </div>
    </div>
  );
}
