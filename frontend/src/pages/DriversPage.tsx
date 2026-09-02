import { useNavigate } from 'react-router-dom';
import { PageHeader, Card, CardHeader, CardBody, Badge, Button } from '../components/ui';

/**
 * Drivers overview. Feature contributions are specific to a single forecast, so
 * they are surfaced in context on the Forecast page ("What is driving this
 * forecast?"). This page explains the concept honestly and routes users there,
 * rather than inventing a standalone attribution ranking.
 */
export function DriversPage() {
  const navigate = useNavigate();
  return (
    <>
      <PageHeader
        title="Drivers"
        description="How the model arrives at a forecast — the features that contribute to each prediction."
        actions={<Badge tone="caution">Model contribution, not causation</Badge>}
      />

      <Card>
        <CardHeader
          title="Drivers are shown with each forecast"
          description="Contributions depend on a specific industry and period, so they live alongside the forecast that produced them."
        />
        <CardBody className="space-y-4">
          <p className="text-sm text-content-muted">
            For the linear model, each prediction decomposes exactly into a base value plus a contribution
            per feature (previous-quarter productivity, trailing average, employment growth, labour-cost
            growth, and seasonal markers). Generate a forecast to see the ranked contributions behind it,
            each expandable to its value, unit, source, and description.
          </p>
          <p className="text-sm text-content-muted">
            These are <span className="font-medium text-content">model contributions</span> — associations
            the model learned from historical data. They do not establish that changing a feature causes
            productivity to change.
          </p>
          <Button onClick={() => navigate('/forecast')}>Generate a forecast to see its drivers</Button>
        </CardBody>
      </Card>
    </>
  );
}
