import { useEffect, useMemo, useState } from 'react';
import { PageHeader, Card, CardHeader, CardBody, EmptyState, Select, Badge } from '../components/ui';
import { ProductivityChart } from '../components/charts/ProductivityChart';
import {
  fetchHistory,
  fetchIndustries,
  fetchMeasures,
  type Industry,
  type Measure,
  type ObservationPoint,
} from '../lib/statcanApi';

type LoadState = 'loading' | 'ready' | 'error';

/**
 * Industry Explorer — wired to the real StatCan v1 API.
 *
 * Lets the user pick an industry and measure and renders the historical
 * productivity series with Recharts. Handles loading, empty, and error states
 * explicitly. Displays real data only; suppressed periods are omitted.
 */
export function IndustryExplorerPage() {
  const [industries, setIndustries] = useState<Industry[]>([]);
  const [measures, setMeasures] = useState<Measure[]>([]);
  const [industryId, setIndustryId] = useState<number | null>(null);
  const [measureId, setMeasureId] = useState<number | null>(null);
  const [points, setPoints] = useState<ObservationPoint[]>([]);

  const [dimsState, setDimsState] = useState<LoadState>('loading');
  const [seriesState, setSeriesState] = useState<LoadState>('loading');
  const [error, setError] = useState<string | null>(null);

  // Load industries + measures once.
  useEffect(() => {
    let cancelled = false;
    setDimsState('loading');
    Promise.all([fetchIndustries(), fetchMeasures()])
      .then(([inds, meas]) => {
        if (cancelled) return;
        setIndustries(inds);
        setMeasures(meas);
        // Sensible defaults: Total economy + Labour productivity if present.
        const defaultIndustry =
          inds.find((i) => /total economy/i.test(i.name)) ?? inds[0];
        const defaultMeasure =
          meas.find((m) => /^labour productivity$/i.test(m.name)) ?? meas[0];
        setIndustryId(defaultIndustry?.memberId ?? null);
        setMeasureId(defaultMeasure?.memberId ?? null);
        setDimsState('ready');
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : 'Failed to load industries and measures.');
        setDimsState('error');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Load the series whenever the selection changes.
  useEffect(() => {
    if (industryId === null || measureId === null) return;
    let cancelled = false;
    setSeriesState('loading');
    fetchHistory({ industry: industryId, measure: measureId })
      .then((res) => {
        if (cancelled) return;
        setPoints(res.data);
        setSeriesState('ready');
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : 'Failed to load the productivity series.');
        setSeriesState('error');
      });
    return () => {
      cancelled = true;
    };
  }, [industryId, measureId]);

  const plottable = useMemo(() => points.filter((p) => p.value !== null), [points]);
  const unit = points[0]?.unit ?? null;

  return (
    <>
      <PageHeader
        title="Industry Explorer"
        description="Historical labour productivity from Statistics Canada table 36-10-0207-01."
        actions={<Badge tone="info">Real data (StatCan)</Badge>}
      />

      {dimsState === 'error' ? (
        <Card>
          <CardBody>
            <EmptyState
              title="Couldn't load data"
              description={error ?? 'The backend API is unreachable. Ensure it is running and data is ingested.'}
            />
          </CardBody>
        </Card>
      ) : dimsState === 'loading' ? (
        <Card>
          <CardBody>
            <EmptyState title="Loading…" description="Fetching industries and measures." />
          </CardBody>
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Select
              label="Industry"
              value={industryId ?? ''}
              onChange={(e) => setIndustryId(Number(e.target.value))}
              options={industries.map((i) => ({
                value: i.memberId,
                label: i.classificationCode ? `${i.name} [${i.classificationCode}]` : i.name,
              }))}
            />
            <Select
              label="Measure"
              value={measureId ?? ''}
              onChange={(e) => setMeasureId(Number(e.target.value))}
              options={measures.map((m) => ({ value: m.memberId, label: m.name }))}
            />
          </div>

          <Card>
            <CardHeader
              title="Historical productivity"
              description={unit ? `Unit: ${unit}` : 'Observed series over time.'}
            />
            <CardBody>
              {seriesState === 'loading' ? (
                <EmptyState title="Loading series…" description="Fetching observations." />
              ) : seriesState === 'error' ? (
                <EmptyState
                  title="Couldn't load the series"
                  description={error ?? 'Try a different selection or check the backend.'}
                />
              ) : plottable.length === 0 ? (
                <EmptyState
                  title="No values available"
                  description="Statistics Canada has not published values for this industry and measure combination (all periods suppressed)."
                />
              ) : (
                <ProductivityChart points={points} />
              )}
            </CardBody>
          </Card>
        </>
      )}
    </>
  );
}
