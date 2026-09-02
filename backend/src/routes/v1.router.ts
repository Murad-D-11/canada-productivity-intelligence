import { Router, type Request, type Response } from 'express';
import { z } from 'zod';
import { prisma } from '../lib/prisma.js';
import { asyncHandler, HttpError } from '../middleware/errorHandler.js';

/**
 * Versioned StatCan data API (Master Prompt 2).
 *
 * Exposes ingested Statistics Canada productivity data through typed,
 * paginated, validated endpoints. Responses are shaped DTOs — raw database
 * tables are never exposed. All data is real (ingested from StatCan); nothing
 * is fabricated.
 */
export const v1Router = Router();

const DEFAULT_PAGE_SIZE = 50;
const MAX_PAGE_SIZE = 500;

/** Shared pagination query schema. */
const paginationSchema = z.object({
  page: z.coerce.number().int().min(1).default(1),
  pageSize: z.coerce.number().int().min(1).max(MAX_PAGE_SIZE).default(DEFAULT_PAGE_SIZE),
});

/** Parse+validate query params, throwing a 400 HttpError on failure. */
function parseQuery<T extends z.ZodTypeAny>(schema: T, req: Request): z.infer<T> {
  const result = schema.safeParse(req.query);
  if (!result.success) {
    throw new HttpError(400, `Invalid query parameters: ${result.error.issues.map((i) => i.message).join('; ')}`);
  }
  return result.data;
}

/** Resolve the primary ingested dataset (product 36100207 by default). */
async function resolveDatasetId(productId = 36100207): Promise<string> {
  const dataset = await prisma.statCanDataset.findUnique({
    where: { productId },
    select: { id: true },
  });
  if (!dataset) {
    throw new HttpError(404, `Dataset ${productId} has not been ingested yet.`);
  }
  return dataset.id;
}

// GET /api/v1/industries -----------------------------------------------------
v1Router.get('/industries', asyncHandler(async (req: Request, res: Response) => {
  const { page, pageSize } = parseQuery(paginationSchema, req);
  const datasetId = await resolveDatasetId();
  const [total, rows] = await Promise.all([
    prisma.statCanIndustry.count({ where: { datasetId } }),
    prisma.statCanIndustry.findMany({
      where: { datasetId },
      orderBy: { name: 'asc' },
      skip: (page - 1) * pageSize,
      take: pageSize,
      select: { memberId: true, name: true, classificationCode: true, parentMemberId: true },
    }),
  ]);
  res.json({
    data: rows.map((r) => ({
      memberId: r.memberId,
      name: r.name,
      classificationCode: r.classificationCode,
      parentMemberId: r.parentMemberId,
    })),
    pagination: { page, pageSize, total, totalPages: Math.ceil(total / pageSize) },
  });
}));

// GET /api/v1/measures -------------------------------------------------------
v1Router.get('/measures', asyncHandler(async (req: Request, res: Response) => {
  const { page, pageSize } = parseQuery(paginationSchema, req);
  const datasetId = await resolveDatasetId();
  const [total, rows] = await Promise.all([
    prisma.statCanMeasure.count({ where: { datasetId } }),
    prisma.statCanMeasure.findMany({
      where: { datasetId },
      orderBy: { name: 'asc' },
      skip: (page - 1) * pageSize,
      take: pageSize,
      select: { memberId: true, name: true, unitOfMeasure: true },
    }),
  ]);
  res.json({
    data: rows.map((r) => ({ memberId: r.memberId, name: r.name, unitOfMeasure: r.unitOfMeasure })),
    pagination: { page, pageSize, total, totalPages: Math.ceil(total / pageSize) },
  });
}));

// GET /api/v1/productivity/history ------------------------------------------
const historySchema = paginationSchema.extend({
  industry: z.coerce.number().int().optional(),
  measure: z.coerce.number().int().optional(),
  from: z.string().regex(/^\d{4}(-\d{2})?(-\d{2})?$/).optional(),
  to: z.string().regex(/^\d{4}(-\d{2})?(-\d{2})?$/).optional(),
});

