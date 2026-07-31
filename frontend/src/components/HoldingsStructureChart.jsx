import { fmtPln } from "../format.js";
import { portfolioStructureTotal, positionStructureValue } from "../portfolioStructure.js";

const MAX_VISIBLE_HOLDINGS = 6;

export default function HoldingsStructureChart({ positions, cashPln = 0, onOpen }) {
  const holdings = (positions || [])
    .map((position) => ({
      id: position.isin,
      name: position.name,
      ticker: position.ticker,
      value: positionStructureValue(position),
      position,
    }))
    .filter((row) => row.value > 0)
    .sort((a, b) => b.value - a.value);
  const total = portfolioStructureTotal(positions, cashPln);

  if (!holdings.length || !total) {
    return <div className="spinner">Brak wycenionych pozycji do pokazania.</div>;
  }

  const visible = holdings.slice(0, MAX_VISIBLE_HOLDINGS);
  const hidden = holdings.slice(MAX_VISIBLE_HOLDINGS);
  const rows = [...visible];
  if (hidden.length) {
    rows.push({
      id: "other",
      name: `Pozostałe (${hidden.length})`,
      value: hidden.reduce((sum, row) => sum + row.value, 0),
      kind: "other",
    });
  }
  if (Number(cashPln) > 0) {
    rows.push({ id: "cash", name: "Gotówka", value: Number(cashPln), kind: "cash" });
  }

  const topThreeShare = holdings
    .slice(0, 3)
    .reduce((sum, row) => sum + row.value, 0) / total * 100;

  return (
    <div className="holdings-structure">
      <div className="holding-bars" aria-label="Udział walorów w wartości portfela">
        {rows.map((row) => {
          const share = row.value / total * 100;
          const content = (
            <>
              <span className="holding-bar-label" title={row.name}>
                <strong>{row.name}</strong>
                {row.ticker && <small>{row.ticker}</small>}
              </span>
              <span className="holding-bar-track" aria-hidden="true">
                <i style={{ width: `${Math.max(1.5, share)}%` }} />
              </span>
              <span className="holding-bar-value" title={fmtPln(row.value)}>{share.toFixed(1)}%</span>
            </>
          );

          return row.position ? (
            <button
              className="holding-bar-row"
              key={row.id}
              onClick={() => onOpen?.(row.id)}
              title={`${row.name}: ${fmtPln(row.value)} (${share.toFixed(1)}%)`}
            >
              {content}
            </button>
          ) : (
            <div
              className={`holding-bar-row ${row.kind || ""}`}
              key={row.id}
              title={`${row.name}: ${fmtPln(row.value)} (${share.toFixed(1)}%)`}
            >
              {content}
            </div>
          );
        })}
      </div>
      <div className="insight-line holdings-concentration">
        <span>Koncentracja w 3 największych walorach</span>
        <strong>{topThreeShare.toFixed(1)}%</strong>
      </div>
    </div>
  );
}
