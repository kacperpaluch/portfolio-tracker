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

const LABELS = {
  value_pln: "Wartość konta",
  benchmark_pln: "Benchmark",
  portfolio_pct: "Stopa zwrotu",
  benchmark_pct: "Benchmark %",
};

export default function HistoryChart({ data }) {
  const [mode, setMode] = useState("pln"); // "pln" | "pct"
  if (!data || data.length === 0)
    return <div className="spinner">Brak danych historycznych — kliknij „Backfill historii".</div>;

  const isPct = mode === "pct";
  const valueKey = isPct ? "portfolio_pct" : "value_pln";
  const benchKey = isPct ? "benchmark_pct" : "benchmark_pln";
  const yFmt = isPct ? (v) => `${v}%` : (v) => `${Math.round(v / 1000)}k`;
  const tipFmt = (v) => (isPct ? fmtPct(v) : fmtPln(v));

  return (
    <>
      <div className="chart-toggle">
        <button className={`tg ${!isPct ? "on" : ""}`} onClick={() => setMode("pln")}>Wartość (PLN)</button>
        <button className={`tg ${isPct ? "on" : ""}`} onClick={() => setMode("pct")}>Stopa zwrotu (%)</button>
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
            formatter={(v, name) => [tipFmt(v), LABELS[name] || name]}
          />
          <Legend formatter={(name) => LABELS[name] || name} wrapperStyle={{ fontSize: 12 }} />
          <Area
            type="monotone"
            isAnimationActive={false}
            dataKey={valueKey}
            stroke="#4493f8"
            strokeWidth={2}
            fill="url(#g)"
            connectNulls={!isPct}
          />
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
        </ComposedChart>
      </ResponsiveContainer>
    </>
  );
}
