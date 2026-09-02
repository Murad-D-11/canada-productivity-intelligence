/**
 * Typed client for the weather + feature API (Master Prompt 3).
 *
 * Wraps the generic getJson helper with concrete request/response types for the
 * ingested MSC GeoMet weather endpoints. The base URL points at `/api`.
 */
import { getJson } from './apiClient';
import type { Paginated } from './statcanApi';

export type WeatherVariable = 'TEMPERATURE' | 'PRECIPITATION' | 'SNOWFALL' | 'WIND_SPEED';

/** Human-friendly labels + units for each weather variable. */
export const WEATHER_VARIABLE_META: Record<WeatherVariable, { label: string; unit: string }> = {
  TEMPERATURE: { label: 'Temperature', unit: 'degC' },
  PRECIPITATION: { label: 'Precipitation', unit: 'mm' },
  SNOWFALL: { label: 'Snowfall', unit: 'cm' },
  WIND_SPEED: { label: 'Wind speed', unit: 'km/h' },
};

/** Canadian province/territory codes (matches the ingestion scope). */
export const PROVINCES: { code: string; name: string }[] = [
  { code: 'AB', name: 'Alberta' },
  { code: 'BC', name: 'British Columbia' },
  { code: 'MB', name: 'Manitoba' },
  { code: 'NB', name: 'New Brunswick' },
  { code: 'NL', name: 'Newfoundland and Labrador' },
  { code: 'NS', name: 'Nova Scotia' },
  { code: 'NT', name: 'Northwest Territories' },
  { code: 'NU', name: 'Nunavut' },
  { code: 'ON', name: 'Ontario' },
  { code: 'PE', name: 'Prince Edward Island' },
  { code: 'QC', name: 'Quebec' },
  { code: 'SK', name: 'Saskatchewan' },
  { code: 'YT', name: 'Yukon' },
];

export interface WeatherPoint {
  period: string;
  periodStart: string;
  periodType: string;
  province: string;
  variable: WeatherVariable;
  value: number | null;
  unit: string;
  aggregation: string;
  sampleCount: number;
  stationId: string;
  station: string;
}

/** Fetch a weather history series for a province + variable. */
export async function fetchWeatherHistory(params: {
  province?: string;
  variable?: WeatherVariable;
  from?: string;
  to?: string;
  pageSize?: number;
}): Promise<Paginated<WeatherPoint>> {
  const search = new URLSearchParams();
  if (params.province) search.set('province', params.province);
  if (params.variable) search.set('variable', params.variable);
  if (params.from) search.set('from', params.from);
  if (params.to) search.set('to', params.to);
  search.set('pageSize', String(params.pageSize ?? 2000));
  return getJson<Paginated<WeatherPoint>>(`/weather/history?${search.toString()}`);
}
