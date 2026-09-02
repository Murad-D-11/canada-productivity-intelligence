import {
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { ObservationPoint } from '../../lib/statcanApi';

interface ForecastChartProps {
  /** Real observed history for the selected series. */
  history: ObservationPoint[];
  /** The forecast value returned by the backend model. */
  forecastValue: number;
  /** Label for the forecast period (e.g. "2026-04"). */
  forecastPeriod: string;
  height?: number;
}

/**
 * Historical productivity with the model forecast appended as a visually
 * distinct point. The observed series is a solid line; the transition from the
 * last observed period to the forecast is a dashed segment ending in a marked
 * forecast dot, so users can tell observed from predicted at a glance.
 *
 * Only real values are plotted (suppressed observations are omitted); the single
 * forecast point is the backend model's output — never fabricated here.
 */
export function ForecastChart({
  history,
  forecastValue,
  forecastPeriod,
  height = 320,
}: ForecastChartProps) {
  const observed = history
    .filter((p) => p.value !== null)
    .map((p) => ({ period: p.period, observed: p.value as number, forecast: null as number | null }))
    .sort((a, b) => a.period.localeCompare(b.period));

  const lastObserved = observed[observed.length - 1];

  // The forecast series carries two points so it renders as a short connecting
  // segment: the last observed period (shared anchor) and the forecast period.
  const rows: Array<{ period: string; observed: number | null; forecast: number | null }> = [
    ...observed,
    { period: forecastPeriod, observed: null, forecast: forecastValue },
  ];
  if (lastObserved) {
    // Anchor the dashed forecast segment at the last observed value.
    const anchor = rows.find((r) => r.period === lastObserved.period);
    if (anchor) anchor.forecast = lastObserved.observed;
  }

  return (
    <div style={{ height }} aria-label="Historical and forecast productivity chart">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={rows} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgb(var(--color-border))" />
          <XAxis
            dataKey="period"
            stroke="rgb(var(--color-content-subtle))"
            fontSize={12}
            minTickGap={32}
          />
          <YAxis
            stroke="rgb(var(--color-content-subtle))"
            fontSize={12}
            domain={['auto', 'auto']}
          />
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
            type="monotone"
            dataKey="observed"
            name="Observed"
            stroke="rgb(var(--color-brand))"
            strokeWidth={2}
            dot={false}
            connectNulls
          />
          <Line
            type="monotone"
            dataKey="forecast"
            name="Forecast"
            stroke="rgb(var(--color-info))"
            strokeWidth={2}
            strokeDasharray="5 4"
            dot={false}
            connectNulls
          />
          <ReferenceDot
            x={forecastPeriod}
            y={forecastValue}
            r={5}
            fill="rgb(var(--color-info))"
            stroke="rgb(var(--color-surface-raised))"
            strokeWidth={2}
            isFront
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
