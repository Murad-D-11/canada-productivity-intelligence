import { Router } from 'express';
import { env } from '../config/env.js';

/**
 * Metadata about the API and its configured data sources. Useful for the
 * frontend Data Status page and for transparency about provenance.
 */
export const metaRouter = Router();

metaRouter.get('/meta', (_req, res) => {
  res.json({
    service: 'canada-productivity-intelligence-api',
    version: '0.1.0',
    environment: env.NODE_ENV,
    dataSources: [
      {
        id: 'STATCAN_WDS',
        name: 'Statistics Canada Web Data Service',
        baseUrl: env.STATCAN_WDS_BASE_URL,
        docs: 'https://www.statcan.gc.ca/en/developers/wds/user-guide',
      },
      {
        id: 'MSC_GEOMET',
        name: 'Environment and Climate Change Canada MSC GeoMet',
        baseUrl: env.MSC_GEOMET_OGC_API_BASE_URL,
        docs: 'https://eccc-msc.github.io/open-data/msc-geomet/ogc_api_en/',
      },
      {
        id: 'CANADIAN_SURVEY_BUSINESS_CONDITIONS',
        name: 'Canadian Survey on Business Conditions',
        baseUrl: env.STATCAN_WDS_BASE_URL,
        docs: 'https://www.statcan.gc.ca/en/survey/business/5426',
      },
    ],
  });
});
