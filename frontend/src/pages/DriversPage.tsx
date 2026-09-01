import { PageHeader, Card, CardHeader, CardBody, EmptyState, Badge } from '../components/ui';

/**
 * Drivers view (design shell). Copy is deliberately careful: SHAP-based
 * attributions describe association, not causation.
 */
export function DriversPage() {
  return (
    <>
      <PageHeader
        title="Drivers"
        description="Feature attributions associated with productivity changes."
        actions={<Badge tone="info">Association, not causation</Badge>}
      />

      <Card>
        <CardHeader
          title="Attribution ranking"
          description="SHAP-based feature contributions render here once a model is trained."
        />
        <CardBody>
          <EmptyState
            title="No attributions yet"
            description="These values describe how features relate to model predictions. They do not imply that changing a driver causes a productivity change."
          />
        </CardBody>
      </Card>
    </>
  );
}
