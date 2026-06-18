import { useState } from "react";
import { fmtPln, cls } from "../format.js";

export default function AllocationPanel({ allocation, onSave }) {
  const [draft, setDraft] = useState({});
  const groups = allocation?.groups || [];
  const targetOf = (g) => (draft[g.category] ?? (g.target_pct ?? ""));
  const set = (cat, v) => setDraft((d) => ({ ...d, [cat]: v }));

  const save = () => {
    const targets = {};
    for (const g of groups) {
      const v = parseFloat(targetOf(g));
      if (!isNaN(v) && v > 0) targets[g.category] = v;
    }
    onSave(targets);
    setDraft({});
  };

  // Suma docelowa z aktualnego draftu (do walidacji 100%).
  const sum = groups.reduce((acc, g) => {
    const v = parseFloat(targetOf(g));
    return acc + (isNaN(v) ? 0 : v);
  }, 0);

  if (groups.length === 0)
    return <div className="spinner">Brak danych. Przypisz instrumentom kategorie w zakładce „Instrumenty".</div>;

  return (
    <div>
      <table>
        <thead>
          <tr>
            <th>Grupa</th>
            <th>Docelowo %</th>
            <th>Rzeczywiście %</th>
            <th>Wartość</th>
            <th>Odchylenie</th>
            <th>Do rebalansu</th>
          </tr>
        </thead>
        <tbody>
          {groups.map((g) => (
            <tr key={g.category}>
              <td>{g.category}</td>
              <td>
                <input
                  className="cell narrow"
                  type="number"
                  step="1"
                  value={targetOf(g)}
                  placeholder="—"
                  onChange={(e) => set(g.category, e.target.value)}
                />
              </td>
              <td>{g.actual_pct == null ? "—" : `${g.actual_pct.toFixed(1)}%`}</td>
              <td>{fmtPln(g.actual_pln)}</td>
              <td className={cls(g.drift_pp == null ? null : -Math.abs(g.drift_pp))}>
                {g.drift_pp == null ? "—" : `${g.drift_pp > 0 ? "+" : ""}${g.drift_pp.toFixed(1)} pp`}
              </td>
              <td className={cls(g.rebalance_pln)}>
                {g.rebalance_pln == null ? "—" : `${g.rebalance_pln > 0 ? "+" : ""}${fmtPln(g.rebalance_pln)}`}
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <td>Suma</td>
            <td className={Math.abs(sum - 100) < 0.01 ? "pos" : "neg"}>{sum.toFixed(0)}%</td>
            <td colSpan={2}>{fmtPln(allocation.total_pln)}</td>
            <td colSpan={2}></td>
          </tr>
        </tfoot>
      </table>
      <div className="alloc-actions">
        <button className="primary" onClick={save}>Zapisz model docelowy</button>
        {Math.abs(sum - 100) >= 0.01 && sum > 0 && (
          <span className="tag">Uwaga: wagi docelowe sumują się do {sum.toFixed(0)}%, nie 100%.</span>
        )}
      </div>
      <p className="tag" style={{ marginTop: 12 }}>
        „Do rebalansu" = kwota do dokupienia (+) lub sprzedaży (−), by trafić w docelowy udział.
        Gotówka liczona jest jako osobna grupa.
      </p>
    </div>
  );
}
