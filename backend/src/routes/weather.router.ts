import { Router, type Request, type Response } from 'express';
import { z } from 'zod';
import { prisma } from '../lib/prisma.js';
import { asyncHandler, HttpError } from '../middleware/errorHandler.js';

/**
 * Weather + feature API (Master Prompt 3).
 *
 * Exposes ingested MSC GeoMet weather observations and the ML-ready feature
 * matrix through typed, paginated, validated endpoints. Responses are shaped
 * DTOs — raw database tables are never exposed. All data is real (ingested /
 * derived); nothing is fabricated. Missing values surface as null.
 *
 * Mounted at `/api`, providing:
 *   GET /api/weather/history
 *   GET /api/features
 */
export const weatherRouter = Router();

const DEFAULT_PAGE_SIZE = 200;
const MAX_PAGE_SIZE = 2000;

const paginationSchema = z.object({
  page: z.coerce.number().int().min(1).default(1),
  pageSize: z.coerce.number().int().min(1).max(MAX_PAGE_SIZE).default(DEFAULT_PAGE_SIZE),
});

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

/** Convert a partial date string (YYYY, YYYY-MM, YYYY-MM-DD) to a Date. */
function toStartDate(s: string): Date {
  const parts = s.split('-');
  const year = Number(parts[0]);
  const month = parts[1] ? Number(parts[1]) : 1;
  const day = parts[2] ? Number(parts[2]) : 1;
  return new Date(Date.UTC(year, month - 1, day));
}

const WEATHER_VARIABLES = ['TEMPERATURE', 'PRECIPITATION', 'SNOWFALL', 'WIND_SPEED'] as const;

// GET /api/weather/history ---------------------------------------------------
const weatherHistorySchema = paginationSchema.extend({
  province: z
    .string()
    .regex(/^[A-Za-z]{2}$/, 'province must be a two-letter code')
    .transform((s) => s.toUpperCase())
    .optional(),
  variable: z.enum(WEATHER_VARIABLES).optional(),
  from: z.string().regex(/^\d{4}(-\d{2})?(-\d{2})?$/).optional(),
  to: z.string().regex(/^\d{4}(-\d{2})?(-\d{2})?$/).optional(),
});

weatherRouter.get(
  '/weather/history',
  asyncHandler(async (req: Request, res: Response) => {
    const q = parseQuery(weatherHistorySchema, req);

    const where: Record<string, unknown> = {};
    if (q.province) where.province = q.province;
    if (q.variable) where.variable = q.variable;
    if (q.from || q.to) {
      const periodStart: Record<string, Date> = {};
      if (q.from) periodStart.gte = toStartDate(q.from);
      if (q.to) periodStart.lte = toStartDate(q.to);
      where.periodStart = periodStart;
    }

    const [total, rows] = await Promise.all([
      prisma.weatherObservation.count({ where }),
      prisma.weatherObservation.findMany({
        where,
        orderBy: [{ periodStart: 'asc' }, { province: 'asc' }, { variable: 'asc' }],
        skip: (q.page - 1) * q.pageSize,
        take: q.pageSize,
        select: {
          periodStart: true,
          periodLabel: true,
          periodType: true,
          province: true,
          variable: true,
          value: true,
          unit: true,
          aggregation: true,
          sampleCount: true,
          station: { select: { stationId: true, name: true } },
        },
      }),
    ]);

    res.json({
      data: rows.map((r) => ({
        period: r.periodLabel,
        periodStart: r.periodStart.toISOString().slice(0, 10),
        periodType: r.periodType,
        province: r.province,
        variable: r.variable,
        value: r.value, // may be null (source-missing; never fabricated)
        unit: r.unit,
        aggregation: r.aggregation,
        sampleCount: r.sampleCount,
        stationId: r.station.stationId,
        station: r.station.name,
      })),
      pagination: { page: q.page, pageSize: q.pageSize, total, totalPages: Math.ceil(total / q.pageSize) },
    });
  }),
);

// GET /api/features ----------------------------------------------------------
const featuresSchema = paginationSchema.extend({
  industry: z.string().optional(),
  measure: z.string().optional(),
  geography: z.string().optional(),
  featureSetId: z.string().optional(),
});

weatherRouter.get(
  '/features',
  asyncHandler(async (req: Request, res: Response) => {
    const q = parseQuery(featuresSchema, req);

    // Resolve the target feature set: an explicit id, or the most recent run.
    let featureSetId = q.featureSetId;
    if (!featureSetId) {
      const latest = await prisma.featureSet.findFirst({
        orderBy: { createdAt: 'desc' },
        select: { id: true },
      });
      if (!latest) {
        throw new HttpError(404, 'No feature set has been generated yet. Run generate-features.');
      }
      featureSetId = latest.id;
    }

    const where: Record<string, unknown> = { featureSetId };
    if (q.industry) where.industry = q.industry;
    if (q.measure) where.measure = q.measure;
    if (q.geography) where.geography = q.geography;

    const [featureSet, total, rows] = await Promise.all([
      prisma.featureSet.findUnique({
        where: { id: featureSetId },
        select: {
          id: true,
          name: true,
          periodCutoff: true,
          periodType: true,
          featureListJson: true,
          rowCount: true,
          createdAt: true,
        },
      }),
      prisma.featureRow.count({ where }),
      prisma.featureRow.findMany({
        where,
        orderBy: [{ industry: 'asc' }, { periodStart: 'asc' }],
        skip: (q.page - 1) * q.pageSize,
        take: q.pageSize,
        select: {
          industry: true,
          geography: true,
          measure: true,
          periodStart: true,
          periodLabel: true,
          periodType: true,
          targetValue: true,
          prodLag1: true,
          prodLag4: true,
          prodRollMean4: true,
          employmentGrowth: true,
          labourCostGrowth: true,
          quarter: true,
          month: true,
          weatherTempMean: true,
          weatherPrecipSum: true,
          weatherSnowfallSum: true,
          weatherWindMean: true,
        },
      }),
    ]);

    if (!featureSet) {
      throw new HttpError(404, `Feature set ${featureSetId} not found.`);
    }

    res.json({
      featureSet: {
        id: featureSet.id,
        name: featureSet.name,
        periodCutoff: featureSet.periodCutoff.toISOString().slice(0, 10),
        periodType: featureSet.periodType,
        features: featureSet.featureListJson,
        rowCount: featureSet.rowCount,
        createdAt: featureSet.createdAt.toISOString(),
      },
      data: rows.map((r) => ({
        industry: r.industry,
        geography: r.geography,
        measure: r.measure,
        period: r.periodLabel,
        periodStart: r.periodStart.toISOString().slice(0, 10),
        periodType: r.periodType,
        targetValue: r.targetValue,
        features: {
          prodLag1: r.prodLag1,
          prodLag4: r.prodLag4,
          prodRollMean4: r.prodRollMean4,
          employmentGrowth: r.employmentGrowth,
          labourCostGrowth: r.labourCostGrowth,
          quarter: r.quarter,
          month: r.month,
          weatherTempMean: r.weatherTempMean,
          weatherPrecipSum: r.weatherPrecipSum,
          weatherSnowfallSum: r.weatherSnowfallSum,
          weatherWindMean: r.weatherWindMean,
        },
      })),
      pagination: { page: q.page, pageSize: q.pageSize, total, totalPages: Math.ceil(total / q.pageSize) },
    });
  }),
);
