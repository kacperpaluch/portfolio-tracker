import React, { useEffect, useRef, useState } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "./api.js";

const plnFmt = new Intl.NumberFormat("pl-PL", { style: "currency", currency: "PLN" });
const fmtPln = (v) => (v == null ? "—" : plnFmt.format(v));
const fmtPct = (v) => (v == null ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(2)}%`);
const cls = (v) => (v == null ? "muted" : v >= 0 ? "pos" : "neg");
const fmtDate = (ts) => (ts ? ts.slice(0, 16).replace("T", " ") : "—");

function Cards({ totals }) {
  const t = totals || {};
  const accountValue = t.portfolio_value_pln ?? t.value_pln ?? t.value_pln_partial;
  return (
    <div className="cards">
      <div className="card">
        <div className="label">Wartość konta</div>
        <div className="value">{fmtPln(accountValue)}</div>
        <div className="tag">ETF {fmtPln(t.value_pln ?? t.value_pln_partial)} + gotówka {fmtPln(t.cash_pln)}</div>
      </div>
      <div className="card">
        <div className="label">Zysk całkowity</div>
        <div className={`value ${cls(t.total_pl_pln)}`}>{fmtPln(t.total_pl_pln)}</div>
        <div className="tag">
          niezreal. <span className={cls(t.unrealized_pl_pln)}>{fmtPln(t.unrealized_pl_pln)}</span>
          {" · "}zreal. <span className={cls(t.realized_pl_pln)}>{fmtPln(t.realized_pl_pln)}</span>
        </div>
      </div>
      <div className="card">
        <div className="label">XIRR</div>
        <div className={`value ${cls(t.xirr)}`}>{t.xirr == null ? "—" : fmtPct(t.xirr * 100)}</div>
        <div className="tag">zwrot z Twojego kapitału (z timingiem wpłat)</div>
      </div>
      <div className="card">
        <div className="label">TWR</div>
        <div className={`value ${cls(t.twr)}`}>{t.twr == null ? "—" : fmtPct(t.twr * 100)}</div>
        <div className="tag">wynik portfela (bez wpływu timingu wpłat)</div>
      </div>
      <div className="card">
        <div className="label">Gotówka</div>
        <div className="value">{fmtPln(t.cash_pln)}</div>
        <div className="tag">wpłacono netto {fmtPln(t.net_deposits_pln)}</div>
      </div>
    </div>
  );
}

const LABELS = { value_pln: "Wartość konta", benchmark_pln: "Benchmark" };
const DETAIL_LABELS = {
  value_pln: "Wartość (rzeczywista)",
  value_const_fx: "Wartość bez zmian kursu",
  cost_pln: "Koszt (wpłacone)",
};

function HistoryChart({ data }) {
  if (!data || data.length === 0)
    return <div className="spinner">Brak danych historycznych — kliknij „Backfill historii".</div>;
  return (
    <ResponsiveContainer width="100%" height={300}>
      <ComposedChart data={data} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
        <defs>
          <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#4493f8" stopOpacity={0.35} />
            <stop offset="100%" stopColor="#4493f8" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="#2c3845" strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="date" tick={{ fill: "#8b97a6", fontSize: 11 }} minTickGap={40} stroke="#2c3845" />
        <YAxis
          tick={{ fill: "#8b97a6", fontSize: 11 }}
          stroke="#2c3845"
          width={70}
          tickFormatter={(v) => `${Math.round(v / 1000)}k`}
        />
        <Tooltip
          contentStyle={{ background: "#1a212b", border: "1px solid #2c3845", borderRadius: 8, color: "#e6edf3" }}
          formatter={(v, name) => [fmtPln(v), LABELS[name] || name]}
        />
        <Legend formatter={(name) => LABELS[name] || name} wrapperStyle={{ fontSize: 12 }} />
        <Area type="monotone" dataKey="value_pln" stroke="#4493f8" strokeWidth={2} fill="url(#g)" />
        <Line type="monotone" dataKey="benchmark_pln" stroke="#d29922" strokeWidth={2} strokeDasharray="5 4" dot={false} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

function InstrumentDetail({ data, onClose }) {
  if (!data) return null;
  const rows = data.rows || [];
  const isPln = data.currency === "PLN";
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <div>
            <h2>{data.name}</h2>
            <div className="tag">
              {data.ticker || data.isin} · {data.currency}
              {data.category ? ` · ${data.category}` : ""} · {data.isin}
            </div>
          </div>
          <button onClick={onClose}>Zamknij ✕</button>
        </div>

        {rows.length === 0 ? (
          <div className="spinner">Brak historii wycen. Uruchom „Backfill historii".</div>
        ) : (
          <>
            {data.summary && (
              <div className="attrib">
                <div className="attrib-item">
                  <div className="label">Zysk / strata</div>
                  <div className={`value ${cls(data.summary.total_pl_pln)}`}>{fmtPln(data.summary.total_pl_pln)}</div>
                </div>
                <div className="attrib-item">
                  <div className="label">z instrumentu</div>
                  <div className={`value small ${cls(data.summary.instrument_pl_pln)}`}>{fmtPln(data.summary.instrument_pl_pln)}</div>
                </div>
                <div className="attrib-item">
                  <div className="label">z waluty (kurs PLN)</div>
                  <div className={`value small ${cls(data.summary.fx_pl_pln)}`}>{fmtPln(data.summary.fx_pl_pln)}</div>
                </div>
                {!isPln && data.summary.baseline_fx && (
                  <div className="attrib-item">
                    <div className="label">Kurs wejścia → dziś</div>
                    <div className="value small muted">{data.summary.baseline_fx} → {rows[rows.length - 1].fx_rate}</div>
                  </div>
                )}
              </div>
            )}

            <ResponsiveContainer width="100%" height={250}>
              <ComposedChart data={rows} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
                <defs>
                  <linearGradient id="gd" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#3fb950" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#3fb950" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#2c3845" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="date" tick={{ fill: "#8b97a6", fontSize: 11 }} minTickGap={40} stroke="#2c3845" />
                <YAxis tick={{ fill: "#8b97a6", fontSize: 11 }} stroke="#2c3845" width={64}
                  tickFormatter={(v) => `${Math.round(v)}`} />
                <Tooltip
                  contentStyle={{ background: "#1a212b", border: "1px solid #2c3845", borderRadius: 8, color: "#e6edf3" }}
                  formatter={(v, name) => [fmtPln(v), DETAIL_LABELS[name] || name]}
                />
                <Legend formatter={(name) => DETAIL_LABELS[name] || name} wrapperStyle={{ fontSize: 12 }} />
                <Area type="monotone" dataKey="value_pln" stroke="#3fb950" strokeWidth={2} fill="url(#gd)" />
                {!isPln && (
                  <Line type="monotone" dataKey="value_const_fx" stroke="#d29922" strokeWidth={1.8} strokeDasharray="5 4" dot={false} />
                )}
                <Line type="monotone" dataKey="cost_pln" stroke="#8b97a6" strokeWidth={1.2} dot={false} />
              </ComposedChart>
            </ResponsiveContainer>

            <div className="modal-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Data</th>
                    <th>Cena giełdowa</th>
                    <th>Kurs NBP</th>
                    <th>Cena PLN</th>
                    <th>Szt.</th>
                    <th>Wartość PLN</th>
                  </tr>
                </thead>
                <tbody>
                  {[...rows].reverse().map((r) => (
                    <tr key={r.date}>
                      <td>{r.date}</td>
                      <td>{r.price_native} {data.currency}</td>
                      <td>{r.fx_rate == null ? "—" : r.fx_rate}</td>
                      <td>{fmtPln(r.price_pln)}</td>
                      <td>{r.quantity || "—"}</td>
                      <td>{r.value_pln ? fmtPln(r.value_pln) : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function PositionsTable({ positions, totals, onOpen }) {
  if (!positions || positions.length === 0)
    return <div className="spinner">Brak pozycji. Zaimportuj plik CSV.</div>;
  return (
    <table>
      <thead>
        <tr>
          <th>Instrument</th>
          <th>Szt.</th>
          <th>Śr. koszt</th>
          <th>Koszt</th>
          <th>Cena</th>
          <th>Wartość</th>
          <th>Zysk/strata</th>
          <th>%</th>
        </tr>
      </thead>
      <tbody>
        {positions.map((p) => (
          <tr key={p.isin}>
            <td>
              <span className="link" onClick={() => onOpen?.(p.isin)}>{p.name}</span>
              {" "}{p.needs_config && <span className="badge">brak tickera</span>}
              <div className="tag">{p.ticker || p.isin} · {p.currency || "?"}</div>
            </td>
            <td>{p.quantity}</td>
            <td>{fmtPln(p.avg_cost_pln)}</td>
            <td>{fmtPln(p.cost_pln)}</td>
            <td>
              {p.price == null ? "—" : p.price}
              {p.fx_rate && p.fx_rate !== 1 ? <div className="tag">×{p.fx_rate}</div> : null}
            </td>
            <td>{fmtPln(p.value_pln)}</td>
            <td className={cls(p.pl_pln)}>{fmtPln(p.pl_pln)}</td>
            <td className={cls(p.pl_pct)}>{fmtPct(p.pl_pct)}</td>
          </tr>
        ))}
      </tbody>
      <tfoot>
        <tr>
          <td>Razem (otwarte)</td>
          <td colSpan={2}></td>
          <td>{fmtPln(totals.cost_pln)}</td>
          <td></td>
          <td>{fmtPln(totals.value_pln ?? totals.value_pln_partial)}</td>
          <td className={cls(totals.unrealized_pl_pln)}>{fmtPln(totals.unrealized_pl_pln)}</td>
          <td className={cls(totals.pl_pct)}>{fmtPct(totals.pl_pct)}</td>
        </tr>
      </tfoot>
    </table>
  );
}

function TransactionForm({ instruments, onAdd }) {
  const today = new Date().toISOString().slice(0, 10);
  const empty = { ts: today, isin: "", type: "BUY", quantity: "", price_pln: "", newIsin: "", newName: "" };
  const [f, setF] = useState(empty);
  const set = (k, v) => setF((s) => ({ ...s, [k]: v }));
  const adding = f.isin === "__new__";

  const submit = () => {
    const isin = adding ? f.newIsin.trim() : f.isin;
    const qty = parseFloat(f.quantity);
    const price = parseFloat(f.price_pln);
    if (!isin || !qty || qty <= 0 || isNaN(price) || price < 0) return;
    onAdd({
      ts: f.ts, isin, name: adding ? f.newName.trim() : undefined,
      type: f.type, quantity: qty, price_pln: price,
    });
    setF({ ...empty, ts: f.ts });
  };

  return (
    <div className="tx-form">
      <input className="cell" type="date" value={f.ts} onChange={(e) => set("ts", e.target.value)} />
      <select className="cell" value={f.isin} onChange={(e) => set("isin", e.target.value)}>
        <option value="">— wybierz walor —</option>
        {instruments.map((i) => <option key={i.isin} value={i.isin}>{i.name}</option>)}
        <option value="__new__">➕ nowy walor…</option>
      </select>
      {adding && (
        <>
          <input className="cell narrow" placeholder="ISIN" value={f.newIsin} onChange={(e) => set("newIsin", e.target.value)} />
          <input className="cell" placeholder="nazwa" value={f.newName} onChange={(e) => set("newName", e.target.value)} />
        </>
      )}
      <select className="cell narrow" value={f.type} onChange={(e) => set("type", e.target.value)}>
        <option value="BUY">Kupno</option>
        <option value="SELL">Sprzedaż</option>
      </select>
      <input className="cell narrow" type="number" step="any" placeholder="szt." value={f.quantity} onChange={(e) => set("quantity", e.target.value)} />
      <input className="cell narrow" type="number" step="any" placeholder="cena PLN" value={f.price_pln} onChange={(e) => set("price_pln", e.target.value)} />
      <button className="primary" onClick={submit}>Dodaj</button>
    </div>
  );
}

function TransactionsTable({ transactions, onOpen, onDelete }) {
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

function CashPanel({ cash, onAdd, onDelete }) {
  const today = new Date().toISOString().slice(0, 10);
  const [form, setForm] = useState({ ts: today, kind: "deposit", amount: "" });
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const submit = () => {
    const amount = parseFloat(form.amount);
    if (!amount || amount <= 0) return;
    onAdd({ ts: form.ts, kind: form.kind, amount });
    setForm({ ...form, amount: "" });
  };
  const flows = cash?.flows || [];
  return (
    <div>
      <div className="cash-summary">
        <div>
          <div className="label">Saldo gotówki</div>
          <div className="value">{fmtPln(cash?.balance_pln)}</div>
        </div>
        <div>
          <div className="label">Wpłacono netto</div>
          <div className="value small">{fmtPln(cash?.net_deposits_pln)}</div>
        </div>
      </div>

      <div className="cash-form">
        <input className="cell" type="date" value={form.ts} onChange={(e) => set("ts", e.target.value)} />
        <select className="cell narrow" value={form.kind} onChange={(e) => set("kind", e.target.value)}>
          <option value="deposit">Wpłata</option>
          <option value="withdrawal">Wypłata</option>
        </select>
        <input
          className="cell"
          type="number"
          step="0.01"
          placeholder="kwota PLN"
          value={form.amount}
          onChange={(e) => set("amount", e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
        />
        <button className="primary" onClick={submit}>Dodaj</button>
      </div>

      {flows.length === 0 ? (
        <div className="spinner">Brak wpłat/wypłat. Dodaj wpłatę, aby śledzić niezainwestowaną gotówkę.</div>
      ) : (
        <table>
          <thead>
            <tr><th>Data</th><th>Typ</th><th>Kwota</th><th></th></tr>
          </thead>
          <tbody>
            {flows.map((f) => (
              <tr key={f.id}>
                <td>{(f.ts || "").slice(0, 10)}</td>
                <td>{f.kind === "deposit" ? "Wpłata" : "Wypłata"}</td>
                <td className={cls(f.amount_pln)}>{fmtPln(f.amount_pln)}</td>
                <td><button onClick={() => onDelete(f.id)}>Usuń</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function InstrumentsPanel({ instruments, onSave }) {
  const [draft, setDraft] = useState({});
  const edit = (isin, field, val) => setDraft((d) => ({ ...d, [isin]: { ...d[isin], [field]: val } }));
  const valueOf = (inst, field) => draft[inst.isin]?.[field] ?? inst[field] ?? "";
  return (
    <table>
      <thead>
        <tr><th>Instrument / ISIN</th><th>Ticker</th><th>Źródło</th><th>Kategoria</th><th>Waluta</th><th>Status</th><th></th></tr>
      </thead>
      <tbody>
        {instruments.map((inst) => (
          <tr key={inst.isin}>
            <td>{inst.name}<div className="tag">{inst.isin}</div></td>
            <td>
              <input className="cell" value={valueOf(inst, "ticker")} placeholder="np. FWIA.DE"
                onChange={(e) => edit(inst.isin, "ticker", e.target.value)} />
            </td>
            <td>
              <select className="cell narrow" value={valueOf(inst, "source") || "yfinance"}
                onChange={(e) => edit(inst.isin, "source", e.target.value)}>
                <option value="yfinance">yfinance</option>
                <option value="stooq">stooq</option>
              </select>
            </td>
            <td>
              <input className="cell" list="cat-list" value={valueOf(inst, "category")} placeholder="np. Akcje"
                onChange={(e) => edit(inst.isin, "category", e.target.value)} />
            </td>
            <td className="muted">{inst.currency || "auto"}</td>
            <td>{inst.needs_config ? <span className="badge">do uzupełnienia</span> : <span className="pos">OK</span>}</td>
            <td>
              <button onClick={() => onSave(inst.isin, {
                ticker: valueOf(inst, "ticker"),
                source: valueOf(inst, "source") || "yfinance",
                currency: inst.currency,
                category: valueOf(inst, "category"),
              })}>Zapisz</button>
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

function AllocationPanel({ allocation, onSave }) {
  const [draft, setDraft] = useState({});
  const groups = allocation?.groups || [];
  const targetOf = (g) => (draft[g.category] ?? (g.target_pct ?? ""));
  const set = (cat, v) => setDraft((d) => ({ ...d, [cat]: v }));

  const save = () => {
    const targets = {};
    for (const g of groups) {
      const v = parseFloat(targetOf(g));
      if (!isNaN(v) && v > 0) targets[g.category] = v;
    }
    onSave(targets);
    setDraft({});
  };

  // Suma docelowa z aktualnego draftu (do walidacji 100%).
  const sum = groups.reduce((acc, g) => {
    const v = parseFloat(targetOf(g));
    return acc + (isNaN(v) ? 0 : v);
  }, 0);

  if (groups.length === 0)
    return <div className="spinner">Brak danych. Przypisz instrumentom kategorie w zakładce „Instrumenty".</div>;

  return (
    <div>
      <table>
        <thead>
          <tr>
            <th>Grupa</th>
            <th>Docelowo %</th>
            <th>Rzeczywiście %</th>
            <th>Wartość</th>
            <th>Odchylenie</th>
            <th>Do rebalansu</th>
          </tr>
        </thead>
        <tbody>
          {groups.map((g) => (
            <tr key={g.category}>
              <td>{g.category}</td>
              <td>
                <input
                  className="cell narrow"
                  type="number"
                  step="1"
                  value={targetOf(g)}
                  placeholder="—"
                  onChange={(e) => set(g.category, e.target.value)}
                />
              </td>
              <td>{g.actual_pct == null ? "—" : `${g.actual_pct.toFixed(1)}%`}</td>
              <td>{fmtPln(g.actual_pln)}</td>
              <td className={cls(g.drift_pp == null ? null : -Math.abs(g.drift_pp))}>
                {g.drift_pp == null ? "—" : `${g.drift_pp > 0 ? "+" : ""}${g.drift_pp.toFixed(1)} pp`}
              </td>
              <td className={cls(g.rebalance_pln)}>
                {g.rebalance_pln == null ? "—" : `${g.rebalance_pln > 0 ? "+" : ""}${fmtPln(g.rebalance_pln)}`}
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <td>Suma</td>
            <td className={Math.abs(sum - 100) < 0.01 ? "pos" : "neg"}>{sum.toFixed(0)}%</td>
            <td colSpan={2}>{fmtPln(allocation.total_pln)}</td>
            <td colSpan={2}></td>
          </tr>
        </tfoot>
      </table>
      <div className="alloc-actions">
        <button className="primary" onClick={save}>Zapisz model docelowy</button>
        {Math.abs(sum - 100) >= 0.01 && sum > 0 && (
          <span className="tag">Uwaga: wagi docelowe sumują się do {sum.toFixed(0)}%, nie 100%.</span>
        )}
      </div>
      <p className="tag" style={{ marginTop: 12 }}>
        „Do rebalansu" = kwota do dokupienia (+) lub sprzedaży (−), by trafić w docelowy udział.
        Gotówka liczona jest jako osobna grupa.
      </p>
    </div>
  );
}

const TABS = [
  ["dashboard", "Pulpit"],
  ["transactions", "Transakcje"],
  ["allocation", "Alokacja"],
  ["cash", "Gotówka"],
  ["instruments", "Instrumenty"],
];

export default function App() {
  const [portfolio, setPortfolio] = useState(null);
  const [history, setHistory] = useState([]);
  const [instruments, setInstruments] = useState([]);
  const [transactions, setTransactions] = useState([]);
  const [cash, setCash] = useState(null);
  const [allocation, setAllocation] = useState(null);
  const [detail, setDetail] = useState(null);
  const [tab, setTab] = useState("dashboard");
  const [benchmarkRate, setBenchmarkRate] = useState(5);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const fileRef = useRef();

  const flash = (text, ok = true) => {
    setMsg({ text, ok });
    setTimeout(() => setMsg(null), 5000);
  };

  const loadAll = async () => {
    const [pf, hist, insts, txs, cs, alloc] = await Promise.all([
      api.portfolio(), api.history(benchmarkRate / 100), api.instruments(), api.transactions(), api.cash(), api.allocation(),
    ]);
    setPortfolio(pf); setHistory(hist); setInstruments(insts); setTransactions(txs); setCash(cs); setAllocation(alloc);
  };

  useEffect(() => {
    loadAll().catch((e) => flash(`Błąd ładowania: ${e.message}`, false));
  }, []);

  // Przeładuj samą historię po zmianie stopy benchmarku.
  useEffect(() => {
    api.history(benchmarkRate / 100).then(setHistory).catch(() => {});
  }, [benchmarkRate]);

  const run = async (fn, okMsg) => {
    setBusy(true);
    try {
      await fn();
      await loadAll();
      if (okMsg) flash(okMsg);
    } catch (e) {
      flash(`Błąd: ${e.message}`, false);
    } finally {
      setBusy(false);
    }
  };

  const openDetail = (isin) => {
    api.instrumentHistory(isin).then(setDetail).catch((e) => flash(`Błąd: ${e.message}`, false));
  };

  const onImport = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    run(async () => {
      const r = await api.importCsv(file);
      flash(`Zaimportowano ${r.imported} transakcji (pominięto duplikatów: ${r.skipped_duplicates}).`);
    });
    e.target.value = "";
  };

  return (
    <div className="app">
      <header className="top">
        <div>
          <h1>Portfolio Tracker</h1>
          <div className="sub">Self-hosted · wyceny w PLN (przeliczane kursem NBP)</div>
        </div>
        <div className="toolbar">
          <input ref={fileRef} type="file" accept=".csv" className="hidden-file" onChange={onImport} />
          <button onClick={() => fileRef.current?.click()} disabled={busy}>Importuj CSV</button>
          <button onClick={() => run(() => api.refresh(), "Odświeżono ceny i kursy.")} disabled={busy}>Odśwież ceny</button>
          <button onClick={() => run(() => api.backfill(), "Pobrano historię wycen.")} disabled={busy}>Backfill historii</button>
        </div>
      </header>

      {msg && <div className={`msg ${msg.ok ? "ok" : "err"}`}>{msg.text}</div>}
      {busy && <div className="spinner">Pracuję…</div>}

      <Cards totals={portfolio?.totals} />

      <nav className="tabs">
        {TABS.map(([id, label]) => (
          <button key={id} className={`tab ${tab === id ? "active" : ""}`} onClick={() => setTab(id)}>
            {label}
            {id === "transactions" && transactions.length ? <span className="count">{transactions.length}</span> : null}
          </button>
        ))}
      </nav>

      {tab === "dashboard" && (
        <>
          <div className="panel">
            <div className="panel-head">
              <h2>Wartość konta vs benchmark</h2>
              <label className="bench-ctrl">
                Benchmark:
                <input
                  type="number"
                  step="0.5"
                  className="cell narrow"
                  value={benchmarkRate}
                  onChange={(e) => setBenchmarkRate(parseFloat(e.target.value) || 0)}
                />
                % rocznie
              </label>
            </div>
            <HistoryChart data={history} />
          </div>
          <div className="panel">
            <h2>Pozycje</h2>
            <PositionsTable positions={portfolio?.positions} totals={portfolio?.totals || {}} onOpen={openDetail} />
          </div>
        </>
      )}

      {tab === "transactions" && (
        <div className="panel">
          <h2>Historia transakcji</h2>
          <TransactionForm
            instruments={instruments}
            onAdd={(body) => run(async () => {
              const r = await api.addTransaction(body);
              flash(r.created ? "Dodano transakcję." : "Pominięto — taka transakcja już istnieje.", r.created);
            })}
          />
          <TransactionsTable
            transactions={transactions}
            onOpen={openDetail}
            onDelete={(id) => run(() => api.deleteTransaction(id), "Usunięto transakcję.")}
          />
        </div>
      )}

      {tab === "allocation" && (
        <div className="panel">
          <h2>Alokacja docelowa vs rzeczywista</h2>
          <AllocationPanel
            allocation={allocation}
            onSave={(targets) => run(() => api.setAllocation(targets), "Zapisano model docelowy.")}
          />
        </div>
      )}

      {tab === "cash" && (
        <div className="panel">
          <h2>Konto gotówkowe</h2>
          <CashPanel
            cash={cash}
            onAdd={(body) => run(() => api.addCash(body), "Dodano operację gotówkową.")}
            onDelete={(id) => run(() => api.deleteCash(id), "Usunięto operację.")}
          />
        </div>
      )}

      {tab === "instruments" && (
        <div className="panel">
          <h2>Instrumenty (mapowanie ISIN → ticker)</h2>
          <InstrumentsPanel
            instruments={instruments}
            onSave={(isin, body) => run(() => api.updateInstrument(isin, body), "Zapisano mapowanie.")}
          />
        </div>
      )}

      {detail && <InstrumentDetail data={detail} onClose={() => setDetail(null)} />}
    </div>
  );
}
