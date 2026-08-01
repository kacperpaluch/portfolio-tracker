import { useRef } from "react";

function ageLabel(hours) {
  if (hours == null) return "—";
  if (hours < 1) return "przed chwilą";
  if (hours < 24) return `${Math.round(hours)} godz. temu`;
  const days = Math.round(hours / 24);
  return `${days} ${days === 1 ? "dzień" : "dni"} temu`;
}

export default function DataPanel({ backups, onBackup, onRestore, onRestoreUpload, busy }) {
  const list = backups?.backups || [];
  const uploadRef = useRef();
  const latest = backups?.latest;
  const validation = backups?.latest_validation;
  const schedule = backups?.schedule;

  const restore = (filename) => {
    const answer = window.prompt(
      `Przywrócenie „${filename}" zastąpi aktualną bazę.\n\nPrzed operacją aplikacja automatycznie utworzy kopię bezpieczeństwa.\nWpisz PRZYWRÓĆ, aby kontynuować:`,
    );
    if (answer === "PRZYWRÓĆ") onRestore(filename);
  };

  const restoreUpload = (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    const answer = window.prompt(
      `Plik „${file.name}" zostanie najpierw sprawdzony, a następnie zastąpi aktualną bazę.\n\nWpisz PRZYWRÓĆ, aby kontynuować:`,
    );
    if (answer === "PRZYWRÓĆ") onRestoreUpload(file);
  };

  return (
    <div>
      <div className={`backup-health ${backups?.healthy ? "good" : "warning"}`}>
        <div className="backup-health-icon">{backups?.healthy ? "OK" : "!"}</div>
        <div>
          <span className="sync-kicker">Stan ochrony danych</span>
          <strong>
            {backups?.healthy
              ? `Ostatnia poprawna kopia ${ageLabel(latest?.age_hours)}`
              : latest
                ? `Kopia wymaga uwagi — ${ageLabel(latest.age_hours)}`
                : "Nie utworzono jeszcze kopii zapasowej"}
          </strong>
          <p>
            {validation?.valid
              ? `Integralność SQLite potwierdzona · ${validation.counts.transactions} transakcji · SHA-256 ${validation.sha256.slice(0, 10)}…`
              : validation?.error || `Ostrzeżenie pojawi się po ${backups?.stale_after_hours || 36} godzinach bez nowej kopii.`}
          </p>
        </div>
      </div>

      <div className="backup-facts">
        <div><span>Harmonogram</span><strong>{schedule ? `${String(schedule.hour).padStart(2, "0")}:${String(schedule.minute).padStart(2, "0")}` : "Wyłączony"}</strong><small>{schedule?.timezone || "wyzwalanie przez API"}</small></div>
        <div><span>Retencja</span><strong>{backups?.keep ?? 14} kopii</strong><small>najstarsze usuwane automatycznie</small></div>
        <div><span>Lokalizacja</span><strong>Named volume</strong><small title={backups?.dir}>{backups?.dir || "data/backup"}</small></div>
      </div>

      <div className="data-actions backup-actions">
        <button className="primary" onClick={onBackup} disabled={busy}>Utwórz backup teraz</button>
        <a className="btn" href="/api/export/db">Pobierz bieżącą bazę</a>
        <a className="btn" href="/api/export/transactions.csv">Eksportuj transakcje</a>
        <button className="secondary" onClick={() => uploadRef.current?.click()} disabled={busy}>Przywróć z pliku .db</button>
        <input ref={uploadRef} type="file" accept=".db,.sqlite,.sqlite3" className="hidden-file" onChange={restoreUpload} />
      </div>

      {list.length === 0 ? (
        <div className="quality-empty backup-empty">Utwórz pierwszą kopię, aby uruchomić kontrolę integralności i możliwość szybkiego odtworzenia.</div>
      ) : (
        <div className="backup-table-wrap">
          <table>
            <thead><tr><th>Kopia</th><th>Rozmiar</th><th>Utworzona</th><th>Wiek</th><th></th></tr></thead>
            <tbody>
              {list.map((backup, index) => (
                <tr key={backup.file}>
                  <td>
                    <strong>{backup.file}</strong>
                    <div className="tag">
                      {backup.kind === "pre_restore" ? "Kopia bezpieczeństwa sprzed odtworzenia" : index === 0 ? "Najnowsza kopia" : "Kopia automatyczna/ręczna"}
                    </div>
                  </td>
                  <td>{backup.size_kb} KB</td>
                  <td>{backup.modified.replace("T", " ")}</td>
                  <td>{ageLabel(backup.age_hours)}</td>
                  <td>
                    <div className="row-actions">
                      <a className="table-link" href={`/api/backups/${encodeURIComponent(backup.file)}/download`}>Pobierz</a>
                      <button disabled={busy} onClick={() => restore(backup.file)}>Przywróć</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="backup-note">
        Każda kopia powstaje przez SQLite Online Backup API i jest automatycznie sprawdzana
        przez <code>integrity_check</code>. Przed odtworzeniem obecna baza zawsze trafia do
        osobnego pliku <code>portfolio-pre-restore-…</code>.
      </p>
    </div>
  );
}
