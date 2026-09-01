import type { AddressInfo } from 'node:net';
import type { Server } from 'node:http';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { createApp } from '../app.js';

/**
 * Boots the app on an ephemeral port and exercises core routes over HTTP.
 * Uses the global fetch available in Node 20+.
 */
describe('API', () => {
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

  it('reports health at /healthz', async () => {
    const res = await fetch(`${baseUrl}/healthz`);
    expect(res.status).toBe(200);
    const body = (await res.json()) as { status: string };
    expect(body.status).toBe('ok');
  });

  it('exposes service metadata with configured data sources', async () => {
    const res = await fetch(`${baseUrl}/api/meta`);
    expect(res.status).toBe(200);
    const body = (await res.json()) as { dataSources: Array<{ id: string }> };
    const ids = body.dataSources.map((d) => d.id);
    expect(ids).toContain('STATCAN_WDS');
    expect(ids).toContain('MSC_GEOMET');
  });

  it('returns 501 Not Implemented for planned domain endpoints', async () => {
    const res = await fetch(`${baseUrl}/api/forecasts`);
    expect(res.status).toBe(501);
    const body = (await res.json()) as { error: string };
    expect(body.error).toBe('Not Implemented');
  });

  it('returns 404 for unknown routes', async () => {
    const res = await fetch(`${baseUrl}/api/does-not-exist`);
    expect(res.status).toBe(404);
  });
});
