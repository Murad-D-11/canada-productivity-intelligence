/**
 * Thin API client. Reads the base URL from Vite env so the same build points at
 * different backends per environment. Endpoints are added as pages are wired to
 * data in later milestones; nothing here fabricates responses.
 */
const baseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:4000/api';

/** Extract a server-provided error message when the response is JSON. */
async function errorMessage(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as { error?: string };
    if (body && typeof body.error === 'string' && body.error.length > 0) {
      return body.error;
    }
  } catch {
    // Non-JSON error body; fall through to the status text.
  }
  return `Request failed: ${res.status} ${res.statusText}`;
}

export async function getJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${baseUrl}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!res.ok) {
    throw new Error(await errorMessage(res));
  }
  return (await res.json()) as T;
}

/** POST a JSON body and parse a JSON response, surfacing backend error text. */
export async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${baseUrl}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(await errorMessage(res));
  }
  return (await res.json()) as T;
}

export const apiBaseUrl = baseUrl;
