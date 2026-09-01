import { PageHeader, StatTile, Card, CardHeader, CardBody, EmptyState } from '../components/ui';
import { ChartPlaceholder } from '../components/charts/ChartPlaceholder';

/** National snapshot. Design shell with placeholder tiles and an empty chart. */
export function OverviewPage() {
  return (
    <>
      <PageHeader
        title="Overview"
        description="A national snapshot of Canadian productivity and its most recent movements."
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile label="Labour productivity (latest)" value="—" hint="Awaiting data" />
        <StatTile label="Quarter-over-quarter change" value="—" hint="Awaiting data" />
        <StatTile label="Multifactor productivity" value="—" hint="Awaiting data" />
        <StatTile label="Industries covered" value="—" hint="Awaiting data" />
      </div>

      <Card>
        <CardHeader
          title="Productivity trend"
          description="Time series will render here once the data pipeline is connected."
        />
        <CardBody>
          <ChartPlaceholder />
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Recent movements" description="Notable changes by industry." />
        <CardBody>
          <EmptyState
            title="No data loaded yet"
            description="This platform never displays fabricated values. Once ETL runs against Statistics Canada, real movements appear here."
          />
        </CardBody>
      </Card>
    </>
  );
}
