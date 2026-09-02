import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { createApp } from '../app.js';

/**
 * Contract tests for the weather + feature API (Master Prompt 3). These run
 * against the real Express app + database, so they double as schema regression
 * tests. Endpoints degrade gracefully when weather/features have not been
 * ingested yet (empty data / 404), so the tests assert shape + status codes
 * without requiring a specific dataset to be present.
 */
async function readJson(res: { json: () => Promise<unknown> }): Promise<any> {
  return (await res.json()) as any;
}

describe('Weather + Feature API', () => {
  let server: Server;
  let baseUrl: string;

  beforeAll(async () => {
    const app = createApp();
    await new Promise<void>((resolve) => {
      server = app.listen(0, () => resolve());
    });
    const { port } = server.address() as AddressInfo;
    baseUrl = `http://127.0.0.1:${port}`;
  });

  afterAll(async () => {
    await new Promise<void>((resolve) => server.close(() => resolve()));
  });

  it('returns a paginated weather history envelope', async () => {
    const res = await fetch(`${baseUrl}/api/weather/history?pageSize=5`);
    expect(res.status).toBe(200);
    const body = await readJson(res);
    expect(Array.isArray(body.data)).toBe(true);
    expect(body.pagination).toMatchObject({ page: 1 });
    // When rows exist, each preserves its province, variable, and station id.
    if (body.data.length > 0) {
      const point = body.data[0];
      expect(point).toHaveProperty('province');
      expect(point).toHaveProperty('variable');
      expect(point).toHaveProperty('stationId');
      expect(point).toHaveProperty('value'); // may be null (never fabricated)
    }
  });

  it('validates the province query param (400 on a non-two-letter code)', async () => {
    const res = await fetch(`${baseUrl}/api/weather/history?province=ONTARIO`);
    expect(res.status).toBe(400);
  });

  it('serves features when generated, or 404 before the first run', async () => {
    const res = await fetch(`${baseUrl}/api/features?pageSize=5`);
    expect([200, 404]).toContain(res.status);
    if (res.status === 200) {
      const body = await readJson(res);
      expect(body.featureSet).toHaveProperty('features');
      expect(Array.isArray(body.data)).toBe(true);
      if (body.data.length > 0) {
        expect(body.data[0]).toHaveProperty('targetValue');
        expect(body.data[0].features).toHaveProperty('prodLag1');
      }
    }
  });
});
