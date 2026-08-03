import { useState } from "react";

const initialDraft = (instruments) => instruments.map((item) => ({
  ...item,
  isin: "",
  name: item.symbol,
  ticker: "",
  currency: item.currency || "",
  source: "yfinance",
}));

export default function BrokerMappingModal({ instruments, filename, busy, onCancel, onSave }) {
  const [drafts, setDrafts] = useState(() => initialDraft(instruments));
  const [validation, setValidation] = useState("");

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
                <span>Ticker Yahoo</span>
                <input className="cell" placeholder="np. ABCD.DE" value={item.ticker}
                  onChange={(event) => edit(index, "ticker", event.target.value)} />
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
        <p className="mapping-help">ISIN i ticker sprawdź na stronie emitenta lub giełdy. Aplikacja nie zgaduje tych danych.</p>
      </form>
    </div>
  );
}
