/**
 * Typed clients for the overview + model metadata endpoints (Master Prompt 9).
 *
 * All values come from the real model and ingested data. The industry ranking
 * is by the model's predicted change — explicitly not an "opportunity score".
 */
import { getJson } from './apiClient';

export interface OverviewIndustry {
  industry: string;
  geography: string;
  basePeriod: string;
  forecastPeriod: string;
  currentObservedProductivity: number | null;
  forecastProductivity: number;
  absolutePredictedChange: number | null;
  percentagePredictedChange: number | null;
}

export interface OverviewResponse {
  target: string;
  geography: string;
  resolution: string;
  horizon: number;
  rankingBasis: string;
  rankingNote: string;
  featureSet: string;
  industries: OverviewIndustry[];
  count: number;
}

/** Real, one-request industry comparison ranked by predicted change. */
export async function fetchOverview(): Promise<OverviewResponse> {
  return getJson<OverviewResponse>('/v1/overview');
}

// -- Model metadata ---------------------------------------------------------

export interface ModelMetrics {
  selected_model?: string;
  beats_baseline?: boolean;
  models?: Array<{
    model_type: string;
    algorithm?: string;
    validation?: { mae: number; rmse: number; r2: number | null };
    test?: { mae: number; rmse: number; r2: number | null };
  }>;
}

export interface ModelInfo {
  version: string;
  type: string;
  algorithm: string;
  target: string;
  resolution: string;
  forecastHorizon: number;
  trainingPeriod: { start: string | null; end: string | null };
  validationPeriod: { start: string | null; end: string | null };
  testPeriod: { start: string | null; end: string | null };
  metrics: ModelMetrics;
  trainedAt: string;
  active: boolean;
}

export interface ModelsResponse {
  models: ModelInfo[];
}

/** Fetch active model metadata + real metrics. */
export async function fetchModels(): Promise<ModelsResponse> {
  return getJson<ModelsResponse>('/v1/models');
}
