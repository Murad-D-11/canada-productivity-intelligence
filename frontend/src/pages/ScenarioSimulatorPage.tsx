import { useEffect, useState } from 'react';
import { PageHeader, Card, CardBody, EmptyState, Select, Badge } from '../components/ui';
import { ScenarioSimulator } from '../components/ScenarioSimulator';
import { fetchIndustries, type Industry } from '../lib/statcanApi';

type LoadState = 'loading' | 'ready' | 'error';

const GEOGRAPHY = 'Canada';
const HORIZON = 1;

/**
 * Standalone what-if scenario simulator. Reuses the same ScenarioSimulator
 * component embedded in the Forecast page, driven by real feature metadata and
 * the trained model. Pick an industry, adjust eligible inputs, and compare the
 * model's baseline vs scenario forecast. Nothing here is fabricated.
 */
export function ScenarioSimulatorPage() {
  const [industries, setIndustries] = useState<Industry[]>([]);
  const [industryName, setIndustryName] = useState<string | null>(null);
  const [state, setState] = useState<LoadState>('loading');

  useEffect(() => {
    let cancelled = false;
    fetchIndustries()
      .then((inds) => {
        if (cancelled) return;
        setIndustries(inds);
        const def = inds.find((i) => /business sector|total economy/i.test(i.name)) ?? inds[0];
        setIndustryName(def?.name ?? null);
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
        title="Scenario Simulator"
        description="Adjust eligible model inputs for an industry and compare the model's baseline vs scenario forecast."
        actions={<Badge tone="caution">Model-based scenario, not causal</Badge>}
      />

      {state === 'loading' ? (
        <Card>
          <CardBody>
            <EmptyState title="Loading…" description="Fetching supported industries." />
          </CardBody>
        </Card>
      ) : state === 'error' ? (
        <Card>
          <CardBody>
            <EmptyState
              title="Couldn't load industries"
              description="The backend API is unreachable. Ensure it is running and data is ingested."
            />
          </CardBody>
        </Card>
      ) : (
        <>
          <Card>
            <CardBody>
              <Select
                label="Industry"
                value={industryName ?? ''}
                onChange={(e) => setIndustryName(e.target.value)}
                options={industries.map((i) => ({ value: i.name, label: i.name }))}
              />
              <p className="mt-2 text-xs text-content-subtle">
                Geography: Canada (national) · Horizon: 1 quarter ahead.
              </p>
            </CardBody>
          </Card>

          {industryName ? (
            <ScenarioSimulator
              key={industryName}
              industry={industryName}
              geography={GEOGRAPHY}
              horizon={HORIZON}
            />
          ) : null}
        </>
      )}
    </>
  );
}
