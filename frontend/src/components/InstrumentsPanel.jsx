import { useState } from "react";

export default function InstrumentsPanel({ instruments, onSave }) {
  const [draft, setDraft] = useState({});
  const edit = (isin, field, val) => setDraft((d) => ({ ...d, [isin]: { ...d[isin], [field]: val } }));
  const valueOf = (inst, field) => draft[inst.isin]?.[field] ?? inst[field] ?? "";
  return (
    <table>
      <thead>
        <tr><th>Instrument / ISIN</th><th>Ticker</th><th>Źródło</th><th>Kategoria</th><th>Waluta</th><th>Status</th><th></th></tr>
      </thead>
      <tbody>
        {instruments.map((inst) => (
          <tr key={inst.isin}>
            <td>{inst.name}<div className="tag">{inst.isin}</div></td>
            <td>
              <input className="cell" value={valueOf(inst, "ticker")} placeholder="np. FWIA.DE"
                onChange={(e) => edit(inst.isin, "ticker", e.target.value)} />
            </td>
            <td>
              <select className="cell narrow" value={valueOf(inst, "source") || "yfinance"}
                onChange={(e) => edit(inst.isin, "source", e.target.value)}>
                <option value="yfinance">yfinance</option>
                <option value="stooq">stooq</option>
              </select>
            </td>
            <td>
              <input className="cell" list="cat-list" value={valueOf(inst, "category")} placeholder="np. Akcje"
                onChange={(e) => edit(inst.isin, "category", e.target.value)} />
            </td>
            <td className="muted">{inst.currency || "auto"}</td>
            <td>{inst.needs_config ? <span className="badge">do uzupełnienia</span> : <span className="pos">OK</span>}</td>
            <td>
              <button onClick={() => onSave(inst.isin, {
                ticker: valueOf(inst, "ticker"),
                source: valueOf(inst, "source") || "yfinance",
                currency: inst.currency,
                category: valueOf(inst, "category"),
              })}>Zapisz</button>
            </td>
          </tr>
        ))}
      </tbody>
      <datalist id="cat-list">
        <option value="Akcje" /><option value="Obligacje" /><option value="Surowce" />
        <option value="Nieruchomości" /><option value="Gotówka" />
      </datalist>
    </table>
  );
}
