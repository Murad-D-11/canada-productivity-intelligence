import { execFile } from 'node:child_process';
import { existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { logger } from '../config/logger.js';
import { HttpError } from '../middleware/errorHandler.js';

/**
 * Thin bridge to the Python ML system (Prompts 4-5).
 *
 * The backend already retrieves feature data from the database itself; this
 * bridge only runs the trained model (predict / explain / model info / feature
 * metadata) by invoking `python -m cpi_ml.bridge` with a JSON request on stdin
 * and reading a JSON response from stdout. This is the simplest mechanism
 * compatible with the existing architecture — no queues, services, or extra
 * infrastructure. Python internals are never exposed to the frontend.
 */

const here = dirname(fileURLToPath(import.meta.url));
// backend/src/services -> repo root is three levels up.
const repoRoot = resolve(here, '../../..');
const mlDir = resolve(repoRoot, 'ml');

/** Resolve the ML virtualenv Python interpreter across OSes. */
function resolvePython(): string {
  const candidates = [
    resolve(mlDir, '.venv/Scripts/python.exe'), // Windows
    resolve(mlDir, '.venv/bin/python'), // POSIX
  ];
  for (const c of candidates) {
    if (existsSync(c)) return c;
  }
  // Fall back to PATH python; the bridge will still emit a structured error if
  // the package or model is unavailable.
  return process.platform === 'win32' ? 'python' : 'python3';
}

const PYTHON = resolvePython();
const BRIDGE_TIMEOUT_MS = 30_000;

export type BridgeAction = 'predict' | 'explain' | 'forecast' | 'model_info' | 'feature_metadata';

export interface BridgeRequest {
  action: BridgeAction;
  features?: Record<string, number | null>;
  model_version?: string;
  forecast_period?: string | null;
}

interface BridgeEnvelope<T> {
  ok: boolean;
  result?: T;
  error?: string;
  code?: string;
}

/** Map a bridge error `code` to an appropriate HTTP status. */
function statusForCode(code: string | undefined): number {
  switch (code) {
    case 'model_missing':
      return 503; // model artifact not trained yet
    case 'missing_features':
    case 'bad_request':
    case 'unknown_action':
      return 400;
    default:
      return 502; // upstream ML failure
  }
}

/**
 * Invoke the Python bridge with a JSON request and return the parsed result.
 * Throws an HttpError (never fabricates data) when the bridge reports failure.
 */
export async function callBridge<T = unknown>(request: BridgeRequest): Promise<T> {
  const payload = JSON.stringify(request);

  const stdout = await new Promise<string>((resolvePromise, reject) => {
    const child = execFile(
      PYTHON,
      ['-m', 'cpi_ml.bridge'],
      {
        cwd: mlDir,
        timeout: BRIDGE_TIMEOUT_MS,
        maxBuffer: 8 * 1024 * 1024,
        // Ensure the package is importable and DATABASE_URL is inherited.
        env: { ...process.env, PYTHONPATH: resolve(mlDir, 'src') },
      },
      (err, out, errOut) => {
        if (err) {
          logger.error({ err, errOut }, 'ML bridge process failed');
          reject(new HttpError(502, 'The forecasting model service is unavailable.'));
          return;
        }
        resolvePromise(out);
      },
    );
    child.stdin?.end(payload);
  });

  let envelope: BridgeEnvelope<T>;
  try {
    envelope = JSON.parse(stdout.trim()) as BridgeEnvelope<T>;
  } catch {
    logger.error({ stdout }, 'ML bridge returned non-JSON output');
    throw new HttpError(502, 'The forecasting model returned an unreadable response.');
  }

  if (!envelope.ok) {
    throw new HttpError(statusForCode(envelope.code), envelope.error ?? 'Model error.');
  }
  return envelope.result as T;
}
