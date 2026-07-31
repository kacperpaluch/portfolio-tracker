import { cls, fmtPct } from "../format.js";

const MONTHS = ["Sty", "Lut", "Mar", "Kwi", "Maj", "Cze", "Lip", "Sie", "Wrz", "Paź", "Lis", "Gru"];

function cellStyle(value) {
  if (value == null) return undefined;
  const alpha = Math.min(0.42, 0.08 + Math.abs(value) / 35);
  return { backgroundColor: value >= 0 ? `rgba(52,122,80,${alpha})` : `rgba(196,76,70,${alpha})` };
}

export default function MonthlyReturnsHeatmap({ rows }) {
  if (!rows?.length) return <div className="quality-empty">Brak pełnej historii miesięcznej.</div>;
  return (
    <div className="monthly-heatmap">
      <table>
        <thead>
          <tr><th>Rok</th>{MONTHS.map((month) => <th key={month}>{month}</th>)}<th>Rok</th></tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.year}>
              <th>{row.year}</th>
              {MONTHS.map((month, index) => {
                const value = row.months?.[String(index + 1)];
                return <td key={month} className={cls(value)} style={cellStyle(value)}>{value == null ? "—" : fmtPct(value)}</td>;
              })}
              <td className={`annual ${cls(row.annual_pct)}`}>{row.annual_pct == null ? "—" : fmtPct(row.annual_pct)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
