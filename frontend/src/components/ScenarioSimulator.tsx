import { useEffect, useMemo, useState } from 'react';
import { Card, CardHeader, CardBody, EmptyState, Button, Badge } from './ui';
import {
  fetchScenarioFeatures,
  simulateScenario,
  type ScenarioFeature,
  type ScenarioResult,
} from '../lib/scenarioApi';

type LoadState = 'loading' | 'ready' | 'error';
type SimState = 'idle' | 'loading' | 'ready' | 'error';

interface ScenarioSimulatorProps {
  /** Reused from the current forecast context — not reconfigured by the user. */
  industry: string;
  geography: string;
  horizon: number;
}

function signed(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  const s = value.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
  return value > 0 ? `+${s}` : s;
}

function fmt(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return value.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

/**
 * "Test a Scenario" — lets the user adjust eligible model inputs and see how the
 * model's forecast changes. Controls, units, sources, and allowed ranges all
 * come from the backend feature metadata; the baseline and scenario predictions
 * come from POST /api/v1/scenarios/simulate. Nothing is computed or fabricated
 * in the browser, and results are framed as model-based scenarios, not causal
 * estimates.
 */
export function ScenarioSimulator({ industry, geography, horizon }: ScenarioSimulatorProps) {
  const [features, setFeatures] = useState<ScenarioFeature[]>([]);
  const [featuresState, setFeaturesState] = useState<LoadState>('loading');
  const [featuresError, setFeaturesError] = useState<string | null>(null);

  // Editable draft values keyed by feature name (strings for controlled inputs).
  const [draft, setDraft] = useState<Record<string, string>>({});

  const [simState, setSimState] = useState<SimState>('idle');
  const [result, setResult] = useState<ScenarioResult | null>(null);
  const [simError, setSimError] = useState<string | null>(null);

  // Load the eligible features (with real baseline values) for this series.
  useEffect(() => {
    let cancelled = false;
    setFeaturesState('loading');
    setResult(null);
    setSimState('idle');
    fetchScenarioFeatures({ industry, geography })
      .then((res) => {
        if (cancelled) return;
        setFeatures(res.features);
        setDraft(baselineDraft(res.features));
        setFeaturesState('ready');
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setFeaturesError(e instanceof Error ? e.message : 'Failed to load scenario features.');
        setFeaturesState('error');
      });
    return () => {
      cancelled = true;
    };
  }, [industry, geography]);

  const baseline = useMemo(() => baselineDraft(features), [features]);

  // Which features has the user actually changed from baseline?
  const changed = useMemo(() => {
    const out: Record<string, number> = {};
    for (const f of features) {
      const raw = draft[f.feature];
      if (raw === undefined || raw === '') continue;
      const value = Number(raw);
      if (Number.isNaN(value)) continue;
      const base = f.currentValue;
      if (base === null || value !== base) out[f.feature] = value;
    }
    return out;
  }, [draft, features]);

  // Client-side validation mirrors the backend metadata bounds.
  const invalid = useMemo(() => {
    const problems: string[] = [];
    for (const f of features) {
      const raw = draft[f.feature];
      if (raw === undefined || raw === '') continue;
      const value = Number(raw);
      if (Number.isNaN(value)) {
        problems.push(`${f.displayName} must be a number.`);
        continue;
      }
      if (f.min !== null && value < f.min) problems.push(`${f.displayName} is below the minimum (${f.min}).`);
      if (f.max !== null && value > f.max) problems.push(`${f.displayName} is above the maximum (${f.max}).`);
    }
    return problems;
  }, [draft, features]);

  const hasChanges = Object.keys(changed).length > 0;

  function onReset() {
    setDraft(baseline);
    setResult(null);
    setSimState('idle');
    setSimError(null);
  }

  async function onSimulate() {
    if (!hasChanges || invalid.length > 0) return;
    setSimState('loading');
    setSimError(null);
    try {
      const res = await simulateScenario({ industry, geography, horizon, changedFeatures: changed });
      setResult(res);
      setSimState('ready');
    } catch (e: unknown) {
      setSimError(e instanceof Error ? e.message : 'Failed to simulate the scenario.');
      setSimState('error');
    }
  }

  return (
    <Card>
      <CardHeader
        title="Test a Scenario"
        description="Adjust eligible model inputs and see how the model's forecast changes."
        actions={<Badge tone="caution">Model-based scenario, not causal</Badge>}
      />
      <CardBody className="space-y-4">
        {featuresState === 'loading' ? (
          <EmptyState title="Loading scenario controls…" description="Fetching the adjustable model inputs for this series." />
        ) : featuresState === 'error' ? (
          <EmptyState
            title="Couldn't load scenario controls"
            description={featuresError ?? 'The scenario inputs are unavailable for this selection.'}
          />
        ) : features.length === 0 ? (
          <EmptyState
            title="No adjustable inputs"
            description="No model features are eligible for scenario simulation for this series."
          />
        ) : (
          <>
            {/* Controls — one per eligible feature */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {features.map((f) => (
                <FeatureControl
                  key={f.feature}
                  feature={f}
                  value={draft[f.feature] ?? ''}
                  onChange={(v) => setDraft((d) => ({ ...d, [f.feature]: v }))}
                />
              ))}
            </div>

            {invalid.length > 0 ? (
              <ul className="rounded-md border border-negative/30 bg-negative/5 px-4 py-2 text-xs text-negative">
                {invalid.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            ) : null}

            <div className="flex flex-wrap items-center gap-3">
              <Button onClick={onSimulate} disabled={simState === 'loading' || !hasChanges || invalid.length > 0}>
                {simState === 'loading' ? 'Simulating…' : 'Simulate'}
              </Button>
              <Button variant="secondary" onClick={onReset} disabled={simState === 'loading'}>
                Reset to baseline
              </Button>
              {!hasChanges ? (
                <span className="text-xs text-content-subtle">Change at least one input to simulate.</span>
              ) : null}
            </div>

            {/* Results */}
            {simState === 'error' ? (
              <EmptyState
                title="Couldn't simulate"
                description={simError ?? 'The scenario could not be run. No result is shown rather than a fabricated value.'}
              />
            ) : simState === 'ready' && result ? (
              <ScenarioResultView result={result} />
            ) : null}
          </>
        )}
      </CardBody>
    </Card>
  );
}

/** Build the baseline draft (feature -> current value as string). */
function baselineDraft(features: ScenarioFeature[]): Record<string, string> {
  const out: Record<string, string> = {};
  for (const f of features) {
    out[f.feature] = f.currentValue === null ? '' : String(f.currentValue);
  }
  return out;
}

interface FeatureControlProps {
  feature: ScenarioFeature;
  value: string;
  onChange: (value: string) => void;
}

function FeatureControl({ feature, value, onChange }: FeatureControlProps) {
  const rangeLabel =
    feature.min !== null && feature.max !== null
      ? `${feature.min} to ${feature.max}`
      : feature.min !== null
        ? `≥ ${feature.min}`
        : feature.max !== null
          ? `≤ ${feature.max}`
          : 'no fixed range';
  const inputId = `scenario-${feature.feature}`;
  return (
    <div className="rounded-md border border-border p-3">
      <div className="flex items-baseline justify-between gap-2">
        <label htmlFor={inputId} className="text-sm font-medium text-content">
          {feature.displayName}
        </label>
        <span className="text-xs text-content-subtle">{feature.unit}</span>
      </div>
      <input
        id={inputId}
        type="number"
        value={value}
        min={feature.min ?? undefined}
        max={feature.max ?? undefined}
        step="any"
        onChange={(e) => onChange(e.target.value)}
        className="mt-2 w-full rounded-md border border-border bg-surface-raised px-3 py-2 text-sm text-content focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand"
      />
      <div className="mt-1.5 flex flex-wrap justify-between gap-x-3 text-xs text-content-subtle">
        <span>
          Current: {feature.currentValue === null ? '—' : feature.currentValue.toLocaleString()}
        </span>
        <span>Allowed: {rangeLabel}</span>
      </div>
      <p className="mt-1 text-xs text-content-subtle">Source: {feature.source}</p>
    </div>
  );
}

function ScenarioResultView({ result }: { result: ScenarioResult }) {
  const diff = result.absoluteDifference;
  const rel = result.relativeDifference;
  const tone = diff > 0 ? 'positive' : diff < 0 ? 'negative' : 'neutral';

  // Simple comparison bar scale: relative to the larger of the two magnitudes.
  const max = Math.max(Math.abs(result.baselinePrediction), Math.abs(result.scenarioPrediction), 1);
  const basePct = (result.baselinePrediction / max) * 100;
  const scenPct = (result.scenarioPrediction / max) * 100;

  return (
    <div className="space-y-4 border-t border-border pt-4">
      {/* Baseline / Scenario / Difference */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div className="rounded-md border border-border px-4 py-3">
          <p className="text-xs text-content-muted">Baseline forecast</p>
          <p className="mt-1 text-xl font-semibold tabular-nums text-content">{fmt(result.baselinePrediction)}</p>
        </div>
        <div className="rounded-md border border-border px-4 py-3">
          <p className="text-xs text-content-muted">Scenario forecast</p>
          <p className="mt-1 text-xl font-semibold tabular-nums text-content">{fmt(result.scenarioPrediction)}</p>
        </div>
        <div className="rounded-md border border-border px-4 py-3">
          <p className="text-xs text-content-muted">Model-predicted difference</p>
          <p className="mt-1 text-xl font-semibold tabular-nums text-content">
            {signed(diff)}
            {rel !== null ? <span className="ml-1 text-sm font-normal text-content-muted">({signed(rel)}%)</span> : null}
          </p>
        </div>
      </div>

      {/* Simple baseline -> scenario comparison bars */}
      <div className="space-y-2">
        <ComparisonBar label="Baseline" value={result.baselinePrediction} pct={basePct} tone="neutral" />
        <ComparisonBar label="Scenario" value={result.scenarioPrediction} pct={scenPct} tone={tone} />
      </div>

      {/* Changed assumptions */}
      <div>
        <p className="mb-2 text-sm font-medium text-content">Changed assumptions</p>
        <div className="overflow-hidden rounded-md border border-border">
          <table className="w-full text-sm">
            <thead className="bg-surface-sunken text-content-muted">
              <tr>
                <th className="px-3 py-2 text-left font-medium">Feature</th>
                <th className="px-3 py-2 text-right font-medium">Current</th>
                <th className="px-3 py-2 text-right font-medium">Scenario</th>
                <th className="px-3 py-2 text-right font-medium">Change</th>
              </tr>
            </thead>
            <tbody>
              {result.changedFeatures.map((c) => (
                <tr key={c.feature} className="border-t border-border">
                  <td className="px-3 py-2 text-content">{c.feature}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-content-muted">
                    {c.baselineValue === null ? '—' : c.baselineValue.toLocaleString()}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums text-content">{c.scenarioValue.toLocaleString()}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-content">
                    {c.baselineValue === null ? '—' : signed(c.scenarioValue - c.baselineValue, 4)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <p className="text-xs text-content-subtle">
        The model predicts a {signed(diff)} difference{rel !== null ? ` (${signed(rel)}%)` : ''} under this scenario for{' '}
        {result.forecastPeriod}. This is a model-based scenario, not a causal estimate or guarantee. {result.warning}
      </p>
    </div>
  );
}

function ComparisonBar({
  label,
  value,
  pct,
  tone,
}: {
  label: string;
  value: number;
  pct: number;
  tone: 'positive' | 'negative' | 'neutral';
}) {
  const color =
    tone === 'positive' ? 'bg-positive' : tone === 'negative' ? 'bg-negative' : 'bg-brand';
  return (
    <div className="flex items-center gap-3">
      <span className="w-20 shrink-0 text-xs text-content-muted">{label}</span>
      <div className="h-4 flex-1 overflow-hidden rounded bg-surface-sunken">
        <div className={`h-full ${color}`} style={{ width: `${Math.max(0, Math.min(100, pct))}%` }} />
      </div>
      <span className="w-16 shrink-0 text-right text-xs tabular-nums text-content">{fmt(value)}</span>
    </div>
  );
}
