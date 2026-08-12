import { Cell, Label, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { fmtPln } from "../format.js";
import { CATEGORY_COLORS, LEGEND_STYLE, TOOLTIP_STYLE } from "../chartTheme.js";

const plural = (n) => (n === 1 ? "kategoria" : n < 5 ? "kategorie" : "kategorii");

export default function AllocationDonut({ groups, total, compact = false }) {
  const data = (groups || []).filter((g) => (g.actual_pln ?? 0) > 0);
  if (data.length === 0 || !total) return null;
  return (
    <div className="alloc-donut">
      <ResponsiveContainer width="100%" height={compact ? 240 : 270}>
        <PieChart>
          <Pie
            data={data}
            dataKey="actual_pln"
            nameKey="category"
            cx="50%"
            cy="50%"
            innerRadius={compact ? 62 : 68}
            outerRadius={compact ? 88 : 104}
            paddingAngle={2}
            isAnimationActive={false}
          >
            {data.map((g, i) => (
              <Cell key={g.category} fill={CATEGORY_COLORS[i % CATEGORY_COLORS.length]} />
            ))}
            {/* Dziura donuta niesie sumę — inaczej środek wykresu to sama pustka. */}
            <Label
              position="center"
              content={({ viewBox }) => (
                <g className="donut-center">
                  <text x={viewBox.cx} y={viewBox.cy - 3} textAnchor="middle" className="donut-total">
                    {fmtPln(total)}
                  </text>
                  <text x={viewBox.cx} y={viewBox.cy + 15} textAnchor="middle" className="donut-sub">
                    {data.length} {plural(data.length)}
                  </text>
                </g>
              )}
            />
          </Pie>
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            formatter={(v, name) => [`${fmtPln(v)} (${((v / total) * 100).toFixed(1)}%)`, name]}
          />
          {!compact && <Legend wrapperStyle={LEGEND_STYLE} />}
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
