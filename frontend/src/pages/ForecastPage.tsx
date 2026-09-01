import { PageHeader, Card, CardHeader, CardBody, Badge, StatTile } from '../components/ui';
import { ChartPlaceholder } from '../components/charts/ChartPlaceholder';

/** Forecast view (design shell). Emphasizes honesty about metrics. */
export function ForecastPage() {
  return (
    <>
      <PageHeader
        title="Forecast"
        description="Model forecasts with prediction intervals, shown alongside real backtest metrics."
        actions={<Badge tone="caution">Metrics shown only when computed</Badge>}
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatTile label="Backtest MAE" value="—" hint="Populated from real folds" />
        <StatTile label="Backtest RMSE" value="—" hint="Populated from real folds" />
        <StatTile label="Training cutoff" value="—" hint="Guards look-ahead" />
      </div>

      <Card>
        <CardHeader
          title="Forecast vs. observed"
          description="Observed history and forecast with interval bands will render here."
        />
        <CardBody>
          <ChartPlaceholder height={300} />
        </CardBody>
      </Card>
    </>
  );
}
