/**
 * Typed client for the scenario simulation API (Master Prompt 6/8).
 *
 * Two calls, both backed by the real model and centralized feature metadata:
 *   - fetchScenarioFeatures: the eligible controllable features for a series,
 *     each with its real current value + metadata-defined unit/source/range.
 *   - simulateScenario: baseline vs scenario forecast under changed inputs.
 *
 * Nothing is computed or fabricated in React. Differences are model-based
 * scenario outputs, not causal estimates.
 */
import { getJson, postJson } from './apiClient';

export interface ScenarioFeature {
  feature: string;
  displayName: string;
  unit: string;
  description: string;
  source: string;
  sourceTable: string | null;
  min: number | null;
  max: number | null;
  currentValue: number | null;
}

export interface ScenarioFeaturesResponse {
  industry: string;
  geography: string;
  basePeriod: string;
  basePeriodStart: string;
  features: ScenarioFeature[];
}

export interface ScenarioChangedFeature {
  feature: string;
  baselineValue: number | null;
  scenarioValue: number;
}

export interface ScenarioResult {
  target: string;
  industry: string;
  geography: string;
  forecastPeriod: string;
  horizon: number;
  baselinePrediction: number;
  scenarioPrediction: number;
  absoluteDifference: number;
  relativeDifference: number | null;
  changedFeatures: ScenarioChangedFeature[];
  model: { version: string; type: string };
  warning: string;
}

/** List the scenario-eligible features (with baseline values) for a series. */
export async function fetchScenarioFeatures(params: {
  industry: string;
  geography?: string;
}): Promise<ScenarioFeaturesResponse> {
  const search = new URLSearchParams({
    industry: params.industry,
    geography: params.geography ?? 'Canada',
  });
  return getJson<ScenarioFeaturesResponse>(`/v1/scenarios/features?${search.toString()}`);
}

/** Run a what-if scenario against the real model. */
export async function simulateScenario(params: {
  industry: string;
  geography?: string;
  horizon?: number;
  changedFeatures: Record<string, number>;
}): Promise<ScenarioResult> {
  return postJson<ScenarioResult>('/v1/scenarios/simulate', {
    industry: params.industry,
    geography: params.geography ?? 'Canada',
    horizon: params.horizon ?? 1,
    changedFeatures: params.changedFeatures,
  });
}
