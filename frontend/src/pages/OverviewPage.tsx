import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { PageHeader, StatTile, Card, CardHeader, CardBody, EmptyState, Badge, Button } from '../components/ui';
import { fetchOverview, type OverviewIndustry, type OverviewResponse } from '../lib/overviewApi';
import { generateForecast, type ForecastResult } from '../lib/forecastApi';

type LoadState = 'loading' | 'ready' | 'error';

// The headline series for the national snapshot. Falls back to the first ranked
// industry if this exact name is not present in the data.
const HEADLINE_INDUSTRY = 'Business sector, goods';

function fmt(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return value.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function signed(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  const s = value.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
  return value > 0 ? `+${s}` : s;
}

function tone(value: number | null | undefined): 'positive' | 'negative' | 'neutral' {
  if (value === null || value === undefined || value === 0 || Number.isNaN(value)) return 'neutral';
  return value > 0 ? 'positive' : 'negative';
}

/**
 * National overview — the "Growing Canada" entry point. Turns real Statistics
 * Canada productivity data and the trained model into a national snapshot plus a
 * model-projected industry comparison. Every number comes from the model or
 * ingested data; the ranking is by predicted change (clearly labelled), not an
 * investment score.
 */
export function OverviewPage() {
  const navigate = useNavigate();

  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [overviewState, setOverviewState] = useState<LoadState>('loading');
  const [overviewError, setOverviewError] = useState<string | null>(null);

  const [headline, setHeadline] = useState<ForecastResult | null>(null);

  useEffect(() => {
    let cancelled = false;
    setOverviewState('loading');
    fetchOverview()
      .then(async (ov) => {
        if (cancelled) return;
        setOverview(ov);
        setOverviewState('ready');
        // Pick the headline industry: the named default if present, else the
        // top-ranked row. Then fetch its full forecast (for drivers).
        const headlineName =
          ov.industries.find((i) => i.industry === HEADLINE_INDUSTRY)?.industry ??
          ov.industries[0]?.industry;
        if (headlineName) {
          try {
            const f = await generateForecast({ industry: headlineName, geography: 'Canada', horizon: 1 });
            if (!cancelled) setHeadline(f);
          } catch {
            // Non-fatal: the comparison table still renders without the snapshot.
          }
        }
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setOverviewError(e instanceof Error ? e.message : 'Failed to load the overview.');
        setOverviewState('error');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const openForecast = (industry: string) =>
    navigate(`/forecast?industry=${encodeURIComponent(industry)}`);

  return (
    <>
      <PageHeader
        title="Canada Productivity Overview"
        description="Where is Canadian labour productivity heading? This turns public Statistics Canada data into next-quarter model projections you can explore by industry."
        actions={<Badge tone="info">Real data + model output</Badge>}
      />

      {overviewState === 'error' ? (
        <Card>
          <CardBody>
            <EmptyState
              title="Couldn't load the overview"
              description={overviewError ?? 'Ensure the backend is running, data is ingested, and a model is trained.'}
            />
          </CardBody>
        </Card>
      ) : overviewState === 'loading' ? (
        <Card>
          <CardBody>
            <EmptyState title="Building the national overview…" description="Forecasting each industry with the trained model." />
          </CardBody>
        </Card>
      ) : overview ? (
        <>
          <NationalSnapshot headline={headline} overview={overview} onOpen={openForecast} />
          <IndustryComparison overview={overview} onOpen={openForecast} />
          <GeographyNote geography={overview.geography} />
          <PurposeNote />
        </>
      ) : null}
    </>
  );
}

function NationalSnapshot({
  headline,
  overview,
  onOpen,
}: {
  headline: ForecastResult | null;
  overview: OverviewResponse;
  onOpen: (industry: string) => void;
}) {
  if (!headline) {
    return (
      <Card>
        <CardHeader title="National snapshot" description="Headline forecast is unavailable right now; the industry comparison below is still live." />
        <CardBody>
          <EmptyState title="Snapshot unavailable" description="The headline industry forecast could not be loaded. No placeholder values are shown." />
        </CardBody>
      </Card>
    );
  }
  const abs = headline.absolutePredictedChange;
  const pct = headline.percentagePredictedChange;
  const drivers = headline.topDrivers.slice(0, 3);
  return (
    <>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile label="Current productivity" value={fmt(headline.currentObservedProductivity)} hint={`${headline.industry} · ${headline.basePeriod}`} />
        <StatTile label="Forecast productivity" value={fmt(headline.forecastProductivity)} hint={`Model · ${headline.forecastPeriod}`} />
        <StatTile
          label="Expected change"
          value={abs === null ? '—' : `${signed(abs)}${pct !== null ? ` (${signed(pct)}%)` : ''}`}
          hint={abs === null ? 'No observed baseline' : abs > 0 ? 'Projected increase' : abs < 0 ? 'Projected decrease' : 'Flat'}
        />
        <StatTile label="Industries covered" value={String(overview.count)} hint="National (Canada)" />
      </div>

      <Card>
        <CardHeader
          title="National snapshot"
          description={`Headline series: ${headline.industry}. Forecast direction and the model drivers behind it.`}
          actions={<Badge tone={tone(abs)}>{abs === null ? 'No basis' : abs > 0 ? 'Increasing' : abs < 0 ? 'Decreasing' : 'Flat'}</Badge>}
        />
        <CardBody className="space-y-3">
          <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-content-muted">
            <span>Target: {headline.target}</span>
            <span>Horizon: {headline.horizon} quarter</span>
            <span>Model: {headline.model.type} · {headline.model.version}</span>
            <span>Latest data: {headline.dataFreshness.basePeriodStart}</span>
          </div>
          <div>
            <p className="mb-2 text-sm font-medium text-content">Major model drivers (this forecast)</p>
            <div className="flex flex-wrap gap-2">
              {drivers.map((d) => (
                <span key={d.feature} className="inline-flex items-center gap-2 rounded-md border border-border px-3 py-1.5 text-xs">
                  <span className="font-medium text-content">{d.displayName}</span>
                  <Badge tone={d.direction === 'increases' ? 'positive' : d.direction === 'decreases' ? 'negative' : 'neutral'}>
                    {d.direction}
                  </Badge>
                </span>
              ))}
            </div>
            <p className="mt-2 text-xs text-content-subtle">{headline.disclaimer}</p>
          </div>
          <Button variant="secondary" onClick={() => onOpen(headline.industry)}>
            Open full forecast
          </Button>
        </CardBody>
      </Card>
    </>
  );
}

function IndustryComparison({ overview, onOpen }: { overview: OverviewResponse; onOpen: (industry: string) => void }) {
  // Only rank rows that have a real percentage change (observed baseline).
  const ranked = useMemo(
    () => overview.industries.filter((r) => r.percentagePredictedChange !== null),
    [overview.industries],
  );
  return (
    <Card>
      <CardHeader
        title="Industry comparison"
        description="Ranked by the model's predicted next-quarter change. A model projection, not an opportunity score or investment recommendation."
        actions={<Badge tone="caution">Ranked by predicted change</Badge>}
      />
      <CardBody className="p-0">
        {ranked.length === 0 ? (
          <div className="p-5">
            <EmptyState title="No comparable forecasts" description="No industries have an observed baseline to compare against." />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-surface-sunken text-content-muted">
                <tr>
                  <th className="px-4 py-2 text-left font-medium">Industry</th>
                  <th className="px-4 py-2 text-right font-medium">Current</th>
                  <th className="px-4 py-2 text-right font-medium">Forecast ({overview.industries[0]?.forecastPeriod})</th>
                  <th className="px-4 py-2 text-right font-medium">Predicted change</th>
                  <th className="px-4 py-2 text-right font-medium">%</th>
                  <th className="px-4 py-2" />
                </tr>
              </thead>
              <tbody>
                {ranked.map((r: OverviewIndustry) => (
                  <tr key={r.industry} className="border-t border-border hover:bg-surface-sunken/50">
                    <td className="px-4 py-2">
                      <button
                        type="button"
                        onClick={() => onOpen(r.industry)}
                        className="text-left text-content hover:text-brand hover:underline"
                      >
                        {r.industry}
                      </button>
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums text-content-muted">{fmt(r.currentObservedProductivity)}</td>
                    <td className="px-4 py-2 text-right tabular-nums text-content">{fmt(r.forecastProductivity)}</td>
                    <td className="px-4 py-2 text-right tabular-nums text-content">{signed(r.absolutePredictedChange)}</td>
                    <td className="px-4 py-2 text-right">
                      <Badge tone={tone(r.percentagePredictedChange)}>{signed(r.percentagePredictedChange)}%</Badge>
                    </td>
                    <td className="px-4 py-2 text-right">
                      <button
                        type="button"
                        onClick={() => onOpen(r.industry)}
                        className="text-xs text-info hover:underline"
                      >
                        View forecast →
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="px-4 py-3 text-xs text-content-subtle">{overview.rankingNote}</p>
      </CardBody>
    </Card>
  );
}

function GeographyNote({ geography }: { geography: string }) {
  return (
    <Card>
      <CardHeader title="Geographic coverage" description="Provincial comparison depends on the ingested data." />
      <CardBody>
        <p className="text-sm text-content-muted">
          The ingested Statistics Canada series (table 36-10-0207-01) currently covers{' '}
          <span className="font-medium text-content">{geography}</span> at the national level only. A
          province/territory comparison will appear here once sub-national productivity data is ingested —
          no provincial figures are shown until then.
        </p>
      </CardBody>
    </Card>
  );
}

function PurposeNote() {
  return (
    <Card>
      <CardBody>
        <p className="text-sm text-content-muted">
          This application turns public Canadian economic data into a tool for understanding productivity
          outlooks and exploring where improvements may warrant further investigation. Projections are
          model-based associations, not causal estimates or guarantees.
        </p>
      </CardBody>
    </Card>
  );
}
