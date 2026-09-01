import { Router, type RequestHandler } from 'express';
import { metaRouter } from './meta.route.js';

/**
 * Aggregates the versioned API surface. Domain endpoints are declared here as
 * explicit "not yet implemented" routes so the API contract is visible and
 * discoverable, while honestly signalling that no data is served yet. They are
 * fleshed out in later milestones once ETL and ML pipelines exist. We never
 * return fabricated data.
 */
export const apiRouter = Router();

apiRouter.use(metaRouter);

/** Endpoints planned for the analytics surface, with their intended purpose. */
const plannedEndpoints: Array<{ method: string; path: string; description: string }> = [
  { method: 'GET', path: '/industries', description: 'List NAICS industries available in the dataset.' },
  { method: 'GET', path: '/geographies', description: 'List national/provincial/territorial geographies.' },
  { method: 'GET', path: '/observations', description: 'Query observed productivity series (as published).' },
  { method: 'GET', path: '/forecasts', description: 'Retrieve model forecasts with prediction intervals.' },
  { method: 'GET', path: '/drivers', description: 'Retrieve SHAP-based driver attributions (association).' },
  { method: 'POST', path: '/scenarios', description: 'Run a what-if scenario simulation.' },
];

apiRouter.get('/endpoints', (_req, res) => {
  res.json({ plannedEndpoints });
});

// Register each planned endpoint as an explicit 501 so consumers get a clear,
// documented signal rather than a generic 404.
for (const endpoint of plannedEndpoints) {
  const handler: RequestHandler = (_req, res) => {
    res.status(501).json({
      error: 'Not Implemented',
      endpoint: `${endpoint.method} ${endpoint.path}`,
      description: endpoint.description,
      note: 'This endpoint is defined by the API contract but not yet wired to data. See docs/architecture.md.',
    });
  };
  const path = endpoint.path;
  switch (endpoint.method) {
    case 'GET':
      apiRouter.get(path, handler);
      break;
    case 'POST':
      apiRouter.post(path, handler);
      break;
    default:
      break;
  }
}
