/**
 * Thin API client. Reads the base URL from Vite env so the same build points at
 * different backends per environment. Endpoints are added as pages are wired to
 * data in later milestones; nothing here fabricates responses.
 */
const baseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:4000/api';

export async function getJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${baseUrl}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!res.ok) {
    throw new Error(`Request failed: ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

export const apiBaseUrl = baseUrl;
