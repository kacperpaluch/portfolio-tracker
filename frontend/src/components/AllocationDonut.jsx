import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { fmtPln } from "../format.js";

const COLORS = ["#4493f8", "#3fb950", "#d29922", "#a371f7", "#f85149", "#56d364", "#79c0ff", "#ffa657", "#f0883e", "#7ee787"];

export default function AllocationDonut({ groups, total }) {
  const data = (groups || []).filter((g) => (g.actual_pln ?? 0) > 0);
  if (data.length === 0 || !total) return null;
  return (
    <div className="alloc-donut">
      <ResponsiveContainer width="100%" height={240}>
        <PieChart>
          <Pie
            data={data}
            dataKey="actual_pln"
            nameKey="category"
            cx="50%"
            cy="50%"
            innerRadius={60}
            outerRadius={95}
            paddingAngle={2}
            isAnimationActive={false}
          >
            {data.map((g, i) => (
              <Cell key={g.category} fill={COLORS[i % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{ background: "#1a212b", border: "1px solid #2c3845", borderRadius: 8, color: "#e6edf3" }}
            formatter={(v, name) => [`${fmtPln(v)} (${((v / total) * 100).toFixed(1)}%)`, name]}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
