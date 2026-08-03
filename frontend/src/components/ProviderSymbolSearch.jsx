import { useState } from "react";
import { api } from "../api.js";

export default function ProviderSymbolSearch({ source, defaultQuery, onSelect }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  if (!['eodhd', 'alphavantage'].includes(source)) return null;

  const show = () => {
    setQuery(defaultQuery || "");
    setResults([]);
    setError("");
    setOpen(true);
  };

  const search = async () => {
    if (!query.trim()) {
      setError("Wpisz ISIN, nazwę albo symbol.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const data = await api.searchProviderSymbols(source, query.trim());
      setResults(data.results || []);
      if (!data.results?.length) setError("Brak pasujących instrumentów.");
    } catch (err) {
      setResults([]);
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const choose = (result) => {
    onSelect(result);
    setOpen(false);
  };

  return (
    <>
      <button type="button" className="symbol-search-trigger" onClick={show}>Wyszukaj</button>
      {open && (
        <div className="modal-backdrop" role="presentation">
          <div className="modal symbol-search-modal" role="dialog" aria-modal="true" aria-label="Wyszukaj symbol">
            <div className="modal-head">
              <div>
                <div className="eyebrow">{source === 'eodhd' ? 'EODHD' : 'Alpha Vantage'}</div>
                <h2>Wyszukaj symbol</h2>
                <p className="mapping-intro">
                  {source === 'eodhd'
                    ? 'Najpewniejszy wynik daje ISIN. Możesz też użyć nazwy lub symbolu.'
                    : 'Wyszukuj po nazwie ETF-u lub tickerze. Alpha Vantage nie wyszukuje niezawodnie po ISIN-ie.'}
                </p>
              </div>
              <button type="button" onClick={() => setOpen(false)} disabled={busy}>Zamknij</button>
            </div>
            <div className="symbol-search-form">
              <input className="cell" autoFocus value={query}
                placeholder={source === 'eodhd' ? 'ISIN, nazwa lub symbol' : 'Nazwa lub symbol'}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={(event) => { if (event.key === 'Enter') { event.preventDefault(); search(); } }} />
              <button type="button" className="primary" onClick={search} disabled={busy}>
                {busy ? 'Szukam…' : 'Szukaj'}
              </button>
            </div>
            {error && <p className="mapping-error" role="alert">{error}</p>}
            {results.length > 0 && (
              <div className="symbol-results">
                {results.map((result, index) => (
                  <button type="button" className="symbol-result"
                    key={`${result.symbol}-${result.region}-${index}`} onClick={() => choose(result)}>
                    <strong>{result.symbol}</strong>
                    <span>{result.name}</span>
                    <small>{[result.exchange || result.region, result.currency, result.isin, result.type]
                      .filter(Boolean).join(' · ')}</small>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
