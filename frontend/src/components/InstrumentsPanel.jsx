import { useState } from "react";
import ProviderSymbolSearch from "./ProviderSymbolSearch.jsx";

export default function InstrumentsPanel({ instruments, onSave }) {
  const [draft, setDraft] = useState({});
  const edit = (isin, field, val) => setDraft((d) => ({ ...d, [isin]: { ...d[isin], [field]: val } }));
  const valueOf = (inst, field) => draft[inst.isin]?.[field] ?? inst[field] ?? "";
  const changeSource = (inst, nextSource) => setDraft((current) => {
    const item = current[inst.isin] || {};
    const previousSource = item.source ?? inst.source ?? "yfinance";
    const previousTicker = item.ticker ?? inst.ticker ?? "";
    const previousCurrency = item.currency ?? inst.currency ?? "";
    const mappings = {
      ...(inst.provider_mappings || {}),
      ...(item.provider_mappings || {}),
    };
    if (previousTicker) {
      mappings[previousSource] = { ticker: previousTicker, currency: previousCurrency };
    }
    const target = mappings[nextSource];
    return {
      ...current,
      [inst.isin]: {
        ...item,
        source: nextSource,
        ticker: target?.ticker || "",
        currency: target?.currency || previousCurrency,
        provider_mappings: mappings,
      },
    };
  });
  const save = async (inst) => {
    await onSave(inst.isin, {
      name: valueOf(inst, "name"),
      ticker: valueOf(inst, "ticker"),
      source: valueOf(inst, "source") || "yfinance",
      currency: valueOf(inst, "currency"),
      category: valueOf(inst, "category"),
    });
    setDraft((current) => {
      const next = { ...current };
      delete next[inst.isin];
      return next;
    });
  };
  const tickerPlaceholder = (inst) => ({
    eodhd: "np. WEBN.XETRA",
    alphavantage: "np. WEBN.DEX",
    yfinance: "np. WEBN.DE",
  }[valueOf(inst, "source") || "yfinance"] || "symbol źródła");
  return (
    <table>
      <thead>
        <tr><th>Nazwa z importu</th><th>Nazwa własna</th><th>Ticker</th><th>Źródło</th><th>Kategoria</th><th>Waluta</th><th>Status</th><th></th></tr>
      </thead>
      <tbody>
        {instruments.map((inst) => (
          <tr key={inst.isin}>
            <td>{inst.imported_name || inst.name}<div className="tag">{inst.isin}</div></td>
            <td>
              <input className="cell" value={valueOf(inst, "name")} placeholder={inst.imported_name || inst.name}
                onChange={(e) => edit(inst.isin, "name", e.target.value)} />
            </td>
            <td>
              <input className="cell" value={valueOf(inst, "ticker")} placeholder={tickerPlaceholder(inst)}
                onChange={(e) => edit(inst.isin, "ticker", e.target.value)} />
              <ProviderSymbolSearch
                source={valueOf(inst, "source") || "yfinance"}
                defaultQuery={(valueOf(inst, "source") === "eodhd" ? inst.isin : valueOf(inst, "name"))}
                onSelect={(result) => {
                  edit(inst.isin, "ticker", result.symbol);
                  if (result.currency) edit(inst.isin, "currency", result.currency.toUpperCase());
                }}
              />
            </td>
            <td>
              <select className="cell narrow" value={valueOf(inst, "source") || "yfinance"}
                onChange={(e) => changeSource(inst, e.target.value)}>
                <option value="yfinance">yfinance</option>
                <option value="eodhd">EODHD</option>
                <option value="alphavantage">Alpha Vantage</option>
              </select>
            </td>
            <td>
              <input className="cell" list="cat-list" value={valueOf(inst, "category")} placeholder="np. Akcje"
                onChange={(e) => edit(inst.isin, "category", e.target.value)} />
            </td>
            <td>
              <input className="cell narrow" maxLength="3" value={valueOf(inst, "currency")} placeholder="EUR"
                onChange={(e) => edit(inst.isin, "currency", e.target.value.toUpperCase())} />
            </td>
            <td>{inst.needs_config ? <span className="badge">do uzupełnienia</span> : <span className="pos">OK</span>}</td>
            <td>
              <button onClick={() => save(inst).catch(() => {})}>Zapisz</button>
            </td>
          </tr>
        ))}
      </tbody>
      <datalist id="cat-list">
        <option value="Akcje" /><option value="Obligacje" /><option value="Surowce" />
        <option value="Nieruchomości" /><option value="Gotówka" />
      </datalist>
    </table>
  );
}
