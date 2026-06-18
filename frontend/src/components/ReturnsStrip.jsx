import { fmtPct, cls } from "../format.js";

const PERIOD_LABELS = [
  ["1m", "1M"],
  ["3m", "3M"],
  ["ytd", "YTD"],
  ["1y", "1R"],
  ["all", "Od początku"],
];

export default function ReturnsStrip({ returns }) {
  if (!returns || !Object.keys(returns).length) return null;
  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Zwroty w okresach</h2>
        <span className="sub">TWR — wynik portfela (bez wpływu timingu wpłat); pod spodem XIRR roczny</span>
      </div>
      <div className="returns-strip">
        {PERIOD_LABELS.map(([key, label]) => {
          const r = returns[key];
          const twr = r?.twr;
          const xirr = r?.xirr;
          return (
            <div className="ret" key={key}>
              <div className="ret-label">{label}</div>
              <div className={`ret-val ${cls(twr)}`}>{twr == null ? "—" : fmtPct(twr * 100)}</div>
              <div className="ret-sub">XIRR {xirr == null ? "—" : `${fmtPct(xirr * 100)} rocznie`}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
