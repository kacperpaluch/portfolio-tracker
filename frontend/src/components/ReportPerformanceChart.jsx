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
import { LEGEND_STYLE, TOOLTIP_STYLE, axisProps, gridProps, paddedDomain, useChartColors } from "../chartTheme.js";

export default function ReportPerformanceChart({ rows, benchmarkRate, cpiSpread }) {
  const colors = useChartColors();
  if (!rows?.length) return <div className="spinner">Brak serii dla wybranego okresu.</div>;
  const hasCpi = rows.some((row) => row.benchmark_cpi_pct != null);
  const domain = paddedDomain(rows, ["portfolio_pct", "benchmark_pct", "benchmark_cpi_pct"]);
  const labels = {
    portfolio_pct: "Portfel",
    benchmark_pct: `Benchmark ${benchmarkRate}%`,
    benchmark_cpi_pct: `Inflacja +${cpiSpread}%`,
  };
  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
        <CartesianGrid {...gridProps(colors)} />
        <XAxis dataKey="date" {...axisProps(colors, 10)} minTickGap={35} />
        <YAxis {...axisProps(colors, 10)} tickFormatter={(value) => `${value.toFixed(1)}%`} width={55} domain={domain} />
        <Tooltip
          contentStyle={TOOLTIP_STYLE}
          formatter={(value, name) => [fmtPct(value), labels[name] || name]}
        />
        <Legend formatter={(name) => labels[name] || name} wrapperStyle={LEGEND_STYLE} />
        <Line type="monotone" dataKey="portfolio_pct" stroke={colors.portfolio} strokeWidth={2.4} dot={false} connectNulls />
        <Line type="monotone" dataKey="benchmark_pct" stroke={colors.benchmark} strokeWidth={1.8} strokeDasharray="5 4" dot={false} connectNulls />
        {hasCpi && <Line type="monotone" dataKey="benchmark_cpi_pct" stroke={colors.cpi} strokeWidth={1.8} strokeDasharray="2 3" dot={false} connectNulls />}
      </LineChart>
    </ResponsiveContainer>
  );
}
