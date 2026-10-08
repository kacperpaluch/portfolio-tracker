// Wybór konta dla nowej operacji. Przy jednym koncie nie ma czego wybierać — nic nie rysuje.
export default function AccountSelect({ accounts, value, onChange, label }) {
  if (!accounts || accounts.length < 2) return null;
  const select = (
    <select className="cell narrow" title="Konto" aria-label="Konto" value={value} onChange={(e) => onChange(Number(e.target.value))}>
      {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
    </select>
  );
  return label ? <label className="field"><span>{label}</span>{select}</label> : select;
}
