import {
  PageHeader,
  Card,
  CardHeader,
  CardBody,
  EmptyState,
  StatTile,
  Button,
  Badge,
} from '../components/ui';

/** What-if scenario simulator (design shell). */
export function ScenarioSimulatorPage() {
  return (
    <>
      <PageHeader
        title="Scenario Simulator"
        description="Explore model-implied outcomes under what-if adjustments to inputs."
        actions={<Badge tone="caution">Model-implied, not guaranteed</Badge>}
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardHeader title="Adjustments" description="Set input changes to simulate." />
          <CardBody className="space-y-4">
            <EmptyState
              title="Controls unavailable"
              description="Adjustment sliders populate from model features once training is complete."
            />
            <Button className="w-full" disabled>
              Run scenario
            </Button>
          </CardBody>
        </Card>

        <div className="space-y-4 lg:col-span-2">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <StatTile label="Baseline" value="—" hint="Current model estimate" />
            <StatTile label="Simulated" value="—" hint="Under your adjustments" />
          </div>
          <Card>
            <CardHeader title="Outcome" description="Baseline vs. simulated comparison." />
            <CardBody>
              <EmptyState
                title="No scenario run"
                description="Results appear after a scenario is submitted against a trained model."
              />
            </CardBody>
          </Card>
        </div>
      </div>
    </>
  );
}
