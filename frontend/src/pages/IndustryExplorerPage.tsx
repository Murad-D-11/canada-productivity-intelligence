import {
  PageHeader,
  Card,
  CardHeader,
  CardBody,
  EmptyState,
  Button,
} from '../components/ui';
import { ChartPlaceholder } from '../components/charts/ChartPlaceholder';

/** Compare productivity across industries and geographies (design shell). */
export function IndustryExplorerPage() {
  return (
    <>
      <PageHeader
        title="Industry Explorer"
        description="Compare productivity across NAICS industries and Canadian geographies."
        actions={
          <Button variant="secondary" disabled>
            Add comparison
          </Button>
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardHeader title="Filters" description="Industry, geography, measure, period." />
          <CardBody>
            <EmptyState
              title="Filters unavailable"
              description="Selection controls populate from the dataset once it is loaded."
            />
          </CardBody>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader title="Comparison" description="Selected series render side by side." />
          <CardBody>
            <ChartPlaceholder />
          </CardBody>
        </Card>
      </div>
    </>
  );
}
