import {
  Area,
  CartesianGrid,
  ComposedChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fmtPct, fmtDate } from "../format.js";

// Obsunięcie portfela (drawdown) — krzywa „pod wodą" liczona na indeksie TWR
// (flow-neutral, więc wpłaty nie maskują spadków). Wartości ≤ 0.
export default function DrawdownChart({ data }) {
  if (!data || !data.series || data.series.length === 0)
    return <div className="spinner">Brak danych historycznych — kliknij „Backfill historii".</div>;

  const { series, max_drawdown, max_drawdown_from, max_drawdown_to, recovery_date, current_drawdown } = data;
  const minVal = Math.min(0, ...series.map((p) => p.drawdown_pct));

  return (
    <>
      <div className="dd-summary">
        <span>
          Max obsunięcie: <strong className="neg">{fmtPct(max_drawdown)}</strong>
          {max_drawdown_from && (
            <span className="muted"> ({fmtDate(max_drawdown_from)} → {fmtDate(max_drawdown_to)})</span>
          )}
        </span>
        <span>
          Bieżące: <strong className={current_drawdown < 0 ? "neg" : "pos"}>{fmtPct(current_drawdown)}</strong>
        </span>
        <span className="muted">
          {recovery_date
            ? `Odbicie po dołku: ${fmtDate(recovery_date)}`
            : current_drawdown < 0
              ? "Jeszcze pod szczytem (brak odbicia)"
              : "Na szczycie"}
        </span>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <ComposedChart data={series} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
          <defs>
            <linearGradient id="dd" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#f85149" stopOpacity={0.05} />
              <stop offset="100%" stopColor="#f85149" stopOpacity={0.4} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="#2c3845" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="date" tick={{ fill: "#8b97a6", fontSize: 11 }} minTickGap={40} stroke="#2c3845" />
          <YAxis
            tick={{ fill: "#8b97a6", fontSize: 11 }}
            stroke="#2c3845"
            width={50}
            domain={[Math.floor(minVal), 0]}
            tickFormatter={(v) => `${v}%`}
          />
          <Tooltip
            contentStyle={{ background: "#1a212b", border: "1px solid #2c3845", borderRadius: 8, color: "#e6edf3" }}
            formatter={(v) => [fmtPct(v), "Obsunięcie"]}
          />
          <ReferenceLine y={0} stroke="#2c3845" />
          <Area
            type="monotone"
            isAnimationActive={false}
            dataKey="drawdown_pct"
            stroke="#f85149"
            strokeWidth={2}
            fill="url(#dd)"
          />
        </ComposedChart>
      </ResponsiveContainer>
    </>
  );
}
