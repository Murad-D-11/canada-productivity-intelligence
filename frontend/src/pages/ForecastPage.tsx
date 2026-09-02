import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { PageHeader, Card, CardHeader, CardBody, EmptyState, Select, Button, Badge, StatTile } from '../components/ui';
import { ForecastChart } from '../components/charts/ForecastChart';
import {
  fetchHistory,
  fetchIndustries,
  fetchMeasures,
  type Industry,
  type Measure,
  type ObservationPoint,
} from '../lib/statcanApi';
import { generateForecast, type ForecastResult, type ForecastDriver } from '../lib/forecastApi';
import { ScenarioSimulator } from '../components/ScenarioSimulator';

type LoadState = 'loading' | 'ready' | 'error';
type ForecastState = 'idle' | 'loading' | 'ready' | 'error';

const GEOGRAPHY = 'Canada'; // The ingested feature data is national only.
const HORIZONS = [1];

/** Format a numeric productivity index value, or an em dash when absent. */
function fmt(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return value.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function signed(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  const s = value.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
  return value > 0 ? `+${s}` : s;
}

function changeTone(value: number | null | undefined): 'positive' | 'negative' | 'neutral' {
  if (value === null || value === undefined || value === 0 || Number.isNaN(value)) return 'neutral';
  return value > 0 ? 'positive' : 'negative';
}

/**
 * Forecast experience — select an industry, generate a one-step-ahead labour
 * productivity forecast from the backend model, and inspect the real model
 * contributions that drive it. Forecast values, drivers, metrics, and freshness
 * all come from POST /api/v1/forecast; nothing is computed or fabricated here.
 */
export function ForecastPage() {
  const [industries, setIndustries] = useState<Industry[]>([]);
  const [measureId, setMeasureId] = useState<number | null>(null);
  const [industryName, setIndustryName] = useState<string | null>(null);
  const [horizon, setHorizon] = useState(1);

  const [dimsState, setDimsState] = useState<LoadState>('loading');
  const [dimsError, setDimsError] = useState<string | null>(null);

  const [forecastState, setForecastState] = useState<ForecastState>('idle');
  const [forecast, setForecast] = useState<ForecastResult | null>(null);
  const [forecastError, setForecastError] = useState<string | null>(null);

  const [history, setHistory] = useState<ObservationPoint[]>([]);
  const [expandedDriver, setExpandedDriver] = useState<string | null>(null);

  const [searchParams] = useSearchParams();
  const requestedIndustry = searchParams.get('industry');

  // Load industries + resolve the Labour productivity measure once.
  useEffect(() => {
    let cancelled = false;
    setDimsState('loading');
    Promise.all([fetchIndustries(), fetchMeasures()])
      .then(([inds, meas]) => {
        if (cancelled) return;
        setIndustries(inds);
        // Preselect a drill-down industry from the URL when it matches a real
        // ingested industry; otherwise fall back to a sensible default.
        const fromUrl = requestedIndustry
          ? inds.find((i) => i.name === requestedIndustry)
          : undefined;
        const defaultIndustry =
          fromUrl ?? inds.find((i) => /total economy|business sector/i.test(i.name)) ?? inds[0];
        setIndustryName(defaultIndustry?.name ?? null);
        const lp = meas.find((m: Measure) => /^labour productivity$/i.test(m.name)) ?? meas[0];
        setMeasureId(lp?.memberId ?? null);
        setDimsState('ready');
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setDimsError(e instanceof Error ? e.message : 'Failed to load industries.');
        setDimsState('error');
      });
    return () => {
      cancelled = true;
    };
  }, [requestedIndustry]);

  // Reset a stale forecast when the selection changes.
  useEffect(() => {
    setForecast(null);
    setForecastState('idle');
    setForecastError(null);
    setExpandedDriver(null);
  }, [industryName, horizon]);

  const selectedIndustryId = useMemo(
    () => industries.find((i) => i.name === industryName)?.memberId ?? null,
    [industries, industryName],
  );

  async function onGenerate() {
    if (!industryName) return;
    setForecastState('loading');
    setForecastError(null);
    setExpandedDriver(null);
    try {
      // Fetch the observed history (for the chart) and the model forecast in
      // parallel. History is best-effort; the forecast is required.
      const historyPromise =
        selectedIndustryId !== null && measureId !== null
          ? fetchHistory({ industry: selectedIndustryId, measure: measureId }).then((r) => r.data)
          : Promise.resolve<ObservationPoint[]>([]);

      const [result, hist] = await Promise.all([
        generateForecast({ industry: industryName, geography: GEOGRAPHY, horizon }),
        historyPromise.catch(() => [] as ObservationPoint[]),
      ]);
      setForecast(result);
      setHistory(hist);
      setForecastState('ready');
    } catch (e: unknown) {
      setForecastError(e instanceof Error ? e.message : 'Failed to generate the forecast.');
      setForecastState('error');
    }
  }

  return (
    <>
      <PageHeader
        title="Forecast"
        description="One-step-ahead labour productivity forecast from the trained model, with the real model contributions behind it."
        actions={<Badge tone="info">Real model output</Badge>}
      />

      {dimsState === 'error' ? (
        <Card>
          <CardBody>
            <EmptyState
              title="Couldn't load industries"
              description={dimsError ?? 'The backend API is unreachable. Ensure it is running and data is ingested.'}
            />
          </CardBody>
        </Card>
      ) : dimsState === 'loading' ? (
        <Card>
          <CardBody>
            <EmptyState title="Loading…" description="Fetching supported industries." />
          </CardBody>
        </Card>
      ) : (
        <>
          {/* Selection controls */}
          <Card>
            <CardBody>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <Select
                  label="Industry"
                  value={industryName ?? ''}
                  onChange={(e) => setIndustryName(e.target.value)}
                  options={industries.map((i) => ({ value: i.name, label: i.name }))}
                />
                <Select
                  label="Geography"
                  value={GEOGRAPHY}
                  onChange={() => undefined}
                  disabled
                  options={[{ value: GEOGRAPHY, label: 'Canada (national)' }]}
                />
                <Select
                  label="Forecast horizon"
                  value={horizon}
                  onChange={(e) => setHorizon(Number(e.target.value))}
                  options={HORIZONS.map((h) => ({ value: h, label: `${h} quarter${h > 1 ? 's' : ''} ahead` }))}
                />
              </div>
              <div className="mt-4 flex items-center gap-3">
                <Button onClick={onGenerate} disabled={forecastState === 'loading' || !industryName}>
                  {forecastState === 'loading' ? 'Generating…' : 'Generate Forecast'}
                </Button>
                <span className="text-xs text-content-subtle">
                  Forecast is computed by the backend model, not in the browser.
                </span>
              </div>
            </CardBody>
          </Card>

          {/* States */}
          {forecastState === 'idle' ? (
            <Card>
              <CardBody>
                <EmptyState
                  title="No forecast yet"
                  description="Choose an industry and select Generate Forecast to see the model's projection and its drivers."
                />
              </CardBody>
            </Card>
          ) : forecastState === 'loading' ? (
            <Card>
              <CardBody>
                <EmptyState title="Generating forecast…" description="Running the model against the latest available data." />
              </CardBody>
            </Card>
          ) : forecastState === 'error' ? (
            <Card>
              <CardBody>
                <EmptyState
                  title="Couldn't generate a forecast"
                  description={
                    forecastError ??
                    'The model or feature data may be unavailable for this selection. No forecast is shown rather than a fabricated value.'
                  }
                />
              </CardBody>
            </Card>
          ) : forecast ? (
            <ForecastResultView
              forecast={forecast}
              history={history}
              expandedDriver={expandedDriver}
              onToggleDriver={(f) => setExpandedDriver((cur) => (cur === f ? null : f))}
            />
          ) : null}
        </>
      )}
    </>
  );
}

interface ForecastResultViewProps {
  forecast: ForecastResult;
  history: ObservationPoint[];
  expandedDriver: string | null;
  onToggleDriver: (feature: string) => void;
}

function ForecastResultView({ forecast, history, expandedDriver, onToggleDriver }: ForecastResultViewProps) {
  const current = forecast.currentObservedProductivity;
  const abs = forecast.absolutePredictedChange;
  const pct = forecast.percentagePredictedChange;

  return (
    <>
      {/* Summary — the visual focus */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatTile
          label="Current productivity"
          value={fmt(current)}
          hint={`Observed · ${forecast.basePeriod}`}
        />
        <StatTile
          label="Forecast productivity"
          value={fmt(forecast.forecastProductivity)}
          hint={`Model · ${forecast.forecastPeriod}`}
        />
        <StatTile
          label="Expected change"
          value={abs === null ? '—' : `${signed(abs)}${pct !== null ? ` (${signed(pct)}%)` : ''}`}
          hint={
            abs === null
              ? 'No observed baseline to compare'
              : abs > 0
                ? 'Model projects an increase'
                : abs < 0
                  ? 'Model projects a decrease'
                  : 'Model projects no change'
          }
        />
      </div>

      <div className="flex flex-wrap items-center gap-2 text-xs text-content-subtle">
        <Badge tone={changeTone(abs)}>
          {abs === null ? 'No change basis' : abs > 0 ? 'Projected increase' : abs < 0 ? 'Projected decrease' : 'Flat'}
        </Badge>
        <span>Target: {forecast.target}</span>
        <span aria-hidden>·</span>
        <span>Model {forecast.model.type} · {forecast.model.version}</span>
        <span aria-hidden>·</span>
        <span>Latest data: {forecast.dataFreshness.basePeriodStart}</span>
      </div>

      {/* Historical + forecast chart */}
      <Card>
        <CardHeader
          title="Observed history and forecast"
          description={`${forecast.industry} · ${forecast.geography}. Solid = observed, dashed = model forecast.`}
        />
        <CardBody>
          {history.filter((p) => p.value !== null).length > 0 ? (
            <ForecastChart
              history={history}
              forecastValue={forecast.forecastProductivity}
              forecastPeriod={forecast.forecastPeriod}
            />
          ) : (
            <EmptyState
              title="No observed history to chart"
              description="The forecast summary above is still valid; the historical series for this series is unavailable to plot."
            />
          )}
        </CardBody>
      </Card>

      {/* Drivers */}
      <Card>
        <CardHeader
          title="What is driving this forecast?"
          description="Model contributions for this prediction — association learned from history, not causal effects."
          actions={<Badge tone="caution">Model contribution, not causation</Badge>}
        />
        <CardBody className="space-y-2">
          {forecast.topDrivers.length === 0 ? (
            <EmptyState title="No drivers available" description="The model did not return feature contributions for this forecast." />
          ) : (
            forecast.topDrivers.map((d) => (
              <DriverRow
                key={d.feature}
                driver={d}
                limitation={forecast.limitations}
                expanded={expandedDriver === d.feature}
                onToggle={() => onToggleDriver(d.feature)}
              />
            ))
          )}
          <p className="pt-2 text-xs text-content-subtle">{forecast.disclaimer}</p>
        </CardBody>
      </Card>

      {/* Scenario simulator — reuses this forecast's industry/geography/horizon */}
      <ScenarioSimulator
        industry={forecast.industry}
        geography={forecast.geography}
        horizon={forecast.horizon}
      />
    </>
  );
}

interface DriverRowProps {
  driver: ForecastDriver;
  limitation: string[];
  expanded: boolean;
  onToggle: () => void;
}

function DriverRow({ driver, limitation, expanded, onToggle }: DriverRowProps) {
  const tone = driver.direction === 'increases' ? 'positive' : driver.direction === 'decreases' ? 'negative' : 'neutral';
  return (
    <div className="rounded-md border border-border">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        className="flex w-full items-center justify-between gap-4 px-4 py-3 text-left transition-colors hover:bg-surface-sunken"
      >
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-content">{driver.displayName}</p>
          <p className="text-xs text-content-subtle">
            Current value: {driver.currentValue === null ? '—' : driver.currentValue.toLocaleString()} {driver.unit}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <span className="text-sm tabular-nums text-content-muted">{signed(driver.contribution, 3)}</span>
          <Badge tone={tone}>{driver.direction}</Badge>
        </div>
      </button>
      {expanded ? (
        <div className="space-y-2 border-t border-border px-4 py-3 text-sm">
          <p className="text-content-muted">{driver.description}</p>
          <dl className="grid grid-cols-1 gap-x-6 gap-y-1 sm:grid-cols-2">
            <div className="flex justify-between gap-4">
              <dt className="text-content-subtle">Current value</dt>
              <dd className="text-content">
                {driver.currentValue === null ? '—' : driver.currentValue.toLocaleString()} {driver.unit}
              </dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-content-subtle">Model contribution</dt>
              <dd className="tabular-nums text-content">{signed(driver.contribution, 4)}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-content-subtle">Direction</dt>
              <dd className="text-content">{driver.direction}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-content-subtle">Source</dt>
              <dd className="text-content">{driver.source}</dd>
            </div>
          </dl>
          <p className="pt-1 text-xs text-content-subtle">
            Limitation: {limitation[limitation.length - 1] ?? 'Contribution reflects the model, not a causal effect.'}
          </p>
        </div>
      ) : null}
    </div>
  );
}
