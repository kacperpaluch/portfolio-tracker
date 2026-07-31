import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { fmtPln } from "../format.js";

const COLORS = ["#347a50", "#4d78ad", "#b27a1c", "#7863a4", "#c45b55", "#5c946a", "#5b9189", "#b87958", "#7b8580", "#899447"];

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
              <Cell key={g.category} fill={COLORS[i % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{ background: "#ffffff", border: "1px solid #c8d3ca", borderRadius: 10, color: "#19231d", fontSize: 12 }}
            formatter={(v, name) => [`${fmtPln(v)} (${((v / total) * 100).toFixed(1)}%)`, name]}
          />
          {!compact && <Legend wrapperStyle={{ fontSize: 10 }} />}
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
