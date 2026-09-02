import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { ObservationPoint } from '../../lib/statcanApi';

interface ProductivityChartProps {
  points: ObservationPoint[];
  height?: number;
}

/**
 * Renders a real historical productivity series. Only points with a non-null
 * value are plotted (StatCan-suppressed periods are omitted rather than shown
 * as zero). This component never fabricates data.
 */
export function ProductivityChart({ points, height = 320 }: ProductivityChartProps) {
  const data = points
    .filter((p) => p.value !== null)
    .map((p) => ({ period: p.period, value: p.value as number }));

  return (
    <div style={{ height }} aria-label="Historical productivity chart">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgb(var(--color-border))" />
          <XAxis
            dataKey="period"
            stroke="rgb(var(--color-content-subtle))"
            fontSize={12}
            minTickGap={32}
          />
          <YAxis stroke="rgb(var(--color-content-subtle))" fontSize={12} domain={['auto', 'auto']} />
          <Tooltip
            contentStyle={{
              background: 'rgb(var(--color-surface-raised))',
              border: '1px solid rgb(var(--color-border))',
              borderRadius: 8,
              fontSize: 12,
            }}
          />
          <Line
            type="monotone"
            dataKey="value"
            stroke="rgb(var(--color-brand))"
            strokeWidth={2}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
