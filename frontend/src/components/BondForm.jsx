import { useRef, useState } from "react";
import AccountSelect from "./AccountSelect.jsx";

// Detaliczne obligacje skarbowe (EDO/TOS/ROS/ROD) — wycena z tabel odsetkowych MF.
export default function BondForm({ accounts, defaultAccount, onAdd, onImportTable, busy }) {
  const today = new Date().toISOString().slice(0, 10);
  const empty = { purchase_date: today, series: "", quantity: "", price_pln: "100", account_id: defaultAccount };
  const [f, setF] = useState(empty);
  const fileRef = useRef(null);
  const set = (k, v) => setF((s) => ({ ...s, [k]: v }));

  const submit = () => {
    const quantity = parseFloat(f.quantity);
    const price = parseFloat(f.price_pln);
    if (!f.series.trim() || !quantity || quantity <= 0 || isNaN(price) || price <= 0) return;
    onAdd({ series: f.series.trim().toUpperCase(), purchase_date: f.purchase_date, quantity, price_pln: price, account_id: f.account_id });
    setF({ ...empty, purchase_date: f.purchase_date, account_id: f.account_id });
  };
  const onPick = (e) => {
    const file = e.target.files?.[0];
    if (file) onImportTable(file);
    e.target.value = "";
  };

  return (
    <div className="tx-form">
      <input className="cell" type="date" title="Dzień zakupu" value={f.purchase_date} onChange={(e) => set("purchase_date", e.target.value)} />
      <AccountSelect accounts={accounts} value={f.account_id} onChange={(v) => set("account_id", v)} />
      <input className="cell narrow" placeholder="seria, np. EDO0334" maxLength="7" value={f.series} onChange={(e) => set("series", e.target.value.toUpperCase())} />
      <input className="cell narrow" type="number" step="1" min="1" placeholder="szt." value={f.quantity} onChange={(e) => set("quantity", e.target.value)} />
      <input className="cell narrow" type="number" step="0.01" min="0" placeholder="cena PLN" title="100 zł, a przy zamianie 99,90 zł" value={f.price_pln} onChange={(e) => set("price_pln", e.target.value)} onKeyDown={(e) => e.key === "Enter" && submit()} />
      <button className="primary" onClick={submit} disabled={busy}>Dodaj obligacje</button>
      <input ref={fileRef} type="file" accept=".pdf" className="hidden-file" onChange={onPick} />
      <button onClick={() => fileRef.current?.click()} disabled={busy}
        title="Zapas, gdy automatyczne pobranie z obligacjeskarbowe.pl zawiedzie">
        Wgraj tabelę odsetkową (PDF)
      </button>
    </div>
  );
}
