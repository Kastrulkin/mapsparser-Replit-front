import { newAuth } from '@/lib/auth_new';
import { readMobileJson } from '@/lib/mobileDataClient';

export class ContentAccessError extends Error {}

// The shared editor must use the current surface's session, never a leftover
// dashboard token when running inside either messenger.
export async function contentRequest<T>(path: string, init?: RequestInit, headers?: () => HeadersInit): Promise<T> {
  if (!headers) return newAuth.makeRequest(path, init);
  const requestHeaders = new Headers(headers());
  if (init?.body) requestHeaders.set('Content-Type', 'application/json');
  const response = await fetch('/api' + path, { ...init, headers: requestHeaders });
  try { return await readMobileJson<T>(response); }
  catch (reason) {
    if (response.status === 401 || response.status === 403) throw new ContentAccessError(reason instanceof Error ? reason.message : 'Нет доступа.');
    throw reason;
  }
}
