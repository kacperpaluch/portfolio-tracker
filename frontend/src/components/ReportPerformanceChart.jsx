import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fmtPct } from "../format.js";

export default function ReportPerformanceChart({ rows, benchmarkRate, cpiSpread }) {
  if (!rows?.length) return <div className="spinner">Brak serii dla wybranego okresu.</div>;
  const hasCpi = rows.some((row) => row.benchmark_cpi_pct != null);
  const labels = {
    portfolio_pct: "Portfel",
    benchmark_pct: `Benchmark ${benchmarkRate}%`,
    benchmark_cpi_pct: `Inflacja +${cpiSpread}%`,
  };
  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
        <CartesianGrid stroke="#dce3dc" strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="date" tick={{ fill: "#68766d", fontSize: 10 }} minTickGap={35} stroke="#dce3dc" />
        <YAxis tick={{ fill: "#68766d", fontSize: 10 }} tickFormatter={(value) => `${value.toFixed(0)}%`} stroke="#dce3dc" width={55} />
        <Tooltip
          contentStyle={{ background: "#fff", border: "1px solid #c8d3ca", borderRadius: 10, fontSize: 12 }}
          formatter={(value, name) => [fmtPct(value), labels[name] || name]}
        />
        <Legend formatter={(name) => labels[name] || name} wrapperStyle={{ fontSize: 10 }} />
        <Line type="monotone" dataKey="portfolio_pct" stroke="#347a50" strokeWidth={2.4} dot={false} connectNulls />
        <Line type="monotone" dataKey="benchmark_pct" stroke="#a06d13" strokeWidth={1.8} strokeDasharray="5 4" dot={false} connectNulls />
        {hasCpi && <Line type="monotone" dataKey="benchmark_cpi_pct" stroke="#7059a5" strokeWidth={1.8} strokeDasharray="2 3" dot={false} connectNulls />}
      </LineChart>
    </ResponsiveContainer>
  );
}
