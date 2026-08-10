import { useCallback, useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Check, ChevronRight, CircleAlert, ExternalLink, Loader2, Pencil, Plus, Radio, Trash2, X } from 'lucide-react';
import ActionPreviewSheet, { type MobileActionPreview } from './ActionPreviewSheet';

type CommunitySource = {
  id: string;
  title?: string;
  canonical_url?: string;
  status?: string;
  sync_status?: string;
  last_sync_error?: string;
  last_collected_at?: string;
  next_sync_at?: string;
  documents_count?: number;
  embeddings_count?: number;
  topics_json?: string[];
  schedule_json?: { interval_hours?: number };
};

type IndustryPulse = {
  key?: string;
  label?: string;
  default_sources_count?: number;
  default_sources?: Array<{ id?: string; title?: string; canonical_url?: string }>;
};

const spring = { type: 'spring', duration: 0.3, bounce: 0 };
const intervalOptions = [['6', 'Каждые 6 часов'], ['12', 'Каждые 12 часов'], ['24', 'Раз в день'], ['72', 'Раз в 3 дня'], ['168', 'Раз в неделю']];
const topicPresets = ['Цены и затраты', 'Маркетинг', 'Клиенты', 'Конкуренты'];
const previewSources: CommunitySource[] = [
  { id: 'preview-ready', title: 'Beauty Business Club', canonical_url: 'https://t.me/beauty_business', sync_status: 'ready', last_collected_at: new Date().toISOString(), next_sync_at: new Date(Date.now() + 86400000).toISOString(), documents_count: 248, embeddings_count: 248, topics_json: ['Маркетинг', 'Клиенты'], schedule_json: { interval_hours: 24 } },
  { id: 'preview-queued', title: 'Предприниматели Батуми', canonical_url: 'https://t.me/business_batumi', sync_status: 'queued', next_sync_at: new Date().toISOString(), documents_count: 0, embeddings_count: 0, topics_json: ['Цены и затраты'], schedule_json: { interval_hours: 12 } },
];

const headers = () => ({ Authorization: `Bearer ${window.sessionStorage.getItem('localos_mini_session') || ''}`, 'Content-Type': 'application/json' });
const read = async (response: Response) => {
  const raw = await response.text();
  let payload: Record<string, unknown> = {};
  try { payload = raw ? JSON.parse(raw) : {}; } catch { throw new Error('Сервис вернул неполный ответ. Попробуйте ещё раз.'); }
  if (!response.ok || payload.success === false) throw new Error(typeof payload.error === 'string' ? payload.error : 'Не удалось выполнить запрос');
  return payload;
};
const actionPreview = (value: unknown): MobileActionPreview | null => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const fields = Object.fromEntries(Object.entries(value));
  const objectRows = (items: unknown): Array<{ id?: string; business_name?: string }> | undefined => Array.isArray(items) ? items.map((item) => {
    const row = item && typeof item === 'object' && !Array.isArray(item) ? Object.fromEntries(Object.entries(item)) : {};
    return { id: typeof row.id === 'string' ? row.id : undefined, business_name: typeof row.business_name === 'string' ? row.business_name : undefined };
  }) : undefined;
  const businessRows = (items: unknown): Array<{ id?: string; name?: string }> | undefined => Array.isArray(items) ? items.map((item) => {
    const row = item && typeof item === 'object' && !Array.isArray(item) ? Object.fromEntries(Object.entries(item)) : {};
    return { id: typeof row.id === 'string' ? row.id : undefined, name: typeof row.name === 'string' ? row.name : undefined };
  }) : undefined;
  const changeRows = (items: unknown): Array<{ object_id?: string; operation?: string; label?: string }> | undefined => Array.isArray(items) ? items.map((item) => {
    const row = item && typeof item === 'object' && !Array.isArray(item) ? Object.fromEntries(Object.entries(item)) : {};
    return {
      object_id: typeof row.object_id === 'string' ? row.object_id : undefined,
      operation: typeof row.operation === 'string' ? row.operation : undefined,
      label: typeof row.label === 'string' ? row.label : undefined,
    };
  }) : undefined;
  return {
    action_id: typeof fields.action_id === 'string' ? fields.action_id : undefined,
    capability: typeof fields.capability === 'string' ? fields.capability : undefined,
    target_businesses: businessRows(fields.target_businesses),
    objects: objectRows(fields.objects),
    changes: changeRows(fields.changes),
    estimated_credits: typeof fields.estimated_credits === 'number' ? fields.estimated_credits : undefined,
    external_effects: fields.external_effects === true,
    is_mass_action: fields.is_mass_action === true,
    expires_at: typeof fields.expires_at === 'string' ? fields.expires_at : undefined,
  };
};
const dateLabel = (value?: string) => {
  if (!value) return 'ещё не собирали';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'дата неизвестна' : date.toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
};
const intervalLabel = (value?: number) => intervalOptions.find(([key]) => key === String(value || 24))?.[1]?.toLowerCase() || 'раз в день';
const statusMeta = (item: CommunitySource) => {
  if (item.sync_status === 'failed' || item.last_sync_error) return { label: 'Нужна проверка', dot: 'bg-rose-400', text: 'Не получилось обновить источник' };
  if (['queued', 'running', 'processing'].includes(item.sync_status || '')) return { label: 'Собираем', dot: 'bg-sky-300 motion-safe:animate-pulse', text: 'Новые публичные материалы уже в очереди' };
  if (item.last_collected_at) return { label: 'Всё работает', dot: 'bg-emerald-400', text: 'Продолжаем следить за новыми обсуждениями' };
  return { label: 'Первый сбор', dot: 'bg-amber-300 motion-safe:animate-pulse', text: 'Проверяем источник и собираем историю' };
};

