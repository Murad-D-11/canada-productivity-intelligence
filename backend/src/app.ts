import cors from 'cors';
import express, { type Express } from 'express';
import helmet from 'helmet';
import { pinoHttp } from 'pino-http';
import { corsOrigins } from './config/env.js';
import { logger } from './config/logger.js';
import { errorHandler, notFoundHandler } from './middleware/errorHandler.js';
import { apiRouter } from './routes/api.router.js';
import { forecastRouter } from './routes/forecast.router.js';
import { healthRouter } from './routes/health.route.js';
import { scenariosRouter } from './routes/scenarios.router.js';
import { v1Router } from './routes/v1.router.js';
import { weatherRouter } from './routes/weather.router.js';

/**
 * Builds and configures the Express application. Factored out from server
 * bootstrap so it can be imported directly in tests without binding a port.
 */
export function createApp(): Express {
  const app = express();

  app.use(helmet());
  app.use(cors({ origin: corsOrigins }));
  app.use(express.json({ limit: '1mb' }));
  app.use(pinoHttp({ logger }));

  // Health endpoints live at the root (not under /api).
  app.use('/', healthRouter);

  // Versioned StatCan data API (real ingested data).
  app.use('/api/v1', v1Router);

  // Forecasting + model endpoints (bridge to the Python ML system).
  app.use('/api/v1', forecastRouter);

  // What-if scenario simulation.
  app.use('/api/v1/scenarios', scenariosRouter);

  // Weather + feature API (real ingested / derived data). Mounted before the
  // meta router so its concrete routes take precedence.
  app.use('/api', weatherRouter);

  // Legacy/meta API surface (service metadata, planned-endpoint contract).
  app.use('/api', apiRouter);

  app.use(notFoundHandler);
  app.use(errorHandler);

  return app;
}
