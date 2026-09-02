import { prisma } from '../lib/prisma.js';
import { HttpError } from '../middleware/errorHandler.js';
import { callBridge } from './mlBridge.js';

/**
 * Forecast + scenario domain service.
 *
 * The backend owns feature retrieval: it reads the most recent ML-ready
 * `FeatureRow` for a requested (industry, geography) from the database and hands
 * that real feature vector to the Python model bridge. The frontend never
 * builds feature vectors, and no values are fabricated — a missing feature set
 * or series surfaces as a typed HttpError.
 */

// The model target measure (matches the trained artifact / feature pipeline).
export const TARGET_MEASURE = 'Labour productivity';

// Model feature columns fed to the estimator, in the pipeline's contract order.
const MODEL_FEATURE_KEYS = [
  'prodLag1',
  'prodLag4',
  'prodRollMean4',
  'employmentGrowth',
  'labourCostGrowth',
  'quarter',
  'month',
] as const;

type FeatureKey = (typeof MODEL_FEATURE_KEYS)[number];
export type FeatureVector = Record<FeatureKey, number | null>;

export interface FeatureContext {
  featureSetId: string;
  featureSetName: string;
  industry: string;
  geography: string;
  measure: string;
  /** The latest period present for this series (basis of the forecast origin). */
  basePeriod: string;
  basePeriodStart: string;
  /** Observed productivity at the base period (may be null if suppressed). */
  currentObserved: number | null;
  features: FeatureVector;
}

export interface FeatureMetaEntry {
  name: string;
  display_name: string;
  unit: string;
  description: string;
  source: string;
  source_table: string | null;
  scenario_eligible: boolean;
  reasonable_min: number | null;
  reasonable_max: number | null;
}

export interface FeatureMetadataBundle {
  features: Record<string, FeatureMetaEntry>;
  scenario_eligible: string[];
}

interface PredictionPayload {
  prediction: number;
  model_version: string;
  model_type: string;
  target: string;
  resolution: string;
  forecast_horizon: number;
  forecast_period: string | null;
  features_used: Record<string, number | null>;
  missing_features: string[];
  model_metadata: Record<string, unknown>;
}

interface ExplanationPayload {
  method: string;
  prediction: number;
  base_value: number;
  target: string;
  model_version: string;
  model_type: string;
  contributions: Array<Record<string, unknown>>;
  missing_features: string[];
  disclaimer: string;
  notes: string[];
}

/** Horizons the trained model actually supports (artifact horizon = 1). */
export const SUPPORTED_HORIZONS = [1] as const;

/**
 * Resolve the most recent feature set + the latest feature row for a series.
 * Returns the real feature vector the model expects. Throws typed errors for
 * unsupported industry/geography or missing feature data (never fabricates).
 */
export async function loadFeatureContext(
  industry: string,
  geography: string,
): Promise<FeatureContext> {
  const featureSet = await prisma.featureSet.findFirst({
    orderBy: { createdAt: 'desc' },
    select: { id: true, name: true },
  });
  if (!featureSet) {
    throw new HttpError(
      503,
      'No feature set has been generated yet. Run the ML feature pipeline first.',
    );
  }

  // Latest row for this (industry, geography, target measure) series.
  const row = await prisma.featureRow.findFirst({
    where: {
      featureSetId: featureSet.id,
      industry,
      geography,
      measure: TARGET_MEASURE,
    },
    orderBy: { periodStart: 'desc' },
    select: {
      industry: true,
      geography: true,
      measure: true,
      periodStart: true,
      periodLabel: true,
      targetValue: true,
      prodLag1: true,
      prodLag4: true,
      prodRollMean4: true,
      employmentGrowth: true,
      labourCostGrowth: true,
      quarter: true,
      month: true,
    },
  });

  if (!row) {
    // Distinguish "industry/geography not supported" from "no data" by checking
    // whether the industry exists at all in the feature set.
    const anyForIndustry = await prisma.featureRow.findFirst({
      where: { featureSetId: featureSet.id, industry },
      select: { id: true },
    });
    if (!anyForIndustry) {
      throw new HttpError(404, `Unsupported industry: ${JSON.stringify(industry)}.`);
    }
    const anyForGeography = await prisma.featureRow.findFirst({
      where: { featureSetId: featureSet.id, geography },
      select: { id: true },
    });
    if (!anyForGeography) {
      throw new HttpError(404, `Unsupported geography: ${JSON.stringify(geography)}.`);
    }
    throw new HttpError(
      404,
      `No feature data for industry ${JSON.stringify(industry)} in ${JSON.stringify(geography)}.`,
    );
  }

  return {
    featureSetId: featureSet.id,
    featureSetName: featureSet.name,
    industry: row.industry,
    geography: row.geography,
    measure: row.measure,
    basePeriod: row.periodLabel,
    basePeriodStart: row.periodStart.toISOString().slice(0, 10),
    currentObserved: row.targetValue,
    features: {
      prodLag1: row.prodLag1,
      prodLag4: row.prodLag4,
      prodRollMean4: row.prodRollMean4,
      employmentGrowth: row.employmentGrowth,
      labourCostGrowth: row.labourCostGrowth,
      quarter: row.quarter,
      month: row.month,
    },
  };
}

/** Fetch the central feature metadata (cached per-process after first call). */
let _featureMetaCache: FeatureMetadataBundle | null = null;
export async function getFeatureMetadata(): Promise<FeatureMetadataBundle> {
  if (_featureMetaCache) return _featureMetaCache;
  const bundle = await callBridge<FeatureMetadataBundle>({ action: 'feature_metadata' });
  _featureMetaCache = bundle;
  return bundle;
}

/** Run the model for a feature vector, returning prediction + explanation. */
export async function runForecast(
  features: FeatureVector,
  forecastPeriod: string | null,
): Promise<{ prediction: PredictionPayload; explanation: ExplanationPayload }> {
  return callBridge<{ prediction: PredictionPayload; explanation: ExplanationPayload }>({
    action: 'forecast',
    features,
    forecast_period: forecastPeriod,
  });
}

/** Run the model for a feature vector, prediction only (used for scenarios). */
export async function runPrediction(
  features: FeatureVector,
  forecastPeriod: string | null,
): Promise<PredictionPayload> {
  const out = await callBridge<{ prediction: PredictionPayload }>({
    action: 'predict',
    features,
    forecast_period: forecastPeriod,
  });
  return out.prediction;
}

/** Model metadata for the /api/v1/models endpoint. */
export async function getModelInfo(): Promise<Record<string, unknown>> {
  return callBridge<Record<string, unknown>>({ action: 'model_info' });
}

/** Compute the next quarterly period label after a YYYY-MM-DD base period. */
export function nextQuarterLabel(basePeriodStart: string, horizon: number): string {
  const [y, m] = basePeriodStart.split('-').map(Number);
  // Quarter-start months are 1,4,7,10. Advance by `horizon` quarters.
  const monthsToAdd = horizon * 3;
  const zeroBased = (m - 1) + monthsToAdd;
  const year = y + Math.floor(zeroBased / 12);
  const month = (zeroBased % 12) + 1;
  return `${year}-${String(month).padStart(2, '0')}`;
}

export type { PredictionPayload, ExplanationPayload };
