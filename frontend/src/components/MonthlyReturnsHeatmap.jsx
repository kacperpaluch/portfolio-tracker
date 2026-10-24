import { cls, fmtPct } from "../format.js";

const MONTHS = ["Sty", "Lut", "Mar", "Kwi", "Maj", "Cze", "Lip", "Sie", "Wrz", "Paź", "Lis", "Gru"];

// Tło z kolorów motywu (działa też w trybie ciemnym); tekst zostaje w kolorze atramentu, żeby trzymał kontrast.
function cellStyle(value) {
  if (value == null) return undefined;
  const share = Math.round(Math.min(32, 6 + Math.abs(value) * 2.5));
  return { backgroundColor: `color-mix(in srgb, var(${value >= 0 ? "--pos" : "--neg"}) ${share}%, transparent)` };
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
                return <td key={month} style={cellStyle(value)}>{value == null ? "—" : fmtPct(value)}</td>;
              })}
              <td className={`annual ${cls(row.annual_pct)}`}>{row.annual_pct == null ? "—" : fmtPct(row.annual_pct)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
