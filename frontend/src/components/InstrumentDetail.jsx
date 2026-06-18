import { useRef } from "react";
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
import { fmtPln, cls } from "../format.js";

const DETAIL_LABELS = {
  value_pln: "Wartość (rzeczywista)",
  value_const_fx: "Wartość bez zmian kursu",
  cost_pln: "Koszt (wpłacone)",
};

export default function InstrumentDetail({ data, onClose, onImportPrices, busy, firstTxDate }) {
  const priceFileRef = useRef(null);
  if (!data) return null;
  const rows = data.rows || [];
  const isPln = data.currency === "PLN";
  const onPickPrices = (e) => {
    const file = e.target.files?.[0];
    if (file) onImportPrices?.(data.isin, file);
    e.target.value = "";
  };
  // Link do pobrania CSV wprost ze stooq — w PRZEGLĄDARCE (jedyny klient, który przechodzi
  // antybota stooq). Symbol = ticker bez sufiksu giełdy (.WA/.DE/.L), zakres od pierwszej
  // transakcji do dziś. Potem plik importujesz przyciskiem obok.
  const stooqUrl = () => {
    const sym = (data.ticker || "").split(".")[0].toLowerCase();
    if (!sym) return null;
    const today = new Date().toISOString().slice(0, 10);
    const since = (firstTxDate || `${new Date().getFullYear() - 5}-01-01`).slice(0, 10);
    const fmt = (d) => d.replaceAll("-", "");
    return `https://stooq.com/q/d/l/?s=${sym}&d1=${fmt(since)}&d2=${fmt(today)}&i=d`;
  };
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
          <div className="modal-actions">
            {stooqUrl() && (
              <a className="btn" href={stooqUrl()} target="_blank" rel="noopener noreferrer"
                title="Otwiera stooq w nowej karcie — przeglądarka pobierze CSV (przejdzie antybota). Potem zaimportuj plik obok.">
                Pobierz CSV ze stooq ↗
              </a>
            )}
            <input ref={priceFileRef} type="file" accept=".csv" className="hidden-file" onChange={onPickPrices} />
            <button onClick={() => priceFileRef.current?.click()} disabled={busy}
              title="Wgraj dzienne ceny z CSV (format stooq) — gdy Yahoo nie ma poprawnej historii">
              Importuj ceny (CSV)
            </button>
            <button onClick={onClose}>Zamknij ✕</button>
          </div>
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
                <Area type="monotone" isAnimationActive={false} dataKey="value_pln" stroke="#3fb950" strokeWidth={2} fill="url(#gd)" />
                {!isPln && (
                  <Line type="monotone" isAnimationActive={false} dataKey="value_const_fx" stroke="#d29922" strokeWidth={1.8} strokeDasharray="5 4" dot={false} />
                )}
                <Line type="monotone" isAnimationActive={false} dataKey="cost_pln" stroke="#8b97a6" strokeWidth={1.2} dot={false} />
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
