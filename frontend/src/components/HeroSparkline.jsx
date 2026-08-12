import { Area, AreaChart, ResponsiveContainer, YAxis } from "recharts";
import { useChartColors } from "../chartTheme.js";

// Tło karty z łączną wartością: przebieg wartości konta zamiast pustego miejsca.
// Bez osi i tooltipa — to ilustracja trendu, pełny wykres jest niżej na Pulpicie.
export default function HeroSparkline({ data }) {
  const colors = useChartColors();
  const rows = (data || []).filter((row) => row.value_pln != null).slice(-180);
  if (rows.length < 2) return null;
  return (
    <div className="hero-spark" aria-hidden="true">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={rows} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="hero-g" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={colors.portfolio} stopOpacity={0.28} />
              <stop offset="100%" stopColor={colors.portfolio} stopOpacity={0} />
            </linearGradient>
          </defs>
          <YAxis hide domain={["dataMin", "dataMax"]} />
          <Area
            type="monotone"
            dataKey="value_pln"
            stroke={colors.portfolio}
            strokeWidth={2}
            fill="url(#hero-g)"
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
