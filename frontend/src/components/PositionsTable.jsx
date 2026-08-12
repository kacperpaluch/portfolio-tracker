import { fmtPln, fmtPct, cls, daysSince } from "../format.js";
import { portfolioStructureTotal, positionStructureValue } from "../portfolioStructure.js";

// Znacznik świeżości ceny (opcjonalnie z kursem FX w tej samej linii). Gdy cena jest
// nieświeża (> weekend + ewentualne święto) — bursztynowy kolor niesie ostrzeżenie sam,
// bez ikony powtarzanej w każdym wierszu; łączne ostrzeżenie jest w nagłówku strony.
function PriceMeta({ date, fxRate }) {
  const d = daysSince(date);
  const fx = fxRate && fxRate !== 1 ? `×${fxRate}` : null;
  if (d == null) return fx ? <div className="tag">{fx}</div> : null;
  const label = d <= 0 ? "dziś" : d === 1 ? "wczoraj" : `${d} dni temu`;
  return (
    <div className={`tag ${d > 4 ? "stale" : ""}`} title={`Ostatnia cena z ${date}`}>
      {[fx, label].filter(Boolean).join(" · ")}
    </div>
  );
}

export default function PositionsTable({ positions, allPositions = positions, totals, onOpen, compact = false }) {
  if (!positions || positions.length === 0)
    return <div className="spinner">Brak pozycji. Zaimportuj plik CSV.</div>;
  const structureTotal = portfolioStructureTotal(allPositions, totals?.cash_pln);
  const positionsShare = structureTotal
    ? allPositions.reduce((sum, position) => sum + positionStructureValue(position), 0) / structureTotal * 100
    : null;
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
          <th>Udział</th>
          <th>Zysk/strata</th>
          <th>%</th>
        </tr>
      </thead>
      <tbody>
        {positions.map((p) => (
          <tr key={p.isin}>
            <td>
              <button className="instrument-link" onClick={() => onOpen?.(p.isin)}>{p.name}</button>
              {" "}{p.needs_config && <span className="badge">brak tickera</span>}
              <div className="tag">{p.ticker || p.isin} · {p.currency || "?"}</div>
            </td>
            <td>{p.quantity}</td>
            <td>{fmtPln(p.avg_cost_pln)}</td>
            <td>{fmtPln(p.cost_pln)}</td>
            <td>
              {p.price == null ? "—" : p.price}
              <PriceMeta date={p.price_date} fxRate={p.fx_rate} />
            </td>
            <td>{fmtPln(p.value_pln)}</td>
            <td>{structureTotal ? `${(positionStructureValue(p) / structureTotal * 100).toFixed(1)}%` : "—"}</td>
            <td className={cls(p.pl_pln)}>{fmtPln(p.pl_pln)}</td>
            <td className={cls(p.pl_pct)}>{fmtPct(p.pl_pct)}</td>
          </tr>
        ))}
      </tbody>
      {!compact && (
        <tfoot>
          <tr>
            <td>Razem (otwarte)</td>
            <td colSpan={2}></td>
            <td>{fmtPln(totals.cost_pln)}</td>
            <td></td>
            <td>{fmtPln(totals.value_pln ?? totals.value_pln_partial)}</td>
            <td>{positionsShare == null ? "—" : `${positionsShare.toFixed(1)}%`}</td>
            <td className={cls(totals.unrealized_pl_pln)}>{fmtPln(totals.unrealized_pl_pln)}</td>
            <td className={cls(totals.pl_pct)}>{fmtPct(totals.pl_pct)}</td>
          </tr>
        </tfoot>
      )}
    </table>
  );
}
