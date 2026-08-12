// Problemy tego samego typu (np. „brak klasy aktywów" dla 9 ETF-ów) zwijamy w jeden
// wiersz — inaczej lista rozpycha stronę o kilkanaście identycznie brzmiących kart.
function groupIssues(issues) {
  const byCode = new Map();
  for (const issue of issues) {
    const group = byCode.get(issue.code);
    if (group) group.items.push(issue);
    else byCode.set(issue.code, { ...issue, items: [issue] });
  }
  return [...byCode.values()];
}

function IssueBody({ issue }) {
  return (
    <>
      <p>{issue.detail}</p>
      {issue.action && <small>{issue.action}</small>}
    </>
  );
}

export default function DataQualityPanel({ quality, busy, onRefresh }) {
  if (!quality) return <div className="spinner">Trwa sprawdzanie jakości danych…</div>;
  const { status, summary, stats, issues } = quality;
  const label = status === "good" ? "Dane są spójne" : status === "error" ? "Wymagają uwagi" : "Drobne braki";
  const groups = groupIssues(issues);

  return (
    <div>
      <div className="quality-overview">
        <div className={`quality-score ${status}`}>
          <span>{status === "good" ? "OK" : summary.issues}</span>
          <div><strong>{label}</strong><small>Kontrola z {quality.checked_at}</small></div>
        </div>
        <div className="quality-stat"><span>Pozycje</span><strong>{stats.open_positions}</strong></div>
        <div className="quality-stat"><span>Transakcje</span><strong>{stats.transactions}</strong></div>
        <div className="quality-stat"><span>Ostatnia cena</span><strong>{stats.latest_price_date || "—"}</strong></div>
        <button className="secondary" disabled={busy} onClick={onRefresh}>Sprawdź ponownie</button>
      </div>

      {issues.length === 0 ? (
        <div className="quality-empty">Ceny, kursy, konfiguracja, alokacja i księga gotówki są spójne.</div>
      ) : (
        <div className="quality-list">
          {groups.map((group) => group.items.length === 1 ? (
            <div className={`quality-issue ${group.severity}`} key={group.code}>
              <span className="quality-indicator" />
              <div>
                <strong>{group.title}</strong>
                <IssueBody issue={group} />
              </div>
            </div>
          ) : (
            <details className={`quality-issue grouped ${group.severity}`} key={group.code}>
              <summary>
                <span className="quality-indicator" />
                <strong>{group.title}</strong>
                <em>{group.items.length}</em>
              </summary>
              <div className="quality-sublist">
                {group.items.map((issue, index) => (
                  <div key={issue.entity || index}>
                    <IssueBody issue={issue} />
                  </div>
                ))}
              </div>
            </details>
          ))}
        </div>
      )}
    </div>
  );
}
