import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Check, CircleAlert, ExternalLink, Loader2, Plus, Radio, Trash2 } from 'lucide-react';

type CommunitySource = {
  id: string;
  title?: string;
  canonical_url?: string;
  status?: string;
  sync_status?: string;
  last_collected_at?: string;
  next_sync_at?: string;
  documents_count?: number;
  embeddings_count?: number;
  topics_json?: string[];
  schedule_json?: { interval_hours?: number };
};

const headers = () => ({ Authorization: `Bearer ${window.sessionStorage.getItem('localos_mini_session') || ''}`, 'Content-Type': 'application/json' });
const read = async (response: Response) => {
  const payload = await response.json();
  if (!response.ok || payload?.success === false) throw new Error(payload?.error || 'Не удалось выполнить запрос');
  return payload;
};
const dateLabel = (value?: string) => {
  if (!value) return 'ещё не собирали';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'дата неизвестна' : date.toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
};

export const CommunitySourcesMobileModule = ({ businessId }: { businessId?: string | null }) => {
  const [items, setItems] = useState<CommunitySource[]>([]);
  const [url, setUrl] = useState('');
  const [topics, setTopics] = useState('');
  const [intervalHours, setIntervalHours] = useState('24');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const load = async () => {
    if (!businessId) { setLoading(false); return; }
    try {
      const payload = await fetch(`/api/business/${encodeURIComponent(businessId)}/community-sources`, { headers: headers() }).then(read);
      setItems(payload.items || []);
      setError('');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Не удалось загрузить источники');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, [businessId]);

  const add = async (event: FormEvent) => {
    event.preventDefault();
    if (!businessId || !url.trim()) return;
    setBusy('add'); setError(''); setMessage('');
    try {
      await fetch(`/api/business/${encodeURIComponent(businessId)}/community-sources`, {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify({
          url: url.trim(),
          topics: topics.split(',').map((item) => item.trim()).filter(Boolean),
          interval_hours: Number(intervalHours),
        }),
      }).then(read);
      setUrl('');
      setTopics('');
      setMessage('Источник добавлен. LocalOS начал собирать публичные материалы.');
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Не удалось добавить источник');
    } finally { setBusy(''); }
  };

  const remove = async (sourceId: string) => {
    if (!businessId) return;
    setBusy(sourceId); setError('');
    try {
      await fetch(`/api/business/${encodeURIComponent(businessId)}/community-sources/${encodeURIComponent(sourceId)}`, { method: 'DELETE', headers: headers() }).then(read);
      setItems((current) => current.filter((item) => item.id !== sourceId));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Не удалось отключить источник');
    } finally { setBusy(''); }
  };

  if (!businessId) return <div className="rounded-[22px] bg-amber-400/10 p-4 text-sm text-amber-100 ring-1 ring-inset ring-amber-300/20">Выберите конкретный бизнес, чтобы настроить его источники.</div>;

  return <div className="space-y-5">
    <section className="rounded-[24px] bg-white/[0.04] p-4 ring-1 ring-inset ring-white/[0.07]">
      <span className="grid h-11 w-11 place-items-center rounded-[15px] bg-primary/15 text-primary"><Radio className="h-5 w-5" /></span>
      <h2 className="mt-4 text-balance text-lg font-semibold">Добавьте источники, за которыми важно следить</h2>
      <p className="mt-2 text-pretty text-xs leading-5 text-zinc-500">LocalOS соберёт публичные посты, найдёт повторяющиеся темы и покажет их в «Пульсе сообщества». Личные и закрытые чаты не собираются.</p>
      <form onSubmit={add} className="mt-4">
        <input value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://t.me/channel" inputMode="url" className="min-h-12 w-full rounded-2xl bg-black/20 px-4 text-sm outline-none ring-1 ring-inset ring-white/[0.07] placeholder:text-zinc-700 focus:ring-primary/50" />
        <input value={topics} onChange={(event) => setTopics(event.target.value)} placeholder="Темы через запятую — необязательно" className="mt-2 min-h-12 w-full rounded-2xl bg-black/20 px-4 text-sm outline-none ring-1 ring-inset ring-white/[0.07] placeholder:text-zinc-700 focus:ring-primary/50" />
        <label className="mt-2 flex min-h-12 items-center gap-3 rounded-2xl bg-black/20 px-4 text-xs text-zinc-500 ring-1 ring-inset ring-white/[0.07]"><span className="flex-1">Проверять источник</span><select value={intervalHours} onChange={(event) => setIntervalHours(event.target.value)} className="bg-transparent text-right text-zinc-200 outline-none"><option value="6">каждые 6 часов</option><option value="12">каждые 12 часов</option><option value="24">раз в день</option><option value="72">раз в 3 дня</option><option value="168">раз в неделю</option></select></label>
        <button type="submit" disabled={busy === 'add' || !url.trim()} className="mt-2 flex min-h-12 w-full items-center justify-center gap-2 rounded-2xl bg-primary text-sm font-semibold transition-transform active:scale-[0.96] disabled:opacity-45">{busy === 'add' ? <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" /> : <Plus className="h-4 w-4" />}{busy === 'add' ? 'Проверяем источник…' : 'Добавить источник'}</button>
      </form>
      <p className="mt-3 text-pretty text-[11px] leading-4 text-zinc-600">Сбор публичных материалов и поиск по ним бесплатны. Кредиты понадобятся только для персонального анализа и генерации.</p>
    </section>
    <AnimatePresence initial={false}>{message ? <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="flex gap-3 rounded-[18px] bg-emerald-400/10 p-4 text-xs text-emerald-100 ring-1 ring-inset ring-emerald-300/20"><Check className="h-4 w-4 shrink-0" />{message}</motion.div> : null}</AnimatePresence>
    {error ? <div className="flex gap-3 rounded-[18px] bg-rose-400/10 p-4 text-xs text-rose-100 ring-1 ring-inset ring-rose-300/20"><CircleAlert className="h-4 w-4 shrink-0" />{error}</div> : null}
    <section><div className="flex items-end justify-between px-1"><h2 className="text-lg font-semibold">Отслеживаем</h2><span className="text-xs tabular-nums text-zinc-600">{items.length}</span></div>
      {loading ? <div className="mt-3 space-y-2">{[1, 2].map((item) => <div key={item} className="h-28 animate-pulse rounded-[22px] bg-white/[0.04] motion-reduce:animate-none" />)}</div> : items.length ? <div className="mt-3 space-y-2">{items.map((item) => <article key={item.id} className="rounded-[22px] bg-white/[0.04] p-4 ring-1 ring-inset ring-white/[0.07]"><div className="flex items-start gap-3"><span className="mt-0.5 h-2 w-2 rounded-full bg-emerald-400" /><div className="min-w-0 flex-1"><b className="block truncate text-sm">{item.title || 'Источник Telegram'}</b><p className="mt-1 truncate text-[11px] text-zinc-600">{item.canonical_url}</p></div>{item.canonical_url ? <a href={item.canonical_url} target="_blank" rel="noreferrer" aria-label="Открыть источник" className="grid h-11 w-11 place-items-center text-zinc-500"><ExternalLink className="h-4 w-4" /></a> : null}</div><div className="mt-3 grid grid-cols-2 gap-2 rounded-[15px] bg-black/20 p-3 text-[10px] text-zinc-600"><span>Материалов <b className="ml-1 tabular-nums text-zinc-300">{item.documents_count || 0}</b></span><span>Поиск готов <b className="ml-1 tabular-nums text-zinc-300">{item.embeddings_count || 0}</b></span><span className="col-span-2">Последний сбор: {dateLabel(item.last_collected_at)}</span><span className="col-span-2">Следующая проверка: {dateLabel(item.next_sync_at)}</span>{item.topics_json?.length ? <span className="col-span-2 truncate">Темы: {item.topics_json.join(', ')}</span> : null}</div><button type="button" disabled={busy === item.id} onClick={() => void remove(item.id)} className="mt-2 flex min-h-11 w-full items-center justify-center gap-2 rounded-[14px] text-xs font-semibold text-zinc-600 ring-1 ring-inset ring-white/[0.06] active:scale-[0.96]"><Trash2 className="h-4 w-4" />Не отслеживать</button></article>)}</div> : <div className="mt-3 rounded-[22px] bg-white/[0.025] p-6 text-center text-xs leading-5 text-zinc-600 ring-1 ring-inset ring-white/[0.06]">Добавьте первый отраслевой канал или публичный канал бизнеса.</div>}
    </section>
  </div>;
};
