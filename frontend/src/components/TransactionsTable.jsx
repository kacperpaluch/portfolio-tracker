import { useMemo, useState } from "react";
import { fmtPln, fmtDate } from "../format.js";

export default function TransactionsTable({ transactions, instruments, onOpen, onDelete, onUpdate }) {
  const [query, setQuery] = useState("");
  const [type, setType] = useState("ALL");
  const [editing, setEditing] = useState(null);
  const [draft, setDraft] = useState(null);
  const [saving, setSaving] = useState(false);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return (transactions || []).filter((tx) => {
      const matchesType = type === "ALL" || tx.type === type;
      const haystack = `${tx.name || ""} ${tx.ticker || ""} ${tx.isin || ""} ${tx.market || ""} ${tx.broker_order_id || ""} ${tx.note || ""}`.toLowerCase();
      return matchesType && (!needle || haystack.includes(needle));
    });
  }, [transactions, query, type]);

  const beginEdit = (tx) => {
    setEditing(tx.id);
    setDraft({
      ts: tx.ts.slice(0, 10),
      isin: tx.isin,
      type: tx.type,
      quantity: tx.quantity,
      price_pln: tx.price_pln,
      commission_pln: tx.commission_pln || 0,
      note: tx.note || "",
    });
  };
  const set = (key, value) => setDraft((current) => ({ ...current, [key]: value }));
  const save = async () => {
    const body = {
      ...draft,
      quantity: parseFloat(draft.quantity),
      price_pln: parseFloat(draft.price_pln),
      commission_pln: parseFloat(draft.commission_pln) || 0,
      note: draft.note.trim() || null,
    };
    if (!body.isin || !body.quantity || body.quantity <= 0 || Number.isNaN(body.price_pln) || body.price_pln < 0) return;
    setSaving(true);
    try {
      await onUpdate(editing, body);
      setEditing(null);
      setDraft(null);
    } finally {
      setSaving(false);
    }
  };

  if (!transactions || transactions.length === 0)
    return <div className="spinner">Brak transakcji. Dodaj pierwszą operację ręcznie.</div>;
  return (
    <div>
      <div className="table-tools">
        <input className="cell" type="search" placeholder="Szukaj po nazwie, tickerze, ISIN lub notatce…" value={query} onChange={(e) => setQuery(e.target.value)} />
        <select className="cell narrow" value={type} onChange={(e) => setType(e.target.value)}>
          <option value="ALL">Wszystkie</option>
          <option value="BUY">Kupna</option>
          <option value="SELL">Sprzedaże</option>
        </select>
        <span>{filtered.length} z {transactions.length}</span>
      </div>
      <table>
        <thead>
          <tr>
            <th>Data</th><th className="txt">Instrument</th><th className="txt">Typ</th><th>Szt.</th><th>Cena</th><th>Wartość</th><th className="txt">Notatka</th><th></th>
          </tr>
        </thead>
        <tbody>
          {filtered.map((t) => editing === t.id ? (
            <tr key={t.id} className="editing-row">
              <td><input className="cell edit-date" type="date" value={draft.ts} onChange={(e) => set("ts", e.target.value)} /></td>
              <td>
                <select className="cell edit-instrument" value={draft.isin} onChange={(e) => set("isin", e.target.value)}>
                  {instruments.map((i) => <option key={i.isin} value={i.isin}>{i.name}</option>)}
                </select>
              </td>
              <td>
                <select className="cell narrow" value={draft.type} onChange={(e) => set("type", e.target.value)}>
                  <option value="BUY">Kupno</option><option value="SELL">Sprzedaż</option>
                </select>
              </td>
              <td><input className="cell edit-number" type="number" step="any" value={draft.quantity} onChange={(e) => set("quantity", e.target.value)} /></td>
              <td><input className="cell edit-number" type="number" step="any" value={draft.price_pln} onChange={(e) => set("price_pln", e.target.value)} /></td>
              <td><input className="cell edit-number" type="number" step="0.01" title="Prowizja" value={draft.commission_pln} onChange={(e) => set("commission_pln", e.target.value)} /></td>
              <td><input className="cell edit-note" value={draft.note} onChange={(e) => set("note", e.target.value)} /></td>
              <td>
                <div className="row-actions">
                  <button disabled={saving} onClick={save}>Zapisz</button>
                  <button disabled={saving} onClick={() => setEditing(null)}>Anuluj</button>
                </div>
              </td>
            </tr>
          ) : (
            <tr key={t.id}>
              <td>
                {fmtDate(t.ts)}
                {t.settlement_date && <div className="tag">Rozl. {t.settlement_date}</div>}
              </td>
              <td className="txt">
                <button className="instrument-link" onClick={() => onOpen?.(t.isin)}>{t.name || t.isin}</button>
                <div className="tag">{t.ticker || t.isin}</div>
                {(t.market || t.broker_order_id) && (
                  <div className="tag">{[t.market, t.broker_order_id && `zlec. ${t.broker_order_id}`].filter(Boolean).join(" · ")}</div>
                )}
              </td>
              {/* Typ operacji to nie wynik — zieleń i czerwień zostają zarezerwowane dla zysku/straty. */}
              <td className="txt">
                <span className={`op-chip ${t.type === "BUY" ? "buy" : "sell"}`}>
                  {t.type === "BUY" ? "Kupno" : "Sprzedaż"}
                </span>
              </td>
              <td>{t.quantity}</td>
              <td>
                {fmtPln(t.price_pln)}
                {t.native_price != null && (
                  <div className="tag">
                    {t.native_price} {t.native_currency}{t.fx_rate != null ? ` · FX ${t.fx_rate}` : ""}
                  </div>
                )}
              </td>
              <td className="flow">
                {t.type === "BUY" ? "−" : "+"}{fmtPln(t.value_pln)}
              </td>
              <td className="txt tx-note-cell">{t.note || "—"}</td>
              <td>
                <div className="row-actions">
                  <button onClick={() => beginEdit(t)}>Edytuj</button>
                  <button className="danger-button" onClick={() => onDelete?.(t.id)}>Usuń</button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {filtered.length === 0 && <div className="spinner">Brak transakcji spełniających filtry.</div>}
    </div>
  );
}
