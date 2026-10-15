import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { browserBearerToken } from '@/lib/browserSessionFetch';
import { readMobileJson } from '@/lib/mobileDataClient';

const webHeaders = (): Record<string, string> => {
  const token = browserBearerToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
};
type Connection = { external_id: string; display_name: string };

export default function MaxChannelConnection({ businessId, headers = webHeaders }: { businessId: string; headers?: () => Record<string, string> }) {
  const [connection, setConnection] = useState<Connection | null>(null);
  const [chat, setChat] = useState('');
  const [token, setToken] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const url = `/api/max/channels/${encodeURIComponent(businessId)}`;
  useEffect(() => {
    const controller = new AbortController();
    setConnection(null); setChat(''); setToken(''); setError(''); setLoading(true);
    void fetch(url, { headers: headers(), signal: controller.signal }).then(readMobileJson<{ connection?: Connection }>).then((result) => {
      if (!controller.signal.aborted) setConnection(result.connection || null);
    }).catch((reason) => { if (!controller.signal.aborted) setError(reason.message); }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [url, headers]);
  const save = async (method: 'POST' | 'DELETE') => {
    if (busy) return; setBusy(true); setError('');
    try {
      const result = await fetch(url, { method, headers: { ...headers(), 'Content-Type': 'application/json' },
        body: method === 'POST' ? JSON.stringify({ chat_id: chat, ...(token.trim() ? { bot_token: token.trim() } : {}) }) : undefined,
      }).then(readMobileJson<{ connection?: Connection }>);
      setConnection(result.connection || null); setToken('');
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось проверить канал'); }
    finally { setBusy(false); }
  };
  return <section className="space-y-4 rounded-xl border border-border p-4">
    <h2 className="text-lg font-semibold">Публикации в канал MAX</h2>
    <p className="text-sm text-muted-foreground">Добавьте бота в свой канал и выдайте право публикации. Здесь проверяется подключение; каждый пост публикуется после отдельного подтверждения в «Контенте».</p>
    {loading ? <p role="status">Проверяем подключение…</p> : connection ? <p role="status">Подключён канал: {connection.display_name} · {connection.external_id}</p> : <p>Канал не подключён</p>}
    <form className="space-y-3" onSubmit={(event) => { event.preventDefault(); void save('POST'); }}>
      <Label htmlFor="max-channel-id">ID канала MAX</Label>
      <Input id="max-channel-id" value={chat} onChange={(event) => setChat(event.target.value)} placeholder="Числовой ID канала" disabled={busy || loading} />
      <details><summary className="min-h-11 cursor-pointer text-sm">Использовать отдельного бота бизнеса</summary>
        <Label htmlFor="max-channel-token">Токен бота</Label><Input id="max-channel-token" type="password" autoComplete="new-password" value={token} onChange={(event) => setToken(event.target.value)} disabled={busy} />
        <p className="mt-2 text-xs text-muted-foreground">Если поле пустое, используется настроенный бот LocalOS.</p>
      </details>
      <Button disabled={busy || loading || !chat.trim()}>{busy ? 'Проверяем…' : 'Проверить и подключить канал'}</Button>
    </form>
    {connection ? <Button variant="outline" disabled={busy} onClick={() => void save('DELETE')}>Отключить канал</Button> : null}
    {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
  </section>;
}
