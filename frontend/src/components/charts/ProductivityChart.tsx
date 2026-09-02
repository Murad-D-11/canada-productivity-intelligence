import {
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { ObservationPoint } from '../../lib/statcanApi';
import type { WeatherPoint } from '../../lib/weatherApi';

export interface WeatherOverlay {
  points: WeatherPoint[];
  label: string;
  unit: string;
}

interface ProductivityChartProps {
  points: ObservationPoint[];
  /** Optional weather series overlaid on a secondary axis (real data only). */
  weather?: WeatherOverlay | null;
  height?: number;
}

/**
 * Renders a real historical productivity series, optionally overlaid with a
 * real weather series on a secondary axis so users can compare the two trends.
 * Only points with a non-null value are plotted (suppressed / source-missing
 * periods are omitted rather than shown as zero). This component never
 * fabricates data.
 */
export function ProductivityChart({ points, weather, height = 320 }: ProductivityChartProps) {
  // Merge productivity + weather by period label so both share the X axis.
  const byPeriod = new Map<string, { period: string; value: number | null; weather: number | null }>();

  for (const p of points) {
    if (p.value === null) continue;
    byPeriod.set(p.period, { period: p.period, value: p.value, weather: null });
  }

  if (weather) {
    for (const w of weather.points) {
      if (w.value === null) continue;
      const existing = byPeriod.get(w.period);
      if (existing) {
        existing.weather = w.value;
      } else {
        // Keep weather-only periods so the overlay isn't truncated to
        // productivity coverage; productivity stays null (unplotted) there.
        byPeriod.set(w.period, { period: w.period, value: null, weather: w.value });
      }
    }
  }

  const data = Array.from(byPeriod.values()).sort((a, b) => a.period.localeCompare(b.period));

  return (
    <div style={{ height }} aria-label="Historical productivity chart">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgb(var(--color-border))" />
          <XAxis
            dataKey="period"
            stroke="rgb(var(--color-content-subtle))"
            fontSize={12}
            minTickGap={32}
          />
          <YAxis
            yAxisId="productivity"
            stroke="rgb(var(--color-content-subtle))"
            fontSize={12}
            domain={['auto', 'auto']}
          />
          {weather ? (
            <YAxis
              yAxisId="weather"
              orientation="right"
              stroke="rgb(var(--color-content-subtle))"
              fontSize={12}
              domain={['auto', 'auto']}
            />
          ) : null}
          <Tooltip
            contentStyle={{
              background: 'rgb(var(--color-surface-raised))',
              border: '1px solid rgb(var(--color-border))',
              borderRadius: 8,
              fontSize: 12,
            }}
          />
          <Legend />
          <Line
            yAxisId="productivity"
            type="monotone"
            dataKey="value"
            name="Productivity"
            stroke="rgb(var(--color-brand))"
            strokeWidth={2}
            dot={false}
            connectNulls
          />
          {weather ? (
            <Line
              yAxisId="weather"
              type="monotone"
              dataKey="weather"
              name={`${weather.label} (${weather.unit})`}
              stroke="#f59e0b"
              strokeWidth={2}
              strokeDasharray="4 2"
              dot={false}
              connectNulls
            />
          ) : null}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
