import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

/**
 * A Recharts line chart rendered against an EMPTY dataset. This demonstrates
 * the charting layer (axes, grid, container) without displaying any fabricated
 * values. Real series are supplied once the data pipelines are wired up.
 */
export function ChartPlaceholder({ height = 260 }: { height?: number }) {
  const emptyData: Array<{ period: string; value: number | null }> = [];

  return (
    <div style={{ height }} aria-label="Chart placeholder (no data yet)">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={emptyData} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgb(var(--color-border))" />
          <XAxis dataKey="period" stroke="rgb(var(--color-content-subtle))" fontSize={12} />
          <YAxis stroke="rgb(var(--color-content-subtle))" fontSize={12} />
          <Tooltip />
          <Line type="monotone" dataKey="value" stroke="rgb(var(--color-brand))" dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
