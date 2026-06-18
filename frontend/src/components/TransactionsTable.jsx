import { fmtPln, fmtDate } from "../format.js";

export default function TransactionsTable({ transactions, onOpen, onDelete }) {
  if (!transactions || transactions.length === 0)
    return <div className="spinner">Brak transakcji. Dodaj ręcznie lub zaimportuj CSV.</div>;
  return (
    <table>
      <thead>
        <tr>
          <th>Data</th><th>Instrument</th><th>Typ</th><th>Szt.</th><th>Cena</th><th>Wartość</th><th></th>
        </tr>
      </thead>
      <tbody>
        {transactions.map((t) => (
          <tr key={t.id}>
            <td>{fmtDate(t.ts)}</td>
            <td>
              <span className="link" onClick={() => onOpen?.(t.isin)}>{t.name || t.isin}</span>
              <div className="tag">{t.ticker || t.isin}</div>
            </td>
            <td className={t.type === "BUY" ? "pos" : "neg"}>{t.type === "BUY" ? "Kupno" : "Sprzedaż"}</td>
            <td>{t.quantity}</td>
            <td>{fmtPln(t.price_pln)}</td>
            <td className={t.type === "BUY" ? "neg" : "pos"}>
              {t.type === "BUY" ? "−" : "+"}{fmtPln(t.value_pln)}
            </td>
            <td><button onClick={() => onDelete?.(t.id)}>Usuń</button></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
