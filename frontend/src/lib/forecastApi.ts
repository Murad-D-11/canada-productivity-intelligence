/**
 * Typed client for the forecasting API (Master Prompt 6).
 *
 * Wraps the generic JSON helpers with concrete types for POST /api/v1/forecast.
 * All forecast values come from the backend/model — nothing is computed in
 * React and nothing is fabricated.
 */
import { postJson } from './apiClient';

export interface ForecastDriver {
  feature: string;
  displayName: string;
  currentValue: number | null;
  contribution: number;
  direction: 'increases' | 'decreases' | 'neutral';
  unit: string;
  source: string;
  description: string;
}

export interface ForecastResult {
  target: string;
  industry: string;
  geography: string;
  basePeriod: string;
  forecastPeriod: string;
  horizon: number;
  resolution: string;
  currentObservedProductivity: number | null;
  forecastProductivity: number;
  absolutePredictedChange: number | null;
  percentagePredictedChange: number | null;
  model: { version: string; type: string };
  baseValue: number;
  topDrivers: ForecastDriver[];
  missingFeatures: string[];
  dataFreshness: {
    featureSet: string;
    basePeriod: string;
    basePeriodStart: string;
  };
  disclaimer: string;
  limitations: string[];
}

export interface ForecastRequest {
  industry: string;
  geography?: string;
  horizon?: number;
}

/** Request a one-step-ahead productivity forecast for an industry. */
export async function generateForecast(req: ForecastRequest): Promise<ForecastResult> {
  return postJson<ForecastResult>('/v1/forecast', {
    industry: req.industry,
    geography: req.geography ?? 'Canada',
    horizon: req.horizon ?? 1,
  });
}
