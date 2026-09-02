import { Router, type Request, type Response } from 'express';
import { z } from 'zod';
import { asyncHandler, HttpError } from '../middleware/errorHandler.js';
import {
  getModelInfo,
  loadFeatureContext,
  nextQuarterLabel,
  runForecast,
  SUPPORTED_HORIZONS,
  TARGET_MEASURE,
} from '../services/forecastService.js';

/**
 * Forecasting + model endpoints (Master Prompt 6).
 *
 *   POST /api/v1/forecast   — one-step-ahead labour-productivity forecast
 *   GET  /api/v1/models     — active model metadata + real metrics
 *
 * Mounted on the existing v1 router. The backend retrieves the real feature
 * vector from the database and calls the Python model bridge; the frontend
 * never constructs ML inputs and no values are fabricated.
 */
export const forecastRouter = Router();

const LIMITATIONS = [
  'One-step-ahead quarterly forecast; accuracy degrades beyond the trained horizon.',
  'National (Canada) coverage only; no sub-national breakdown.',
  'Top drivers are model contributions (association), not causal effects.',
];

const forecastSchema = z.object({
  industry: z.string().min(1, 'industry is required'),
  geography: z.string().min(1).default('Canada'),
  horizon: z.coerce.number().int().default(1),
});

function parseBody<T extends z.ZodTypeAny>(schema: T, req: Request): z.infer<T> {
  const result = schema.safeParse(req.body);
  if (!result.success) {
    throw new HttpError(
      400,
      `Invalid request body: ${result.error.issues.map((i) => i.message).join('; ')}`,
    );
  }
  return result.data;
}

// POST /api/v1/forecast ------------------------------------------------------
forecastRouter.post(
  '/forecast',
  asyncHandler(async (req: Request, res: Response) => {
    const body = parseBody(forecastSchema, req);

    if (!SUPPORTED_HORIZONS.includes(body.horizon as 1)) {
      throw new HttpError(
        400,
        `Unsupported horizon ${body.horizon}. Supported: ${SUPPORTED_HORIZONS.join(', ')}.`,
      );
    }

    const ctx = await loadFeatureContext(body.industry, body.geography);
    const forecastPeriod = nextQuarterLabel(ctx.basePeriodStart, body.horizon);
    const { prediction, explanation } = await runForecast(ctx.features, forecastPeriod);

    // Absolute + percentage change vs the latest observed value, only when the
    // observed value exists (never fabricate a baseline).
    const current = ctx.currentObserved;
    const absoluteChange = current !== null ? prediction.prediction - current : null;
    const percentChange =
      current !== null && current !== 0 ? (absoluteChange! / current) * 100 : null;

    // Top drivers = largest-magnitude model contributions for THIS forecast.
    const topDrivers = explanation.contributions.slice(0, 5).map((c) => ({
      feature: c.feature,
      displayName: c.display_name,
      currentValue: c.current_value,
      contribution: c.contribution,
      direction: c.direction,
      unit: c.unit,
      source: c.source,
      description: c.description,
    }));

    res.json({
      target: prediction.target ?? TARGET_MEASURE,
      industry: ctx.industry,
      geography: ctx.geography,
      basePeriod: ctx.basePeriod,
      forecastPeriod,
      horizon: body.horizon,
      resolution: prediction.resolution,
      currentObservedProductivity: current,
      forecastProductivity: prediction.prediction,
      absolutePredictedChange: absoluteChange,
      percentagePredictedChange: percentChange,
      model: {
        version: prediction.model_version,
        type: prediction.model_type,
      },
      baseValue: explanation.base_value,
      topDrivers,
      missingFeatures: prediction.missing_features,
      dataFreshness: {
        featureSet: ctx.featureSetName,
        basePeriod: ctx.basePeriod,
        basePeriodStart: ctx.basePeriodStart,
      },
      disclaimer: explanation.disclaimer,
      limitations: LIMITATIONS,
    });
  }),
);

// GET /api/v1/models ---------------------------------------------------------
forecastRouter.get(
  '/models',
  asyncHandler(async (_req: Request, res: Response) => {
    const info = (await getModelInfo()) as Record<string, any>;
    res.json({
      models: [
        {
          version: info.model_version,
          type: info.model_type,
          algorithm: info.algorithm,
          target: info.target,
          resolution: info.resolution,
          forecastHorizon: info.forecast_horizon,
          trainingPeriod: info.training_period,
          validationPeriod: info.validation_period,
          testPeriod: info.test_period,
          metrics: info.metrics,
          trainedAt: info.trained_at,
          active: info.is_active,
        },
      ],
    });
  }),
);
