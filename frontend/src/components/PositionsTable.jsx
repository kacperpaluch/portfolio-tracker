import { fmtPln, fmtPct, cls, daysSince } from "../format.js";

// Znacznik świeżości ceny. Pokazuje „kiedy ostatnia cena"; gdy nieświeża (> weekend +
// ewentualne święto) — ostrzeżenie, że czas ręcznie zaimportować CSV.
function PriceAge({ date }) {
  const d = daysSince(date);
  if (d == null) return null;
  const stale = d > 4;
  const label = d <= 0 ? "dziś" : d === 1 ? "wczoraj" : `${d} dni temu`;
  return (
    <div className={`tag ${stale ? "stale" : ""}`} title={`Ostatnia cena z ${date}`}>
      {stale ? "⚠️ " : ""}{label}
    </div>
  );
}

export default function PositionsTable({ positions, totals, onOpen }) {
  if (!positions || positions.length === 0)
    return <div className="spinner">Brak pozycji. Zaimportuj plik CSV.</div>;
  return (
    <table>
      <thead>
        <tr>
          <th>Instrument</th>
          <th>Szt.</th>
          <th>Śr. koszt</th>
          <th>Koszt</th>
          <th>Cena</th>
          <th>Wartość</th>
          <th>Zysk/strata</th>
          <th>%</th>
        </tr>
      </thead>
      <tbody>
        {positions.map((p) => (
          <tr key={p.isin}>
            <td>
              <span className="link" onClick={() => onOpen?.(p.isin)}>{p.name}</span>
              {" "}{p.needs_config && <span className="badge">brak tickera</span>}
              <div className="tag">{p.ticker || p.isin} · {p.currency || "?"}</div>
            </td>
            <td>{p.quantity}</td>
            <td>{fmtPln(p.avg_cost_pln)}</td>
            <td>{fmtPln(p.cost_pln)}</td>
            <td>
              {p.price == null ? "—" : p.price}
              {p.fx_rate && p.fx_rate !== 1 ? <div className="tag">×{p.fx_rate}</div> : null}
              <PriceAge date={p.price_date} />
            </td>
            <td>{fmtPln(p.value_pln)}</td>
            <td className={cls(p.pl_pln)}>{fmtPln(p.pl_pln)}</td>
            <td className={cls(p.pl_pct)}>{fmtPct(p.pl_pct)}</td>
          </tr>
        ))}
      </tbody>
      <tfoot>
        <tr>
          <td>Razem (otwarte)</td>
          <td colSpan={2}></td>
          <td>{fmtPln(totals.cost_pln)}</td>
          <td></td>
          <td>{fmtPln(totals.value_pln ?? totals.value_pln_partial)}</td>
          <td className={cls(totals.unrealized_pl_pln)}>{fmtPln(totals.unrealized_pl_pln)}</td>
          <td className={cls(totals.pl_pct)}>{fmtPct(totals.pl_pct)}</td>
        </tr>
      </tfoot>
    </table>
  );
}
