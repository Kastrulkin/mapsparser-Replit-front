import { useOutletContext } from "react-router-dom";
import type { DashboardOutletContext } from "@/types/business";
import MaxChannelConnection from "@/components/MaxChannelConnection";
import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { newAuth } from '@/lib/auth_new';

export default function MaxConnectionPage() {
  const { currentBusinessId, controlScope } = useOutletContext<DashboardOutletContext>();
  const [code, setCode] = useState('');
  const [connected, setConnected] = useState(false);
  const [notifications, setNotifications] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [expiresAt, setExpiresAt] = useState(0);
  const [expired, setExpired] = useState(false);
  useEffect(() => {
    let active = true;
    void newAuth.makeRequest('/max/connection').then((result) => { if (active) { setConnected(Boolean(result.connection)); setNotifications(Boolean(result.connection?.notifications_enabled)); } }).catch((reason) => { if (active) setError(reason.message); });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    if (!expiresAt) return;
    const timeout = window.setTimeout(() => { setExpired(true); setCode(''); }, Math.max(0, expiresAt - Date.now()));
    return () => window.clearTimeout(timeout);
  }, [expiresAt]);
  const act = async (action: () => Promise<void>) => {
    if (busy) return; setBusy(true); setError('');
    try { await action(); } catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось выполнить действие'); }
    finally { setBusy(false); }
  };
  return <section className="mx-auto max-w-xl space-y-5 p-6">
    <h1 className="text-2xl font-semibold">LocalOS в MAX</h1>
    <p className="text-muted-foreground">Подключите MAX, чтобы управлять своими бизнесами, давать поручения и проверять результаты.</p>
    <p role="status">{connected ? 'Аккаунт подключён' : 'Аккаунт не подключён'}</p>
    <Button disabled={busy} onClick={() => void act(async () => {
      const result = await newAuth.makeRequest('/max/link-code', { method: 'POST' });
      setCode(result.code); setExpired(false); setExpiresAt(Date.now() + result.expires_in * 1000);
    })}>{code ? 'Получить новый код' : 'Получить код подключения'}</Button>
    {code ? <div className="space-y-2"><Input aria-label="Одноразовый код MAX" readOnly value={code} /><p className="text-sm text-muted-foreground">Скопируйте код в мини-приложение LocalOS в MAX. Код действует 10 минут. Новый код отменяет предыдущий.</p></div> : null}
    {expired ? <p role="status">Код истёк. Получите новый код.</p> : null}
    {connected ? <div className="space-y-4"><label className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={notifications} disabled={busy} onChange={(event) => { const enabled = event.target.checked; void act(async () => { await newAuth.makeRequest('/max/connection', { method: 'PATCH', body: JSON.stringify({ notifications_enabled: enabled }) }); setNotifications(enabled); }); }} />Получать уведомления в MAX</label>
      <Button variant="outline" disabled={busy} onClick={() => void act(async () => { await newAuth.makeRequest('/max/connection', { method: 'DELETE' }); setConnected(false); setNotifications(false); setCode(''); })}>Отключить аккаунт MAX</Button></div> : null}
    {currentBusinessId && (!controlScope || controlScope.kind === "business") ? <MaxChannelConnection key={currentBusinessId} businessId={currentBusinessId} /> : <p className="text-sm text-muted-foreground">Выберите конкретный бизнес для подключения канала публикаций.</p>}
    {error ? <p role="alert" className="text-destructive">{error}</p> : null}
  </section>;
}
