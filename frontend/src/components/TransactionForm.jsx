import { useState } from "react";

export default function TransactionForm({ instruments, onAdd }) {
  const today = new Date().toISOString().slice(0, 10);
  const empty = { ts: today, isin: "", type: "BUY", quantity: "", price_pln: "", newIsin: "", newName: "" };
  const [f, setF] = useState(empty);
  const set = (k, v) => setF((s) => ({ ...s, [k]: v }));
  const adding = f.isin === "__new__";

  const submit = () => {
    const isin = adding ? f.newIsin.trim() : f.isin;
    const qty = parseFloat(f.quantity);
    const price = parseFloat(f.price_pln);
    if (!isin || !qty || qty <= 0 || isNaN(price) || price < 0) return;
    onAdd({
      ts: f.ts, isin, name: adding ? f.newName.trim() : undefined,
      type: f.type, quantity: qty, price_pln: price,
    });
    setF({ ...empty, ts: f.ts });
  };

  return (
    <div className="tx-form">
      <input className="cell" type="date" value={f.ts} onChange={(e) => set("ts", e.target.value)} />
      <select className="cell" value={f.isin} onChange={(e) => set("isin", e.target.value)}>
        <option value="">— wybierz walor —</option>
        {instruments.map((i) => <option key={i.isin} value={i.isin}>{i.name}</option>)}
        <option value="__new__">➕ nowy walor…</option>
      </select>
      {adding && (
        <>
          <input className="cell narrow" placeholder="ISIN" value={f.newIsin} onChange={(e) => set("newIsin", e.target.value)} />
          <input className="cell" placeholder="nazwa" value={f.newName} onChange={(e) => set("newName", e.target.value)} />
        </>
      )}
      <select className="cell narrow" value={f.type} onChange={(e) => set("type", e.target.value)}>
        <option value="BUY">Kupno</option>
        <option value="SELL">Sprzedaż</option>
      </select>
      <input className="cell narrow" type="number" step="any" placeholder="szt." value={f.quantity} onChange={(e) => set("quantity", e.target.value)} />
      <input className="cell narrow" type="number" step="any" placeholder="cena PLN" value={f.price_pln} onChange={(e) => set("price_pln", e.target.value)} />
      <button className="primary" onClick={submit}>Dodaj</button>
    </div>
  );
}
