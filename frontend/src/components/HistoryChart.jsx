import { useState } from "react";
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
import { fmtPln, fmtPct } from "../format.js";

export default function HistoryChart({ data, benchmarkRate = 5, cpiSpread = 2 }) {
  const [mode, setMode] = useState("pln"); // "pln" | "pct"
  const [showBench, setShowBench] = useState(true);
  const [showCpi, setShowCpi] = useState(true);

  if (!data || data.length === 0)
    return <div className="spinner">Brak danych historycznych — kliknij „Backfill historii".</div>;

  // Benchmark inflacyjny pokazujemy tylko gdy backend zwrócił dane CPI (Eurostat pobrany).
  const hasCpi = data.some((d) => d.benchmark_cpi_pln != null);

  const isPct = mode === "pct";
  const valueKey = isPct ? "portfolio_pct" : "value_pln";
  const benchKey = isPct ? "benchmark_pct" : "benchmark_pln";
  const cpiKey = isPct ? "benchmark_cpi_pct" : "benchmark_cpi_pln";
  const yFmt = isPct ? (v) => `${v}%` : (v) => `${Math.round(v / 1000)}k`;
  const tipFmt = (v) => (isPct ? fmtPct(v) : fmtPln(v));

  const labels = {
    [valueKey]: isPct ? "Stopa zwrotu" : "Wartość konta",
    [benchKey]: `Benchmark ${benchmarkRate}%`,
    [cpiKey]: `Inflacja +${cpiSpread}%`,
  };

  return (
    <>
      <div className="chart-toggle">
        <button className={`tg ${!isPct ? "on" : ""}`} onClick={() => setMode("pln")}>Wartość (PLN)</button>
        <button className={`tg ${isPct ? "on" : ""}`} onClick={() => setMode("pct")}>Stopa zwrotu (%)</button>
        <span className="chart-toggle-sep" />
        <button className={`tg ${showBench ? "on" : ""}`} onClick={() => setShowBench((v) => !v)}>
          Benchmark {benchmarkRate}%
        </button>
        {hasCpi && (
          <button className={`tg ${showCpi ? "on" : ""}`} onClick={() => setShowCpi((v) => !v)}>
            Inflacja +{cpiSpread}%
          </button>
        )}
      </div>
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
            tickFormatter={yFmt}
          />
          <Tooltip
            contentStyle={{ background: "#1a212b", border: "1px solid #2c3845", borderRadius: 8, color: "#e6edf3" }}
            formatter={(v, name) => [tipFmt(v), labels[name] || name]}
          />
          <Legend formatter={(name) => labels[name] || name} wrapperStyle={{ fontSize: 12 }} />
          <Area
            type="monotone"
            isAnimationActive={false}
            dataKey={valueKey}
            stroke="#4493f8"
            strokeWidth={2}
            fill="url(#g)"
            connectNulls={!isPct}
          />
          {showBench && (
            <Line
              type="monotone"
              isAnimationActive={false}
              dataKey={benchKey}
              stroke="#d29922"
              strokeWidth={2}
              strokeDasharray="5 4"
              dot={false}
              connectNulls={!isPct}
            />
          )}
          {hasCpi && showCpi && (
            <Line
              type="monotone"
              isAnimationActive={false}
              dataKey={cpiKey}
              stroke="#a371f7"
              strokeWidth={2}
              strokeDasharray="2 3"
              dot={false}
              connectNulls={!isPct}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </>
  );
}
