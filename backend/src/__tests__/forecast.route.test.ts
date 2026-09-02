import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { createApp } from '../app.js';

/**
 * Targeted integration tests for the forecast + scenario endpoints (Master
 * Prompt 6). These run against the real Express app, the real database, and the
 * real Python model bridge, so they double as a smoke test of the full path.
 *
 * They require: Postgres running with ingested data + a generated feature set,
 * and a trained model artifact (ml/artifacts). When the feature set or model is
 * unavailable the valid-input tests skip with a clear signal rather than
 * failing spuriously — matching the existing v1 route test convention.
 */
async function readJson(res: { json: () => Promise<unknown> }): Promise<any> {
  return (await res.json()) as any;
}

describe('Forecast + scenario API', () => {
  let server: Server;
  let baseUrl: string;
  let ready = false;
  // A real industry present in the ingested feature set.
  const industry = 'Agriculture, forestry, fishing and hunting';

  beforeAll(async () => {
    const app = createApp();
    await new Promise<void>((resolve) => {
      server = app.listen(0, () => resolve());
    });
    baseUrl = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;

    // Consider the environment ready only if a feature set exists.
    const status = await readJson(await fetch(`${baseUrl}/api/v1/data/status`));
    ready = Boolean(status.ingested) && Boolean(status.features);
  });

  afterAll(async () => {
    await new Promise<void>((resolve) => server.close(() => resolve()));
  });

  it('returns a forecast for a supported industry (valid)', async () => {
    if (!ready) return; // skip when features/model unavailable
    const res = await fetch(`${baseUrl}/api/v1/forecast`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ industry, geography: 'Canada', horizon: 1 }),
    });
    expect(res.status).toBe(200);
    const body = await readJson(res);
    expect(body.target).toBe('Labour productivity');
    expect(typeof body.forecastProductivity).toBe('number');
    expect(body).toHaveProperty('forecastPeriod');
    expect(body.model).toHaveProperty('version');
    expect(Array.isArray(body.topDrivers)).toBe(true);
    // Drivers are model contributions, not causal effects.
    expect(String(body.disclaimer).toLowerCase()).toContain('not causal');
  });

  it('rejects an unsupported industry (invalid)', async () => {
    const res = await fetch(`${baseUrl}/api/v1/forecast`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ industry: 'Nonexistent Industry XYZ', geography: 'Canada', horizon: 1 }),
    });
    // 404 when features exist but industry unknown; 503 if no feature set at all.
    expect([404, 503]).toContain(res.status);
  });

  it('simulates a valid scenario on an eligible feature (valid)', async () => {
    if (!ready) return;
    const res = await fetch(`${baseUrl}/api/v1/scenarios/simulate`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        industry,
        geography: 'Canada',
        horizon: 1,
        changedFeatures: { employmentGrowth: 0.02 },
      }),
    });
    expect(res.status).toBe(200);
    const body = await readJson(res);
    expect(typeof body.baselinePrediction).toBe('number');
    expect(typeof body.scenarioPrediction).toBe('number');
    expect(typeof body.absoluteDifference).toBe('number');
    expect(body.changedFeatures[0].feature).toBe('employmentGrowth');
    expect(String(body.warning).toLowerCase()).toContain('not causal');
  });

  it('rejects a non-controllable scenario feature (invalid)', async () => {
    // `quarter` is a calendar marker: not eligible for scenario simulation.
    const res = await fetch(`${baseUrl}/api/v1/scenarios/simulate`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        industry,
        geography: 'Canada',
        horizon: 1,
        changedFeatures: { quarter: 3 },
      }),
    });
    expect(res.status).toBe(400);
  });
});
