import { Router, type Request, type Response } from 'express';
import { z } from 'zod';
import { asyncHandler, HttpError } from '../middleware/errorHandler.js';
import {
  getFeatureMetadata,
  loadFeatureContext,
  nextQuarterLabel,
  runPrediction,
  SUPPORTED_HORIZONS,
  type FeatureVector,
} from '../services/forecastService.js';

/**
 * What-if scenario simulation (Master Prompt 6).
 *
 *   POST /api/v1/scenarios/simulate
 *
 * Retrieves the real baseline feature vector, computes the baseline forecast,
 * applies ONLY validated scenario changes to eligible features, recomputes the
 * forecast, and returns the difference. Scenario changes are validated against
 * the centralized feature metadata (Prompt 5): unknown features, out-of-range
 * values, the target, and non-controllable features (including weather,
 * calendar, and lag features) are rejected. Industry / geography / date are
 * identifiers, not scenario levers, and cannot be changed here.
 *
 * The response is explicit that differences are MODEL contributions, not causal
 * effects: the simulator shows how the model's output moves, not what would
 * actually happen in the economy.
 */
export const scenariosRouter = Router();

const NON_CAUSAL_WARNING =
  'Scenario differences are changes in the model prediction under altered inputs. ' +
  'They describe association learned from historical data, NOT causal effects: this ' +
  'does not predict what would actually happen if the feature changed in reality.';

const simulateSchema = z.object({
  industry: z.string().min(1, 'industry is required'),
  geography: z.string().min(1).default('Canada'),
  horizon: z.coerce.number().int().default(1),
  // changedFeatures: { featureName: newValue }
  changedFeatures: z.record(z.string(), z.number()).default({}),
});

const eligibleQuerySchema = z.object({
  industry: z.string().min(1, 'industry is required'),
  geography: z.string().min(1).default('Canada'),
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

function parseQuery<T extends z.ZodTypeAny>(schema: T, req: Request): z.infer<T> {
  const result = schema.safeParse(req.query);
  if (!result.success) {
    throw new HttpError(
      400,
      `Invalid query parameters: ${result.error.issues.map((i) => i.message).join('; ')}`,
    );
  }
  return result.data;
}

// GET /api/v1/scenarios/features --------------------------------------------
// Lists the scenario-eligible features for a series, each with its real current
// (baseline) value and the metadata-defined unit, source, and allowed range.
// The frontend renders controls from this — it never invents controllable
// variables or bounds. Ineligible/immutable features are excluded.
scenariosRouter.get(
  '/features',
  asyncHandler(async (req: Request, res: Response) => {
    const q = parseQuery(eligibleQuerySchema, req);
    const meta = await getFeatureMetadata();
    const ctx = await loadFeatureContext(q.industry, q.geography);

    const features = meta.scenario_eligible
      .map((name) => {
        const fm = meta.features[name];
        if (!fm) return null;
        return {
          feature: name,
          displayName: fm.display_name,
          unit: fm.unit,
          description: fm.description,
          source: fm.source,
          sourceTable: fm.source_table,
          min: fm.reasonable_min,
          max: fm.reasonable_max,
          currentValue: (ctx.features as Record<string, number | null>)[name] ?? null,
        };
      })
      .filter((f): f is NonNullable<typeof f> => f !== null);

    res.json({
      industry: ctx.industry,
      geography: ctx.geography,
      basePeriod: ctx.basePeriod,
      basePeriodStart: ctx.basePeriodStart,
      features,
    });
  }),
);

// POST /api/v1/scenarios/simulate --------------------------------------------
scenariosRouter.post(
  '/simulate',
  asyncHandler(async (req: Request, res: Response) => {
    const body = parseBody(simulateSchema, req);

    if (!SUPPORTED_HORIZONS.includes(body.horizon as 1)) {
      throw new HttpError(
        400,
        `Unsupported horizon ${body.horizon}. Supported: ${SUPPORTED_HORIZONS.join(', ')}.`,
      );
    }

    const changed = body.changedFeatures;
    const changedNames = Object.keys(changed);
    if (changedNames.length === 0) {
      throw new HttpError(400, 'Provide at least one feature in changedFeatures.');
    }

    // Validate every requested change against the centralized feature metadata.
    const meta = await getFeatureMetadata();
    const eligible = new Set(meta.scenario_eligible);
    const modelFeatures = new Set(Object.keys(meta.features));

    for (const [name, value] of Object.entries(changed)) {
      if (!modelFeatures.has(name)) {
        throw new HttpError(400, `Unknown or non-model feature: ${JSON.stringify(name)}.`);
      }
      if (!eligible.has(name)) {
        // Covers target, calendar (quarter/month), lag-only, and weather —
        // none are user-controllable scenario levers.
        throw new HttpError(
          400,
          `Feature ${JSON.stringify(name)} is not eligible for scenario simulation.`,
        );
      }
      if (typeof value !== 'number' || !Number.isFinite(value)) {
        throw new HttpError(400, `Invalid value for ${JSON.stringify(name)}: must be a finite number.`);
      }
      const fm = meta.features[name];
      if (fm.reasonable_min !== null && value < fm.reasonable_min) {
        throw new HttpError(
          400,
          `Value ${value} for ${JSON.stringify(name)} is below the allowed minimum ${fm.reasonable_min}.`,
        );
      }
      if (fm.reasonable_max !== null && value > fm.reasonable_max) {
        throw new HttpError(
          400,
          `Value ${value} for ${JSON.stringify(name)} is above the allowed maximum ${fm.reasonable_max}.`,
        );
      }
    }

    // Real baseline feature vector from the database.
    const ctx = await loadFeatureContext(body.industry, body.geography);
    const forecastPeriod = nextQuarterLabel(ctx.basePeriodStart, body.horizon);

    // Baseline forecast.
    const baseline = await runPrediction(ctx.features, forecastPeriod);

    // Apply validated changes to a copy, then recompute.
    const scenarioFeatures: FeatureVector = { ...ctx.features };
    const applied: Array<{ feature: string; baselineValue: number | null; scenarioValue: number }> = [];
    for (const [name, value] of Object.entries(changed)) {
      const key = name as keyof FeatureVector;
      applied.push({ feature: name, baselineValue: ctx.features[key] ?? null, scenarioValue: value });
      scenarioFeatures[key] = value;
    }
    const scenario = await runPrediction(scenarioFeatures, forecastPeriod);

    const absoluteDifference = scenario.prediction - baseline.prediction;
    const relativeDifference =
      baseline.prediction !== 0 ? (absoluteDifference / baseline.prediction) * 100 : null;

    res.json({
      target: baseline.target,
      industry: ctx.industry,
      geography: ctx.geography,
      forecastPeriod,
      horizon: body.horizon,
      baselinePrediction: baseline.prediction,
      scenarioPrediction: scenario.prediction,
      absoluteDifference,
      relativeDifference,
      changedFeatures: applied,
      model: { version: baseline.model_version, type: baseline.model_type },
      warning: NON_CAUSAL_WARNING,
    });
  }),
);
