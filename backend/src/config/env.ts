import { existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { config as loadDotenv } from 'dotenv';
import { z } from 'zod';

// Load .env. Prefer the repo-root .env (one level above backend) so the same
// file configures every service; fall back to the current working directory.
const here = dirname(fileURLToPath(import.meta.url));
const rootEnv = resolve(here, '../../../.env');
loadDotenv(existsSync(rootEnv) ? { path: rootEnv } : undefined);

/**
 * Environment schema. Values are validated at startup so the service fails
 * fast on misconfiguration rather than at first request.
 */
const envSchema = z.object({
  NODE_ENV: z.enum(['development', 'test', 'production']).default('development'),
  BACKEND_PORT: z.coerce.number().int().positive().default(4000),
  CORS_ORIGIN: z.string().default('http://localhost:5173'),
  LOG_LEVEL: z.enum(['fatal', 'error', 'warn', 'info', 'debug', 'trace']).default('info'),
  DATABASE_URL: z.string().optional(),
  STATCAN_WDS_BASE_URL: z.string().url().default('https://www150.statcan.gc.ca/t1/wds/rest'),
  MSC_GEOMET_OGC_API_BASE_URL: z.string().url().default('https://api.weather.gc.ca'),
});

export type AppEnv = z.infer<typeof envSchema>;

const parsed = envSchema.safeParse(process.env);

if (!parsed.success) {
  // Surface configuration errors clearly and stop the process.
  console.error('Invalid environment configuration:', parsed.error.flatten().fieldErrors);
  throw new Error('Environment validation failed');
}

export const env: AppEnv = parsed.data;

/** Parsed list of allowed CORS origins. */
export const corsOrigins: string[] = env.CORS_ORIGIN.split(',').map((o) => o.trim());
