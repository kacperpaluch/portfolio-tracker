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
import { TOOLTIP_STYLE, axisProps, gridProps, useChartColors } from "../chartTheme.js";

// Obsunięcie portfela (drawdown) — krzywa „pod wodą" liczona na indeksie TWR
// (flow-neutral, więc wpłaty nie maskują spadków). Wartości ≤ 0.
export default function DrawdownChart({ data }) {
  const colors = useChartColors();
  if (!data || !data.series || data.series.length === 0)
    return <div className="spinner">Brak danych historycznych — uzupełnij historię w sekcji „Dane i ustawienia".</div>;

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
              <stop offset="0%" stopColor={colors.loss} stopOpacity={0.03} />
              <stop offset="100%" stopColor={colors.loss} stopOpacity={0.22} />
            </linearGradient>
          </defs>
          <CartesianGrid {...gridProps(colors)} />
          <XAxis dataKey="date" {...axisProps(colors)} minTickGap={40} />
          <YAxis
            {...axisProps(colors)}
            width={50}
            domain={[Math.floor(minVal), 0]}
            tickFormatter={(v) => `${v}%`}
          />
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            formatter={(v) => [fmtPct(v), "Obsunięcie"]}
          />
          <ReferenceLine y={0} stroke={colors.grid} />
          <Area
            type="monotone"
            isAnimationActive={false}
            dataKey="drawdown_pct"
            stroke={colors.loss}
            strokeWidth={2}
            fill="url(#dd)"
          />
        </ComposedChart>
      </ResponsiveContainer>
    </>
  );
}
