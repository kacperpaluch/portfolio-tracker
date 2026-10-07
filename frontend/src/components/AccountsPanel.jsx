import { useState } from "react";

// Konta inwestycyjne: nazwa + czy zyski są opodatkowane (19%). IKE/IKZE zostają bez podatku.
export default function AccountsPanel({ accounts, onSave, busy }) {
  const [draft, setDraft] = useState({});
  const [fresh, setFresh] = useState({ name: "", taxed: true });
  const valueOf = (a, field) => draft[a.id]?.[field] ?? a[field];
  const edit = (id, field, val) => setDraft((d) => ({ ...d, [id]: { ...d[id], [field]: val } }));
  const add = () => {
    if (!fresh.name.trim()) return;
    onSave(null, { name: fresh.name.trim(), taxed: fresh.taxed });
    setFresh({ name: "", taxed: true });
  };
  return (
    <table>
      <thead>
        <tr><th className="txt">Konto</th><th className="txt">Podatek od zysków</th><th></th></tr>
      </thead>
      <tbody>
        {accounts.map((a) => (
          <tr key={a.id}>
            <td className="txt"><input className="cell" aria-label="Nazwa konta" value={valueOf(a, "name")} onChange={(e) => edit(a.id, "name", e.target.value)} /></td>
            <td className="txt">
              <label><input type="checkbox" checked={!!valueOf(a, "taxed")} onChange={(e) => edit(a.id, "taxed", e.target.checked)} /> opodatkowane 19%</label>
            </td>
            <td><button disabled={busy} onClick={() => onSave(a.id, { name: String(valueOf(a, "name")).trim(), taxed: !!valueOf(a, "taxed") })}>Zapisz</button></td>
          </tr>
        ))}
        <tr>
          <td className="txt"><input className="cell" placeholder="nowe konto, np. Zwykłe" value={fresh.name} onChange={(e) => setFresh({ ...fresh, name: e.target.value })} onKeyDown={(e) => e.key === "Enter" && add()} /></td>
          <td className="txt">
            <label><input type="checkbox" checked={fresh.taxed} onChange={(e) => setFresh({ ...fresh, taxed: e.target.checked })} /> opodatkowane 19%</label>
          </td>
          <td><button className="primary" disabled={busy} onClick={add}>Dodaj konto</button></td>
        </tr>
      </tbody>
    </table>
  );
}
