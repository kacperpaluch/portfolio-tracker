import { useState } from "react";
import ProviderSymbolSearch from "./ProviderSymbolSearch.jsx";

const initialDraft = (instruments) => instruments.map((item) => ({
  ...item,
  isin: "",
  name: item.symbol,
  ticker: "",
  currency: item.currency || "",
  source: "eodhd",
}));

export default function BrokerMappingModal({ instruments, filename, busy, onCancel, onSave }) {
  const [drafts, setDrafts] = useState(() => initialDraft(instruments));
  const [validation, setValidation] = useState("");
  const tickerHelp = (source) => ({
    eodhd: ["Symbol EODHD", "np. WEBN.XETRA"],
    alphavantage: ["Symbol Alpha Vantage", "np. WEBN.DEX"],
    yfinance: ["Ticker Yahoo", "np. WEBN.DE"],
  }[source]);

  const edit = (index, field, value) => {
    setDrafts((current) => current.map((item, itemIndex) => (
      itemIndex === index ? { ...item, [field]: value } : item
    )));
  };

  const submit = (event) => {
    event.preventDefault();
    const mappings = drafts.map((item) => ({
      ...item,
      isin: item.isin.trim().toUpperCase(),
      name: item.name.trim(),
      ticker: item.ticker.trim(),
      currency: item.currency.trim().toUpperCase(),
    }));
    const invalid = mappings.find((item) => (
      !/^[A-Z]{2}[A-Z0-9]{9}[0-9]$/.test(item.isin)
      || !item.name
      || !item.ticker
      || !/^[A-Z]{3}$/.test(item.currency)
    ));
    if (invalid) {
      setValidation("Uzupełnij poprawny ISIN, nazwę, ticker oraz trzyznakowy kod waluty.");
      return;
    }
    setValidation("");
    onSave(mappings);
  };

  return (
    <div className="modal-backdrop" role="presentation">
      <form className="modal broker-mapping-modal" onSubmit={submit}>
        <div className="modal-head">
          <div>
            <div className="eyebrow">Import eMAKLER</div>
            <h2>Uzupełnij nowe instrumenty</h2>
            <p className="mapping-intro">
              Plik <strong>{filename}</strong> nie zawiera ISIN-ów. Dane zapiszą się w Twojej bazie,
              a import zostanie automatycznie ponowiony.
            </p>
          </div>
          <div className="modal-actions">
            <button type="button" onClick={onCancel} disabled={busy}>Anuluj</button>
            <button type="submit" className="primary" disabled={busy}>Zapisz i importuj</button>
          </div>
        </div>

        <div className="mapping-list">
          {drafts.map((item, index) => (
            <fieldset className="mapping-card" key={`${item.broker}-${item.symbol}-${item.exchange}`}>
              <legend>{item.symbol}</legend>
              <div className="mapping-origin">
                <span>{item.exchange}</span>
                <span>{item.broker}</span>
              </div>
              <label>
                <span>ISIN</span>
                <input className="cell" autoFocus={index === 0} maxLength="12" placeholder="12-znakowy ISIN"
                  value={item.isin} onChange={(event) => edit(index, "isin", event.target.value)} />
              </label>
              <label>
                <span>Nazwa instrumentu</span>
                <input className="cell" value={item.name}
                  onChange={(event) => edit(index, "name", event.target.value)} />
              </label>
              <label>
                <span>Źródło notowań</span>
                <select className="cell" value={item.source}
                  onChange={(event) => edit(index, "source", event.target.value)}>
                  <option value="eodhd">EODHD</option>
                  <option value="alphavantage">Alpha Vantage</option>
                  <option value="yfinance">Yahoo Finance</option>
                </select>
              </label>
              <label>
                <span>{tickerHelp(item.source)[0]}</span>
                <input className="cell" placeholder={tickerHelp(item.source)[1]} value={item.ticker}
                  onChange={(event) => edit(index, "ticker", event.target.value)} />
                <ProviderSymbolSearch
                  source={item.source}
                  defaultQuery={item.source === "eodhd" ? (item.isin || item.symbol) : (item.name || item.symbol)}
                  onSelect={(result) => {
                    edit(index, "ticker", result.symbol);
                    if (result.currency) edit(index, "currency", result.currency.toUpperCase());
                    if (result.isin) edit(index, "isin", result.isin.toUpperCase());
                    if (result.name && (!item.name || item.name === item.symbol)) edit(index, "name", result.name);
                  }}
                />
              </label>
              <label>
                <span>Waluta</span>
                <input className="cell narrow" maxLength="3" placeholder="EUR" value={item.currency}
                  onChange={(event) => edit(index, "currency", event.target.value)} />
              </label>
            </fieldset>
          ))}
        </div>
        {validation && <p className="mapping-error" role="alert">{validation}</p>}
        <p className="mapping-help">ISIN i symbol źródła sprawdź przed zapisem. Każdy provider używa innego sufiksu giełdy.</p>
      </form>
    </div>
  );
}
