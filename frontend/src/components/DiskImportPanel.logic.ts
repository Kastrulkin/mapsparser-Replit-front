import { voiceHeaders } from '@/components/operator/OperatorVoice.logic';

export async function diskRequest(path: string, body?: unknown, signal?: AbortSignal) {
  const response = await fetch('/api/media-intelligence/disk-import' + path, { method: body === undefined ? 'GET' : 'POST',
    headers: { ...voiceHeaders(), ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
    body: body === undefined ? undefined : JSON.stringify(body), signal });
  const data = await response.json(); signal?.throwIfAborted();
  if (response.status === 404 && body === undefined) return { enabled: false, can_configure: false, sources: [] };
  if (!response.ok) throw new Error(response.status === 403 ? 'Нет доступа к импорту' : data.error || 'Не удалось выполнить действие');
  return data;
}
