import { Button } from '@/components/ui/button';
import { useLatestCallback } from '@/hooks/useLatestCallback';
import { Paperclip } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { voiceHeaders } from './OperatorVoice.logic';

type Config = { enabled: boolean; can_configure: boolean; recipient_user_id?: string; version: number; recipients: { id: string; name: string }[] };
type Disk = { configured: boolean; connection: { status: string }; photos: { status: string; count: number }[] };

export function OperatorWorkdayInput({ businessId, channel, conversationId, disabled, headers = voiceHeaders, onConversation }: {
  businessId: string; channel: string; conversationId?: string | null; disabled?: boolean;
  headers?: () => Record<string, string>; onConversation: (id: string) => void;
}) {
  const [config, setConfig] = useState<Config | null>(null);
  const [googleDrive, setGoogleDrive] = useState<Disk | null>(null);
  const [disk, setDisk] = useState<Disk | null>(null);
  const [recipient, setRecipient] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const input = useRef<HTMLInputElement>(null);
  const lifetime = useRef(new AbortController());
  async function request(path: string, body?: unknown) {
    const signal = lifetime.current.signal;
    const response = await fetch(`/api/operator/${path}`, { method: body === undefined ? 'GET' : 'POST',
      headers: body === undefined ? headers() : { ...headers(), 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body), signal });
    const data = await response.json();
    signal.throwIfAborted();
    if (!response.ok) throw new Error(data.error || 'Не удалось выполнить действие');
    return data;
  }
  async function refresh() {
    const signal = lifetime.current.signal;
    const current = await request(`workday/config?business_id=${encodeURIComponent(businessId)}`);
    setConfig(current); setRecipient(current.recipient_user_id || '');
    try { setGoogleDrive(await request(`google-drive/status?business_id=${encodeURIComponent(businessId)}`)); }
    catch { signal.throwIfAborted(); setGoogleDrive(null); }
    setDisk(await request(`disk/status?business_id=${encodeURIComponent(businessId)}`));
  }
  // Refresh on scope/channel changes; form edits must not reload and replace the draft.
  const refreshScope = useLatestCallback(() => {
    const controller = new AbortController(); lifetime.current = controller;
    setConfig(null); setDisk(null); setGoogleDrive(null); setError(''); setNotice(''); setBusy(false);
    void refresh().catch(() => { if (!controller.signal.aborted) setConfig(null); });
    return () => controller.abort();
  });
  useEffect(refreshScope, [businessId, channel, refreshScope]);
  async function perform(action: () => Promise<void>) {
    const signal = lifetime.current.signal;
    setBusy(true); setError('');
    try { await action(); } catch (caught) {
      if (!signal.aborted) setError(caught instanceof Error ? caught.message : 'Не удалось выполнить действие');
    } finally { if (!signal.aborted) setBusy(false); }
  }
  async function upload(files: FileList | null) {
    if (!files?.length) return;
    await perform(async () => {
      const signal = lifetime.current.signal;
      if (files.length > 10) throw new Error('Выберите не более 10 файлов.');
      let currentConversation = conversationId;
      for (const file of Array.from(files)) {
        if (file.size > 10 * 1024 * 1024) throw new Error('Максимальный размер файла — 10 МБ.');
        const form = new FormData(); form.append('business_id', businessId); form.append('channel', channel);
        form.append('file', file); form.append('request_id', crypto.randomUUID());
        if (currentConversation) form.append('conversation_id', currentConversation);
        const response = await fetch('/api/operator/attachments', { method: 'POST', headers: headers(), body: form, signal });
        const body = await response.json(); signal.throwIfAborted(); if (!response.ok) throw new Error(body.error || 'Не удалось загрузить файл.');
        currentConversation = body.conversation_id; onConversation(body.conversation_id);
      }
      setNotice('Файлы сохранены. Напишите или наговорите, что сделать: пост, расписание или финансовые итоги.');
    });
    if (input.current) input.current.value = '';
  }
  if (!config?.enabled) return null;
  return <div className="space-y-2 py-2">
    <div className="flex flex-wrap gap-2">
      <Button type="button" variant="outline" disabled={disabled || busy} onClick={() => input.current?.click()}><Paperclip className="mr-2 h-4 w-4" />Фото или файл</Button>
      <Button type="button" variant="ghost" disabled={disabled || busy || !conversationId} onClick={() => void perform(async () => {
        await request('workday/clear-input', { business_id: businessId, conversation_id: conversationId }); setNotice('Текущий материал завершён. Можно начать новую задачу.');
      })}>Завершить текущий материал</Button>
      <input ref={input} className="hidden" type="file" multiple accept="image/jpeg,image/png,image/webp,.pdf,.xlsx,.csv" aria-label="Фото или файл для Оператора" onChange={event => void upload(event.target.files)} />
    </div>
    {notice && <p role="status" className="text-sm text-muted-foreground">{notice}</p>}
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    {config.can_configure && <details className="text-sm"><summary className="cursor-pointer py-2">Настройки рабочего пилота</summary>
      <div className="space-y-3 py-2">
        <label className="block space-y-1"><span>Получатель тестовых сообщений</span><select className="min-h-11 w-full rounded-md border bg-background px-3" value={recipient} onChange={event => setRecipient(event.target.value)}>
          <option value="">Отправка выключена</option>{config.recipients.map(person => <option key={person.id} value={person.id}>{person.name}</option>)}
        </select></label>
        <Button type="button" variant="outline" disabled={busy} onClick={() => void perform(async () => {
          await request('workday/recipient', { business_id: businessId, version: config.version, recipient_user_id: recipient || null });
          await refresh(); setNotice('Получатель сохранён. Каждое сообщение требует проверки и подтверждения.');
        })}>Сохранить получателя</Button>
        <p>Яндекс Диск: {disk?.connection.status === 'connected' ? 'подключён' : 'не подключён'}. Фото сначала сохраняются в LocalOS.</p>
        {disk?.photos.some(row => row.status === 'needs_retry') && <p>Некоторые фотографии ждут повторной синхронизации.</p>}
        <div className="flex flex-wrap gap-2">
          {disk?.connection.status !== 'connected' ? <Button type="button" variant="outline" disabled={busy || !disk?.configured} onClick={() => void perform(async () => {
            const body = await request('disk/connect', { business_id: businessId }); window.location.assign(body.url);
          })}>Подключить Яндекс Диск</Button> : <>
            <Button type="button" variant="outline" disabled={busy} onClick={() => void perform(async () => { await request('disk/retry', { business_id: businessId }); await refresh(); setNotice('Синхронизация поставлена в очередь.'); })}>Синхронизировать фото</Button>
            <Button type="button" variant="ghost" disabled={busy} onClick={() => void perform(async () => { await request('disk/disconnect', { business_id: businessId }); await refresh(); })}>Отключить Диск</Button>
          </>}
        </div>
        {!disk?.configured && <p className="text-muted-foreground">Подключение Диска ещё не настроено в LocalOS. Работа с фото доступна.</p>}
        <p>Google Диск: {googleDrive?.connection.status === 'connected' ? 'подключён' : googleDrive?.connection.status === 'needs_reconnect' ? 'доступ отозван — подключите заново' : 'не подключён'}. Фото сначала сохраняются в LocalOS.</p>
        {googleDrive?.photos.some(row => row.status === 'needs_retry') && <p>Некоторые фотографии ждут повторной синхронизации.</p>}
        <div className="flex flex-wrap gap-2">
          {googleDrive?.connection.status !== 'connected' ? <Button type="button" variant="outline" disabled={busy || !googleDrive?.configured} onClick={() => void perform(async () => {
            const body = await request('google-drive/connect', { business_id: businessId }); window.location.assign(body.url);
          })}>Подключить Google Диск</Button> : <>
            <Button type="button" variant="outline" disabled={busy} onClick={() => void perform(async () => { await request('google-drive/retry', { business_id: businessId }); await refresh(); setNotice('Синхронизация поставлена в очередь.'); })}>Синхронизировать фото с Google</Button>
            <Button type="button" variant="ghost" disabled={busy} onClick={() => void perform(async () => { await request('google-drive/disconnect', { business_id: businessId }); await refresh(); })}>Отключить Google Диск</Button>
          </>}
        </div>
        {!googleDrive?.configured && <p className="text-muted-foreground">Подключение Google Диска ещё не настроено в LocalOS. Работа с фото доступна.</p>}
      </div>
    </details>}
  </div>;
}
