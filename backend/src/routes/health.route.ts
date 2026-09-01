import { Router } from 'express';

/**
 * Liveness and readiness endpoints. These intentionally avoid touching the
 * database so they can report process health even when the DB is unavailable;
 * a separate data-status endpoint reports data/DB readiness.
 */
export const healthRouter = Router();

healthRouter.get('/healthz', (_req, res) => {
  res.json({ status: 'ok', uptime: process.uptime(), timestamp: new Date().toISOString() });
});

healthRouter.get('/readyz', (_req, res) => {
  res.json({ status: 'ready' });
});
