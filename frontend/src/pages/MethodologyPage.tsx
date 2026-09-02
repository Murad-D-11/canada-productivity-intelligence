import { useEffect, useState } from 'react';
import { PageHeader, Card, CardHeader, CardBody, Badge, EmptyState } from '../components/ui';
import { fetchModels, type ModelInfo } from '../lib/overviewApi';

type LoadState = 'loading' | 'ready' | 'error';

interface DataSource {
  organization: string;
  dataset: string;
  provides: string;
  resolution: string;
  why: string;
  link: string;
  active: boolean;
  activeNote: string;
}

// Only the sources the application actually uses. StatCan drives the model;
// MSC GeoMet is wired but not yet ingested, stated honestly.
const dataSources: DataSource[] = [
  {
    organization: 'Statistics Canada',
    dataset: 'Table 36-10-0207-01 — Labour productivity and related measures, by industry (product 36100207)',
    provides: 'Labour productivity, total hours worked, jobs, and compensation by NAICS industry',
    resolution: 'Quarterly, national (Canada)',
    why: 'Source of the forecast target and the productivity/employment/labour-cost features',
    link: 'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610020701',
    active: true,
    activeNote: 'In use',
  },
  {
    organization: 'Environment and Climate Change Canada',
    dataset: 'MSC GeoMet — climate observations (OGC API)',
    provides: 'Temperature, precipitation, snowfall, wind by station/province',
    resolution: 'Monthly, provincial',
    why: 'Optional weather features in the pipeline; included automatically once ingested',
    link: 'https://eccc-msc.github.io/open-data/msc-geomet/ogc_api_en/',
    active: false,
    activeNote: 'Configured, not yet ingested',
  },
];

const pipeline: string[] = [
  'Official data (Statistics Canada WDS)',
  'Cleaning (preserve suppressed values as null; no silent imputation)',
  'Temporal alignment (normalize to the quarterly reference period)',
  'Feature engineering (past-only lags, rolling mean, growth, seasonal markers)',
  'Model training (naive baseline, ridge, random forest)',
  'Chronological validation (time-ordered train/validation/test; no shuffling)',
  'Forecast (one-step-ahead labour productivity)',
  'Explainability (exact per-forecast model contributions)',
  'Scenario analysis (re-run the model under changed eligible inputs)',
];

const limitations: { title: string; body: string }[] = [
  {
    title: 'Predictive, not causal',
    body: 'Drivers and scenario differences are model contributions — statistical association learned from history. They do not establish that changing a feature causes productivity to change.',
  },
  {
    title: 'Public data has reporting delays',
    body: 'Official statistics are released and revised on a schedule; the latest period reflects what Statistics Canada has published, which can lag the present.',
  },
  {
    title: 'Historical relationships can change',
    body: 'The model learns from past patterns. Structural shifts (shocks, policy, measurement changes) can break those relationships going forward.',
  },
  {
    title: 'Scenarios are model responses',
    body: 'A scenario shows how the model output moves under altered inputs — not a forecast of what would actually happen in the economy.',
  },
  {
    title: 'Uncertainty is not fabricated',
    body: 'Prediction intervals are shown only if genuinely computed. This model reports point forecasts and real backtest error (MAE/RMSE/R²) rather than an invented confidence band.',
  },
];

const principles = [
  { title: 'Real data only', body: 'Values come from official Government of Canada sources. Nothing is fabricated.' },
  { title: 'No silent imputation', body: 'Unreleased observations stay null with their source status preserved.' },
  { title: 'No look-ahead', body: 'Features use only past periods; models are validated with time-ordered splits.' },
  { title: 'Honest metrics', body: 'Reported accuracy comes from genuine out-of-sample folds — never hard-coded.' },
];

function fmtMetric(v: number | null | undefined, digits = 3): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  return v.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

/**
 * Methodology — the data sources, the end-to-end pipeline, the real trained
 * model metrics (pulled live from /api/v1/models), and the limitations. Model
 * numbers are never hard-coded; if the API is unavailable the section says so.
 */
