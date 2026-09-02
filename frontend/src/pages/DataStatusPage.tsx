import { useEffect, useState } from 'react';
import { PageHeader, Card, CardHeader, CardBody, Badge, EmptyState, StatTile } from '../components/ui';
import { fetchDataStatus, type DataStatus } from '../lib/statcanApi';

type LoadState = 'loading' | 'ready' | 'error';

interface SourceRow {
  id: string;
  name: string;
  docs: string;
}

// Sources match the backend data contract. Live freshness comes from the API.
const sources: SourceRow[] = [
  {
    id: 'STATCAN_WDS',
    name: 'Statistics Canada Web Data Service',
    docs: 'https://www.statcan.gc.ca/en/developers/wds/user-guide',
  },
  {
    id: 'MSC_GEOMET',
    name: 'Environment and Climate Change Canada MSC GeoMet',
    docs: 'https://eccc-msc.github.io/open-data/msc-geomet/ogc_api_en/',
  },
];

/** Data source freshness, coverage, and provenance — from the real API. */
export function DataStatusPage() {
  const [status, setStatus] = useState<DataStatus | null>(null);
  const [state, setState] = useState<LoadState>('loading');

  useEffect(() => {
    let cancelled = false;
    fetchDataStatus()
      .then((s) => {
        if (cancelled) return;
        setStatus(s);
        setState('ready');
      })
      .catch(() => {
        if (cancelled) return;
        setState('error');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <>
      <PageHeader
        title="Data Status"
        description="Freshness, coverage, and provenance of the official data sources — read live from the API."
        actions={<Badge tone="info">Real data</Badge>}
      />

      {state === 'loading' ? (
        <Card>
          <CardBody>
            <EmptyState title="Loading data status…" description="Querying ingestion coverage and freshness." />
          </CardBody>
        </Card>
      ) : state === 'error' || !status ? (
        <Card>
          <CardBody>
            <EmptyState
              title="Data status unavailable"
              description="The backend API is unreachable. No status is shown rather than a fabricated one."
            />
          </CardBody>
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatTile
              label="Productivity observations"
              value={status.counts ? status.counts.observations.toLocaleString() : '—'}
              hint={status.dataset?.tableRef ?? 'StatCan'}
            />
            <StatTile
              label="Latest productivity period"
              value={status.productivity?.latestObservationPeriod ?? '—'}
              hint={status.productivity?.latestObservationDate ?? 'Awaiting data'}
            />
            <StatTile
              label="Industries covered"
              value={status.supported ? String(status.supported.industries) : '—'}
              hint={status.supported ? status.supported.geographies.join(', ') : 'National'}
            />
            <StatTile
              label="Feature rows"
              value={status.features ? status.features.rowCount.toLocaleString() : '—'}
              hint={status.features ? `Set: ${status.features.name}` : 'No feature set yet'}
            />
          </div>

          <Card>
            <CardHeader title="Statistics Canada — productivity" description={status.dataset?.title ?? 'Labour productivity dataset'} />
            <CardBody>
              <dl className="grid grid-cols-1 gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
                <Row label="Table" value={status.dataset?.tableRef ?? '—'} />
                <Row label="Frequency" value={status.dataset?.frequency ?? '—'} />
                <Row
                  label="Coverage"
                  value={`${status.dataset?.coverage.start ?? '—'} to ${status.dataset?.coverage.end ?? '—'}`}
                />
                <Row label="Latest release" value={status.dataset?.releaseTime?.slice(0, 10) ?? '—'} />
              </dl>
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Environment Canada — weather"
              description="Optional weather features; included automatically once ingested."
            />
            <CardBody>
              {status.weather && status.weather.observations > 0 ? (
                <dl className="grid grid-cols-1 gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
                  <Row label="Observations" value={status.weather.observations.toLocaleString()} />
                  <Row label="Latest period" value={status.weather.latestObservationPeriod ?? '—'} />
                </dl>
              ) : (
                <p className="text-sm text-content-muted">
                  No weather observations ingested yet. Weather features remain inactive until MSC GeoMet
                  data is ingested — the model runs on productivity features in the meantime.
                </p>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Source documentation" description="Official references for the configured data sources." />
            <CardBody className="p-0">
              <ul className="divide-y divide-border">
                {sources.map((s) => (
                  <li key={s.id} className="flex items-center justify-between gap-4 px-5 py-4">
                    <p className="truncate text-sm font-medium text-content">{s.name}</p>
                    <a href={s.docs} target="_blank" rel="noreferrer" className="text-xs text-info hover:underline">
                      Documentation
                    </a>
                  </li>
                ))}
              </ul>
            </CardBody>
          </Card>
        </>
      )}
    </>
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
