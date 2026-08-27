import { useCallback, useEffect, useMemo, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { ArrowUpRight, BarChart3, CircleAlert, Loader2, MessageSquareText, Plus, Radio, RefreshCw, Send } from 'lucide-react';

import { mobileAuthHeaders, mobileScopeQuery, readMobileJson } from '@/lib/mobileDataClient';
import type { MobileScope } from './ScopeProvider';

export type CommunityFeedTopic = {
  id: string;
  eyebrow?: string;
  title?: string;
  description?: string;
  message_count?: number | null;
  sources_count?: number | null;
  source_name?: string;
  source_url?: string | null;
  last_discussed_at?: string;
};

export type CommunityFeedItem = {
  id: string;
  platform: string;
  source_id?: string;
  source_name?: string;
  source_url?: string;
  title?: string;
  text: string;
  published_at?: string;
  url: string;
};

export type CommunityFeedTrend = {
  key: string;
  label: string;
  period_days: number;
  message_count: number;
  topics: Array<{
    key: string;
    title: string;
    message_count: number;
    percent: number;
  }>;
};

export type CommunityFeedPayload = {
  topics?: CommunityFeedTopic[];
  topic_trends?: CommunityFeedTrend[];
  items?: CommunityFeedItem[];
  cursor?: string | null;
  as_of?: string;
  freshness?: { status?: string; updated_at?: string | null };
  available_actions?: string[];
};

const previewPayload: CommunityFeedPayload = {
  topics: [
    {
      id: 'topic-prices',
      eyebrow: 'Главная тема',
      title: 'Растут цены на красители',
      description: 'Владельцы салонов сравнивают поставщиков и обсуждают, как сохранить маржу.',
      message_count: 21,
      sources_count: 3,
      source_name: 'Beauty Business Club',
      source_url: 'https://t.me/beauty_business/101',
      last_discussed_at: new Date().toISOString(),
    },
    {
      id: 'topic-marking',
      eyebrow: 'Обсуждали',
      title: 'Новые правила маркировки',
      description: 'Предприниматели делятся первыми результатами внедрения.',
      source_name: 'Салоны России',
      source_url: 'https://t.me/salons/204',
      last_discussed_at: new Date().toISOString(),
    },
  ],
  topic_trends: [
    { key: 'month', label: 'Месяц', period_days: 30, message_count: 124, topics: [{ key: 'acquisition', title: 'Привлечение клиентов', message_count: 41, percent: 33 }, { key: 'taxes_law', title: 'Налоги и законы', message_count: 15, percent: 12 }, { key: 'retention', title: 'Удержание клиентов', message_count: 14, percent: 11 }] },
    { key: 'quarter', label: 'Квартал', period_days: 90, message_count: 356, topics: [{ key: 'acquisition', title: 'Привлечение клиентов', message_count: 103, percent: 29 }, { key: 'staff', title: 'Команда и найм', message_count: 71, percent: 20 }, { key: 'sales', title: 'Продажи и средний чек', message_count: 57, percent: 16 }] },
    { key: 'year', label: 'Год', period_days: 365, message_count: 1084, topics: [{ key: 'staff', title: 'Команда и найм', message_count: 238, percent: 22 }, { key: 'acquisition', title: 'Привлечение клиентов', message_count: 206, percent: 19 }, { key: 'costs', title: 'Цены и расходы', message_count: 174, percent: 16 }] },
  ],
  items: [
    { id: 'message-1', platform: 'telegram', source_name: 'Beauty Business Club', text: 'Собрали сравнение цен поставщиков на август и разобрали, как изменения влияют на себестоимость услуг.', published_at: new Date().toISOString(), url: 'https://t.me/beauty_business/101' },
    { id: 'message-2', platform: 'telegram', source_name: 'Салоны России', text: 'Коллеги, кто уже перешёл на новую схему маркировки? Делимся ошибками и решениями.', published_at: new Date(Date.now() - 3600000).toISOString(), url: 'https://t.me/salons/204' },
  ],
  cursor: null,
  as_of: new Date().toISOString(),
  freshness: { status: 'live', updated_at: new Date().toISOString() },
  available_actions: ['community_sources.manage'],
};

const spring = { type: 'spring', duration: 0.3, bounce: 0 };

const formatTime = (value?: string) => {
  if (!value) return 'время не указано';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return 'время не указано';
  const distance = Date.now() - parsed.getTime();
  if (distance >= 0 && distance < 60000) return 'только что';
  if (distance >= 0 && distance < 3600000) return `${Math.max(1, Math.floor(distance / 60000))} мин назад`;
  if (distance >= 0 && distance < 86400000) return `${Math.floor(distance / 3600000)} ч назад`;
  return parsed.toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
};

const messageCountLabel = (value: number) => {
  const ending = value % 100;
  if (ending >= 11 && ending <= 14) return `${value} сообщений`;
  if (value % 10 === 1) return `${value} сообщение`;
  if (value % 10 >= 2 && value % 10 <= 4) return `${value} сообщения`;
  return `${value} сообщений`;
};

const openExternal = (url?: string | null) => {
  if (!url) return;
  const telegram = window.Telegram?.WebApp;
  if (url.startsWith('https://t.me/') && telegram?.openTelegramLink) {
    telegram.openTelegramLink(url);
    return;
  }
  window.open(url, '_blank', 'noopener,noreferrer');
};

const FeedSkeleton = () => <div aria-label="Загружаем ленту" className="space-y-3 px-4">
  <div className="h-[430px] animate-pulse rounded-[26px] bg-white/[0.04] motion-reduce:animate-none" />
  <div className="h-28 animate-pulse rounded-[22px] bg-white/[0.04] motion-reduce:animate-none" />
  <div className="h-28 animate-pulse rounded-[22px] bg-white/[0.04] motion-reduce:animate-none" />
</div>;

type CommunityFeedMobileProps = {
  scope?: MobileScope;
  preview?: boolean;
  openSources?: () => void;
};

export const CommunityFeedMobile = ({ scope, preview = false, openSources }: CommunityFeedMobileProps) => {
  const [payload, setPayload] = useState<CommunityFeedPayload | null>(preview ? previewPayload : null);
  const [pending, setPending] = useState<CommunityFeedItem[]>([]);
  const [loading, setLoading] = useState(!preview);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState('');
  const [trendPeriod, setTrendPeriod] = useState('month');

  const fetchFeed = useCallback(async (cursor = '') => {
    if (preview) return previewPayload;
    const params = mobileScopeQuery(scope);
    params.set('limit', '20');
    if (cursor) params.set('cursor', cursor);
    return fetch(`/api/operator/mobile/feed?${params.toString()}`, { headers: mobileAuthHeaders() }).then(readMobileJson<CommunityFeedPayload>);
  }, [preview, scope?.kind, scope?.id]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setPending([]);
    setError('');
    void fetchFeed().then((result) => { if (active) setPayload(result); }).catch((reason) => {
      if (active) setError(reason instanceof Error ? reason.message : 'Не удалось загрузить ленту.');
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [fetchFeed]);

  useEffect(() => {
    if (preview || !payload) return;
    const timer = window.setInterval(() => {
      if (document.visibilityState !== 'visible') return;
      void fetchFeed().then((result) => {
        const known = new Set((payload.items || []).map((item) => item.id));
        const next = (result.items || []).filter((item) => !known.has(item.id));
        setPending(next);
        setPayload((current) => current ? { ...current, topics: result.topics, topic_trends: result.topic_trends, as_of: result.as_of, freshness: result.freshness } : result);
      }).catch(() => undefined);
    }, 30000);
    return () => window.clearInterval(timer);
  }, [fetchFeed, payload?.items]);

  const topics = payload?.topics || [];
  const topicTrends = payload?.topic_trends || [];
  const activeTrend = topicTrends.find((item) => item.key === trendPeriod) || topicTrends[0];
  const items = payload?.items || [];
  const canManageSources = Boolean(openSources && (payload?.available_actions || []).includes('community_sources.manage'));
  const updatedLabel = useMemo(() => formatTime(payload?.as_of), [payload?.as_of]);

  const revealNew = () => {
    if (!pending.length) return;
    setPayload((current) => current ? { ...current, items: [...pending, ...(current.items || [])] } : current);
    setPending([]);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const loadMore = async () => {
    if (!payload?.cursor || loadingMore) return;
    setLoadingMore(true);
    try {
      const result = await fetchFeed(payload.cursor);
      setPayload((current) => current ? { ...current, items: [...(current.items || []), ...(result.items || [])], cursor: result.cursor } : result);
      setError('');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Не удалось загрузить ещё сообщений.');
    } finally { setLoadingMore(false); }
  };

  if (loading && !payload) return <FeedSkeleton />;

  return <section className="px-4">
    <div className="mb-5 flex items-start gap-3">
      <div className="min-w-0 flex-1">
        <h1 className="text-balance text-2xl font-semibold tracking-[-0.04em]">Лента</h1>
        <p className="mt-1 text-pretty text-sm leading-6 text-zinc-500">Главное из отслеживаемых отраслевых каналов и чатов.</p>
      </div>
      {canManageSources ? <button type="button" onClick={openSources} aria-label="Источники ленты" className="grid h-11 w-11 shrink-0 place-items-center rounded-[14px] bg-white/[0.05] text-zinc-400 shadow-[0_0_0_1px_rgba(255,255,255,0.07)] transition-[background-color,transform] active:scale-[0.96]"><Plus className="h-5 w-5" /></button> : null}
    </div>

    {error ? <div role="alert" className="mb-4 flex gap-3 rounded-[18px] bg-rose-400/10 p-4 text-xs leading-5 text-rose-100 shadow-[0_0_0_1px_rgba(251,113,133,0.2)]"><CircleAlert className="h-4 w-4 shrink-0" />{error}</div> : null}

    <section aria-labelledby="feed-topics-title" className="rounded-[26px] bg-gradient-to-b from-zinc-900 to-zinc-900/70 p-5 shadow-[0_22px_70px_rgba(0,0,0,0.28),0_0_0_1px_rgba(255,255,255,0.08)]">
      <div className="flex items-center gap-3">
        <span className="grid h-11 w-11 shrink-0 place-items-center rounded-[15px] bg-primary/15 text-primary"><Radio className="h-5 w-5" /></span>
        <div><small className="font-semibold uppercase tracking-[0.12em] text-primary/80">За последние 24 часа</small><h2 id="feed-topics-title" className="mt-1 text-balance text-lg font-semibold">О чём говорят предприниматели</h2></div>
      </div>
      {topics.length ? <div className="mt-5 divide-y divide-white/[0.06]">
        {topics.slice(0, 3).map((topic, index) => <button key={topic.id} type="button" disabled={!topic.source_url} onClick={() => openExternal(topic.source_url)} className="flex min-h-[84px] w-full items-start gap-3 py-4 text-left transition-[opacity,transform] active:scale-[0.96] disabled:active:scale-100">
          <span className="mt-1 font-mono text-xs tabular-nums text-primary/70">0{index + 1}</span>
          <span className="min-w-0 flex-1"><b className="block text-balance text-sm leading-5">{topic.title || 'Важная тема'}</b><span className="mt-1 block text-pretty text-xs leading-5 text-zinc-500">{topic.description}</span><small className="mt-2 flex flex-wrap items-center gap-x-2 text-[10px] text-zinc-600"><span>{topic.source_name || 'Telegram'}</span>{topic.message_count ? <span className="tabular-nums">{messageCountLabel(topic.message_count)}</span> : null}<span>{formatTime(topic.last_discussed_at)}</span></small></span>
          {topic.source_url ? <ArrowUpRight className="mt-1 h-4 w-4 shrink-0 text-zinc-600" /> : null}
        </button>)}
      </div> : <div className="mt-5 rounded-[18px] bg-black/15 px-4 py-5 text-sm leading-6 text-zinc-500"><b className="block text-zinc-300">Темы ещё формируются</b><span className="mt-1 block text-pretty">ЛокалОС покажет тему, когда она повторится в нескольких обсуждениях.</span>{canManageSources ? <button type="button" onClick={openSources} className="mt-3 min-h-11 rounded-[14px] bg-white/[0.05] px-4 text-xs font-semibold text-zinc-300 transition-[background-color,transform] active:scale-[0.96]">Добавить источник</button> : null}</div>}

      {topicTrends.length ? <div className="mt-2 border-t border-white/[0.06] pt-5">
        <div className="flex items-start gap-3">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-[14px] bg-white/[0.05] text-zinc-400"><BarChart3 className="h-4 w-4" /></span>
          <div className="min-w-0"><h3 className="text-balance text-sm font-semibold">Главные темы в динамике</h3><p className="mt-1 text-pretty text-[11px] leading-5 text-zinc-600">Доля среди распознанных тем в отслеживаемых источниках.</p></div>
        </div>
        <div className="mt-4 grid grid-cols-3 gap-1 rounded-[15px] bg-black/20 p-1" role="tablist" aria-label="Период статистики">
          {topicTrends.map((period) => <button key={period.key} type="button" role="tab" aria-selected={activeTrend?.key === period.key} onClick={() => setTrendPeriod(period.key)} className={`min-h-10 rounded-[11px] px-2 text-[11px] font-semibold transition-[background-color,color,transform] active:scale-[0.96] ${activeTrend?.key === period.key ? 'bg-white/[0.09] text-zinc-100 shadow-[0_6px_18px_rgba(0,0,0,0.18)]' : 'text-zinc-600'}`}>{period.label}</button>)}
        </div>
        <AnimatePresence initial={false} mode="wait">
          {activeTrend ? <motion.div key={activeTrend.key} role="tabpanel" initial={{ opacity: 0, y: 5, filter: 'blur(4px)' }} animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }} exit={{ opacity: 0, y: -4 }} transition={spring} className="mt-4 space-y-4">
            {activeTrend.topics.length ? activeTrend.topics.map((topic) => <div key={topic.key}>
              <div className="flex items-baseline justify-between gap-3 text-xs"><span className="min-w-0 text-pretty text-zinc-400">{topic.title}</span><b className="shrink-0 tabular-nums text-zinc-200">{topic.percent}%</b></div>
              <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/[0.05]" role="progressbar" aria-label={topic.title} aria-valuenow={topic.percent} aria-valuemin={0} aria-valuemax={100}><span className="block h-full rounded-full bg-primary/75 transition-[width] duration-300 motion-reduce:transition-none" style={{ width: `${Math.min(100, topic.percent)}%` }} /></div>
            </div>) : <p className="text-pretty text-xs leading-5 text-zinc-600">За этот период пока мало распознанных тем.</p>}
            {activeTrend.message_count ? <p className="text-[10px] tabular-nums text-zinc-700">Учтено: {messageCountLabel(activeTrend.message_count)}</p> : null}
          </motion.div> : null}
        </AnimatePresence>
      </div> : null}
    </section>

    <div className="mb-2 mt-7 flex min-h-11 items-center justify-between gap-3 px-1">
      <div><h2 className="text-balance text-lg font-semibold">Новые сообщения</h2><p className="mt-1 text-xs text-zinc-600">Обновлено {updatedLabel}</p></div>
      <span className="flex min-h-9 items-center gap-2 rounded-full bg-sky-400/10 px-3 text-[10px] font-semibold text-sky-300"><Send className="h-3.5 w-3.5" />Telegram</span>
    </div>

    <AnimatePresence initial={false}>
      {pending.length ? <motion.button type="button" initial={{ opacity: 0, y: 8, filter: 'blur(4px)' }} animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }} exit={{ opacity: 0, y: -5 }} transition={spring} onClick={revealNew} className="sticky top-3 z-10 mb-3 flex min-h-11 w-full items-center justify-center gap-2 rounded-[15px] bg-primary px-4 text-xs font-semibold text-white shadow-[0_12px_32px_rgba(255,92,51,0.28)] transition-transform active:scale-[0.96]"><RefreshCw className="h-4 w-4" /><span className="tabular-nums">Новых сообщений: {pending.length}</span></motion.button> : null}
    </AnimatePresence>

    {items.length ? <div className="divide-y divide-white/[0.06]">
      {items.map((item) => <article key={item.id} className="py-5">
        <button type="button" onClick={() => openExternal(item.url)} className="w-full text-left transition-[opacity,transform] active:scale-[0.96]">
          <span className="flex items-center gap-2 text-[11px] text-zinc-600"><span className="font-semibold text-zinc-400">{item.source_name || 'Telegram'}</span><span>·</span><time dateTime={item.published_at}>{formatTime(item.published_at)}</time></span>
          {item.title ? <h3 className="mt-2 text-balance text-[15px] font-semibold leading-5">{item.title}</h3> : null}
          <p className="mt-2 line-clamp-6 whitespace-pre-line text-pretty text-sm leading-6 text-zinc-400">{item.text}</p>
          <span className="mt-3 inline-flex min-h-10 items-center gap-2 text-xs font-semibold text-primary">Открыть сообщение <ArrowUpRight className="h-4 w-4" /></span>
        </button>
      </article>)}
    </div> : <div className="mt-3 rounded-[24px] bg-white/[0.025] px-6 py-10 text-center shadow-[0_0_0_1px_rgba(255,255,255,0.06)]"><MessageSquareText className="mx-auto h-7 w-7 text-zinc-700" /><h3 className="mt-3 font-semibold">Сообщений пока нет</h3><p className="mx-auto mt-2 max-w-xs text-pretty text-sm leading-6 text-zinc-600">ЛокалОС покажет здесь новые публичные сообщения из ваших и отраслевых источников.</p>{canManageSources ? <button type="button" onClick={openSources} className="mt-4 min-h-11 rounded-[14px] bg-primary px-4 text-xs font-semibold text-white transition-transform active:scale-[0.96]">Добавить источник</button> : null}</div>}

    {payload?.cursor ? <button type="button" onClick={() => void loadMore()} disabled={loadingMore} className="mt-3 flex min-h-12 w-full items-center justify-center gap-2 rounded-2xl bg-white/[0.05] text-sm font-semibold text-zinc-300 shadow-[0_0_0_1px_rgba(255,255,255,0.07)] transition-[background-color,transform] active:scale-[0.96] disabled:opacity-50">{loadingMore ? <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" /> : null}{loadingMore ? 'Загружаем…' : 'Показать ещё'}</button> : null}
  </section>;
};

export default CommunityFeedMobile;
