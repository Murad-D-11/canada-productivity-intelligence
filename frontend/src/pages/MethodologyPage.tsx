import { PageHeader, Card, CardHeader, CardBody } from '../components/ui';

interface Principle {
  title: string;
  body: string;
}

const principles: Principle[] = [
  {
    title: 'Real data only',
    body: 'Values come from official Government of Canada sources. Nothing is fabricated or invented.',
  },
  {
    title: 'No silent imputation',
    body: 'Unreleased observations stay null with their source status flag preserved. Any imputation is explicit and documented.',
  },
  {
    title: 'No look-ahead',
    body: 'Features use only past periods and models are validated with expanding-window backtests, so future information never leaks into training.',
  },
  {
    title: 'Honest metrics',
    body: 'Reported accuracy comes from genuine out-of-sample folds — never hard-coded.',
  },
  {
    title: 'Association, not causation',
    body: 'Driver attributions (SHAP) describe how features relate to predictions. They do not establish cause and effect.',
  },
];

/** Static methodology summary mirroring docs/methodology.md. */
export function MethodologyPage() {
  return (
    <>
      <PageHeader
        title="Methodology"
        description="How data is sourced, modeled, and evaluated — and the guarantees behind it."
      />

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {principles.map((p) => (
          <Card key={p.title}>
            <CardHeader title={p.title} />
            <CardBody>
              <p className="text-sm text-content-muted">{p.body}</p>
            </CardBody>
          </Card>
        ))}
      </div>
    </>
  );
}
