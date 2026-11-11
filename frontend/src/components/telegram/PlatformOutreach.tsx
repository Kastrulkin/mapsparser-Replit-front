import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Button } from '@/components/ui/button';
import { mobileJsonHeaders, readMobileJson, type MobileJob } from '@/lib/mobileDataClient';
import { useLatestCallback } from '@/hooks/useLatestCallback';
import { useMobileJobPolling } from './useMobileJobPolling';

type Reply = { id: string; lead_name?: string; business_name?: string; business_id?: string; channel: string; reply_text?: string; occurred_at?: string };
type Search = { id: string; business_id: string; business_name?: string; audience?: string; target_count?: string; stage?: string; status: string };
type Workspace = { items: Reply[]; cursor?: string | null; searches: Search[]; active_job?: MobileJob | null;
  senders: Array<{ channel: string; status: string; last_reply_sync_at?: string | null; sync_failed?: boolean }>;
  readiness: { search_enabled: boolean; web_enabled: boolean; yandex_enabled: boolean; sync_enabled: boolean } };
type Preview = { status?: string; chat_response?: string; approval?: { action_id?: string }; job_id?: string; blocked_reasons?: string[] };
const scope = { kind: 'platform' };
const endpoint = '/api/operator/mobile/platform/outreach';
const dateLabel = (value?: string | null) => value ? new Date(value).toLocaleString('ru-RU') : 'Ещё не проверялся';

