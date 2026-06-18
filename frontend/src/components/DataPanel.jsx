export default function DataPanel({ backups, onBackup, busy }) {
  const list = backups?.backups || [];
  return (
    <div>
      <div className="data-actions">
        <a className="btn" href="/api/export/transactions.csv">⬇ Eksport transakcji (CSV)</a>
        <a className="btn" href="/api/export/db">⬇ Pobierz całą bazę (.db)</a>
        <button className="primary" onClick={onBackup} disabled={busy}>Backup teraz (na serwerze)</button>
      </div>
      <p className="tag" style={{ margin: "12px 0 18px" }}>
        Automatyczny backup co noc (pora i retencja ustawiane w <code>docker-compose.yml</code>) do{" "}
        <code>{backups?.dir || "data/backup"}</code>.
      </p>
      {list.length === 0 ? (
        <div className="spinner">Brak kopii zapasowych — kliknij „Backup teraz".</div>
      ) : (
        <table>
          <thead><tr><th>Plik</th><th>Rozmiar</th><th>Data</th></tr></thead>
          <tbody>
            {list.map((b) => (
              <tr key={b.file}>
                <td>{b.file}</td>
                <td>{b.size_kb} KB</td>
                <td>{b.modified.replace("T", " ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
