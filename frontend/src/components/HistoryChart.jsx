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

export default function HistoryChart({ data, benchmarkRate = 5, cpiSpread = 2, compact = false }) {
  const [mode, setMode] = useState("pln"); // "pln" | "pct"
  const [showBench, setShowBench] = useState(true);
  const [showCpi, setShowCpi] = useState(true);

  if (!data || data.length === 0)
    return <div className="spinner">Brak danych historycznych — uzupełnij historię w sekcji „Dane i ustawienia".</div>;

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
      <ResponsiveContainer width="100%" height={compact ? 270 : 330}>
        <ComposedChart data={data} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
          <defs>
            <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#347a50" stopOpacity={0.20} />
              <stop offset="100%" stopColor="#347a50" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="#dce3dc" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="date" tick={{ fill: "#68766d", fontSize: 11 }} minTickGap={40} stroke="#dce3dc" />
          <YAxis
            tick={{ fill: "#68766d", fontSize: 11 }}
            stroke="#dce3dc"
            width={70}
            tickFormatter={yFmt}
          />
          <Tooltip
            contentStyle={{ background: "#ffffff", border: "1px solid #c8d3ca", borderRadius: 10, color: "#19231d", fontSize: 12 }}
            formatter={(v, name) => [tipFmt(v), labels[name] || name]}
          />
          {!compact && <Legend formatter={(name) => labels[name] || name} wrapperStyle={{ fontSize: 10 }} />}
          <Area
            type="monotone"
            isAnimationActive={false}
            dataKey={valueKey}
            stroke="#347a50"
            strokeWidth={2}
            fill="url(#g)"
            connectNulls={!isPct}
          />
          {showBench && (
            <Line
              type="monotone"
              isAnimationActive={false}
              dataKey={benchKey}
              stroke="#a06d13"
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
              stroke="#7059a5"
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
