import { useState } from 'react';
import { KeyRound } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { newAuth } from '@/lib/auth_new';

type Candidate = { title: string; text: string; source_id: string };
type Preview = {
  version: string;
  saved: boolean;
  sections: { key: string; label: string; href: string; items: Candidate[] }[];
  requests: { id: string; request_text: string; status: string; metadata_json: { service?: string; user_email?: string }; created_at: string }[];
  events: Record<string, number>;
  owner_state?: { password_set?: boolean; is_verified?: boolean };
};

export function PreparedCabinetInvite({ businessId, disabled }: { businessId: string; disabled: boolean }) {
  return <CabinetDialog key={businessId} businessId={businessId} disabled={disabled} />;
}

function CabinetDialog({ businessId, disabled }: { businessId: string; disabled: boolean }) {
  const [url, setUrl] = useState('');
  const [status, setStatus] = useState('');
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [selection, setSelection] = useState<Record<string, string[]>>({});
  const base = '/superadmin/businesses/' + encodeURIComponent(businessId) + '/prepared-cabinet';
  const refresh = async () => {
    const data: Preview = await newAuth.makeRequest(base);
    setPreview(data);
    setSelection(Object.fromEntries(data.sections.map(section => [section.key, section.items.map(item => item.source_id)])));
  };
  const action = async (run: () => Promise<void>) => {
    setBusy(true);
    setStatus('');
    try { await run(); } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Не удалось выполнить действие.');
    } finally { setBusy(false); }
  };
  const ready = preview?.sections.every(section => selection[section.key]?.length > 0);
  const save = async () => {
    if (!preview) return;
    await newAuth.makeRequest(base, { method: 'PUT', body: JSON.stringify({ selection, version: preview.version }) });
    await refresh();
    setStatus('Выбранные материалы доступны владельцу.');
  };
  return <Dialog onOpenChange={open => {
    if (open) void action(refresh);
    else { setUrl(''); setStatus(''); setPreview(null); }
  }}>
    <DialogTrigger asChild>
      <Button variant="ghost" size="icon" disabled={disabled} aria-label="Приглашение в подготовленный кабинет" title="Подготовить кабинет и приглашение"><KeyRound className="h-4 w-4" /></Button>
    </DialogTrigger>
    <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto">
      <DialogHeader>
        <DialogTitle>Подготовить кабинет владельцу</DialogTitle>
        <DialogDescription>Выберите готовые материалы компании, проверьте тексты и откройте их владельцу. Затем скопируйте приглашение.</DialogDescription>
      </DialogHeader>
      <div className="space-y-4" aria-busy={busy}>
        <Button variant="outline" disabled={busy} onClick={() => void action(refresh)}>Обновить предпросмотр</Button>
        {preview?.sections.map(section => <section key={section.key} className="space-y-2 rounded-xl border p-3">
          <h3 className="font-semibold">{section.label} · {section.items.length}</h3>
          {section.items.length ? section.items.map(item => <div key={item.source_id} className="rounded-lg border p-3">
            <label className="flex items-start gap-2">
              <Checkbox disabled={busy} checked={selection[section.key]?.includes(item.source_id) || false} onCheckedChange={checked => setSelection(previous => ({ ...previous, [section.key]: checked ? [...previous[section.key], item.source_id] : previous[section.key].filter(id => id !== item.source_id) }))} />
              <span className="text-sm font-medium">{item.title}</span>
            </label>
            <details className="mt-2 text-sm"><summary className="cursor-pointer">Посмотреть текст</summary><p className="whitespace-pre-wrap break-words pt-2">{item.text}</p></details>
          </div>) : <p className="text-sm text-muted-foreground">Подготовьте материалы в существующем разделе компании. Затем обновите предпросмотр.</p>}
        </section>)}
        <Button disabled={busy || !ready} onClick={() => void action(save)}>Открыть выбранные материалы владельцу</Button>
        {preview?.saved && <section className="space-y-3 rounded-xl border p-3">
          <p className="text-sm">Кабинет подготовлен. Для нового владельца ссылка действует 7 дней.</p>
          <Button disabled={busy} onClick={() => void action(async () => {
            const result = await newAuth.makeRequest(base + '/invitation', { method: 'POST' });
            setUrl(result.setup_url);
          })}>Выпустить ссылку</Button>
          <Button variant="outline" disabled={busy} onClick={() => void action(async () => {
            await newAuth.makeRequest(base + '/invitation', { method: 'DELETE' }); setUrl(''); setStatus('Ссылка отозвана.');
          })}>Отозвать ссылку</Button>
          <p className="text-sm"><a className="underline" href={'/dashboard/today?business_id=' + encodeURIComponent(businessId)}>Открыть существующий кабинет</a></p>
        </section>}
        {url && <div className="space-y-2">
          <Input value={url} readOnly aria-label="Ссылка приглашения" onFocus={event => event.currentTarget.select()} />
          <Button variant="outline" onClick={() => void action(async () => { await navigator.clipboard.writeText(url); setStatus('Ссылка скопирована.'); })}>Скопировать ссылку</Button>
        </div>}
        {preview?.saved && <details className="rounded-xl border p-3 text-sm">
          <summary className="cursor-pointer font-medium">Этапы знакомства с кабинетом</summary>
          <p className="py-2">Пароль {preview.owner_state?.password_set ? 'установлен' : 'ожидается'} · Почта {preview.owner_state?.is_verified ? 'подтверждена' : 'ожидает подтверждения'}</p>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" disabled={busy || Boolean(preview.events.action_marked_sent)} onClick={() => void action(async () => {
              await newAuth.makeRequest(base + '/milestone', { method:'POST',body:JSON.stringify({action:'shared'}) }); await refresh();
            })}>{preview.events.action_marked_sent ? 'Передача ссылки отмечена' : 'Отметить, что передал ссылку'}</Button>
            <Button variant="outline" disabled={busy || Boolean(preview.events.deal_started)} onClick={() => void action(async () => {
              await newAuth.makeRequest(base + '/milestone', { method:'POST',body:JSON.stringify({action:'agreed'}) }); await refresh();
            })}>{preview.events.deal_started ? 'Ведение согласовано' : 'Отметить согласие на ведение'}</Button>
          </div>
        </details>}
        {preview && <p className="text-sm text-muted-foreground">Просмотров разделов {preview.events.partial_result_viewed || 0} · Копирований {preview.events.message_copied || 0}</p>}
        {preview?.requests.length ? <section className="space-y-3">
          <h3 className="font-semibold">Запросы помощи с подключением</h3>
          {preview.requests.map(item => <article key={item.id} className="space-y-2 rounded-xl border p-3 text-sm">
            <p className="font-medium">{item.metadata_json.service || 'Подключения'} · {item.status === 'done' ? 'Помощь оказана' : item.status === 'in_progress' ? 'В работе' : 'Новое обращение'}</p>
            <p className="whitespace-pre-wrap">{item.request_text}</p>
            <p>{item.metadata_json.user_email}</p>
            {item.status !== 'done' && <Button variant="outline" disabled={busy} onClick={() => void action(async () => {
              await newAuth.makeRequest('/superadmin/businesses/' + encodeURIComponent(businessId) + '/connection-help', {
                method: 'PATCH', body: JSON.stringify({ id: item.id, previous_status: item.status, status: item.status === 'in_progress' ? 'done' : 'in_progress' }),
              }); await refresh();
            })}>{item.status === 'in_progress' ? 'Помощь оказана' : 'Взять в работу'}</Button>}
          </article>)}
        </section> : null}
        {status && <p role="status" className="text-sm">{status}</p>}
      </div>
    </DialogContent>
  </Dialog>;
}
