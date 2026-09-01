import { PageHeader, Card, CardHeader, CardBody, Badge } from '../components/ui';

interface SourceRow {
  id: string;
  name: string;
  docs: string;
}

// Sources match the backend /api/meta contract. Freshness/coverage are shown as
// "unknown" here because the app is not yet connected to the API.
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
  {
    id: 'CANADIAN_SURVEY_BUSINESS_CONDITIONS',
    name: 'Canadian Survey on Business Conditions',
    docs: 'https://www.statcan.gc.ca/en/survey/business/5426',
  },
];

/** Data source freshness, coverage, and provenance (design shell). */
export function DataStatusPage() {
  return (
    <>
      <PageHeader
        title="Data Status"
        description="Freshness, coverage, and provenance of the configured official data sources."
      />

      <Card>
        <CardHeader
          title="Configured sources"
          description="Live freshness and coverage populate once the app is connected to the API."
        />
        <CardBody className="p-0">
          <ul className="divide-y divide-border">
            {sources.map((s) => (
              <li key={s.id} className="flex items-center justify-between gap-4 px-5 py-4">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-content">{s.name}</p>
                  <a
                    href={s.docs}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs text-info hover:underline"
                  >
                    Documentation
                  </a>
                </div>
                <Badge tone="neutral">Status: unknown</Badge>
              </li>
            ))}
          </ul>
        </CardBody>
      </Card>
    </>
  );
}
