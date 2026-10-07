import { useState } from "react";
import { fmtPln } from "../format.js";
import AccountSelect from "./AccountSelect.jsx";

export default function CashPanel({ cash, accounts, defaultAccount, onAdd, onDelete }) {
  const today = new Date().toISOString().slice(0, 10);
  const [form, setForm] = useState({ ts: today, kind: "deposit", amount: "", account_id: defaultAccount });
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const submit = () => {
    const amount = parseFloat(form.amount);
    if (!amount || amount <= 0) return;
    onAdd({ ts: form.ts, kind: form.kind, amount, account_id: form.account_id });
    setForm({ ...form, amount: "" });
  };
  const flows = cash?.flows || [];
  const multi = (accounts || []).length > 1;
  const accountName = (id) => accounts.find((a) => a.id === id)?.name || "—";
  return (
    <div>
      <div className="cash-summary">
        <div>
          <div className="label">Saldo gotówki</div>
          <div className="value">{fmtPln(cash?.balance_pln)}</div>
        </div>
        <div>
          <div className="label">Wpłacono netto</div>
          <div className="value small">{fmtPln(cash?.net_deposits_pln)}</div>
        </div>
      </div>

      <div className="cash-form">
        <input className="cell" type="date" value={form.ts} onChange={(e) => set("ts", e.target.value)} />
        <AccountSelect accounts={accounts} value={form.account_id} onChange={(v) => set("account_id", v)} />
        <select className="cell narrow" value={form.kind} onChange={(e) => set("kind", e.target.value)}>
          <option value="deposit">Wpłata</option>
          <option value="withdrawal">Wypłata</option>
        </select>
        <input
          className="cell"
          type="number"
          step="0.01"
          placeholder="kwota PLN"
          value={form.amount}
          onChange={(e) => set("amount", e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
        />
        <button className="primary" onClick={submit}>Dodaj</button>
      </div>

      {flows.length === 0 ? (
        <div className="spinner">Brak wpłat/wypłat. Dodaj wpłatę, aby śledzić niezainwestowaną gotówkę.</div>
      ) : (
        <table>
          <thead>
            <tr><th>Data</th><th className="txt">Typ</th>{multi && <th className="txt">Konto</th>}<th>Kwota</th><th></th></tr>
          </thead>
          <tbody>
            {flows.map((f) => (
              <tr key={f.id}>
                <td>{(f.ts || "").slice(0, 10)}</td>
                <td className="txt">
                  <span className={`op-chip ${f.kind === "deposit" ? "buy" : "sell"}`}>
                    {f.kind === "deposit" ? "Wpłata" : "Wypłata"}
                  </span>
                </td>
                {multi && <td className="txt">{accountName(f.account_id)}</td>}
                {/* Wpłata to przepływ, nie zysk — bez zieleni. */}
                <td className="flow">{fmtPln(f.amount_pln)}</td>
                <td><button onClick={() => onDelete(f.id)}>Usuń</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