export const CommunitySourcesMobileModule = ({ businessId }: { businessId?: string | null }) => {
  const [items, setItems] = useState<CommunitySource[]>([]);
  const [industry, setIndustry] = useState<IndustryPulse | null>(null);
  const [url, setUrl] = useState('');
  const [topics, setTopics] = useState<string[]>([]);
  const [customTopics, setCustomTopics] = useState('');
  const [intervalHours, setIntervalHours] = useState('24');
  const [editingId, setEditingId] = useState('');
  const [editTopics, setEditTopics] = useState('');
  const [editInterval, setEditInterval] = useState('24');
  const [removeId, setRemoveId] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [preview, setPreview] = useState<MobileActionPreview | null>(null);

  const load = useCallback(async () => {
    if (!businessId) { setLoading(false); return; }
    if (businessId === 'preview') { setItems(previewSources); setIndustry({ key: 'beauty', label: 'Бьюти-индустрия', default_sources_count: 18, default_sources: [{ title: 'Владельцы салонов красоты' }, { title: 'Маркетинг салона красоты' }, { title: 'Бьюти-бизнес' }] }); setLoading(false); return; }
    try {
      const payload = await fetch(`/api/business/${encodeURIComponent(businessId)}/community-sources`, { headers: headers() }).then(read);
      setItems(Array.isArray(payload.items) ? payload.items : []);
      const industryPayload = payload.industry;
      if (industryPayload && typeof industryPayload === 'object' && !Array.isArray(industryPayload)) {
        const value = Object.fromEntries(Object.entries(industryPayload));
        setIndustry({
          key: typeof value.key === 'string' ? value.key : undefined,
          label: typeof value.label === 'string' ? value.label : undefined,
          default_sources_count: typeof value.default_sources_count === 'number' ? value.default_sources_count : 0,
          default_sources: Array.isArray(value.default_sources) ? value.default_sources.filter((source) => Boolean(source) && typeof source === 'object').map((source) => {
            const fields = Object.fromEntries(Object.entries(source));
            return {
              id: typeof fields.id === 'string' ? fields.id : undefined,
              title: typeof fields.title === 'string' ? fields.title : undefined,
              canonical_url: typeof fields.canonical_url === 'string' ? fields.canonical_url : undefined,
            };
          }) : [],
        });
      } else setIndustry(null);
      setError('');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Не удалось загрузить источники');
    } finally { setLoading(false); }
  }, [businessId]);

  useEffect(() => { void load(); }, [load]);

  const add = async (event: FormEvent) => {
    event.preventDefault();
    if (!businessId || !url.trim()) return;
    setBusy('add'); setError(''); setMessage('');
    try {
      const extraTopics = customTopics.split(',').map((item) => item.trim()).filter(Boolean);
      if (businessId === 'preview') {
        setItems((current) => [{ id: `preview-${Date.now()}`, title: url.replace(/^https?:\/\/t\.me\//, '@'), canonical_url: url, sync_status: 'queued', next_sync_at: new Date().toISOString(), documents_count: 0, embeddings_count: 0, topics_json: [...new Set([...topics, ...extraTopics])], schedule_json: { interval_hours: Number(intervalHours) } }, ...current]);
        setUrl(''); setTopics([]); setCustomTopics(''); setMessage('Источник добавлен. ЛокалОС начал собирать публичные материалы.');
        return;
      }
      const payload = await fetch(`/api/business/${encodeURIComponent(businessId)}/community-sources`, {
        method: 'POST', headers: headers(), body: JSON.stringify({ url: url.trim(), topics: [...new Set([...topics, ...extraTopics])], interval_hours: Number(intervalHours) }),
      }).then(read);
      setUrl(''); setTopics([]); setCustomTopics('');
      setMessage(typeof payload.message === 'string' ? payload.message : 'Источник добавлен. ЛокалОС начал собирать публичные материалы.');
      await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось добавить источник'); }
    finally { setBusy(''); }
  };

  const startEditing = (item: CommunitySource) => {
    setEditingId(item.id);
    setEditTopics((item.topics_json || []).join(', '));
    setEditInterval(String(item.schedule_json?.interval_hours || 24));
    setMessage(''); setError('');
  };

  const save = async (sourceId: string) => {
    if (!businessId) return;
    setBusy(`save:${sourceId}`); setError(''); setMessage('');
    try {
      if (businessId === 'preview') {
        setItems((current) => current.map((item) => item.id === sourceId ? { ...item, topics_json: editTopics.split(',').map((topic) => topic.trim()).filter(Boolean), schedule_json: { interval_hours: Number(editInterval) } } : item));
        setEditingId(''); setMessage('Настройки сохранены. Новый график уже учтён.');
        return;
      }
      await fetch(`/api/business/${encodeURIComponent(businessId)}/community-sources/${encodeURIComponent(sourceId)}`, {
        method: 'PATCH', headers: headers(), body: JSON.stringify({ topics: editTopics.split(',').map((item) => item.trim()).filter(Boolean), interval_hours: Number(editInterval) }),
      }).then(read);
      setEditingId(''); setMessage('Настройки сохранены. Новый график уже учтён.');
      await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось сохранить настройки'); }
    finally { setBusy(''); }
  };

  const prepareRemove = async () => {
    if (!businessId || !removeId) return;
    const sourceId = removeId;
    setBusy(`remove:${sourceId}`); setError('');
    try {
      if (businessId === 'preview') {
        setItems((current) => current.filter((item) => item.id !== sourceId));
        setRemoveId(''); setEditingId(''); setMessage('Источник больше не влияет на ваш «Пульс сообщества».');
        return;
      }
      const payload = await fetch('/api/operator/mobile/actions/preview', {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify({
          scope_type: 'business',
          scope_id: businessId,
          capability: 'community_sources.unsubscribe',
          input: { business_id: businessId, source_id: sourceId },
        }),
      }).then(read);
      const nextPreview = actionPreview(payload.preview);
      if (!nextPreview?.action_id) throw new Error('Не удалось подготовить проверку действия');
      setRemoveId('');
      setPreview(nextPreview);
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось отключить источник'); }
    finally { setBusy(''); }
  };

  const confirmRemove = async () => {
    const actionId = preview?.action_id;
    const sourceId = preview?.objects?.[0]?.id;
    if (!actionId || !sourceId) return;
    setBusy(`confirm:${actionId}`); setError('');
    try {
      await fetch(`/api/operator/mobile/actions/${encodeURIComponent(actionId)}/confirm`, {
        method: 'POST', headers: headers(), body: JSON.stringify({}),
      }).then(read);
      setItems((current) => current.filter((item) => item.id !== sourceId));
      setEditingId(''); setPreview(null);
      setMessage('Источник больше не влияет на ваш «Пульс сообщества».');
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось отключить источник'); }
    finally { setBusy(''); }
  };

  if (!businessId) return <div className="rounded-[22px] bg-amber-400/10 p-4 text-sm text-amber-100 shadow-[0_0_0_1px_rgba(252,211,77,0.2)]">Выберите конкретный бизнес, чтобы настроить его источники.</div>;

  const defaultSourcesCount = Number(industry?.default_sources_count || 0);

  return <div className="space-y-6">
    <section className="rounded-[26px] bg-gradient-to-b from-zinc-900 to-zinc-900/70 p-5 shadow-[0_22px_70px_rgba(0,0,0,0.28),0_0_0_1px_rgba(255,255,255,0.08)]">
      {defaultSourcesCount ? <div className="mb-5 border-b border-white/[0.06] pb-5"><div className="flex items-start gap-3"><span className="grid h-11 w-11 shrink-0 place-items-center rounded-[15px] bg-emerald-400/10 text-emerald-300"><Check className="h-5 w-5" /></span><div className="min-w-0 flex-1"><small className="font-semibold uppercase tracking-[0.12em] text-emerald-300/80">Уже работает</small><h2 className="mt-1 text-balance text-lg font-semibold">{industry?.key === 'beauty' ? 'Бьюти-пульс уже включён' : 'Отраслевой пульс уже включён'}</h2><p className="mt-1 text-pretty text-xs leading-5 text-zinc-500">ЛокалОС уже собирает обсуждения из <span className="tabular-nums text-zinc-300">{defaultSourcesCount}</span> проверенных открытых источников и показывает главное на экране «Сегодня».</p></div></div>{industry?.default_sources?.length ? <p className="mt-3 line-clamp-2 text-pretty text-[11px] leading-5 text-zinc-600">Например: {industry.default_sources.map((source) => source.title).filter(Boolean).join(' · ')}</p> : null}</div> : null}
      <span className="grid h-11 w-11 place-items-center rounded-[15px] bg-primary/15 text-primary"><Radio className="h-5 w-5" /></span>
      <h2 className="mt-4 text-balance text-xl font-semibold tracking-[-0.03em]">{defaultSourcesCount ? 'Добавить свои источники' : 'За чем следить?'}</h2>
      <p className="mt-2 text-pretty text-sm leading-6 text-zinc-500">Добавьте публичный канал или открытую группу. ЛокалОС добавит важные темы в вашу сводку. Если источник уже есть в общей базе, повторно собирать его не придётся.</p>
      <form onSubmit={add} className="mt-5">
        <label className="text-xs font-medium text-zinc-400"><span className="mb-2 block px-1">Ссылка на публичный канал или группу</span><input value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://t.me/channel" inputMode="url" autoCapitalize="none" className="min-h-12 w-full rounded-2xl bg-black/20 px-4 text-sm text-zinc-100 outline-none ring-1 ring-inset ring-white/[0.08] placeholder:text-zinc-700 focus:ring-primary/50" /></label>
        <details className="mt-3 rounded-[18px] bg-black/15 shadow-[0_0_0_1px_rgba(255,255,255,0.06)]">
          <summary className="flex min-h-12 cursor-pointer list-none items-center gap-3 px-4 text-xs font-semibold text-zinc-400"><span className="flex-1">Уточнить темы и график</span><ChevronRight className="h-4 w-4" /></summary>
          <div className="border-t border-white/[0.055] p-3">
            <p className="px-1 text-[11px] leading-4 text-zinc-600">Какие темы важнее всего?</p>
            <div className="mt-2 flex flex-wrap gap-2">{topicPresets.map((topic) => { const selected = topics.includes(topic); return <button key={topic} type="button" aria-pressed={selected} onClick={() => setTopics((current) => selected ? current.filter((item) => item !== topic) : [...current, topic])} className={`min-h-11 rounded-[14px] px-3 text-xs font-medium transition-[background-color,color,transform] active:scale-[0.96] ${selected ? 'bg-primary/15 text-primary shadow-[0_0_0_1px_rgba(255,92,51,0.25)]' : 'bg-white/[0.04] text-zinc-500 shadow-[0_0_0_1px_rgba(255,255,255,0.06)]'}`}>{topic}</button>; })}</div>
            <input value={customTopics} onChange={(event) => setCustomTopics(event.target.value)} placeholder="Другие темы через запятую" className="mt-3 min-h-12 w-full rounded-2xl bg-black/20 px-4 text-sm outline-none ring-1 ring-inset ring-white/[0.07] placeholder:text-zinc-700 focus:ring-primary/50" />
            <label className="mt-3 block text-[11px] text-zinc-600"><span className="mb-1.5 block px-1">Как часто проверять</span><select value={intervalHours} onChange={(event) => setIntervalHours(event.target.value)} className="min-h-12 w-full rounded-2xl bg-zinc-900 px-4 text-sm text-zinc-200 outline-none ring-1 ring-inset ring-white/[0.07] focus:ring-primary/50">{intervalOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          </div>
        </details>
        <button type="submit" disabled={busy === 'add' || !url.trim()} className="mt-3 flex min-h-12 w-full items-center justify-center gap-2 rounded-2xl bg-primary text-sm font-semibold shadow-[0_12px_32px_rgba(255,92,51,0.24)] transition-[filter,transform] active:scale-[0.96] disabled:opacity-45">{busy === 'add' ? <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" /> : <Plus className="h-4 w-4" />}{busy === 'add' ? 'Проверяем доступность…' : 'Начать следить'}</button>
      </form>
      <p className="mt-3 text-pretty text-[11px] leading-4 text-zinc-600">Сбор публичных материалов и поиск бесплатны. Личные и закрытые чаты не собираются.</p>
    </section>

    <AnimatePresence initial={false}>{message ? <motion.div initial={{ opacity: 0, y: 6, filter: 'blur(4px)' }} animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }} exit={{ opacity: 0 }} transition={spring} className="flex gap-3 rounded-[18px] bg-emerald-400/10 p-4 text-xs leading-5 text-emerald-100 shadow-[0_0_0_1px_rgba(110,231,183,0.2)]"><motion.span initial={{ scale: 0.25, opacity: 0, filter: 'blur(4px)' }} animate={{ scale: 1, opacity: 1, filter: 'blur(0px)' }} transition={spring}><Check className="h-4 w-4" /></motion.span>{message}</motion.div> : null}</AnimatePresence>
    {error ? <div role="alert" className="flex gap-3 rounded-[18px] bg-rose-400/10 p-4 text-xs leading-5 text-rose-100 shadow-[0_0_0_1px_rgba(251,113,133,0.2)]"><CircleAlert className="h-4 w-4 shrink-0" />{error}</div> : null}

    <section>
      <div className="flex min-h-11 items-center justify-between gap-3 px-1"><div><h2 className="text-balance text-lg font-semibold">Добавленные вами</h2><p className="mt-1 text-xs text-zinc-600">Они дополняют отраслевой пульс для вашего бизнеса</p></div><span className="text-sm tabular-nums text-zinc-500">{items.length}</span></div>
      {loading ? <div className="mt-3 space-y-2" aria-busy="true">{[1, 2].map((item) => <div key={item} className="h-40 animate-pulse rounded-[24px] bg-white/[0.04] motion-reduce:animate-none" />)}</div> : items.length ? <div className="mt-3 space-y-3">{items.map((item) => { const status = statusMeta(item); const editing = editingId === item.id; return <motion.article layout key={item.id} className="rounded-[24px] bg-white/[0.04] p-4 shadow-[0_16px_50px_rgba(0,0,0,0.16),0_0_0_1px_rgba(255,255,255,0.07)]">
        <div className="flex items-start gap-3"><span className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${status.dot}`} /><div className="min-w-0 flex-1"><b className="block truncate text-sm">{item.title || 'Источник Telegram'}</b><p className="mt-1 truncate text-[11px] text-zinc-600">{item.canonical_url}</p></div>{item.canonical_url ? <a href={item.canonical_url} target="_blank" rel="noreferrer" aria-label="Открыть источник" className="grid h-11 w-11 place-items-center rounded-[14px] text-zinc-500 transition-[background-color,transform] active:scale-[0.96]"><ExternalLink className="h-4 w-4" /></a> : null}</div>
        <div className="mt-3 border-y border-white/[0.055] py-3"><div className="flex items-start justify-between gap-4"><div><b className="block text-xs text-zinc-300">{status.label}</b><p className="mt-1 text-pretty text-[11px] leading-4 text-zinc-600">{status.text}</p></div><span className="shrink-0 text-right"><b className="block text-sm tabular-nums text-zinc-300">{item.documents_count || 0}</b><small className="text-[9px] text-zinc-700">материалов</small></span></div>{item.last_sync_error ? <p className="mt-2 text-pretty text-[10px] leading-4 text-rose-300">{item.last_sync_error}</p> : null}</div>
        <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-[10px] leading-4 text-zinc-600"><span><b className="block font-medium text-zinc-400">Последний сбор</b>{dateLabel(item.last_collected_at)}</span><span><b className="block font-medium text-zinc-400">Следующий</b>{dateLabel(item.next_sync_at)}</span><span className="col-span-2"><b className="font-medium text-zinc-400">Ваш график:</b> {intervalLabel(item.schedule_json?.interval_hours)}</span>{item.topics_json?.length ? <span className="col-span-2 text-pretty"><b className="font-medium text-zinc-400">Темы:</b> {item.topics_json.join(', ')}</span> : null}</div>
        <AnimatePresence initial={false}>{editing ? <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={spring} className="overflow-hidden"><div className="mt-4 border-t border-white/[0.055] pt-4"><label className="text-[11px] text-zinc-600"><span className="mb-1.5 block px-1">Темы через запятую</span><input value={editTopics} onChange={(event) => setEditTopics(event.target.value)} className="min-h-12 w-full rounded-2xl bg-black/20 px-4 text-sm outline-none ring-1 ring-inset ring-white/[0.07] focus:ring-primary/50" /></label><label className="mt-3 block text-[11px] text-zinc-600"><span className="mb-1.5 block px-1">Как часто проверять</span><select value={editInterval} onChange={(event) => setEditInterval(event.target.value)} className="min-h-12 w-full rounded-2xl bg-zinc-900 px-4 text-sm outline-none ring-1 ring-inset ring-white/[0.07]">{intervalOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><div className="mt-3 grid grid-cols-[1fr_48px] gap-2"><button type="button" disabled={busy === `save:${item.id}`} onClick={() => void save(item.id)} className="flex min-h-12 items-center justify-center gap-2 rounded-2xl bg-primary text-sm font-semibold transition-transform active:scale-[0.96] disabled:opacity-45">{busy === `save:${item.id}` ? <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" /> : <Check className="h-4 w-4" />}Сохранить</button><button type="button" aria-label="Не отслеживать" onClick={() => setRemoveId(item.id)} className="grid h-12 w-12 place-items-center rounded-2xl text-rose-300 shadow-[0_0_0_1px_rgba(251,113,133,0.16)] transition-transform active:scale-[0.96]"><Trash2 className="h-4 w-4" /></button></div></div></motion.div> : null}</AnimatePresence>
        {!editing ? <button type="button" onClick={() => startEditing(item)} className="mt-3 flex min-h-11 w-full items-center justify-center gap-2 rounded-[14px] bg-white/[0.045] text-xs font-semibold text-zinc-400 shadow-[0_0_0_1px_rgba(255,255,255,0.06)] transition-[background-color,transform] active:scale-[0.96]"><Pencil className="h-4 w-4" />Настроить</button> : null}
      </motion.article>; })}</div> : <div className="mt-3 rounded-[24px] bg-white/[0.025] p-7 text-center shadow-[0_0_0_1px_rgba(255,255,255,0.06)]"><Radio className="mx-auto h-7 w-7 text-zinc-700" /><b className="mt-3 block">{defaultSourcesCount ? 'Отраслевой пульс уже работает' : 'Добавьте первый источник'}</b><p className="mx-auto mt-2 max-w-xs text-pretty text-xs leading-5 text-zinc-600">{defaultSourcesCount ? 'Свои каналы добавлять необязательно. Добавьте их, если хотите видеть в сводке конкретные источники.' : 'Добавьте отраслевой канал или публичный канал бизнеса по ссылке выше.'}</p></div>}
    </section>

    <AnimatePresence initial={false}>{removeId ? <motion.div className="fixed inset-0 z-50 flex items-end justify-center bg-black/65 px-3 pb-[calc(12px+env(safe-area-inset-bottom))] backdrop-blur-sm" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setRemoveId('')}><motion.section role="dialog" aria-modal="true" aria-labelledby="remove-source-title" onClick={(event) => event.stopPropagation()} className="w-full max-w-xl rounded-[28px] bg-zinc-900 p-5 shadow-[0_28px_100px_rgba(0,0,0,0.7),0_0_0_1px_rgba(255,255,255,0.1)]" initial={{ y: 32 }} animate={{ y: 0 }} exit={{ y: 24 }} transition={spring}><div className="flex items-start gap-3"><span className="grid h-11 w-11 shrink-0 place-items-center rounded-[14px] bg-rose-400/10 text-rose-300"><Trash2 className="h-5 w-5" /></span><div className="min-w-0 flex-1"><h2 id="remove-source-title" className="text-balance text-lg font-semibold">Перестать следить?</h2><p className="mt-1 text-pretty text-xs leading-5 text-zinc-500">Источник исчезнет из вашего «Пульса». Уже собранные публичные материалы не удаляются.</p></div><button type="button" aria-label="Закрыть" onClick={() => setRemoveId('')} className="grid h-11 w-11 shrink-0 place-items-center rounded-[14px] text-zinc-500 active:scale-[0.96]"><X className="h-4 w-4" /></button></div><div className="mt-5 grid grid-cols-2 gap-2"><button type="button" onClick={() => setRemoveId('')} className="min-h-12 rounded-2xl bg-white/[0.05] text-sm font-semibold shadow-[0_0_0_1px_rgba(255,255,255,0.07)] active:scale-[0.96]">Оставить</button><button type="button" disabled={busy === `remove:${removeId}`} onClick={() => void prepareRemove()} className="flex min-h-12 items-center justify-center gap-2 rounded-2xl bg-rose-500 text-sm font-semibold active:scale-[0.96] disabled:opacity-50">{busy === `remove:${removeId}` ? <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" /> : null}Не отслеживать</button></div></motion.section></motion.div> : null}</AnimatePresence>
    <ActionPreviewSheet preview={preview} busy={Boolean(preview?.action_id && busy === `confirm:${preview.action_id}`)} confirmLabel="Не отслеживать" onCancel={() => setPreview(null)} onConfirm={() => void confirmRemove()} />
  </div>;
};
