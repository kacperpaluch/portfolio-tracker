import { useRef, useState } from "react";
import AccountSelect from "./AccountSelect.jsx";

// Detaliczne obligacje skarbowe (EDO/TOS/ROS/ROD) — wycena z tabel odsetkowych MF.
export default function BondForm({ accounts, defaultAccount, onAdd, onImportTable, busy }) {
  const today = new Date().toISOString().slice(0, 10);
  const empty = { purchase_date: today, series: "", quantity: "", price_pln: "100", account_id: defaultAccount };
  const [f, setF] = useState(empty);
  const [error, setError] = useState("");
  const fileRef = useRef(null);
  const set = (k, v) => setF((s) => ({ ...s, [k]: v }));

  const submit = () => {
    const quantity = parseFloat(f.quantity);
    const price = parseFloat(f.price_pln);
    const problem = !f.series.trim() ? "Podaj serię obligacji, np. EDO0334."
      : !quantity || quantity <= 0 ? "Podaj liczbę sztuk większą od zera."
      : isNaN(price) || price <= 0 ? "Podaj cenę zakupu jednej obligacji w PLN."
      : "";
    setError(problem);
    if (problem) return;
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
      <label className="field"><span>Dzień zakupu</span>
        <input className="cell" type="date" value={f.purchase_date} onChange={(e) => set("purchase_date", e.target.value)} />
      </label>
      <AccountSelect label="Konto" accounts={accounts} value={f.account_id} onChange={(v) => set("account_id", v)} />
      <label className="field"><span>Seria</span>
        <input className="cell" placeholder="np. EDO0334" maxLength="7" value={f.series} onChange={(e) => set("series", e.target.value.toUpperCase())} />
      </label>
      <label className="field"><span>Sztuki</span>
        <input className="cell narrow" type="number" step="1" min="1" value={f.quantity} onChange={(e) => set("quantity", e.target.value)} />
      </label>
      <label className="field"><span>Cena PLN</span>
        <input className="cell narrow" type="number" step="0.01" min="0" title="100 zł, a przy zamianie 99,90 zł" value={f.price_pln} onChange={(e) => set("price_pln", e.target.value)} onKeyDown={(e) => e.key === "Enter" && submit()} />
      </label>
      <button className="primary" onClick={submit} disabled={busy}>Dodaj obligacje</button>
      <input ref={fileRef} type="file" accept=".pdf" className="hidden-file" onChange={onPick} />
      <button onClick={() => fileRef.current?.click()} disabled={busy}
        title="Zapas, gdy automatyczne pobranie z obligacjeskarbowe.pl zawiedzie">
        Wgraj tabelę odsetkową (PDF)
      </button>
      {error && <p className="form-error" role="alert">{error}</p>}
    </div>
  );
}