export function PlatformOutreach({ openBusiness }: { openBusiness?: (id: string) => void }) {
  const [data, setData] = useState<Workspace | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [job, setJob] = useState<MobileJob | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [audience, setAudience] = useState('');
  const [geography, setGeography] = useState('');
  const [quantity, setQuantity] = useState('10');
  const [provider, setProvider] = useState('auto');
  const [preview, setPreview] = useState<Preview | null>(null);
  const [businessId, setBusinessId] = useState('');
  const version = useRef(0);
  const actionLock = useRef(false);
  const clearPrivate = () => { version.current++; setLoading(false); setData(null); setPreview(null); setJob(null); setBusinessId(''); setFormOpen(false); setAudience(''); setGeography(''); setNotice(''); setError('Доступ к платформе изменился. Откройте LocalOS заново.'); };
  const read = async <T,>(response: Response) => {
    if ([401, 403].includes(response.status)) clearPrivate();
    return readMobileJson<T>(response);
  };
  const load = useLatestCallback(async (cursor?: string) => {
    const current = ++version.current;
    setLoading(true);
    try {
      const response = await fetch(endpoint + (cursor ? `?cursor=${encodeURIComponent(cursor)}` : ''), { headers: mobileJsonHeaders() });
      if (current !== version.current) return;
      const result = await read<Workspace>(response);
      if (current !== version.current) return;
      setData(previous => ({ ...result, items: cursor ? [...(previous?.items || []), ...result.items] : result.items }));
      if (result.active_job) setJob(result.active_job);
      setError('');
    } catch (failure) { if (current === version.current) setError(failure instanceof Error ? failure.message : 'Не удалось загрузить ответы'); }
    finally { if (current === version.current) setLoading(false); }
  });
  useEffect(() => { void load(); return () => { version.current++; }; }, [load]);
  useMobileJobPolling({ job, scope, onJob: setJob, onError: () => { setJob(null); void load(); }, onComplete: completed => {
    const state = completed.result?.sync_status;
    setNotice(completed.status === 'failed' ? 'Проверка не завершена. Повторите запрос.' : state === 'partial' ? 'Часть каналов не удалось обновить. Доступные ответы показаны ниже.' : state === 'no_sources' ? 'В этом проходе не было источников или диалогов, доступных для проверки.' : 'Проверка подключённых каналов завершена в пределах одного прохода.');
    void load();
  } });
  const post = (body: Record<string, unknown>) => fetch(endpoint, { method: 'POST', headers: mobileJsonHeaders(), body: JSON.stringify(body) });
  const refresh = async () => {
    if (actionLock.current) return;
    const current = version.current;
    actionLock.current = true; setBusy('sync'); setError('');
    try {
      const result = await post({ action: 'sync', request_id: crypto.randomUUID() }).then(read<{ job: MobileJob }>);
      if (current !== version.current) return;
      setJob(result.job); setNotice('Проверяем ответы в подключённых каналах…');
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Не удалось начать проверку'); }
    finally { actionLock.current = false; setBusy(''); }
  };
  const prepare = async (event: FormEvent) => {
    event.preventDefault();
    if (actionLock.current) return;
    const current = version.current;
    actionLock.current = true; setBusy('preview'); setError(''); setPreview(null);
    try {
      const result = await post({ action: 'search_preview', audience, search_geography: geography.split(/[;,\n]/).map(place => place.trim()).filter(Boolean), target_count: Number(quantity), request_id: crypto.randomUUID(), ...(provider === 'yandex' ? { web_search_provider: 'yandex' } : {}) }).then(read<{ business_id: string; operator_result: Preview }>);
      if (current !== version.current) return;
      setBusinessId(result.business_id); setPreview(result.operator_result);
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Не удалось проверить условия'); }
    finally { actionLock.current = false; setBusy(''); }
  };
  const confirm = async () => {
    if (actionLock.current || !preview?.approval?.action_id || !businessId) return;
    const current = version.current;
    actionLock.current = true; setBusy('confirm'); setError('');
    try {
      const response = await fetch(`/api/operator/actions/${encodeURIComponent(preview.approval.action_id)}/confirm`, { method: 'POST', headers: mobileJsonHeaders(), body: JSON.stringify({ business_id: businessId }) });
      const result = await read<{ operator_result: Preview }>(response);
      if (current !== version.current) return;
      const outcome = result.operator_result;
      setNotice(outcome.chat_response || (outcome.job_id ? 'Поиск запущен.' : 'Поиск не запущен. Проверьте условия заново.'));
      setPreview(null);
      if (outcome.job_id) setFormOpen(false);
      await load();
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Не удалось подтвердить запуск'); }
    finally { actionLock.current = false; setBusy(''); }
  };
  const searchAvailable = Boolean(data?.readiness.search_enabled && (data.readiness.web_enabled || data.readiness.yandex_enabled));
  const checking = Boolean(job?.id && !job.terminal);
  return <section aria-label="Аутрич всей платформы" className="space-y-5">
    <div><h2 className="text-xl font-semibold">LocalOS · Вся платформа</h2><p className="mt-2 text-sm text-muted-foreground">Ответы и поиски по всем добавленным бизнесам.</p></div>
    {error && <p role="alert">{error}</p>}
    {notice && <p role="status">{notice}</p>}
    <div className="flex flex-wrap gap-2"><Button disabled={Boolean(busy) || checking || !data?.readiness.sync_enabled} onClick={() => void refresh()}>{checking ? 'Проверяем входящие…' : 'Проверить входящие'}</Button><Button variant="outline" disabled={!searchAvailable || Boolean(busy)} onClick={() => { setFormOpen(true); setPreview(null); setProvider(data?.readiness.web_enabled ? 'auto' : 'yandex'); }}>Новый поиск</Button><Button variant="ghost" disabled={loading} onClick={() => void load()}>Обновить список</Button></div>
    {data && !searchAvailable && <p className="text-sm text-muted-foreground">Новый поиск временно недоступен: нужно включить поиск и подключить поисковый сервис.</p>}
    {formOpen && <form aria-label="Новый поиск лидов" onSubmit={prepare} className="space-y-3 rounded-2xl border p-4">
      <h3 className="font-semibold">Найти новые компании для LocalOS</h3>
      <label className="block text-sm">Кого ищем<input required maxLength={500} value={audience} disabled={Boolean(busy) || Boolean(preview?.approval)} onChange={event => setAudience(event.target.value)} className="mt-1 min-h-11 w-full rounded-lg border bg-background p-3" placeholder="Например, салоны красоты" /></label>
      <label className="block text-sm">Где ищем<input required value={geography} disabled={Boolean(busy) || Boolean(preview?.approval)} onChange={event => setGeography(event.target.value)} className="mt-1 min-h-11 w-full rounded-lg border bg-background p-3" placeholder="Города или страны через запятую" /></label>
      <label className="block text-sm">Количество компаний<input required type="number" min={1} max={1000} value={quantity} disabled={Boolean(busy) || Boolean(preview?.approval)} onChange={event => setQuantity(event.target.value)} className="mt-1 min-h-11 w-full rounded-lg border bg-background p-3" /></label>
      <label className="block text-sm">Источник<select value={provider} disabled={Boolean(busy) || Boolean(preview?.approval)} onChange={event => setProvider(event.target.value)} className="mt-1 min-h-11 w-full rounded-lg border bg-background p-3"><option value="auto" disabled={!data?.readiness.web_enabled}>Поиск в интернете</option>{data?.readiness.yandex_enabled && <option value="yandex">Яндекс — платные поисковые запросы</option>}</select></label>
      <p className="text-sm text-muted-foreground">Только поиск и проверка контактов. Письма не готовятся и не отправляются. До запуска покажем условия и расходы.</p>
      {preview && <div className="whitespace-pre-wrap rounded-lg border p-3" aria-label="Условия поиска">{preview.chat_response}</div>}
      <div className="flex flex-wrap gap-2">{preview?.status === 'approval_required' && preview.approval?.action_id ? <><Button type="button" disabled={Boolean(busy)} onClick={() => void confirm()}>Подтвердить запуск поиска</Button><Button type="button" variant="outline" disabled={Boolean(busy)} onClick={() => setPreview(null)}>Изменить условия</Button></> : <Button type="submit" disabled={Boolean(busy)}>{busy === 'preview' ? 'Проверяем условия…' : 'Показать условия и стоимость'}</Button>}<Button type="button" variant="ghost" disabled={Boolean(busy)} onClick={() => { setPreview(null); setFormOpen(false); }}>Закрыть</Button></div>
    </form>}
    <section aria-label="Входящие по всем бизнесам" className="space-y-3"><h3 className="font-semibold">Входящие ответы</h3><p className="text-sm text-muted-foreground">Сохранённые ответы. «Проверить входящие» обновляет подключённые email, Telegram и VK. Личные диалоги MAX не читаются.</p>
      {data?.items.map(reply => <article key={reply.id} className="space-y-2 rounded-xl border p-4"><h4 className="font-semibold">{reply.lead_name || 'Компания'}</h4><p className="text-sm text-muted-foreground">{reply.business_name || 'LocalOS'} · {reply.channel} · {dateLabel(reply.occurred_at)}</p><p className="whitespace-pre-wrap break-words">{reply.reply_text || 'Текст ответа не сохранён'}</p>{reply.business_id && openBusiness && <Button variant="outline" onClick={() => openBusiness(reply.business_id || '')}>Открыть работу бизнеса</Button>}</article>)}
      {data && !data.items.length && <p>Сохранённых ответов пока нет.</p>}
      {data?.cursor && <Button variant="outline" disabled={loading} onClick={() => void load(data.cursor || undefined)}>Ещё ответы</Button>}
      {loading && <p role="status">Загружаем ответы…</p>}
    </section>
    <section aria-label="Поиски по всем бизнесам" className="space-y-3"><h3 className="font-semibold">Последние поиски</h3>{data?.searches.map(search => <article key={search.id} className="space-y-1 rounded-xl border p-3"><h4 className="font-semibold">{search.audience || 'Поиск компаний'}</h4><p className="text-sm text-muted-foreground">{search.business_name || 'LocalOS'}{search.target_count ? ` · Цель: ${search.target_count}` : ''}</p><p>{search.stage || search.status}</p></article>)}{data && !data.searches.length && <p>Сохранённых поисков пока нет.</p>}</section>
    <details><summary className="min-h-11 cursor-pointer py-3">Последняя проверка каналов</summary>{data?.senders.map((sender, index) => <p key={index} className="py-1 text-sm">{sender.channel} · {dateLabel(sender.last_reply_sync_at)}{sender.sync_failed ? ' · Не удалось обновить' : ''}</p>)}</details>
  </section>;
}
