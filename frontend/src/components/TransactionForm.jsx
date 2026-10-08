import { useState } from "react";
import AccountSelect from "./AccountSelect.jsx";

export default function TransactionForm({ instruments, accounts, defaultAccount, onAdd }) {
  const today = new Date().toISOString().slice(0, 10);
  const empty = {
    ts: today, isin: "", type: "BUY", quantity: "", price_pln: "",
    commission_pln: "", note: "", newIsin: "", newName: "", account_id: defaultAccount,
  };
  const [f, setF] = useState(empty);
  const [error, setError] = useState("");
  const set = (k, v) => setF((s) => ({ ...s, [k]: v }));
  const adding = f.isin === "__new__";

  const submit = () => {
    const isin = adding ? f.newIsin.trim() : f.isin;
    const qty = parseFloat(f.quantity);
    const price = parseFloat(f.price_pln);
    const problem = !isin ? (adding ? "Podaj ISIN nowego waloru." : "Wybierz walor.")
      : !qty || qty <= 0 ? "Podaj liczbę sztuk większą od zera."
      : isNaN(price) || price < 0 ? "Podaj cenę za sztukę w PLN."
      : "";
    setError(problem);
    if (problem) return;
    onAdd({
      ts: f.ts, isin, name: adding ? f.newName.trim() : undefined,
      type: f.type, quantity: qty, price_pln: price,
      commission_pln: parseFloat(f.commission_pln) || 0,
      note: f.note.trim() || undefined,
      account_id: f.account_id,
    });
    setF({ ...empty, ts: f.ts, account_id: f.account_id });
  };

  return (
    <div className="tx-form">
      <label className="field"><span>Data</span>
        <input className="cell" type="date" value={f.ts} onChange={(e) => set("ts", e.target.value)} />
      </label>
      <AccountSelect label="Konto" accounts={accounts} value={f.account_id} onChange={(v) => set("account_id", v)} />
      <label className="field"><span>Walor</span>
        <select className="cell" value={f.isin} onChange={(e) => set("isin", e.target.value)}>
          <option value="">— wybierz walor —</option>
          {instruments.map((i) => <option key={i.isin} value={i.isin}>{i.name}</option>)}
          <option value="__new__">➕ nowy walor…</option>
        </select>
      </label>
      {adding && (
        <>
          <label className="field"><span>ISIN</span>
            <input className="cell" value={f.newIsin} onChange={(e) => set("newIsin", e.target.value)} />
          </label>
          <label className="field"><span>Nazwa</span>
            <input className="cell" value={f.newName} onChange={(e) => set("newName", e.target.value)} />
          </label>
        </>
      )}
      <label className="field"><span>Typ</span>
        <select className="cell narrow" value={f.type} onChange={(e) => set("type", e.target.value)}>
          <option value="BUY">Kupno</option>
          <option value="SELL">Sprzedaż</option>
        </select>
      </label>
      <label className="field"><span>Sztuki</span>
        <input className="cell narrow" type="number" step="any" value={f.quantity} onChange={(e) => set("quantity", e.target.value)} />
      </label>
      <label className="field"><span>Cena PLN</span>
        <input className="cell narrow" type="number" step="any" value={f.price_pln} onChange={(e) => set("price_pln", e.target.value)} />
      </label>
      <label className="field"><span>Prowizja</span>
        <input className="cell narrow" type="number" step="0.01" min="0" placeholder="0" value={f.commission_pln} onChange={(e) => set("commission_pln", e.target.value)} />
      </label>
      <label className="field tx-note"><span>Notatka</span>
        <input className="cell" placeholder="opcjonalnie" value={f.note} onChange={(e) => set("note", e.target.value)} onKeyDown={(e) => e.key === "Enter" && submit()} />
      </label>
      <button className="primary" onClick={submit}>Dodaj</button>
      {error && <p className="form-error" role="alert">{error}</p>}
    </div>
  );
}
