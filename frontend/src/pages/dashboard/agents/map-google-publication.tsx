import { useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { api } from '@/services/api';
import { recordValue } from './normalization';

type Change = { field: string; label: string; before: unknown; after: unknown };
type Preview = { changes: Change[]; google_title: string; google_name: string };
type Outcome = { verified?: boolean; verification_only?: boolean; write_outcome?: string; message?: string; has_pending_edits?: boolean; fields?: { field: string; label: string; matches: boolean }[] };
type Publication = { action_id: string; approval_digest: string; preview: Preview; status: string; outcome?: Outcome };
type Connection = { connected: boolean; message: string; title?: string; can_modify_services?: boolean; publication?: Publication };
const fields = [{ field: 'name', label: 'Название' }, { field: 'phone', label: 'Телефон' }, { field: 'website', label: 'Сайт' }, { field: 'description', label: 'Описание' }, { field: 'services', label: 'Услуги и цены' }];
const readable = (value: unknown): string => {
  if (Array.isArray(value)) return value.length ? value.map((raw) => {
    const item = recordValue(raw); const free = recordValue(item?.freeFormServiceItem); const label = recordValue(free?.label); const price = recordValue(item?.price); const structured = recordValue(item?.structuredServiceItem);
    return `${String(label?.displayName || structured?.serviceTypeId || 'Услуга Google')}${price ? ` — ${Number(price.units || 0) + Number(price.nanos || 0) / 1e9} ${String(price.currencyCode || '')}` : ''}${label?.description ? `\n${String(label.description)}` : ''}`;
  }).join('\n\n') : 'Нет услуг';
  return typeof value === 'string' && value ? value : 'Не заполнено';
};
const errorText = (reason: unknown) => {
  const response = recordValue(recordValue(reason)?.response); const data = recordValue(response?.data);
  return typeof data?.error === 'string' ? data.error : reason instanceof Error ? reason.message : 'Не удалось проверить Google. Повторите позже.';
};

export const MapGooglePublication = ({ runId, submission, revision, dirty, ready, hasServices }: { runId: string; submission: boolean; revision: number; dirty: boolean; ready: boolean; hasServices: boolean }) => {
  const [connection, setConnection] = useState<Connection | null>(null);
  const [publication, setPublication] = useState<Publication | null>(null);
  const [selected, setSelected] = useState(['name', 'phone', 'website', 'description']);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const alive = useRef(true);
  const operationInFlight = useRef(false);
  const endpoint = `/agent-runs/${runId}/map-google`;
  const load = async () => {
    if (operationInFlight.current) return;
    operationInFlight.current = true; setBusy(true); setError('');
    try { const response = await api.get(endpoint); if (alive.current) { setConnection(response.data); setPublication(response.data.publication || null); setConfirmed(false); } }
    catch (reason) { if (alive.current) setError(errorText(reason)); }
    finally { operationInFlight.current = false; if (alive.current) setBusy(false); }
  };
  useEffect(() => { alive.current = true; void load(); return () => { alive.current = false; }; }, [runId]);
  useEffect(() => { setConfirmed(false); }, [revision, dirty]);
  const command = async (operation: 'prepare' | 'approve' | 'reject' | 'verify') => {
    if (operationInFlight.current || (operation !== 'verify' && dirty) || operation === 'approve' && !confirmed) return;
    operationInFlight.current = true; setBusy(true); setError(''); setMessage('');
    try {
      const body = operation === 'prepare' ? { operation, revision, selected_fields: selected, request_id: crypto.randomUUID() } : { operation, action_id: publication?.action_id, approved_digest: publication?.approval_digest, approved: operation === 'approve' };
      const response = await api.post(endpoint, body);
      if (!alive.current) return;
      const data = response.data;
      setConfirmed(false);
      if (operation === 'prepare') {
        if (data.status === 'no_changes') { setPublication(null); setMessage(data.message); }
        else setPublication({ action_id: data.action_id, approval_digest: data.approval_digest, preview: data.preview, status: data.status });
      } else { setPublication((previous) => previous ? { ...previous, status: data.status || previous.status, outcome: data.result || previous.outcome } : null); }
    } catch (reason) { if (alive.current) { setError(errorText(reason)); setConfirmed(false); } }
    finally { operationInFlight.current = false; if (alive.current) setBusy(false); }
  };
  const pending = publication?.status === 'pending_human';
  const sent = publication?.status === 'completed' || publication?.status === 'failed';
  return <section aria-label="Отправка в Google" className="space-y-3 rounded-xl border border-border bg-muted/40 p-4" aria-busy={busy}>
    <h4 className="font-semibold">Google — отправка через API после подтверждения</h4>
    <p className="text-sm">LocalOS может отправить название, телефон, сайт, описание и услуги. Адрес, часы работы и фотографии перенесите в Google вручную. Яндекс и 2ГИС оформляются вручную целиком.</p>
    {!connection && busy ? <p role="status" className="text-sm">Проверяем подключение Google…</p> : null}
    {connection ? <p className="text-sm">{connection.message}{connection.connected && connection.title ? ` Карточка: ${connection.title}.` : ''}</p> : null}
    {!connection?.connected ? <div className="flex flex-wrap gap-2"><Button variant="outline" asChild><a href="/dashboard/settings?focus=google">Подключить Google Business</a></Button><Button variant="ghost" disabled={busy} onClick={() => void load()}>Проверить подключение</Button></div> : null}
    {connection?.connected ? <Button variant="ghost" size="sm" disabled={busy} onClick={() => void load()}>Обновить состояние Google</Button> : null}
    {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
    {message ? <p role="status" className="text-sm">{message}</p> : null}
    {submission && connection?.connected ? <>
      <p className="text-sm">Сначала отметьте и сохраните три шага подготовки. Затем выберите сведения и сравните их с текущей карточкой Google. Пустые поля не удаляют сведения в Google; существующие услуги сохраняются.</p>
      <fieldset disabled={busy} className="flex flex-wrap gap-4"><legend className="mb-2 text-sm font-medium">Что отправить в Google</legend>{fields.map((item) => <label key={item.field} className="flex items-center gap-2 text-sm"><input type="checkbox" className="h-4 w-4" checked={selected.includes(item.field)} disabled={item.field === 'services' && (!hasServices || !connection.can_modify_services)} onChange={(event) => { setSelected((previous) => event.target.checked ? [...previous, item.field] : previous.filter((key) => key !== item.field)); setPublication(null); setConfirmed(false); }} />{item.label}</label>)}</fieldset>
      {hasServices && !connection.can_modify_services ? <p className="text-sm text-muted-foreground">Google не разрешает менять услуги этой карточки через API. Перенесите их вручную.</p> : null}
      {dirty ? <p className="text-sm text-muted-foreground">Сначала нажмите «Сохранить прогресс». Несохранённые правки не отправляются.</p> : !ready ? <p className="text-sm text-muted-foreground">Подтвердите шаги «Данные», «Услуги» и «Фотографии».</p> : null}
      <Button disabled={busy || dirty || !ready || !selected.length} onClick={() => void command('prepare')}>{publication ? 'Подготовить новое сравнение' : 'Сравнить с Google'}</Button>
      {publication ? <div className="space-y-3 border-t border-border pt-4">
        <div><h5 className="font-semibold">Правки для {publication.preview.google_title || 'карточки Google'}</h5><p className="text-xs text-muted-foreground">{publication.preview.google_name} · подтверждение действует 30 минут</p></div>
        {publication.preview.changes.map((change) => <div key={change.field} className="rounded-lg border border-border bg-background p-3"><h6 className="text-sm font-semibold">{change.label}</h6><div className="mt-2 grid gap-3 sm:grid-cols-2"><div><p className="text-xs text-muted-foreground">Сейчас в Google</p><p className="whitespace-pre-wrap break-words text-sm">{readable(change.before)}</p></div><div><p className="text-xs text-muted-foreground">Будет отправлено</p><p className="whitespace-pre-wrap break-words text-sm">{readable(change.after)}</p></div></div></div>)}
        {pending ? <><label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1 h-4 w-4" checked={confirmed} disabled={busy || dirty || !ready} onChange={(event) => setConfirmed(event.target.checked)} /><span>Я проверил карточку и все показанные изменения. Подтверждаю их отправку в Google.</span></label><div className="flex flex-wrap gap-2"><Button disabled={busy || dirty || !ready || !confirmed} onClick={() => void command('approve')}>Подтвердить и отправить в Google</Button><Button variant="outline" disabled={busy || dirty} onClick={() => void command('reject')}>Отклонить правки</Button></div></> : null}
        {publication.status === 'rejected' || publication.status === 'expired' ? <p role="status" className="text-sm">{publication.status === 'rejected' ? 'Правки отклонены.' : 'Срок подтверждения истёк.'} Для отправки подготовьте новое сравнение.</p> : null}
        {sent ? <div className="space-y-2"><p role="status" className="text-sm font-medium">{publication.outcome?.verified ? 'Повторное чтение API: выбранные сведения совпадают с подтверждёнными правками.' : publication.status === 'failed' ? 'Отправку завершить не удалось. Проверьте результат и подготовьте новое сравнение при необходимости.' : 'Совпадение сведений после отправки пока не подтверждено.'}</p>{publication.outcome?.message ? <p className="text-sm">{publication.outcome.message}</p> : null}{publication.outcome?.fields?.map((field) => <p key={field.field} className="text-sm">{field.label}: {field.matches ? 'совпадает' : 'требует проверки'}</p>)}<Button variant="outline" disabled={busy} onClick={() => void command('verify')}>Повторно проверить Google</Button></div> : null}
        <p className="text-sm text-muted-foreground">Проверка API не подтверждает внешний вид и публикацию на Google Картах. Дождитесь модерации и отдельно проверьте публичную карточку на шаге 5.</p>
      </div> : null}
    </> : null}
  </section>;
};
