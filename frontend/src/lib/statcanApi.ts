/**
 * Typed client for the StatCan v1 data API.
 *
 * Wraps the generic getJson helper with concrete request/response types for the
 * ingested Statistics Canada endpoints. The base URL points at `/api/v1`.
 */
import { getJson } from './apiClient';

export interface Pagination {
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
}

export interface Industry {
  memberId: number;
  name: string;
  classificationCode: string | null;
  parentMemberId: number | null;
}

export interface Measure {
  memberId: number;
  name: string;
  unitOfMeasure: string | null;
}

export interface ObservationPoint {
  period: string;
  periodStart: string;
  periodType: string;
  value: number | null;
  unit: string;
  industry: string;
  industryId: number;
  measure: string;
  measureId: number;
  geography: string;
  coordinate: string;
  vectorId: number | null;
  statusCode: string | null;
}

export interface Paginated<T> {
  data: T[];
  pagination: Pagination;
}

export interface DataStatus {
  ingested: boolean;
  message?: string;
  dataset?: {
    productId: number;
    tableRef: string | null;
    title: string;
    frequency: string | null;
    coverage: { start: string | null; end: string | null };
    releaseTime: string | null;
  };
  counts?: { industries: number; measures: number; observations: number };
  supported?: { industries: number; geographies: string[] };
  productivity?: { latestObservationPeriod: string | null; latestObservationDate: string | null };
  weather?: {
    observations: number;
    latestObservationPeriod: string | null;
    latestObservationDate: string | null;
  };
  features?: {
    id: string;
    name: string;
    periodCutoff: string;
    rowCount: number;
    generatedAt: string;
  } | null;
  lastIngestion?: Record<string, unknown> | null;
}

/** Fetch all industries (follows pagination to build the full selector list). */
export async function fetchIndustries(): Promise<Industry[]> {
  const first = await getJson<Paginated<Industry>>('/v1/industries?pageSize=500');
  return first.data;
}

/** Fetch all measures. */
export async function fetchMeasures(): Promise<Measure[]> {
  const first = await getJson<Paginated<Measure>>('/v1/measures?pageSize=500');
  return first.data;
}

/** Fetch a productivity history series for an industry + measure. */
export async function fetchHistory(params: {
  industry: number;
  measure: number;
  pageSize?: number;
}): Promise<Paginated<ObservationPoint>> {
  const search = new URLSearchParams({
    industry: String(params.industry),
    measure: String(params.measure),
    pageSize: String(params.pageSize ?? 500),
  });
  return getJson<Paginated<ObservationPoint>>(`/v1/productivity/history?${search.toString()}`);
}

/** Fetch ingestion/data status. */
export async function fetchDataStatus(): Promise<DataStatus> {
  return getJson<DataStatus>('/v1/data/status');
}
