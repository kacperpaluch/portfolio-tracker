import { fmtPln, fmtPct, cls } from "../format.js";

export default function DailyChangesTable({ rows }) {
  if (!rows || rows.length === 0)
    return <div className="spinner">Brak danych — kliknij „Backfill historii", aby zasilić serię wartości.</div>;
  // Najnowsze u góry.
  const ordered = [...rows].reverse();
  // Znacznik: co napędzało dany dzień — ruch instrumentu czy kurs NBP.
  const driver = (r) => {
    if (Math.abs(r.change_pln) < 0.01) return "—";
    const i = Math.abs(r.instrument_pln ?? 0);
    const f = Math.abs(r.fx_pln ?? 0);
    return f > i ? "💱 kurs" : "📈 instrument";
  };
  return (
    <table>
      <thead>
        <tr>
          <th>Data</th>
          <th>Wartość ETF</th>
          <th>Kupno/sprzedaż</th>
          <th>Zmiana (zł)</th>
          <th title="Ruch ceny samego instrumentu (przy stałym kursie)">Instrument</th>
          <th title="Efekt zmiany kursu NBP dzień-do-dnia">Kurs NBP</th>
          <th>Co napędzało</th>
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
            <td className={cls(r.instrument_pln)}>{r.instrument_pln == null ? "—" : fmtPln(r.instrument_pln)}</td>
            <td className={cls(r.fx_pln)}>{r.fx_pln == null ? "—" : fmtPln(r.fx_pln)}</td>
            <td className="muted">{driver(r)}</td>
            <td className={cls(r.change_pct)}>{r.change_pct == null ? "—" : fmtPct(r.change_pct)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
