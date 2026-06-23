import { fmtPln, fmtPct, cls } from "../format.js";

export default function DailyChangesTable({ rows }) {
  if (!rows || rows.length === 0)
    return <div className="spinner">Brak danych — kliknij „Backfill historii", aby zasilić serię wartości.</div>;
  const ordered = [...rows].reverse();
  return (
    <table>
      <thead>
        <tr>
          <th>Data</th>
          <th>Wartość ETF</th>
          <th>Kupno/sprzedaż</th>
          <th>Zmiana (zł)</th>
          <th>Zmiana (%)</th>
        </tr>
      </thead>
      <tbody>
        {ordered.map((r) => (
          <tr key={r.date}>
            <td>{r.date}</td>
            <td>{fmtPln(r.value_pln)}</td>
            <td className="muted">{r.flow_pln ? fmtPln(r.flow_pln) : "—"}</td>
            <td className={cls(r.change_pln)}>{fmtPln(r.change_pln)}</td>
            <td className={cls(r.change_pct)}>{r.change_pct == null ? "—" : fmtPct(r.change_pct)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}