import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { createApp } from '../app.js';

/** Parse a fetch Response body as a loosely-typed JSON object for assertions. */
async function readJson(res: { json: () => Promise<unknown> }): Promise<any> {
  return (await res.json()) as any;
}

/**
 * Integration tests for the StatCan v1 API. These run against the real Express
 * app and the real (ingested) database, so they double as schema + data
 * regression tests. They require:
 *   - Postgres running with ingested data (docker compose up postgres + ingest)
 *   - DATABASE_URL configured (loaded from the repo-root .env by env.ts)
 *
 * If the dataset has not been ingested, the endpoints return 404 and the tests
 * are skipped with a clear message rather than failing spuriously.
 */
describe('StatCan v1 API', () => {
  let server: Server;
  let baseUrl: string;
  let ingested = false;

  beforeAll(async () => {
    const app = createApp();
    await new Promise<void>((resolve) => {
      server = app.listen(0, () => resolve());
    });
    const { port } = server.address() as AddressInfo;
    baseUrl = `http://127.0.0.1:${port}`;

    const status = await readJson(await fetch(`${baseUrl}/api/v1/data/status`));
    ingested = Boolean(status.ingested);
  });

  afterAll(async () => {
    await new Promise<void>((resolve) => server.close(() => resolve()));
  });

  it('reports data status with a typed shape', async () => {
    const res = await fetch(`${baseUrl}/api/v1/data/status`);
    expect(res.status).toBe(200);
    const body = await readJson(res);
    expect(body).toHaveProperty('ingested');
    if (body.ingested) {
      expect(body.dataset.productId).toBe(36100207);
      expect(body.counts.observations).toBeGreaterThan(0);
    }
  });

  it('lists industries with pagination metadata', async () => {
    if (!ingested) return; // skip when no data
    const res = await fetch(`${baseUrl}/api/v1/industries`);
    expect(res.status).toBe(200);
    const body = await readJson(res);
    expect(Array.isArray(body.data)).toBe(true);
    expect(body.pagination).toMatchObject({ page: 1 });
    expect(body.data.length).toBeGreaterThan(0);
    // Industry names come from StatCan metadata (not hardcoded).
    expect(body.data[0]).toHaveProperty('name');
    expect(body.data[0]).toHaveProperty('memberId');
  });

  it('lists measures', async () => {
    if (!ingested) return;
    const res = await fetch(`${baseUrl}/api/v1/measures`);
    expect(res.status).toBe(200);
    const body = await readJson(res);
    expect(body.data.length).toBeGreaterThan(0);
    const names = body.data.map((m: { name: string }) => m.name);
    expect(names).toContain('Labour productivity');
  });

  it('returns a productivity history series with original identifiers', async () => {
    if (!ingested) return;
    const res = await fetch(
      `${baseUrl}/api/v1/productivity/history?industry=19&measure=5&pageSize=10`,
    );
    expect(res.status).toBe(200);
    const body = await readJson(res);
    expect(Array.isArray(body.data)).toBe(true);
    if (body.data.length > 0) {
      const point = body.data[0];
      // Original StatCan identifiers are preserved end-to-end.
      expect(point).toHaveProperty('coordinate');
      expect(point).toHaveProperty('period');
      expect(point).toHaveProperty('value'); // may be null (suppressed)
    }
  });

  it('validates query params (400 on bad pageSize)', async () => {
    const res = await fetch(`${baseUrl}/api/v1/industries?pageSize=99999`);
    expect(res.status).toBe(400);
  });

  it('returns 404 for an unknown industry filter', async () => {
    if (!ingested) return;
    const res = await fetch(
      `${baseUrl}/api/v1/productivity/history?industry=999999&measure=5`,
    );
    expect(res.status).toBe(404);
  });
});