export function MethodologyPage() {
  const [model, setModel] = useState<ModelInfo | null>(null);
  const [modelState, setModelState] = useState<LoadState>('loading');

  useEffect(() => {
    let cancelled = false;
    fetchModels()
      .then((res) => {
        if (cancelled) return;
        setModel(res.models[0] ?? null);
        setModelState('ready');
      })
      .catch(() => {
        if (cancelled) return;
        setModelState('error');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <>
      <PageHeader
        title="Methodology"
        description="How official data becomes a productivity forecast — sources, pipeline, real model metrics, and limitations."
      />

      {/* Data sources */}
      <Card>
        <CardHeader title="Data sources" description="Only the sources the application actually uses." />
        <CardBody className="space-y-4">
          {dataSources.map((s) => (
            <div key={s.dataset} className="rounded-md border border-border p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-content">{s.organization}</p>
                  <p className="text-sm text-content-muted">{s.dataset}</p>
                </div>
                <Badge tone={s.active ? 'positive' : 'neutral'}>{s.activeNote}</Badge>
              </div>
              <dl className="mt-3 grid grid-cols-1 gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
                <Row label="Provides" value={s.provides} />
                <Row label="Resolution" value={s.resolution} />
                <Row label="Why it's used" value={s.why} />
                <div className="flex justify-between gap-4">
                  <dt className="text-content-subtle">Reference</dt>
                  <dd>
                    <a href={s.link} target="_blank" rel="noreferrer" className="text-info hover:underline">
                      Official source
                    </a>
                  </dd>
                </div>
              </dl>
            </div>
          ))}
        </CardBody>
      </Card>

      {/* Pipeline */}
      <Card>
        <CardHeader title="Pipeline" description="Official data to scenario analysis." />
        <CardBody>
          <ol className="space-y-2">
            {pipeline.map((step, i) => (
              <li key={step} className="flex items-start gap-3 text-sm">
                <span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-brand/10 text-xs font-medium text-brand">
                  {i + 1}
                </span>
                <span className="text-content-muted">{step}</span>
              </li>
            ))}
          </ol>
        </CardBody>
      </Card>

      {/* Model information — real metrics */}
      <Card>
        <CardHeader
          title="Model information"
          description="Pulled live from the trained model artifact. Metrics are real backtest results."
        />
        <CardBody>
          {modelState === 'loading' ? (
            <EmptyState title="Loading model metadata…" description="Fetching the active model's real metrics." />
          ) : modelState === 'error' || !model ? (
            <EmptyState
              title="Model metadata unavailable"
              description="The model service is unreachable or no model is trained. No metrics are shown rather than fabricated ones."
            />
          ) : (
            <ModelDetails model={model} />
          )}
        </CardBody>
      </Card>

      {/* Limitations */}
      <Card>
        <CardHeader title="Limitations" description="What this tool does and does not claim." />
        <CardBody className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {limitations.map((l) => (
            <div key={l.title} className="rounded-md border border-border p-4">
              <p className="text-sm font-medium text-content">{l.title}</p>
              <p className="mt-1 text-sm text-content-muted">{l.body}</p>
            </div>
          ))}
        </CardBody>
      </Card>

      {/* Data integrity principles */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {principles.map((p) => (
          <Card key={p.title}>
            <CardHeader title={p.title} />
            <CardBody>
              <p className="text-sm text-content-muted">{p.body}</p>
            </CardBody>
          </Card>
        ))}
      </div>
    </>
  );
}

function ModelDetails({ model }: { model: ModelInfo }) {
  const selected = model.metrics.models?.find((m) => m.model_type === model.metrics.selected_model);
  const baseline = model.metrics.models?.find((m) => m.model_type === 'naive');
  return (
    <div className="space-y-4">
      <dl className="grid grid-cols-1 gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
        <Row label="Model" value={`${model.type} (${model.algorithm})`} />
        <Row label="Target" value={model.target} />
        <Row label="Resolution" value={model.resolution} />
        <Row label="Forecast horizon" value={`${model.forecastHorizon} quarter`} />
        <Row label="Training period" value={`${model.trainingPeriod.start ?? '—'} to ${model.trainingPeriod.end ?? '—'}`} />
        <Row label="Validation period" value={`${model.validationPeriod.start ?? '—'} to ${model.validationPeriod.end ?? '—'}`} />
        <Row label="Test period" value={`${model.testPeriod.start ?? '—'} to ${model.testPeriod.end ?? '—'}`} />
        <Row label="Validation method" value="Chronological (time-ordered) split; selection by validation MAE" />
        <Row label="Model version" value={model.version} />
        <Row label="Trained at" value={model.trainedAt} />
      </dl>

      {/* Real test metrics + baseline comparison */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-surface-sunken text-content-muted">
            <tr>
              <th className="px-3 py-2 text-left font-medium">Model</th>
              <th className="px-3 py-2 text-right font-medium">Test MAE</th>
              <th className="px-3 py-2 text-right font-medium">Test RMSE</th>
              <th className="px-3 py-2 text-right font-medium">Test R²</th>
            </tr>
          </thead>
          <tbody>
            {(model.metrics.models ?? []).map((m) => (
              <tr key={m.model_type} className="border-t border-border">
                <td className="px-3 py-2 text-content">
                  {m.model_type}
                  {m.model_type === model.metrics.selected_model ? (
                    <Badge tone="info" className="ml-2">selected</Badge>
                  ) : m.model_type === 'naive' ? (
                    <Badge tone="neutral" className="ml-2">baseline</Badge>
                  ) : null}
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-content">{fmtMetric(m.test?.mae)}</td>
                <td className="px-3 py-2 text-right tabular-nums text-content">{fmtMetric(m.test?.rmse)}</td>
                <td className="px-3 py-2 text-right tabular-nums text-content">{fmtMetric(m.test?.r2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selected && baseline ? (
        <p className="text-xs text-content-subtle">
          Selection: <span className="font-medium text-content">{model.metrics.selected_model}</span> was chosen by
          validation MAE. On the held-out test period its MAE is {fmtMetric(selected.test?.mae)} vs the naive
          baseline&apos;s {fmtMetric(baseline.test?.mae)} — reported honestly whether or not the learned model wins
          out of sample.
        </p>
      ) : null}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-content-subtle">{label}</dt>
      <dd className="text-right text-content">{value}</dd>
    </div>
  );
}
