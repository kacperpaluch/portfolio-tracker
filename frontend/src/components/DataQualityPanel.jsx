export default function DataQualityPanel({ quality, busy, onRefresh }) {
  if (!quality) return <div className="spinner">Trwa sprawdzanie jakości danych…</div>;
  const { status, summary, stats, issues } = quality;
  const label = status === "good" ? "Dane są spójne" : status === "error" ? "Wymagają uwagi" : "Drobne braki";

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
          {issues.map((issue, index) => (
            <div className={`quality-issue ${issue.severity}`} key={`${issue.code}-${issue.entity || index}`}>
              <span className="quality-indicator" />
              <div>
                <strong>{issue.title}</strong>
                <p>{issue.detail}</p>
                {issue.action && <small>{issue.action}</small>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
