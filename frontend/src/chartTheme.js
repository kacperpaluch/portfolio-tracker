import { useEffect, useState } from "react";

// Wspólny motyw wykresów (recharts).
//
// Recharts ustawia kolory jako atrybuty SVG (także na ikonach legendy), więc muszą to być
// konkretne wartości, nie `var(--…)`. Jedynym źródłem prawdy zostaje arkusz stylów:
// odczytujemy z niego zmienne i przeliczamy je ponownie, gdy system przełączy motyw.

const VARS = {
  portfolio: "--series-portfolio",
  benchmark: "--series-benchmark",
  cpi: "--series-cpi",
  cost: "--series-cost",
  loss: "--series-loss",
  axis: "--muted",
  grid: "--border",
};

function readColors() {
  const style = getComputedStyle(document.documentElement);
  return Object.fromEntries(
    Object.entries(VARS).map(([key, name]) => [key, style.getPropertyValue(name).trim()]),
  );
}

export function useChartColors() {
  const [colors, setColors] = useState(readColors);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const sync = () => setColors(readColors());
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);
  return colors;
}

export const axisProps = (colors, fontSize = 11) => ({
  tick: { fill: colors.axis, fontSize },
  stroke: colors.grid,
});

export const gridProps = (colors) => ({
  stroke: colors.grid,
  strokeDasharray: "3 3",
  vertical: false,
});

// Inline style => `var()` działa i sam nadąża za zmianą motywu.
export const TOOLTIP_STYLE = {
  background: "var(--surface)",
  border: "1px solid var(--border-strong)",
  borderRadius: 10,
  color: "var(--text)",
  fontSize: 12,
};

export const LEGEND_STYLE = { fontSize: 10 };

// Paleta kategorii dla donuta alokacji — tony średnie, czytelne na jasnym i ciemnym tle.
export const CATEGORY_COLORS = [
  "#3f8f60", "#4d78ad", "#b27a1c", "#8a6fb8", "#c45b55",
  "#4f9e93", "#99a83f", "#b87958", "#7b8580", "#6f7fb5",
];

// Domena osi dla serii, która potrafi być całkiem płaska (np. raport za jeden dzień).
// Bez tego recharts rysuje pięć identycznych etykiet „0%".
export function paddedDomain(rows, keys, minSpan = 1) {
  const values = rows.flatMap((row) => keys.map((key) => row[key])).filter((v) => v != null);
  if (values.length === 0) return ["auto", "auto"];
  const min = Math.min(...values);
  const max = Math.max(...values);
  if (max - min >= minSpan) return ["auto", "auto"];
  const center = (min + max) / 2;
  return [center - minSpan / 2, center + minSpan / 2];
}