v1Router.get('/productivity/history', asyncHandler(async (req: Request, res: Response) => {
  const q = parseQuery(historySchema, req);
  const datasetId = await resolveDatasetId();

  // Resolve optional industry/measure member ids to row ids.
  const where: Record<string, unknown> = { datasetId };
  if (q.industry !== undefined) {
    const ind = await prisma.statCanIndustry.findUnique({
      where: { datasetId_memberId: { datasetId, memberId: q.industry } },
      select: { id: true },
    });
    if (!ind) throw new HttpError(404, `Industry member ${q.industry} not found.`);
    where.industryId = ind.id;
  }
  if (q.measure !== undefined) {
    const meas = await prisma.statCanMeasure.findUnique({
      where: { datasetId_memberId: { datasetId, memberId: q.measure } },
      select: { id: true },
    });
    if (!meas) throw new HttpError(404, `Measure member ${q.measure} not found.`);
    where.measureId = meas.id;
  }
  if (q.from || q.to) {
    const periodStart: Record<string, Date> = {};
    if (q.from) periodStart.gte = toStartDate(q.from);
    if (q.to) periodStart.lte = toStartDate(q.to);
    where.periodStart = periodStart;
  }

  const [total, rows] = await Promise.all([
    prisma.statCanObservation.count({ where }),
    prisma.statCanObservation.findMany({
      where,
      orderBy: { periodStart: 'asc' },
      skip: (q.page - 1) * q.pageSize,
      take: q.pageSize,
      select: {
        periodStart: true,
        periodLabel: true,
        periodType: true,
        value: true,
        unit: true,
        coordinate: true,
        vectorId: true,
        statusCode: true,
        industry: { select: { memberId: true, name: true } },
        measure: { select: { memberId: true, name: true } },
        geography: { select: { memberId: true, name: true } },
      },
    }),
  ]);

  res.json({
    data: rows.map((r) => ({
      period: r.periodLabel,
      periodStart: r.periodStart.toISOString().slice(0, 10),
      periodType: r.periodType,
      value: r.value,
      unit: r.unit,
      industry: r.industry.name,
      industryId: r.industry.memberId,
      measure: r.measure.name,
      measureId: r.measure.memberId,
      geography: r.geography.name,
      // Original StatCan identifiers, surfaced for transparency.
      coordinate: r.coordinate,
      vectorId: r.vectorId,
      statusCode: r.statusCode,
    })),
    pagination: { page: q.page, pageSize: q.pageSize, total, totalPages: Math.ceil(total / q.pageSize) },
  });
}));

// GET /api/v1/data/status ----------------------------------------------------
v1Router.get('/data/status', asyncHandler(async (_req: Request, res: Response) => {
  const dataset = await prisma.statCanDataset.findUnique({
    where: { productId: 36100207 },
    select: {
      productId: true,
      tableRef: true,
      title: true,
      frequency: true,
      startDate: true,
      endDate: true,
      releaseTime: true,
    },
  });

  if (!dataset) {
    res.json({ ingested: false, message: 'No StatCan data ingested yet.' });
    return;
  }

  const datasetId = (await resolveDatasetId()) as string;
  const [industries, measures, observations, lastRun] = await Promise.all([
    prisma.statCanIndustry.count({ where: { datasetId } }),
    prisma.statCanMeasure.count({ where: { datasetId } }),
    prisma.statCanObservation.count({ where: { datasetId } }),
    prisma.ingestionRun.findFirst({
      where: { datasetId },
      orderBy: { startedAt: 'desc' },
      select: {
        status: true,
        mode: true,
        startedAt: true,
        finishedAt: true,
        observationsDownloaded: true,
        observationsInserted: true,
        observationsUpdated: true,
        duplicatesSkipped: true,
        rowsRejected: true,
        missingValues: true,
        earliestPeriod: true,
        latestPeriod: true,
        durationSeconds: true,
      },
    }),
  ]);

  res.json({
    ingested: observations > 0,
    dataset: {
      productId: dataset.productId,
      tableRef: dataset.tableRef,
      title: dataset.title,
      frequency: dataset.frequency,
      coverage: {
        start: dataset.startDate?.toISOString().slice(0, 10) ?? null,
        end: dataset.endDate?.toISOString().slice(0, 10) ?? null,
      },
      releaseTime: dataset.releaseTime?.toISOString() ?? null,
    },
    counts: { industries, measures, observations },
    lastIngestion: lastRun
      ? {
          status: lastRun.status,
          mode: lastRun.mode,
          startedAt: lastRun.startedAt.toISOString(),
          finishedAt: lastRun.finishedAt?.toISOString() ?? null,
          downloaded: lastRun.observationsDownloaded,
          inserted: lastRun.observationsInserted,
          updated: lastRun.observationsUpdated,
          duplicates: lastRun.duplicatesSkipped,
          rejected: lastRun.rowsRejected,
          missingValues: lastRun.missingValues,
          earliestPeriod: lastRun.earliestPeriod?.toISOString().slice(0, 10) ?? null,
          latestPeriod: lastRun.latestPeriod?.toISOString().slice(0, 10) ?? null,
          durationSeconds: lastRun.durationSeconds,
        }
      : null,
  });
}));

/** Convert a partial date string (YYYY, YYYY-MM, YYYY-MM-DD) to a Date. */
function toStartDate(s: string): Date {
  const parts = s.split('-');
  const year = Number(parts[0]);
  const month = parts[1] ? Number(parts[1]) : 1;
  const day = parts[2] ? Number(parts[2]) : 1;
  return new Date(Date.UTC(year, month - 1, day));
}
